# Comprehensive Analysis & Roadmap (V16.0 â€?Deployability)

> Full architecture audit, engine layer implementation, UI modernization, and roadmap
> for the `image_splitter` project â€?aligned with Blender's operator philosophy.
>
> **Current state**: V16.0 (package 0.8.0) â€?see STATUS_V14.md, REPORT_V15.md Â§7
> and the V16 section below (Â§6.2) for the latest audit rounds.

---

## 1. Architecture (Current State â€?V9.0)

### 1.1 File Map

```
image_splitter/
â”œâ”€â”€ cli.py                    # CLI entry point (multiprocessing + presets)
â”œâ”€â”€ gui.py                    # GUI (history/macro/console/presets/pipeline, now threading-safe)
â”œâ”€â”€ core.py                   # Processing pipeline + processor auto-discovery
â”œâ”€â”€ models.py                 # 13 validated config dataclasses
â”œâ”€â”€ settings.py               # Settings persistence (~/.image_splitter/)
â”œâ”€â”€ keymap.py                 # Keybinding system (8 global shortcuts)
â”œâ”€â”€ script_engine.py          # Batch scripting engine
â”œâ”€â”€ logging_config.py         # Logging configuration
â”œâ”€â”€ py.typed                  # PEP 561 type marker
â”œâ”€â”€ engine/                   # Kernel layer
â”?  â”œâ”€â”€ base.py               # BaseProcessor/BaseConfig interfaces
â”?  â”œâ”€â”€ registry.py           # Thread-safe singleton registry
â”?  â”œâ”€â”€ dispatcher.py         # Command parser + chain execution + extra_config
â”?  â”œâ”€â”€ config_coercion.py    # Type coercion for 6 param types
â”?  â”œâ”€â”€ history.py            # Undo/redo stack + JSON export
â”?  â”œâ”€â”€ macro.py              # Record/sandboxed playback â†?Python scripts
â”?  â”œâ”€â”€ presets.py            # Named parameter presets (save/load/import/export)
â”?  â”œâ”€â”€ props.py              # Typed Property descriptors â€?Experimental API
â”?  â”œâ”€â”€ data_blocks.py        # ImageDataBlock (name registry, version, ref-count)
â”?  â”œâ”€â”€ nodes.py              # DAG nodes (Socket/Connection/BaseNode + 4 concrete)
â”?  â”œâ”€â”€ evaluator.py          # NodeGraph evaluator + LRU EvaluationCache
â”?  â”œâ”€â”€ legacy_adapter.py     # ProcessorNodeAdapter + ChainAsGraph (unified execution bridge)
â”?  â””â”€â”€ _ui_metadata_util.py  # Auto-generate UI metadata from dataclass fields
â”œâ”€â”€ processors/               # 13 built-in operators (+1 plugin = 14)
â”œâ”€â”€ plugins/                  # User plugin directory
â”?  â””â”€â”€ example_plugin.py
â”œâ”€â”€ ui/
â”?  â”œâ”€â”€ _state.py             # GuiState â€?framework-agnostic ViewModel
â”?  â”œâ”€â”€ console.py            # Interactive command console (customtkinter)
â”?  â”œâ”€â”€ pipeline.py           # Visual chain editor (customtkinter)
â”?  â””â”€â”€ param_widgets.py      # Shared parameter widget factory (customtkinter)
â”œâ”€â”€ .github/workflows/
â”?  â””â”€â”€ ci.yml                # CI: 3 OS Ã— 4 Python = 12 jobs
â””â”€â”€ tests/                    # 498 tests, 41 files
    â”œâ”€â”€ conftest.py           # Shared fixtures (BaseTest, colors, images)
    â”œâ”€â”€ test_props.py         # Property System: 30 tests
    â”œâ”€â”€ test_data_blocks.py   # ImageDataBlock: 22 tests
    â”œâ”€â”€ test_node_graph.py    # Node Graph + Evaluator: 35 tests
    â”œâ”€â”€ test_legacy_adapter.py# Legacy Adapter integration: 15 tests
    â”œâ”€â”€ test_workflow.py      # 20 end-to-end integration tests
    â””â”€â”€ ...                   # 23 existing specialized test files
```

