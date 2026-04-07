# image_splitter/core.py
import os
import sys
import importlib
import pkgutil
from PIL import Image
from typing import Tuple, List, Generator, Any, Optional
from image_splitter.models import SplitConfig
from image_splitter.engine.registry import ProcessorRegistry
from image_splitter.engine.base import BaseProcessor

def register_all_processors():
    """自动化寻找并注册 processors 目录下的所有插件类"""
    import image_splitter.processors as processors
    pkg_path = os.path.dirname(os.path.abspath(processors.__file__))
    
    # 清空重置，确保无状态遗留 (由 Registry.reset 实现)
    ProcessorRegistry.reset()
    
    # 遍历 processors 包下的所有模块
    for _, modname, _ in pkgutil.walk_packages([pkg_path], processors.__name__ + "."):
        try:
            # 动态导入模块
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
            print(f"Failed to load module {modname}: {e}")

def process_image(
    image_path: str,
    processor_name: str,
    config: Any
) -> Tuple[bool, str]:
    """
    通用图像处理逻辑入口
    """
    try:
        # 0. 自动注册检测
        if not ProcessorRegistry.list_all():
            register_all_processors()

        if not os.path.exists(image_path):
            return False, f"错误: 找不到文件 {image_path}"
            
        processor = ProcessorRegistry.get(processor_name)
        
        # 1. 统一校验配置
        if hasattr(config, 'validate'):
            config.validate()

        with Image.open(image_path) as orig_img:
            # 2. 图像处理
            processed_items = processor.process(orig_img, config)
            
            # 3. 输出策略解析
            output_dir = "./output"
            template = "{filename}_{index}"
            if isinstance(config, dict):
                output_dir = config.get('output_dir', output_dir)
                template = config.get('template', template)
            else:
                output_dir = getattr(config, 'output_dir', output_dir)
                template = getattr(config, 'template', template)
                
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            ext = os.path.splitext(image_path)[1] or ".png"
            ext_map = Image.registered_extensions()
            target_format = ext_map.get(ext.lower(), 'PNG')
            
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
                    if cell != orig_img: cell.close()
                    return False, f"命名模板包含无效的占位符: {e}"
                
                safe_name = os.path.basename(name.replace('\\', '/'))
                if not safe_name.lower().endswith(curr_ext.lower()):
                    safe_name += curr_ext
                    
                save_path = os.path.join(output_dir, safe_name)
                
                try:
                    save_fmt = ext_map.get(os.path.splitext(save_path)[1].lower(), 'PNG')
                    save_args = {"format": save_fmt}
                    if save_fmt in ('JPEG', 'WEBP'):
                        save_args["quality"] = context.get('quality', 95)
                        
                    cell.save(save_path, **save_args)
                finally:
                    if cell != orig_img:
                        cell.close()
                count += 1
                
        return True, f"成功完成 [{processor.display_name}] 任务，生成 {count} 张图至 {output_dir}"
        
    except Exception as e:
        return False, f"处理异常 ({type(e).__name__}): {str(e)}"

def split_image_core(image_path: str, config: Any) -> Tuple[bool, str]:
    return process_image(image_path, "grid_splitter", config)

def batch_process_images(
    input_paths: List[str], 
    processor_name: str,
    config: Any
) -> Generator[Tuple[str, bool, str], None, None]:
    for path in input_paths:
        success, msg = process_image(path, processor_name, config)
        yield path, success, msg
