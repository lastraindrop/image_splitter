"""Core image processing pipeline and processor discovery."""
import importlib
import logging
import pkgutil
import sys
import uuid
from pathlib import Path
from typing import Any, Generator, List, Tuple

from PIL import Image

from image_splitter.engine.base import BaseProcessor
from image_splitter.engine.config_coercion import coerce_processor_config
from image_splitter.engine.registry import ProcessorRegistry

# Initialize logging
logger = logging.getLogger(__name__)


def _prepare_image_for_save(image: Image.Image, save_format: str) -> Image.Image:
    """Prepare image for saving (handles transparency and format conversion).

    Args:
        image: Original PIL image object.
        save_format: Target save format (e.g., 'JPEG').

    Returns:
        Processed image object. If JPEG and contains transparency, it will be flattened.
    """
    if save_format not in ('JPEG', 'BMP'):
        return image

    if image.mode in ('RGB', 'L', 'CMYK'):
        return image

    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        rgba_image = image.convert('RGBA')
        flattened = Image.new('RGB', rgba_image.size, (255, 255, 255))
        flattened.paste(rgba_image, mask=rgba_image.getchannel('A'))
        return flattened

    return image.convert('RGB')


def register_all_processors() -> None:
    """Automatically discover and register all processor plugin classes.

    Scans both the built-in processors/ package and the user plugins/
    directory. All non-abstract BaseProcessor subclasses are instantiated
    and registered.
    """
    import image_splitter.processors as processors
    pkg_path = Path(processors.__file__).parent

    # Clear and reset to ensure no state residue
    ProcessorRegistry.reset()

    # Scan built-in processors package
    _scan_package(pkg_path, processors.__name__)

    # Scan user plugins directory
    plugins_path = Path(__file__).parent / "plugins"
    if plugins_path.is_dir():
        plugin_init = plugins_path / "__init__.py"
        if plugin_init.exists():
            _scan_package(plugins_path, "image_splitter.plugins")

    # If all failed, at least register the grid_splitter as fallback
    if not ProcessorRegistry.list_all():
        logger.warning("No processors found — registering fallback grid_splitter")
        from image_splitter.processors.splitter import GridSplitter
        ProcessorRegistry.register(GridSplitter())


def _scan_package(pkg_path: Path, prefix: str) -> None:
    """Scan a package directory for BaseProcessor subclasses and register them.

    Args:
        pkg_path: Path to the package directory.
        prefix: Python module prefix (e.g., 'image_splitter.processors').
    """
    for _, modname, _ in pkgutil.walk_packages([str(pkg_path)], prefix + "."):
        try:
            if modname in sys.modules:
                module = sys.modules[modname]
            else:
                module = importlib.import_module(modname)

            for attr in dir(module):
                obj = getattr(module, attr)
                if (isinstance(obj, type)
                        and issubclass(obj, BaseProcessor)
                        and obj is not BaseProcessor):
                    try:
                        instance = obj()
                        ProcessorRegistry.register(instance)
                    except TypeError:
                        continue
        except Exception as e:
            logger.debug("Failed to load module %s: %s", modname, e)


def _execute_via_graph(
    image: Image.Image,
    processor: BaseProcessor,
    config: dict[str, Any],
) -> List[Tuple[Image.Image, dict[str, Any]]]:
    """Execute a single processor through the Node Graph engine.

    Builds a minimal graph (ImageInputNode → ProcessorNodeAdapter →
    ImageOutputNode), evaluates it, and returns ``(image, context)``
    pairs — preserving per-output metadata (row, col, ext, quality, etc.)
    needed for template-based file naming and format selection.

    This is the unified execution path used by both ``process_image()``
    and ``ChainAsGraph.execute_chain()`` — all processor invocations
    flow through the same Node Graph evaluator.

    Args:
        image: Source PIL Image (caller must close).
        processor: A registered BaseProcessor instance.
        config: Coerced processor configuration dict.

    Returns:
        List of ``(PIL.Image, context_dict)`` tuples.  Caller is
        responsible for closing returned images.
    """
    # Late imports to avoid circular dependencies.
    from image_splitter.engine.data_blocks import ImageDataBlock
    from image_splitter.engine.evaluator import NodeGraph
    from image_splitter.engine.legacy_adapter import ProcessorNodeAdapter
    from image_splitter.engine.nodes import ImageInputNode, ImageOutputNode

    # V14: unique-per-call temporary block names.  Fixed names like
    # "__proc_input__" lived in the class-level ImageDataBlock registry,
    # so two concurrent executions (threaded GUI, plugin background work)
    # would race: one thread's forget() released the other's image.
    uid = uuid.uuid4().hex[:8]
    input_block_name = f"__proc_input_{uid}__"
    output_block_name = f"__proc_output_{uid}__"

    # 1. Create input block (owning a copy so the caller's image survives).
    input_block = ImageDataBlock(
        name=input_block_name,
        image=image.copy(),
    )

    # 2. Build a linear graph: input → adapter → output.
    graph = NodeGraph()

    in_node = ImageInputNode("__in__")
    in_node.set_prop("source", input_block.name)
    graph.add_node(in_node)

    adapter = ProcessorNodeAdapter(processor, f"__proc_{processor.name}__")
    adapter._props.update(config)
    graph.add_node(adapter)
    graph.connect(in_node.name, "image", adapter.name, "image")

    out_node = ImageOutputNode("__out__")
    out_node.set_prop("target", output_block_name)
    graph.add_node(out_node)
    graph.connect(adapter.name, "image", out_node.name, "image")

    # 3. Evaluate the graph, collecting per-output context dicts.
    #    V14-4: cleanup is in try/finally — a processor exception used to
    #    leak the temporary ImageDataBlocks (with their full-size copies)
    #    until the next call overwrote them.
    try:
        graph.evaluate(force_all=True)
        pairs = adapter.image_context_pairs
    finally:
        # Clean up temporary blocks (not global blocks).
        for block_name in (input_block_name, output_block_name):
            ImageDataBlock.forget(block_name)

    return pairs


