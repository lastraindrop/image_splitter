# Technical Guide — Image Splitter Pro

> Comprehensive technical reference covering architecture principles, the unified
> execution path, processing pipeline details, the parameter **dynamic alignment**
> protocol (and the tests that lock it), and test methodology.
>
> **Status**: V14.0 (package version 0.7.1) — 465 tests / 39 files, mypy 0 errors
> (44 source files), ruff clean.

---

## 1. Architecture Overview

### 1.1 Layer Map

```
┌──────────────────────────────────────────────────────────────┐
│ Entry points:  cli.py  │  gui.py + ui/  │  script_engine.py │
├──────────────────────────────────────────────────────────────┤
│ core.py — process_image() + _execute_via_graph()             │
│           (THE single execution path)                        │
├──────────────────────────────────────────────────────────────┤
│ engine/ — base · registry · config_coercion · dispatcher     │
│           nodes · evaluator · data_blocks · legacy_adapter   │
│           history · macro · presets · _ui_metadata_util      │
├──────────────────────────────────────────────────────────────┤
│ models.py — 13 validated config dataclasses                  │
│ processors/ (13 built-in) + plugins/ (user drop-ins)         │
├──────────────────────────────────────────────────────────────┤
│ settings · keymap · logging_config (persistence & infra)     │
└──────────────────────────────────────────────────────────────┘
```

**Dependency rule**: arrows point downward only. `engine/` never imports
`core.py` at module level (late imports inside functions break the cycle);
processors never import entry points; `ui/` never imports tkinter types into
the state layer (`ui/_state.py` is plain-Python).

### 1.2 Design Philosophy (Blender Alignment)

| Blender concept | This project | Status |
|-----------------|--------------|--------|
| Operators (`bpy.ops`) | `BaseProcessor` + `ProcessorRegistry` | Core |
| ID DataBlocks (`bpy.data`) | `ImageDataBlock` (named/versioned/ref-counted) | Core |
| Node compositor | `NodeGraph` DAG + `Evaluator` | Core |
| `bpy.props` | `engine/props.py` descriptors | **Experimental — no consumers** |
| Info editor operator log | `HistoryManager` + macro recording | Core |
| Presets / App templates | `presets.py` named parameter presets | Core |
| Python console | `ui/console.py` | Core |

---

## 2. The Unified Execution Path (Most Important Invariant)

**Every processor invocation — CLI, GUI batch, GUI console, pipeline editor,
script engine, presets — flows through exactly one function:
`core._execute_via_graph()`.**

```
process_image(path, name, config)
  │
  ├─ 1. register_all_processors() (auto, if registry empty)
  ├─ 2. Path.exists() → fail-fast
  ├─ 3. ProcessorRegistry.get(name)
  ├─ 4. coerce_processor_config(processor, raw_dict)      ← type coercion
  ├─ 5. processor.config_model(**model_input)             ← fail-fast validation
  │
  ├─ 6. _execute_via_graph(orig_img, processor, config):
  │      uid = uuid4().hex[:8]                    ← V14-A1: unique temp names
  │      ImageDataBlock(f"__proc_input_{uid}__")  ← copy #1 (caller survives)
  │      NodeGraph:
  │        ImageInputNode ──▶ ProcessorNodeAdapter ──▶ ImageOutputNode
  │      graph.evaluate(force_all=True)           ← try/finally (V14-4)
  │      finally: forget temp blocks               ← zero leak on exception
  │      return [(image, context), ...]
  │
  └─ 7. per output: template.format(context) → path-traversal guard
        → _prepare_image_for_save() → ICC preserve → save → close cell
```

`ChainAsGraph.execute_chain()` builds the same graph shape (input → N
adapters → output) with **UUID-suffixed** `__chain_*__` block names and
returns safe copies. `CommandDispatcher.execute_chain()` is a deprecated
delegate to `ChainAsGraph` — there is no second implementation.

**Locked by**: `test_execute_via_graph.py`, `test_chain_as_graph_all.py`
(ChainAsGraph vs process_image pixel-identical for all 13 processors),
`test_v14_fixes.py::TestV14GraphCleanup` (zero block leak on success AND on
exception, unique names per call).

### 2.1 Concurrency Model

| Mode | Mechanism | Isolation |
|------|-----------|-----------|
| CLI (default) | `ProcessPoolExecutor` (spawn-safe, `freeze_support`) | Process |
| GUI (batch/console/pipeline) | `threading.Thread` + `stop_event`, serialized by `_busy` flag | Thread |
| Script engine | Serial in-process | N/A |

**Why the UUID block names matter (V14-A1)**: `ImageDataBlock._name_registry`
is class-level global state. Fixed temp names (`__proc_input__`) meant two
concurrent executions would race — one thread's `forget()` released the
other's live image. The registry lock protects dict *operations*, not logical
name ownership. Unique per-call names remove the collision class entirely.
GUI additionally serializes operations via the `_busy` flag (P1-8).

---

## 3. Parameter Dynamic Alignment Protocol

This is the system that prevents "parameter drift" bugs — where a parameter
exists in the model but not in the UI, or the CLI coerces to the wrong type.

