# core.py
import os
from PIL import Image
from typing import Tuple, List, Generator, Any
from models import SplitConfig
from engine.registry import ProcessorRegistry
from processors.splitter import GridSplitter
from processors.resizer import ImageResizer
from processors.custom_splitter import CustomLineSplitter
from processors.adjuster import CanvasAdjuster

# 注册处理器
ProcessorRegistry.register(GridSplitter())
ProcessorRegistry.register(ImageResizer())
ProcessorRegistry.register(CustomLineSplitter())
ProcessorRegistry.register(CanvasAdjuster())

def process_image(
    image_path: str,
    processor_name: str,
    config: Any
) -> Tuple[bool, str]:
    """
    通用图像处理逻辑入口
    :param image_path: 源图路径
    :param processor_name: 处理器注册名 (如 'grid_splitter' 或 'resizer')
    :param config: 处理器对应的配置对象
    """
    try:
        if not os.path.exists(image_path):
            return False, f"错误: 找不到文件 {image_path}"
            
        processor = ProcessorRegistry.get(processor_name)
        
        # 统一校验配置
        if hasattr(config, 'validate'):
            config.validate()

        with Image.open(image_path) as orig_img:
            processed_items = processor.process(orig_img, config)
            
            output_dir = getattr(config, 'output_dir', './output')
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            ext = os.path.splitext(image_path)[1] or ".png"
            ext_map = Image.registered_extensions()
            target_format = ext_map.get(ext.lower(), 'PNG')
            
            template = getattr(config, 'template', "{filename}_{index}")
            
            count = 0
            for cell, context in processed_items:
                # 合并基本上下文
                base_ctx = {
                    "filename": base_name, 
                    "ext": ext.lstrip('.'),
                    "index": str(count + 1).zfill(2) # 默认序号
                }
                base_ctx.update(context)
                
                try:
                    name = template.format(**base_ctx)
                except KeyError as e:
                    return False, f"命名模板包含无效的占位符: {e}"
                
                safe_name = os.path.basename(name.replace('\\', '/'))
                if not safe_name.lower().endswith(ext.lower()):
                    safe_name += ext
                    
                save_path = os.path.join(output_dir, safe_name)
                
                try:
                    cell.save(save_path, format=target_format)
                finally:
                    cell.close()
                count += 1
                
        return True, f"成功完成 [{processor.display_name}] 任务，生成 {count} 张图至 {output_dir}"
        
    except Exception as e:
        return False, f"处理异常 ({type(e).__name__}): {str(e)}"

# 保持对原有函数签名的兼容性
def split_image_core(image_path: str, config: SplitConfig) -> Tuple[bool, str]:
    return process_image(image_path, "grid_splitter", config)


def batch_process_images(
    input_paths: List[str], 
    config: SplitConfig
) -> Generator[Tuple[str, bool, str], None, None]:
    """
    批量处理多个图片
    """
    for path in input_paths:
        success, msg = split_image_core(path, config)
        yield path, success, msg
