"""UI components package for Image Splitter Pro.

Architecture
------------
The UI follows a ViewModel pattern to remain framework-agnostic:

* ``_state.py`` — :class:`GuiState` dataclass holds ALL observable state
  as plain Python types.  No Tkinter / customtkinter / Dear PyGui types.

* ``gui.py`` (View) — Projects ``GuiState`` onto customtkinter widgets.
  Widget callbacks mutate ``GuiState``, never widgets directly.

* ``ui/console.py``, ``ui/pipeline.py``, ``ui/param_widgets.py`` —
  Reusable View components that read/write state through the same
  ``GuiState`` interface.

Migration Path to Dear PyGui
-----------------------------
1. Replace ``gui.py`` with a Dear PyGui View that reads ``GuiState``
   and declares widgets via ``dpg.add_*()`` each frame.
2. ``ui/console.py`` → Dear PyGui console implementation.
3. ``ui/pipeline.py`` → Dear PyGui pipeline editor (use ``dpg.node_editor``).
4. ``ui/param_widgets.py`` → Dear PyGui parameter widgets.
5. ``ui/_state.py`` — **No changes.**  The state layer is framework-agnostic.
6. ``core.py``, ``engine/`` — **No changes.**  Already fully decoupled.

Expected effort for Dear PyGui migration: ~2500 lines of View code,
zero changes to engine / state layer / processor logic.
"""
