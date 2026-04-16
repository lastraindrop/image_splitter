# image_splitter/core.py
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

# 初始化日志
logger = logging.getLogger(__name__)


def _prepare_image_for_save(image: Image.Image, save_format: str) -> Image.Image:
    """准备保存时的图像（处理透明度与格式转换）。

    Args:
        image: 原始 PIL 图像对象。
        save_format: 目标保存格式（如 'JPEG'）。

    Returns:
        处理后的图像对象。如果是 JPEG 且包含透明通道，则会进行铺底处理。
    """
    if save_format != 'JPEG':
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
    """自动化寻找并注册 processors 目录下的所有插件类。

    该函数会扫描 image_splitter.processors 包下的所有模块，
    并实例化所有继承自 BaseProcessor 的非抽象类。
    """
    import image_splitter.processors as processors
    pkg_path = Path(processors.__file__).parent
    
    # 清空重置，确保无状态遗留
    ProcessorRegistry.reset()
    
    # 遍历 processors 包下的所有模块
    for _, modname, _ in pkgutil.walk_packages([str(pkg_path)], processors.__name__ + "."):
        try:
            # 动态导入/重载模块
            if modname in sys.modules:
                module = importlib.reload(sys.modules[modname])
            else:
                module = importlib.import_module(modname)
            
            # 找到模块中定义的 BaseProcessor 的非抽象子类
            for attr in dir(module):
                obj = getattr(module, attr)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseProcessor) and 
                    obj is not BaseProcessor):
                    
                    # 实例化并注册
                    try:
                        instance = obj()
                        ProcessorRegistry.register(instance)
                    except TypeError:
                        continue
        except Exception as e:
            logger.error("Failed to load module %s: %s", modname, e)


def process_image(
    image_path: str,
    processor_name: str,
    config: Any
) -> Tuple[bool, str]:
    """通用图像处理逻辑入口。

    Args:
        image_path: 输入图像的路径。
        processor_name: 已注册的处理器名称。
        config: 处理配置，可以是字典或对应的 DataClass 实例。

    Returns:
        一个元组 (success, message)。success 表示是否处理成功，message 是结果描述。
    """
    try:
        # 0. 自动注册检测
        if not ProcessorRegistry.list_all():
            register_all_processors()

        img_p = Path(image_path)
        if not img_p.exists():
            return False, f"错误: 找不到文件 {image_path}"
            
        processor = ProcessorRegistry.get(processor_name)

        # 1. 统一配置清洗与模型验证 (Fail-Fast)
        raw_dict = config if isinstance(config, dict) else (config.__dict__ if hasattr(config, '__dict__') else {})
        config_dict = coerce_processor_config(processor, raw_dict)
        
        if processor.config_model:
            from dataclasses import fields
            model_fields = {f.name for f in fields(processor.config_model)}
            model_input = {k: v for k, v in config_dict.items() if k in model_fields}
            processor.config_model(**model_input)

        with Image.open(img_p) as orig_img:
            # 2. 图像处理
            processed_items = processor.process(orig_img, config_dict)
            
            # 3. 输出策略解析
            output_dir = Path(config_dict.get('output_dir', "./output"))
            template = config_dict.get('template', "{filename}_{index}")
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = img_p.stem
            ext = img_p.suffix or ".png"
            ext_map = Image.registered_extensions()
            
            count = 0
            for cell, context in processed_items:
                # 4. 命名与保存
                base_ctx = {
                    "filename": base_name, 
                    "ext": ext.lstrip('.'),
                    "index": str(count + 1).zfill(2),
                    "w": cell.width,
                    "h": cell.height
                }
                base_ctx.update(context)
                
                # 允许处理器动态改变后缀
                curr_ext = f".{base_ctx['ext']}"
                
                try:
                    name = template.format(**base_ctx)
                except KeyError as e:
                    if cell != orig_img:
                        cell.close()
                    return False, f"命名模板包含无效的占位符: {e}"
                
                # 提取文件名，防止路径穿越
                safe_name = Path(name.replace('\\', '/')).name
                if not safe_name.lower().endswith(curr_ext.lower()):
                    safe_name += curr_ext
                    
                save_path = output_dir / safe_name
                
                save_image = cell
                try:
                    save_fmt = ext_map.get(save_path.suffix.lower(), 'PNG')
                    save_image = _prepare_image_for_save(cell, save_fmt)
                    save_args = {"format": save_fmt}
                    if save_fmt in ('JPEG', 'WEBP'):
                        save_args["quality"] = int(context.get('quality', 95))
                    icc_profile = cell.info.get('icc_profile')
                    if icc_profile:
                        save_args['icc_profile'] = icc_profile
                        
                    save_image.save(save_path, **save_args)
                finally:
                    if save_image is not cell:
                        save_image.close()
                    if cell != orig_img:
                        cell.close()
                count += 1
                
        return True, f"成功完成 [{processor.display_name}] 任务，生成 {count} 张图至 {output_dir}"
        
    except Exception as e:
        logger.exception("Error processing image %s", image_path)
        return False, f"处理异常 ({type(e).__name__}): {str(e)}"


def split_image_core(image_path: str, config: Any) -> Tuple[bool, str]:
    """网格切割的便捷调用入口。"""
    return process_image(image_path, "grid_splitter", config)


def batch_process_images(
    input_paths: List[str], 
    processor_name: str,
    config: Any
) -> Generator[Tuple[str, bool, str], None, None]:
    """批量处理图像。

    Args:
        input_paths: 图像路径列表。
        processor_name: 处理器名称。
        config: 配置对象。

    Yields:
        (路径, 是否成功, 描述信息) 的元组。
    """
    for path in input_paths:
        success, msg = process_image(path, processor_name, config)
        yield path, success, msg
