"""Core image processing pipeline and processor discovery."""
import importlib
import logging
import pkgutil
import sys
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
            
            # 2. Image processing
            processed_items = processor.process(orig_img, config_dict)
            
            # 3. Output strategy parsing
            output_dir = Path(config_dict.get('output_dir', "./output"))
            template = config_dict.get('template', "{filename}_{index}")
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = img_p.stem
            ext = img_p.suffix or ".png"
            ext_map = Image.registered_extensions()
            
            count = 0
            for cell, context in processed_items:
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
                    if cell != orig_img:
                        cell.close()
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
                    if cell != orig_img:
                        cell.close()
                count += 1
                
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
