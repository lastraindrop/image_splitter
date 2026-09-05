# Comprehensive Analysis & Roadmap (V10.0 — Unified Execution)

> Full architecture audit, engine layer implementation, UI modernization, and roadmap
> for the `image_splitter` project — aligned with Blender's operator philosophy.
>
> **Current state**: V14.0 (package 0.7.1) — see STATUS_V13.md / STATUS_V14.md for
> the latest audit rounds. This document's roadmap section is kept in sync (§7).

---

## 1. Architecture (Current State — V9.0)

### 1.1 File Map

```
image_splitter/
├── cli.py                    # CLI entry point (multiprocessing + presets)
├── gui.py                    # GUI (history/macro/console/presets/pipeline, now threading-safe)
├── core.py                   # Processing pipeline + processor auto-discovery
├── models.py                 # 13 validated config dataclasses
├── settings.py               # Settings persistence (~/.image_splitter/)
├── keymap.py                 # Keybinding system (8 global shortcuts)
├── script_engine.py          # Batch scripting engine
├── logging_config.py         # Logging configuration
├── py.typed                  # PEP 561 type marker
├── engine/                   # Kernel layer
│   ├── base.py               # BaseProcessor/BaseConfig interfaces
│   ├── registry.py           # Thread-safe singleton registry
│   ├── dispatcher.py         # Command parser + chain execution + extra_config
│   ├── config_coercion.py    # Type coercion for 6 param types
│   ├── history.py            # Undo/redo stack + JSON export
│   ├── macro.py              # Record/sandboxed playback → Python scripts
│   ├── presets.py            # Named parameter presets (save/load/import/export)
│   ├── props.py              # Typed Property descriptors — Experimental API
│   ├── data_blocks.py        # ImageDataBlock (name registry, version, ref-count)
│   ├── nodes.py              # DAG nodes (Socket/Connection/BaseNode + 4 concrete)
│   ├── evaluator.py          # NodeGraph evaluator + LRU EvaluationCache
│   ├── legacy_adapter.py     # ProcessorNodeAdapter + ChainAsGraph (unified execution bridge)
│   └── _ui_metadata_util.py  # Auto-generate UI metadata from dataclass fields
├── processors/               # 13 built-in operators (+1 plugin = 14)
├── plugins/                  # User plugin directory
│   └── example_plugin.py
├── ui/
│   ├── _state.py             # GuiState — framework-agnostic ViewModel
│   ├── console.py            # Interactive command console (customtkinter)
│   ├── pipeline.py           # Visual chain editor (customtkinter)
│   └── param_widgets.py      # Shared parameter widget factory (customtkinter)
├── .github/workflows/
│   └── ci.yml                # CI: 3 OS × 4 Python = 12 jobs
└── tests/                    # 465 tests, 39 files
    ├── conftest.py           # Shared fixtures (BaseTest, colors, images)
    ├── test_props.py         # Property System: 30 tests
    ├── test_data_blocks.py   # ImageDataBlock: 22 tests
    ├── test_node_graph.py    # Node Graph + Evaluator: 35 tests
    ├── test_legacy_adapter.py# Legacy Adapter integration: 15 tests
    ├── test_workflow.py      # 20 end-to-end integration tests
    └── ...                   # 23 existing specialized test files
```

### 1.2 Quality Matrix

| Dimension | Score | Details |
|-----------|-------|---------|
| **Module Decoupling** | ★★★★★ | 5-layer engine + processors + plugins. Zero cross-import cycles. |
| **Extensibility** | ★★★★★ | New processor = BaseProcessor subclass + drop-in. |
| **Metadata-Driven UI** | ★★★★★ | Auto-renders from `get_ui_metadata()` + shared widget factory. |
| **Type Safety** | ★★★★★ | All configs validated. mypy 0 errors. 69 source files. |
| **Test Coverage** | ★★★★★ | 465 tests across 39 files (engine, processors, UI, integration). |
| **Thread Safety** | ★★★★★ | All 3 worker threads snapshot `current_files`; no race conditions. |
| **Error Handling** | ★★★★☆ | Save operations now have error handling; image load failures logged. |
| **Resource Management** | ★★★★★ | `with Image.open()` + finally close + ICC preserve + ChainAsGraph image safety. |
| **Cross-Platform** | ★★★★★ | Platform-aware fonts, pathlib, CI on all 3 OS. |
| **Code Style** | ★★★★★ | Google Style + mypy + shared theme/param-widget infrastructure. |

---

## 2. Engine Layer — Phase 1-4 (COMPLETED)

### Phase 1: Property System (`engine/props.py`, 484 lines)
- `Property[T]` descriptor with coerce/validate/update callbacks
- 7 factory functions: `IntProp`, `FloatProp`, `BoolProp`, `EnumProp`, `StrProp`, `ListProp`, `ColorProp`
- `to_ui_metadata()` bridge for backward-compatible metadata generation

### Phase 2: DataBlock System (`engine/data_blocks.py`, 246 lines)
- `ImageDataBlock` — named, versioned, reference-counted image containers
- Class-level `_name_registry` with `get_by_name()`, `forget()`, `list_all()`, `clear_all()`
- Version tracking: increments on `image` setter and `touch()`
- Reference counting: `use()` / `unuse()` with auto-release at zero