def process_image(
    image_path: str,
    processor_name: str,
    config: Any
) -> Tuple[bool, str]:
    """Entry point for general image processing logic.

    Args:
        image_path: Path to the input image.
        processor_name: Registered processor name.
        config: Processing configuration, can be a dict or a corresponding DataClass instance.

    Returns:
        A tuple of (success, message). success indicates if processing was successful, message is the result description.
    """
    try:
        # 0. Auto-registration check
        if not ProcessorRegistry.list_all():
            register_all_processors()

        img_p = Path(image_path)
        if not img_p.exists():
            return False, f"Error: File not found: {image_path}"
            
        processor = ProcessorRegistry.get(processor_name)

        # 1. Unified configuration coercion and model validation (Fail-Fast)
        raw_dict = (
            config if isinstance(config, dict)
            else config.__dict__ if hasattr(config, '__dict__')
            else {}
        )
        config_dict = coerce_processor_config(processor, raw_dict)
        
        if processor.config_model:
            from dataclasses import fields
            model_fields = {f.name for f in fields(processor.config_model)}
            model_input = {k: v for k, v in config_dict.items() if k in model_fields}
            processor.config_model(**model_input)

        with Image.open(img_p) as orig_img:
            # Preserve metadata from original image before processing
            orig_icc_profile = orig_img.info.get('icc_profile')
            
            # 2. Execute processor via unified Node Graph path.
            processed_items = _execute_via_graph(orig_img, processor, config_dict)
            
            # 3. Output strategy parsing
            output_dir = Path(config_dict.get('output_dir', "./output"))
            template = config_dict.get('template', "{filename}_{index}")
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = img_p.stem
            ext = img_p.suffix or ".png"
            ext_map = Image.registered_extensions()
            
            count = 0
            opened_cells: list[Image.Image] = []
            try:
                for cell, context in processed_items:
                    opened_cells.append(cell)
                    # 4. Naming and saving
                    base_ctx = {
                        "filename": base_name, 
                        "ext": ext.lstrip('.'),
                        "index": f"{count + 1:02d}",
                        "w": cell.width,
                        "h": cell.height
                    }
                    base_ctx.update(context)
                    
                    # Allow processor to dynamically change extension
                    curr_ext = f".{base_ctx['ext']}"
                    
                    try:
                        name = template.format(**base_ctx)
                    except KeyError as e:
                        return False, f"Invalid template placeholder: {e}"
                    
                    # Extract filename to prevent path traversal
                    safe_name = Path(name.replace('\\', '/')).name
                    if not safe_name.lower().endswith(curr_ext.lower()):
                        safe_name += curr_ext
                        
                    save_path = output_dir / safe_name
                    
                    save_image = cell
                    try:
                        save_fmt = ext_map.get(save_path.suffix.lower(), 'PNG')
                        save_image = _prepare_image_for_save(cell, save_fmt)
                        save_args: dict[str, Any] = {"format": save_fmt}
                        if save_fmt in ('JPEG', 'WEBP'):
                            save_args["quality"] = int(context.get('quality', 95))
                        icc_profile = context.get('icc_profile') or cell.info.get('icc_profile') or orig_icc_profile
                        if icc_profile:
                            save_args['icc_profile'] = icc_profile
                            
                        save_image.save(save_path, **save_args)
                    finally:
                        if save_image is not cell:
                            save_image.close()
                    # P1-9: Close successfully saved cells to prevent
                    # resource leaks.  Previously `opened_cells.pop()`
                    # removed the cell from tracking without closing it.
                    opened_cells.pop()
                    try:
                        cell.close()
                    except Exception:
                        pass
                    count += 1
            finally:
                # Close any cells that were not successfully saved
                for leaked_cell in opened_cells:
                    if leaked_cell is not orig_img:
                        try:
                            leaked_cell.close()
                        except Exception:
                            pass
                
        return (
            True,
            f"Successfully completed [{processor.display_name}] task, "
            f"generated {count} image(s) to {output_dir}"
        )
        
    except Exception as e:
        logger.exception("Error processing image %s", image_path)
        return False, f"Processing exception ({type(e).__name__}): {str(e)}"


def split_image_core(image_path: str, config: Any) -> Tuple[bool, str]:
    """Convenience entry point for grid splitting."""
    return process_image(image_path, "grid_splitter", config)


def batch_process_images(
    input_paths: List[str], 
    processor_name: str,
    config: Any
) -> Generator[Tuple[str, bool, str], None, None]:
    """Process images in batches.

    Args:
        input_paths: List of image paths.
        processor_name: Processor name.
        config: Configuration object.

    Yields:
        A tuple of (path, success, description).
    """
    for path in input_paths:
        success, msg = process_image(path, processor_name, config)
        yield path, success, msg