### 1.2 Quality Matrix

| Dimension | Score | Details |
|-----------|-------|---------|
| **Module Decoupling** | â˜…â˜…â˜…â˜…â˜?| 5-layer engine + processors + plugins. Zero cross-import cycles. |
| **Extensibility** | â˜…â˜…â˜…â˜…â˜?| New processor = BaseProcessor subclass + drop-in. |
| **Metadata-Driven UI** | â˜…â˜…â˜…â˜…â˜?| Auto-renders from `get_ui_metadata()` + shared widget factory. |
| **Type Safety** | â˜…â˜…â˜…â˜…â˜?| All configs validated. mypy 0 errors. 69 source files. |
| **Test Coverage** | â˜…â˜…â˜…â˜…â˜?| 498 tests across 41 files (engine, processors, UI, integration). |
| **Thread Safety** | â˜…â˜…â˜…â˜…â˜?| All 3 worker threads snapshot `current_files`; no race conditions. |
| **Error Handling** | â˜…â˜…â˜…â˜…â˜?| Save operations now have error handling; image load failures logged. |
| **Resource Management** | â˜…â˜…â˜…â˜…â˜?| `with Image.open()` + finally close + ICC preserve + ChainAsGraph image safety. |
| **Cross-Platform** | â˜…â˜…â˜…â˜…â˜?| Platform-aware fonts, pathlib, CI on all 3 OS. |
| **Code Style** | â˜…â˜…â˜…â˜…â˜?| Google Style + mypy + shared theme/param-widget infrastructure. |

---

## 2. Engine Layer â€?Phase 1-4 (COMPLETED)

### Phase 1: Property System (`engine/props.py`, 484 lines)
- `Property[T]` descriptor with coerce/validate/update callbacks
- 7 factory functions: `IntProp`, `FloatProp`, `BoolProp`, `EnumProp`, `StrProp`, `ListProp`, `ColorProp`
- `to_ui_metadata()` bridge for backward-compatible metadata generation

### Phase 2: DataBlock System (`engine/data_blocks.py`, 246 lines)
- `ImageDataBlock` â€?named, versioned, reference-counted image containers
- Class-level `_name_registry` with `get_by_name()`, `forget()`, `list_all()`, `clear_all()`
- Version tracking: increments on `image` setter and `touch()`
- Reference counting: `use()` / `unuse()` with auto-release at zero

### Phase 3: Node Graph + Evaluator (`engine/nodes.py`, 332 lines + `engine/evaluator.py`, 278 lines)
- `SocketType` enum (IMAGE, MASK, VALUE, COLOR)
- `Socket` â€?typed connection points with value caching
- `Connection` â€?directed link with type/direction validation
- `BaseNode` (ABC) â€?abstract node with `_setup_sockets()`, `evaluate()`, dirty tracking
- Concrete nodes: `ImageInputNode`, `ImageOutputNode`, `ColorAdjustNode`, `BlendNode`
- `NodeGraph` â€?DAG with add/remove/connect/disconnect, Kahn's topological sort, BFS dirty propagation, `evaluate(force_all)`
- `EvaluationCache` â€?LRU cache keyed by `(node_name, node_version)`