### Phase 3: Node Graph + Evaluator (`engine/nodes.py`, 332 lines + `engine/evaluator.py`, 278 lines)
- `SocketType` enum (IMAGE, MASK, VALUE, COLOR)
- `Socket` — typed connection points with value caching
- `Connection` — directed link with type/direction validation
- `BaseNode` (ABC) — abstract node with `_setup_sockets()`, `evaluate()`, dirty tracking
- Concrete nodes: `ImageInputNode`, `ImageOutputNode`, `ColorAdjustNode`, `BlendNode`
- `NodeGraph` — DAG with add/remove/connect/disconnect, Kahn's topological sort, BFS dirty propagation, `evaluate(force_all)`
- `EvaluationCache` — LRU cache keyed by `(node_name, node_version)`

### Phase 4: Legacy Adapter (`engine/legacy_adapter.py`, 186 lines)
- `ProcessorNodeAdapter(BaseNode)` — wraps any `BaseProcessor` as a `BaseNode`
- `ChainAsGraph.execute_chain()` — drop-in replacement for `CommandDispatcher.execute_chain()`
- Multi-output support for splitters (collects all results via `_all_outputs`)
- Input image safety (copies before storing to avoid `clear_all()` closing caller's image)

---

## 3. UI Hardening (COMPLETED — this session)

| # | Fix | Impact |
|---|-----|--------|
| P0-1 | Thread safety: `self.current_files` snapshot before 3 worker threads | Prevents IndexError/crash on concurrent remove |
| P0-2 | `_run_chain_thread` switched from `CommandDispatcher` to `ChainAsGraph` | Uses new engine layer |
| P1-1 | `pipeline.py` + `console.py` now use injected `theme` parameter | 47 hardcoded colors eliminated |
| P1-2 | `ui/param_widgets.py` shared factory eliminates duplicated if-elif-else | Single source of widget creation truth |
| P1-3 | `settings.py`, `keymap.py`, `presets.py` save operations now handle IOError | No crash on disk full / permission denied |
| P2-1 | 5 shortcuts added to `DEFAULT_KEYMAP` (Ctrl+`, Ctrl+P, Ctrl+Shift+R, Ctrl+Z, Ctrl+Shift+Z) | User-configurable |
| P2-2 | `_on_file_selected` now uses `logger.exception()` | Debuggable image load failures |
| P2-3 | Canvas resize debounce (`after_cancel` + `_resize_after_id`) | No render queue pile-up |
| — | Removed duplicate `<Delete>` binding | Dead code eliminated |
| — | `showinfo` → `showwarning` for output dir open failure | Correct message box type |

---

## 4. ChainAsGraph Multi-Output Support (COMPLETED)

- `ProcessorNodeAdapter` now stores all output images in `_all_outputs`
- `ChainAsGraph.execute_chain()` detects multi-output processors (splitters) and collects all results
- Input image protected via `image.copy()` — `clear_all()` no longer closes the caller's image
- Pixel-identical to `CommandDispatcher` for all chain configurations

---

## 5. Test Suite

### 5.1 Statistics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Test files | 25 | 29 | +4 (props, data_blocks, node_graph, legacy_adapter) |
| Test count | 218 | 308 | +90 (engine layer coverage) |
| Source files (mypy) | 64 | 69 | +5 (engine + param_widgets) |
| mypy errors | 0 | 0 | — |

### 5.2 New Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_props.py` | 30 | All 7 factory functions, coercion, validation, update, ui_metadata |
| `test_data_blocks.py` | 22 | Registry, version, ref counting, clone, metadata, lifecycle |
| `test_node_graph.py` | 35 | Socket/Connection, BaseNode, NodeGraph DAG, dirty propagation, EvaluationCache, cycle detection |
| `test_legacy_adapter.py` | 15 | Adapter, ChainAsGraph vs Dispatcher pixel-identical, multi-output |

---

## 6. Implementation History

### V9.0 — Current Session (Node Graph Engine + UI Hardening)

| # | Change | Type |
|---|--------|------|
| 1 | Phase 1-2: `engine/props.py` + `engine/data_blocks.py` | Engine |
| 2 | Phase 3: `engine/nodes.py` + `engine/evaluator.py` | Engine |
| 3 | Phase 4: `engine/legacy_adapter.py` | Engine |
| 4 | `engine/__init__.py` — 24 symbol public API | Engine |
| 5 | 4 new test files: props, data_blocks, node_graph, legacy_adapter | Testing |
| 6 | ChainAsGraph multi-output + image safety fixes | Bug fix |
| 7 | UI thread safety, theme refactoring, widget factory | UI Hardening |
| 8 | Keymap expansion, error handling, canvas debounce | UI Hardening |
| 9 | Documentation sync: README, PLAN, DEVELOPER, TECHNICAL | Documentation |
| 10 | `py.typed` marker + `.gitignore` created | Infrastructure |

### V8.0 — Previous Session

| # | Change | Type |
|---|--------|------|
| 1 | `conftest.py` — shared fixtures with BaseTest | Architecture |
| 2 | Merged test files, dedup, fixed hardcoded counts | Consolidation |
| 3 | `test_workflow.py` — 20 new end-to-end tests | Coverage |
| 4 | Updated documentation | Documentation |
| 5 | CI/CD pipeline | DevOps |

---

## 7. Future Roadmap

### Completed ✅
- [x] 13 built-in processors + 1 plugin example
- [x] Google Python Style + full mypy compliance (0 errors)
- [x] 40+ bug fixes (BUG-01 through BUG-40 + UI hardening fixes)
- [x] Operation history (undo/redo) + JSON export
- [x] Macro recording & playback
- [x] Interactive command console
- [x] Parameter presets system
- [x] Visual pipeline chain editor
- [x] Cross-platform font handling
- [x] CI/CD pipeline (GitHub Actions)
- [x] **Typed Property descriptor system** (7 factory functions)
- [x] **ImageDataBlock** (named, versioned, ref-counted)
- [x] **DAG Node Graph + Evaluator** (4 nodes, topological sort, dirty propagation, LRU cache)
- [x] **Legacy Adapter** (zero-break migration — ProcessorNodeAdapter + ChainAsGraph)
- [x] **UI Hardening** (thread safety, theme refactoring, widget factory, keymap expansion)
- [x] **Unified execution path** — CommandDispatcher → ChainAsGraph delegation
- [x] **Thread-safe ImageDataBlock** registry with fine-grained locking
- [x] **ChainAsGraph all-processor validation** — pixel-identical for all 13 processors
  - [x] mypy 0 errors (465 tests / 39 files as of V14)
- [x] **GUI param sync fix** — widget→state data flow restored
- [x] **Security hardening** — macro sandbox escape blocked, `type` removed from builtins
- [x] **Resource management** — image close on cell save, cache eviction, data block replacement
- [x] **Branching DAG dirty propagation** verified via dedicated test
- [x] **P0 UI component test coverage** — param_widgets, console panel, pipeline editor, GUI param sync
- [x] **Test-suite optimization (P1)** — shared helpers (TkTestCase base, CLI run_cli, assert_images_equal)
- [x] **Test-suite optimization (P2)** — duplicate consolidation (make_rgb_image dedup, ChainAsGraph equivalence dedup)
- [x] **Test-suite optimization (P3)** — CommandDispatcher delegation guard
- [x] **V13 packaging repair** — standard layout, `pip install -e .` + console scripts verified
- [x] **V13 interaction fixes** — keymap dead-bindings, border double width<3, console chain threading, CLI dir expansion, preset precedence, chain output format
- [x] **V14 interaction-path audit** — dashed border visual fix (the V10 "dash-pattern" fix was still a visual no-op: same-color dashes over a same-color solid fill), macro pipeline_chain playback, keymap typing-context guard, `_execute_via_graph` exception leak, CLI settings default_rows/cols, chain ICC preservation, preset name sanitization, preset snapshot noise removal, watermark glyph-origin compensation
- [x] **V14 concurrency hardening** — UUID-suffixed temp data blocks (fixed names were a latent cross-thread collision)
- [x] **V14 GUI file logging** — rotating log at ~/.image_splitter/logs/gui.log

### Short-Term (P1-P2) — next 1-2 rounds
- [ ] **GUI batch parallelization** — reuse the CLI `ProcessPoolExecutor` path; must define abort semantics (cancel pending futures) and keep per-file progress reporting; requires real-machine smoke
- [ ] **`props.py` keep-or-deprecate decision** — 488 lines with zero consumers since V9; either wire into processors or remove (YAGNI)
- [ ] **Metadata dual-track unification** — `adjuster`/`geometry` override `get_ui_metadata()` with types diverging from their config models; converge overrides onto dataclass metadata (or lock divergence with tests)
- [ ] **Release chain** — replace placeholder `example.com` URLs in pyproject; verify sdist/wheel build; tag 0.7.x
- [ ] **Real-machine GUI smoke** — full manual pass (load → preview → batch → preset → macro → console) before any public release
- [ ] **Macro sandbox doc downgrade** — README/TECHNICAL describe it as anti-footgun guard, not security boundary (TECHNICAL.md §6 done; README wording pending)
- [ ] Registry duplicate-name policy — reject or require explicit opt-in instead of warn-and-replace

### Long-Term (P3+)
- [ ] Visual node graph editor with drag-connect (Blender compositor style)
- [ ] Interactive guide placement (click to add h_lines/v_lines) + proxy preview for large files
- [ ] Plugin hot-reload without restart
- [ ] Drag-drop files onto GUI
- [ ] Per-op contexts (row/col) threaded through chain output naming (chains currently use `{stem}_chain_{idx}`)
- [ ] Explicit-unit dimension parameter for canvas_adjuster (current int≤1-ratio heuristic is documented but ambiguous)
- [ ] Distributed processing (RPC-based multi-node)
- [ ] WASM edition (browser-based offline processing)
- [ ] Plugin marketplace — community plugin sharing
