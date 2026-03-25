# core.py
import os
from PIL import Image

def split_image_core(image_path, rows, cols, output_dir, template="{filename}_{index}", offsets=(0, 0, 0, 0)):
    """
    核心切图函数
    template: 命名模板，支持 {filename}, {row}, {col}, {index}, {ext}
    offsets: (left, top, right, bottom) 裁剪偏移量
    """
    try:
        if not os.path.exists(image_path):
            return False, f"错误: 找不到文件 {image_path}"
            
        img = Image.open(image_path)
        
        # 应用偏移量 (裁剪原图边缘)
        orig_w, orig_h = img.size
        left_off, top_off, right_off, bottom_off = offsets
        crop_box = (left_off, top_off, orig_w - right_off, orig_h - bottom_off)
        
        # 验证裁剪区域是否合法
        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
            raise ValueError(f"偏移量过大，导致有效图片区域无效 (当前区域: {crop_box})")
            
        img = img.crop(crop_box)
        img_width, img_height = img.size
        
        if rows <= 0 or cols <= 0:
            raise ValueError("行数和列数必须大于0")
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        ext = os.path.splitext(image_path)[1] or ".png"
            
        count = 1
        for i in range(rows):
            for j in range(cols):
                left = int(j * img_width / cols)
                upper = int(i * img_height / rows)
                right = int((j + 1) * img_width / cols)
                lower = int((i + 1) * img_height / rows)
                
                cell = img.crop((left, upper, right, lower))
                
                # 解析模板命名
                # {index} 使用 zfill(2) 补零
                name = template.format(
                    filename=base_name,
                    row=i + 1,
                    col=j + 1,
                    index=str(count).zfill(2),
                    ext=ext[1:] # 去掉点
                )
                if not name.endswith(ext):
                    name += ext
                    
                save_path = os.path.join(output_dir, name)
                cell.save(save_path)
                count += 1
                
        return True, f"成功！共生成 {rows * cols} 张图片至 {output_dir}"
        
    except Exception as e:
        return False, f"发生错误: {str(e)}"

def batch_process_images(input_paths, rows, cols, output_root, template="{filename}_{index}", offsets=(0, 0, 0, 0)):
    """
    批量处理多个图片
    """
    results = []
    total_success = 0
    
    for path in input_paths:
        # 每个文件单独一个子目录 (可选，或者直接平铺)
        # 这里默认直接在 output_root 下平铺，除非模板包含路径
        success, msg = split_image_core(path, rows, cols, output_root, template, offsets)
        results.append((path, success, msg))
        if success:
            total_success += 1
            
    return total_success, results
