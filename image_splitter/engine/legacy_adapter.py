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

    Parses the same ``cmd_str`` format, builds a linear ``NodeGraph``
    (ImageInputNode → …ProcessorNodeAdapter… → ImageOutputNode), evaluates
    it, and returns the resulting images as a list.
    """

    @staticmethod
    def execute_chain(
        image: Image.Image,
        cmd_str: str,
        extra_config: Dict[str, Any] | None = None,
    ) -> List[Image.Image]:
        """Execute a command string via the Node Graph engine.

        Args:
            image: Source PIL image.
            cmd_str: Pipe-separated command string understood by
                ``CommandDispatcher.parse_command``.
            extra_config: Optional extra configuration merged into every
                processor call.

        Returns:
            List of output ``PIL.Image`` objects (may be empty).
        """
        # Lazy imports — evaluator.py is imported here to avoid potential
        # circular dependencies during parallel development.
        from image_splitter.engine.evaluator import NodeGraph
        from image_splitter.engine.nodes import ImageInputNode, ImageOutputNode

        # Ensure processors are registered.
        if not ProcessorRegistry.list_all():
            from image_splitter.core import register_all_processors
            register_all_processors()

        # 1. Parse the command string.
        ops: List[tuple[str, Dict[str, Any]]] = CommandDispatcher.parse_command(cmd_str)

        # V14: unique-per-call temp block names — fixed "__chain_input__"
        # names in the class-level registry raced between concurrent
        # executions (one thread's forget() released the other's image).
        import uuid
        uid = uuid.uuid4().hex[:8]
        input_name = f"__chain_input_{uid}__"
        output_name = f"__chain_output_{uid}__"

        # 2. Create an ImageDataBlock for the input image.
        #    Use a copy so the caller's image is not closed by clear_all().
        input_block = ImageDataBlock(name=input_name, image=image.copy())

        # 3. Build a linear NodeGraph.
        graph = NodeGraph()

        # Input node
        in_node = ImageInputNode("__in__")
        in_node.set_prop("source", input_block.name)
        graph.add_node(in_node)

        # Processor nodes
        prev_name: str = in_node.name
        adapters: list[ProcessorNodeAdapter] = []
        for idx, (op_name, props) in enumerate(ops):
            processor = ProcessorRegistry.get(op_name)
            adapter = ProcessorNodeAdapter(processor, f"__proc_{idx}_{op_name}__")
            # Merge extra_config + per-op props, then coerce once.
            # This preserves the old CommandDispatcher behavior:
            # {**extra, **props} → coerce_processor_config.
            from image_splitter.engine.config_coercion import coerce_processor_config
            merged_props: dict[str, Any] = {}
            if extra_config:
                merged_props.update(extra_config)
            merged_props.update(props)
            adapter._props.update(
                coerce_processor_config(processor, merged_props)
            )
            graph.add_node(adapter)

            # Connect previous → current (by node name).
            graph.connect(prev_name, "image", adapter.name, "image")
            prev_name = adapter.name
            adapters.append(adapter)

        # Output node
        out_node = ImageOutputNode("__out__")
        out_node.set_prop("target", output_name)
        graph.add_node(out_node)
        graph.connect(prev_name, "image", out_node.name, "image")

        # 4. Evaluate the graph; on any failure still clean up temp blocks.
        result_images: List[Image.Image] = []
        try:
            graph.evaluate(force_all=True)

            # 5. Collect result (copy before cleanup so returned images
            #    survive cleanup calling .close()).
            #    For multi-output processors (splitters), collect all
            #    results from the last adapter's _all_outputs.
            if adapters and len(adapters[-1]._all_outputs) > 1:
                # Multi-output: collect all output images
                for img in adapters[-1]._all_outputs:
                    result_images.append(img.copy())
            else:
                # Single-output: use the output block
                output_block = ImageDataBlock.get_by_name(output_name)
                if output_block is not None and output_block.image is not None:
                    result_images.append(output_block.image.copy())
        finally:
            # 6. Clean up — only release blocks created by this chain,
            #    not ALL blocks in the global registry.
            for block_name in (input_name, output_name):
                ImageDataBlock.forget(block_name)
            # Close intermediate adapter outputs so multi-op chains do not
            # retain every intermediate image until garbage collection.
            # The final results are copies (or owned by the caller), so
            # closing here is safe.
            for adapter in adapters:
                for img in adapter._all_outputs:
                    try:
                        img.close()
                    except Exception:
                        pass
                adapter._all_outputs = []
                adapter._all_contexts = []

        return result_images
