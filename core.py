# core.py
import os
from PIL import Image
from typing import Tuple, List, Generator, Optional, Any

def split_image_core(
    image_path: str, 
    rows: int, 
    cols: int, 
    output_dir: str, 
    template: str = "{filename}_{index}", 
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0)
) -> Tuple[bool, str]:
    """
    核心切图函数 (专业级增强)
    :param image_path: 原始图片路径
    :param rows: 切割行数
    :param cols: 切割列数
    :param output_dir: 输出目录
    :param template: 命名模板，支持 {filename}, {row}, {col}, {index}, {ext}
    :param offsets: (left, top, right, bottom) 裁剪偏移量
    :return: (是否成功, 提示消息)
    """
    try:
        # Fail-Fast: 先验证参数
        if rows <= 0 or cols <= 0:
            return False, "行数和列数必须大于0"
            
        if not os.path.exists(image_path):
            return False, f"错误: 找不到文件 {image_path}"
            
        with Image.open(image_path) as orig_img:
            # 应用偏移量 (裁剪原图边缘)
            orig_w, orig_h = orig_img.size
            left_off, top_off, right_off, bottom_off = offsets
            
            # 计算有效裁剪矩形
            crop_box = (left_off, top_off, orig_w - right_off, orig_h - bottom_off)
            
            # 验证裁剪区域是否合法
            if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                return False, f"偏移量导致区域无效: {crop_box} (原图尺寸: {orig_w}x{orig_h})"
                
            # 获取裁剪后的内存副本
            img = orig_img.crop(crop_box)
            img_width, img_height = img.size
                
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            ext = os.path.splitext(image_path)[1] or ".png"

            # 验证模板是否合法
            try:
                # 测试一次 format 确保没有无效 key
                _ = template.format(filename=base_name, row=1, col=1, index="01", ext=ext.lstrip('.'))
            except KeyError as e:
                return False, f"命名模板包含无效的占位符: {e}"
                
            count = 1
            for i in range(rows):
                for j in range(cols):
                    left = int(j * img_width / cols)
                    upper = int(i * img_height / rows)
                    right = int((j + 1) * img_width / cols)
                    lower = int((i + 1) * img_height / rows)
                    
                    # 避免零宽度区域裁剪
                    if right <= left or lower <= upper:
                        continue
                        
                    cell = img.crop((left, upper, right, lower))
                    
                    # 解析模板命名
                    name = template.format(
                        filename=base_name,
                        row=i + 1,
                        col=j + 1,
                        index=str(count).zfill(2),
                        ext=ext.lstrip('.')
                    )
                    
                    # 确保扩展名正确
                    if not name.lower().endswith(ext.lower()):
                        name += ext
                        
                    save_path = os.path.join(output_dir, name)
                    cell.save(save_path)
                    cell.close()  # 显式关闭子图资源
                    count += 1
                
        return True, f"成功生成 {count-1} 张图片至 {output_dir}"
        
    except (OSError, ValueError) as e:
        return False, f"处理异常 ({type(e).__name__}): {str(e)}"

def batch_process_images(
    input_paths: List[str], 
    rows: int, 
    cols: int, 
    output_root: str, 
    template: str = "{filename}_{index}", 
    offsets: Tuple[int, int, int, int] = (0, 0, 0, 0)
) -> Generator[Tuple[str, bool, str], None, None]:
    """
    批量处理多个图片
    """
    for path in input_paths:
        success, msg = split_image_core(path, rows, cols, output_root, template, offsets)
        yield path, success, msg