### 3.1 Single Source of Truth

```
models.py dataclass
  field(metadata={"label": "Rows", "min": 1})
        │
        ▼  _ui_metadata_util.ui_metadata_from_dataclass()   (AUTO)
UI metadata: [{"name","label","type","default","min","max","options"}]
        │
        ├──▶ GUI param panels        (create_param_widget)
        ├──▶ CLI --set coercion      (config_coercion._coerce_value)
        └──▶ chain parsing           (CommandDispatcher / ChainAsGraph)
```

- A field **with** a `label` → exposed everywhere automatically.
- A field **without** a `label` (e.g. `output_dir`, `template`) → shared
  infrastructure, handled by the entry points, never shown as a processor param.
- Type is inferred from the annotation (`int→int`, `List[int]→list`,
  `Optional[X]→X`); `options` in metadata forces `enum`.
- Processors may override `get_ui_metadata()` only when the UI differs from
  the dataclass schema (e.g. `geometry` exposes rotate as an enum of strings).

### 3.2 The Coercion → Validation Pipeline

```
Raw input (any layer)          Coercion                Model validation
─────────────────────          ────────────────        ─────────────────
CLI  --set rows=3     "3"  →   int("3") → 3      →     SplitConfig(3) ✓
GUI  StringVar        "3"  →   3                 →     ✓
Chain rows=3          3    →   3 (already int)   →     ✓
Script rows=3         "3"  →   3                 →     ✓
```

Order is mandatory: **coerce first, validate second**. Validation
(`config_model.__post_init__`) only accepts already-coerced values.

| Type | Coercion rule | Rejected as |
|------|---------------|-------------|
| `int` | `int(str)`; float-strings via `float()` truncation; inf/NaN → error | `ValueError` w/ label |
| `float` | `float(value)` | `ValueError` |
| `bool` | `true/1/yes/on` / `false/0/no/off` (case-insensitive) | `ValueError` |
| `list` | `ast.literal_eval` (list/tuple accepted) | `ValueError` |
| `enum` | `str(value)` must ∈ `options` | `ValueError` |
| `str` | pass-through | — |

Unknown type strings fail loudly (never silently coerce to str) so that a
misconfigured metadata dict is caught at first use.

**Locked by**: `test_config_coercion.py`, `test_ui_metadata_util.py`,
`test_operator_compliance.py` (every processor's metadata ↔ model ↔ process
contract), `test_error_paths.py` (bad enum/list/int values).

### 3.3 Dynamic Alignment Checklist (Adding/Changing a Parameter)

1. Add/modify the field in `models.py` with `metadata={"label": ...}` and
   `__post_init__` validation.
2. If the processor overrides `get_ui_metadata()`, update the override **and**
   keep types compatible with the model.
3. If the parameter feeds a template variable, add it to the returned
   `context` dict in `process()`.
4. Run the alignment lock tests:
   ```bash
   python -m pytest tests/test_operator_compliance.py tests/test_chain_as_graph_all.py -v
   ```
5. If it's a grid-style parameter with a settings default, wire the settings
   fallback explicitly in `cli.py` (see BUG CLI-2 lesson: argparse help text
   defaults are documentation, not behavior).

### 3.4 Context Injection (Template Variables)

| Source | Variables |
|--------|-----------|
| `core.py` (always) | `{filename}` `{index}` `{w}` `{h}` `{ext}` |
| splitters | `{row}` `{col}` |
| adjuster | `{anchor}` `{orig_w}` `{orig_h}` `{target_w}` `{target_h}` |
| watermark | `{text}` `{anchor}` |
| format_converter | `{ext}` (override), `{quality}` |

`process_image` merges system context first, then per-output processor
context (processor values win). The save format derives from the final
extension (so `format_converter` genuinely changes the output format), with
quality applied to lossy formats only.

---

## 4. Processor Contract

```python
class MyProcessor(BaseProcessor):
    name         # str, snake_case, unique key
    display_name # str, unique, shown in GUI
    category     # Split | Transform | Edit | Filter | Export
    tool_tip     # str
    config_model # Optional[dataclass] — validated before process()
    process(image, config) -> List[(Image, context_dict)]   # pure-ish: copy inputs
    draw_preview(canvas, thumb_size, canvas_pos, ratio, props, theme)  # optional
    get_ui_metadata() -> List[dict]   # auto from config_model; override rarely
```

Rules enforced by the compliance test suite:

1. `process()` must **not** mutate or close the input image.
2. Every returned image must be a **new** object (result of crop/resize/copy).
3. The context dict must be JSON-serialisable values (used by templates).
4. `draw_preview` must tag overlay items with `"overlay"` so the GUI can
   clear them (`canvas.delete("overlay")`).
5. Registering a duplicate `name` logs a warning and replaces (plugin
   override semantics).

---

## 5. GUI Hardening Notes (V14)

- **Keymap typing guard** (`gui._is_typing_context`): all global keybindings
  are bound on the toplevel; Tk bindtags propagate key events upward, so
  `<Delete>` inside any entry also reached the global handler (verified
  defect). The guard suppresses global actions while focus is in an input
  widget (CTk classes + `winfo_class ∈ {Entry, Text, Spinbox, Combobox,
  TEntry, TCombobox}` — CTkComboBox hosts an inner tk.Entry, so the class
  check alone is insufficient).