### Phase 4: Legacy Adapter (`engine/legacy_adapter.py`, 186 lines)
- `ProcessorNodeAdapter(BaseNode)` â€?wraps any `BaseProcessor` as a `BaseNode`
- `ChainAsGraph.execute_chain()` â€?drop-in replacement for `CommandDispatcher.execute_chain()`
- Multi-output support for splitters (collects all results via `_all_outputs`)
- Input image safety (copies before storing to avoid `clear_all()` closing caller's image)

---

## 3. UI Hardening (COMPLETED â€?this session)

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
| â€?| Removed duplicate `<Delete>` binding | Dead code eliminated |
| â€?| `showinfo` â†?`showwarning` for output dir open failure | Correct message box type |

---

## 4. ChainAsGraph Multi-Output Support (COMPLETED)

- `ProcessorNodeAdapter` now stores all output images in `_all_outputs`
- `ChainAsGraph.execute_chain()` detects multi-output processors (splitters) and collects all results
- Input image protected via `image.copy()` â€?`clear_all()` no longer closes the caller's image
- Pixel-identical to `CommandDispatcher` for all chain configurations

---

## 5. Test Suite

### 5.1 Statistics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Test files | 25 | 29 | +4 (props, data_blocks, node_graph, legacy_adapter) |
| Test count | 218 | 308 | +90 (engine layer coverage) |
| Source files (mypy) | 64 | 69 | +5 (engine + param_widgets) |
| mypy errors | 0 | 0 | â€?|

### 5.2 New Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_props.py` | 30 | All 7 factory functions, coercion, validation, update, ui_metadata |
| `test_data_blocks.py` | 22 | Registry, version, ref counting, clone, metadata, lifecycle |
| `test_node_graph.py` | 35 | Socket/Connection, BaseNode, NodeGraph DAG, dirty propagation, EvaluationCache, cycle detection |
| `test_legacy_adapter.py` | 15 | Adapter, ChainAsGraph vs Dispatcher pixel-identical, multi-output |

---

## 6. Implementation History

### V9.0 â€?Current Session (Node Graph Engine + UI Hardening)

| # | Change | Type |
|---|--------|------|
| 1 | Phase 1-2: `engine/props.py` + `engine/data_blocks.py` | Engine |
| 2 | Phase 3: `engine/nodes.py` + `engine/evaluator.py` | Engine |
| 3 | Phase 4: `engine/legacy_adapter.py` | Engine |
| 4 | `engine/__init__.py` â€?24 symbol public API | Engine |
| 5 | 4 new test files: props, data_blocks, node_graph, legacy_adapter | Testing |
| 6 | ChainAsGraph multi-output + image safety fixes | Bug fix |
| 7 | UI thread safety, theme refactoring, widget factory | UI Hardening |
| 8 | Keymap expansion, error handling, canvas debounce | UI Hardening |
| 9 | Documentation sync: README, PLAN, DEVELOPER, TECHNICAL | Documentation |
| 10 | `py.typed` marker + `.gitignore` created | Infrastructure |

### V16.0 â€?Deployability (current session)

| # | Change | Type |
|---|--------|------|
| 1 | **Shared parallel runner** `core.run_parallel_batch()` â€?one concurrency/abort/progress implementation for CLI and GUI (jobs<=1 runs in-process sequentially; abort cancels pending futures, in-flight file finishes) | Architecture |
| 2 | **GUI batch parallelization** â€?batch runs now use the shared runner with `max_workers` setting (was single-threaded) | Feature |
| 3 | **`{batch}` template placeholder** â€?1-based input-file sequence disambiguates same-stem files (L-1); CLI prints a pre-flight warning when stems collide | Feature |
| 4 | **Registry duplicate policy** (A4) â€?`register()` raises on duplicate unless `allow_override=True`; builtin scan strict, plugin scan opt-in (documented shadowing) | Hardening |
| 5 | Release chain â€?placeholder `example.com` URLs removed, LICENSE added, version 0.8.0; sdist+wheel build verified; clean-venv install smoke passed (CLI script, GUI `--version`, installed-package e2e processing incl. `{batch}` fan-out); PyInstaller onefile spec (`packaging/image_splitter.spec`) built and GUI-exe smoke passed | Packaging |
| 6 | L-fixes: case-insensitive input discovery (L-7), console reject suppression (L-2), BlendNode opacity clamp + derived-image close (L-3), EvaluationCache invalidate/clear close images (L-6), canvas after-callback guard (L-9) | Robustness |
| 7 | `props.py` decision recorded: frozen experimental API, do not extend | Documentation |
| 8 | `test_v16_fixes.py` â€?17 regression tests; suite now 498 tests / 41 files | Testing |

### V15.0 â€?Fan-Out + Lean Execution (previous session)

| # | Change | Type |
|---|--------|------|
| 1 | **Chain fan-out**: mid-chain multi-output processors (splitters) now apply subsequent ops to *every* output â€?`grid_splitter|resizer` yields all cells, not 1 | Bug fix (semantic) |
| 2 | **Lean execution path**: `_execute_via_graph` / `ChainAsGraph` borrow the caller's image (`forget(close_image=False)`) and drop the `ImageOutputNode` round-trip â€?1 defensive copy per invocation instead of 3 | Performance |
| 3 | **GUI startup**: parameter panel is built at launch and honours the persisted `default_processor` setting (panel was empty until first manual re-selection) | Bug fix (UI) |
| 4 | `settings.json` / `keymap.json` containing non-dict JSON fall back to defaults instead of crashing with TypeError/AttributeError | Robustness |
| 5 | `smart_crop` luminance path estimates the background from a border frame â€?content detection now works on white backgrounds (scans, screenshots) | Feature |
| 6 | `import_preset` surfaces `OSError` as a failed import instead of crashing | Robustness |
| 7 | `test_v15_fixes.py` â€?16 regression tests; stale mid-chain-splitter test updated to fan-out semantics; total suite now 481 tests / 40 files | Testing |

### V14.0 â€?Interaction-Path Audit (previous session)

Detailed in STATUS_V14.md; highlights: dashed border visual fix, macro
pipeline_chain playback, keymap typing-context guard, `_execute_via_graph`
exception leak, CLI settings defaults, chain ICC preservation, preset
sanitization, UUID-suffixed temp data blocks, GUI rotating file log.

### V8.0 â€?Previous Session

| # | Change | Type |
|---|--------|------|
| 1 | `conftest.py` â€?shared fixtures with BaseTest | Architecture |
| 2 | Merged test files, dedup, fixed hardcoded counts | Consolidation |
| 3 | `test_workflow.py` â€?20 new end-to-end tests | Coverage |
| 4 | Updated documentation | Documentation |
| 5 | CI/CD pipeline | DevOps |

---

## 7. Future Roadmap

### Completed âœ?- [x] 13 built-in processors + 1 plugin example
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
- [x] **Legacy Adapter** (zero-break migration â€?ProcessorNodeAdapter + ChainAsGraph)
- [x] **UI Hardening** (thread safety, theme refactoring, widget factory, keymap expansion)
- [x] **Unified execution path** â€?CommandDispatcher â†?ChainAsGraph delegation
- [x] **Thread-safe ImageDataBlock** registry with fine-grained locking
- [x] **ChainAsGraph all-processor validation** â€?pixel-identical for all 13 processors
  - [x] mypy 0 errors (498 tests / 41 files as of V16)
- [x] **GUI param sync fix** â€?widgetâ†’state data flow restored
- [x] **Security hardening** â€?macro sandbox escape blocked, `type` removed from builtins
- [x] **Resource management** â€?image close on cell save, cache eviction, data block replacement
- [x] **Branching DAG dirty propagation** verified via dedicated test
- [x] **P0 UI component test coverage** â€?param_widgets, console panel, pipeline editor, GUI param sync
- [x] **Test-suite optimization (P1)** â€?shared helpers (TkTestCase base, CLI run_cli, assert_images_equal)
- [x] **Test-suite optimization (P2)** â€?duplicate consolidation (make_rgb_image dedup, ChainAsGraph equivalence dedup)
- [x] **Test-suite optimization (P3)** â€?CommandDispatcher delegation guard
- [x] **V13 packaging repair** â€?standard layout, `pip install -e .` + console scripts verified
- [x] **V13 interaction fixes** â€?keymap dead-bindings, border double width<3, console chain threading, CLI dir expansion, preset precedence, chain output format
- [x] **V14 interaction-path audit** â€?dashed border visual fix (the V10 "dash-pattern" fix was still a visual no-op: same-color dashes over a same-color solid fill), macro pipeline_chain playback, keymap typing-context guard, `_execute_via_graph` exception leak, CLI settings default_rows/cols, chain ICC preservation, preset name sanitization, preset snapshot noise removal, watermark glyph-origin compensation
- [x] **V14 concurrency hardening** â€?UUID-suffixed temp data blocks (fixed names were a latent cross-thread collision)
- [x] **V14 GUI file logging** â€?rotating log at ~/.image_splitter/logs/gui.log
- [x] **V15 chain fan-out** â€?mid-chain splitters apply subsequent ops to every output (flat-map semantics)
- [x] **V15 lean execution** â€?1 defensive copy per processor invocation (was 3); borrowed-image ownership via `forget(close_image=False)`
- [x] **V15 GUI startup panel** â€?parameter panel populated at launch, honours `default_processor`
- [x] **V15 config robustness** â€?non-dict `settings.json` / `keymap.json` fall back to defaults
- [x] **V15 smart_crop light backgrounds** â€?border-frame background estimation
- [x] **V16 GUI batch parallelization** â€?shared `run_parallel_batch` runner, cancel-pending abort
- [x] **V16 `{batch}` placeholder + duplicate-stem pre-flight warning** (L-1)
- [x] **V16 registry duplicate policy** â€?raise by default, plugin opt-in override (A4)
- [x] **V16 release chain** â€?LICENSE, URL cleanup, 0.8.0, sdist/wheel build + clean-venv smoke, PyInstaller onefile verified

### Short-Term (P1-P2) â€?next 1-2 rounds
- [x] **GUI batch parallelization** â€?done in V16 via shared `run_parallel_batch` (cancel-pending abort, per-file progress; frozen-exe smoke passed)
- [x] **`props.py` keep-or-deprecate decision** â€?V16: frozen experimental API, documented "do not extend"; removal deferred until the node-graph UI question is settled
- [ ] **Metadata dual-track unification** â€?`adjuster`/`geometry` override `get_ui_metadata()` with types diverging from their config models; converge overrides onto dataclass metadata (or lock divergence with tests)
- [x] **Release chain** â€?V16: placeholder URLs removed (commented template left for the real repo), LICENSE added, sdist/wheel build + clean-venv smoke verified, 0.8.0; tag on release
- [ ] **Real-machine GUI smoke** â€?full manual pass (load â†?preview â†?batch â†?preset â†?macro â†?console) before any public release
- [x] **Macro sandbox doc downgrade** â€?README/TECHNICAL describe it as anti-footgun guard, not security boundary
- [x] Registry duplicate-name policy â€?V16: raise by default, `allow_override=True` opt-in

### Long-Term (P3+)
- [ ] Visual node graph editor with drag-connect (Blender compositor style)
- [ ] Interactive guide placement (click to add h_lines/v_lines) + proxy preview for large files
- [ ] Plugin hot-reload without restart
- [ ] Drag-drop files onto GUI
- [ ] Per-op contexts (row/col) threaded through chain output naming (chains currently use `{stem}_chain_{idx}`)
- [ ] Explicit-unit dimension parameter for canvas_adjuster (current intâ‰?-ratio heuristic is documented but ambiguous)
- [ ] Distributed processing (RPC-based multi-node)
- [ ] WASM edition (browser-based offline processing)
- [ ] Plugin marketplace â€?community plugin sharing
