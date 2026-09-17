"""Legacy adapter — wraps existing BaseProcessor subclasses as BaseNode instances.

Provides a zero-break migration path from the old CommandDispatcher pipeline
to the new Node Graph evaluation engine.  Two public classes:

* ``ProcessorNodeAdapter`` — adapts a single ``BaseProcessor`` into a ``BaseNode``.
* ``ChainAsGraph`` — drop-in replacement for ``CommandDispatcher.execute_chain()``
  that builds and evaluates a linear ``NodeGraph`` instead.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.engine.data_blocks import ImageDataBlock
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.nodes import BaseNode, SocketType
from image_splitter.engine.registry import ProcessorRegistry


# ---------------------------------------------------------------------------
# ProcessorNodeAdapter
# ---------------------------------------------------------------------------

class ProcessorNodeAdapter(BaseNode):
    """Wraps any existing ``BaseProcessor`` subclass into a ``BaseNode``.

    The adapter exposes the processor through the node interface (sockets,
    properties, evaluation) so it can participate in the Node Graph without
    modifying the original processor code.
    """

    def __init__(self, processor: BaseProcessor, node_name: str) -> None:
        # Set processor reference before super().__init__() so that
        # _setup_sockets() (called by BaseNode.__init__) can access it if
        # needed in future subclasses.
        self._processor: BaseProcessor = processor
        super().__init__(node_name)

        # Override class-level metadata after BaseNode init.
        self.node_type = processor.name
        self.display_name = processor.display_name

        # Populate _props from the processor's UI metadata.  Bypass
        # set_prop() to avoid dirty-marking during initialization.
        for field in processor.get_ui_metadata():
            self._props[field["name"]] = field.get("default")

        # Stores all output images for multi-output processors (splitters).
        self._all_outputs: List[Image.Image] = []
        # Stores the context dicts paired with each output image.
        self._all_contexts: List[Dict[str, Any]] = []

    @property
    def image_context_pairs(self) -> List[tuple[Image.Image, Dict[str, Any]]]:
        """Return ``(image, context_dict)`` pairs from the last evaluation.

        Preserves the processor's per-output metadata (row, col, filename,
        ext, quality, etc.) used by ``core.process_image()`` for template
        variable substitution and save-format selection.
        """
        return list(zip(self._all_outputs, self._all_contexts))

    # -- Socket setup -------------------------------------------------------

    def _setup_sockets(self) -> None:
        """Add one IMAGE input and one IMAGE output."""
        self._add_input("image", SocketType.IMAGE)
        self._add_output("image", SocketType.IMAGE)

    # -- Evaluation ---------------------------------------------------------

    def evaluate(self) -> None:
        """Execute the wrapped processor on the incoming image.

        Reads ``self.inputs["image"].value``, calls
        ``self._processor.process()``, forwards the first result image to
        ``self.outputs["image"]``, and stores all results in
        ``self._all_outputs`` for multi-output processors (e.g. splitters).

        Marks the node clean.
        """
        img: Image.Image | None = self.inputs["image"].value
        if img is None:
            self._all_outputs = []
            self.mark_clean()
            return

        results: list[tuple[Any, ...]] = self._processor.process(img, dict(self._props))

        if results:
            self.outputs["image"].value = results[0][0]
            self._all_outputs = [r[0] for r in results]
            # Preserve context dicts for template naming (row, col, ext, etc.)
            self._all_contexts = [r[1] if len(r) > 1 else {} for r in results]
        else:
            self._all_outputs = []
            self._all_contexts = []

        self.mark_clean()


# ---------------------------------------------------------------------------
# ChainAsGraph
# ---------------------------------------------------------------------------

class ChainAsGraph:
    """Drop-in replacement for ``CommandDispatcher.execute_chain()``.

    Parses the same ``cmd_str`` format and executes every operator
    through the Node Graph engine.

    Chain semantics (V15): operators are applied **per image** with
    flat-map fan-out.  A multi-output operator (e.g. a splitter) in the
    middle of a chain fans out — every subsequent operator is applied to
    *each* of its outputs, and all results are collected.  Previously
    only ``results[0]`` propagated through the single socket, silently
    discarding the remaining outputs.
    """

    @staticmethod
    def _apply_op(
        image: Image.Image,
        processor: BaseProcessor,
        merged_props: Dict[str, Any],
    ) -> List[Image.Image]:
        """Run one operator on one image via the Node Graph engine.

        Mirrors ``core._execute_via_graph``: a minimal
        ``ImageInputNode → ProcessorNodeAdapter`` graph, evaluated with
        a borrowed (non-copied) input block so the caller keeps image
        ownership.  Returns all outputs (fan-out aware).
        """
        import uuid

        from image_splitter.engine.config_coercion import coerce_processor_config
        from image_splitter.engine.evaluator import NodeGraph
        from image_splitter.engine.nodes import ImageInputNode

        uid = uuid.uuid4().hex[:8]
        input_name = f"__chain_input_{uid}__"

        # Borrow the caller's image — ImageInputNode copies it into the
        # graph, and forget(close_image=False) never closes it.
        input_block = ImageDataBlock(name=input_name, image=image)

        graph = NodeGraph()
        in_node = ImageInputNode("__in__")
        in_node.set_prop("source", input_block.name)
        graph.add_node(in_node)

        adapter = ProcessorNodeAdapter(processor, f"__proc_{processor.name}__")
        adapter._props.update(coerce_processor_config(processor, merged_props))
        graph.add_node(adapter)
        graph.connect(in_node.name, "image", adapter.name, "image")

        try:
            graph.evaluate(force_all=True)
            outputs = list(adapter._all_outputs)
            # Detach from the adapter so a later cleanup pass cannot
            # close images the caller now owns.
            adapter._all_outputs = []
            adapter._all_contexts = []
        finally:
            ImageDataBlock.forget(input_name, close_image=False)
        return outputs

    @staticmethod
    def execute_chain(
        image: Image.Image,
        cmd_str: str,
        extra_config: Dict[str, Any] | None = None,
    ) -> List[Image.Image]:
        """Execute a command string via the Node Graph engine.

        Args:
            image: Source PIL image (not closed by this method).
            cmd_str: Pipe-separated command string understood by
                ``CommandDispatcher.parse_command``.
            extra_config: Optional extra configuration merged into every
                processor call.

        Returns:
            List of output ``PIL.Image`` objects (may be empty).
        """
        # Ensure processors are registered.
        if not ProcessorRegistry.list_all():
            from image_splitter.core import register_all_processors
            register_all_processors()

        # 1. Parse the command string.
        ops: List[tuple[str, Dict[str, Any]]] = CommandDispatcher.parse_command(cmd_str)

        # 2. Flat-map worklist: each op is applied to every current image.
        #    Multi-output ops (splitters) fan out mid-chain; single-output
        #    ops keep the list length — identical to the old linear graph.
        current: List[Image.Image] = [image]
        try:
            for op_idx, (op_name, props) in enumerate(ops):
                processor = ProcessorRegistry.get(op_name)
                merged_props: dict[str, Any] = {}
                if extra_config:
                    merged_props.update(extra_config)
                merged_props.update(props)

                next_images: List[Image.Image] = []
                for img in current:
                    outputs = ChainAsGraph._apply_op(img, processor, merged_props)
                    next_images.extend(outputs)
                    # Close consumed intermediates eagerly.  The original
                    # caller-owned image is only borrowed — never closed.
                    if not (op_idx == 0 and img is image):
                        try:
                            img.close()
                        except Exception:
                            pass
                current = next_images
                if not current:
                    break
        except Exception:
            # A failing operator must not leak the intermediate images
            # produced so far (V14-4 hygiene).  The caller's original is
            # borrowed and stays open.
            for img in current:
                if img is not image:
                    try:
                        img.close()
                    except Exception:
                        pass
            raise

        # The first op borrowed the caller's image; every image now in
        # `current` was produced by a processor and is owned by us.
        # Strip the borrowed original if it somehow survived (it cannot
        # be in `current` — processor outputs are fresh images).
        return current