- **Preset name sanitization** (`presets._preset_path`): regex strips
  `<>:"/\|?*` + control chars + leading/trailing dots/spaces; names with no
  alphanumerics fall back to `unnamed`. Lookup sanitizes identically →
  round-trip safe.
- **GUI file logging**: `setup_file_logging()` attaches a rotating handler
  (`~/.image_splitter/logs/gui.log`, 1 MB × 3) — GUI users cannot see stderr.
- **Test focus conventions**: a withdrawn Tk window cannot take keyboard
  focus and `focus_force()` is unreliable under test runners on Windows.
  Use the project's offscreen mapping (`geometry("+10000+10000")` + `update`)
  and **`focus_set()`** (Tk-internal focus record) — see
  `test_v14_fixes.py::TestV14KeymapTypingGuard`.

## 6. Macro System Threat Model (Honest Scope)

`MacroPlayer` executes scripts via `exec` with a restricted `__builtins__`
and an import allow-list (`image_splitter`, `PIL`). Known remaining escape
routes exist (`getattr` whitelisted; `().__class__.__base__.__subclasses__()`
traversal). **This is an anti-footgun guard for locally-authored macros, not
a security boundary.** Never play macros from untrusted sources.

---

## 7. Test Methodology

### 7.1 Organization (39 files, 465 tests)

| Layer | Files |
|-------|-------|
| Engine | test_props, test_data_blocks, test_node_graph, test_legacy_adapter, test_execute_via_graph, test_engine_v4, test_config_coercion, test_dispatcher, test_history, test_operator_compliance |
| Processors | test_adjuster, test_custom_splitter, test_edge_cases, test_error_paths, test_new_processors, test_processors_expanded, test_save_compatibility |
| Entry points | test_cli, test_gui_smoke, test_gui_workflows, test_gui_param_sync, test_gui_state, test_ui_preview, test_console_panel, test_pipeline_editor, test_param_widgets |
| Infrastructure | test_settings, test_keymap, test_script_engine, test_macro, test_presets, test_plugin, test_ui_metadata_util |
| Integration | test_integration, test_workflow, test_chain_as_graph_all |
| Regression | test_bug_fixes, test_v13_fixes, test_v14_fixes |

### 7.2 Conventions (Mandatory)

1. Inherit `BaseTest` (conftest) — auto temp dirs + fixture images + processor
   registration. GUI tests inherit `TkTestCase` (`map_offscreen=True` when
   real focus/key events are needed).
2. Never hardcode processor counts — `processor_count()` / `assertGreaterEqual`.
3. New processor → `test_processors_expanded.py`; compliance is automatic.
4. Bug fix → regression test in the current version file
   (`test_v13_fixes.py`, `test_v14_fixes.py`, …) **after reproducing the bug
   with a minimal script** (V13/V14 methodology: no fix without reproduction).
5. Any execution-path change must keep `test_chain_as_graph_all.py` green —
   it is the pixel-identity lock between chain and single-op paths.

### 7.3 Commands

```bash
python -m pytest tests/ -v                        # full suite
python -m pytest tests/ -k "not gui and not ui_preview" -v   # headless CI
python -m pytest tests/test_operator_compliance.py -v        # alignment locks
python -m mypy image_splitter --ignore-missing-imports       # types
python -m ruff check image_splitter/ --ignore=E501           # lint
```

---

## 8. Known Limitations (Design Decisions, Not Bugs)

| Limitation | Rationale / Follow-up |
|------------|----------------------|
| GUI batch is sequential (single thread) | Parallelization tracked in PLAN.md (needs pool + abort semantics + real-machine smoke) |
| `props.py` has no consumers | Experimental; deprecation decision tracked in PLAN.md |
| Chain outputs use fixed `{stem}_chain_{idx}` naming | Per-op contexts (row/col) not yet threaded through chains — tracked in PLAN.md |
| `AdjustConfig` int≤1 = ratio, >1 = pixels | Documented heuristic; explicit-unit param is a roadmap item |
| History undo/redo restores parameters, not files | By design (files on disk are immutable outputs) |

---

## 9. Version History

| Version | Date | Highlights |
|---------|------|------------|
| V9.0 | 2026-06 | Node graph engine, presets, pipeline editor, CI/CD |
| V10.0 | 2026-06 | Unified execution (`_execute_via_graph`), UI hardening |
| V12.0 | 2026-06 | Test-suite optimization, P0 UI component coverage (426 tests) |
| V13.0 | 2026-09 | **Packaging fix** (standard layout), keymap dead-bindings, border double width<3, console chain threading, CLI dir expansion, preset precedence, chain format honoring (443 tests) |
| V14.0 | 2026-09 | **Current** — interaction-path audit: dashed border visual fix, macro chain playback, keymap typing guard, graph exception leak, CLI settings defaults, chain ICC preservation, preset name sanitization, UUID temp blocks, GUI rotating file log, watermark origin compensation (465 tests) |
