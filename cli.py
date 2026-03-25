import argparse
import sys
import os
import glob
from core import batch_process_images

def main():
    parser = argparse.ArgumentParser(description="网格图片切割工具 (进阶 CLI 版)")
    
    # 输入支持多个文件或通配符
    parser.add_argument("input", nargs="+", help="输入图片路径、通配符或目录")
    parser.add_argument("-r", "--rows", type=int, required=True, help="切割的行数")
    parser.add_argument("-c", "--cols", type=int, required=True, help="切割的列数")
    parser.add_argument("-o", "--output", default="./output", help="输出文件夹路径 (默认: ./output)")
    parser.add_argument("-t", "--template", default="{filename}_{index}", help="命名模板 (默认: {filename}_{index})，支持 {row}, {col}, {index}, {filename}, {ext}")
    parser.add_argument("--offset", nargs=4, type=int, default=[0, 0, 0, 0], metavar=('L', 'T', 'R', 'B'), help="边缘偏移量: 左 上 右 下 (默认: 0 0 0 0)")
    parser.add_argument("--recursive", action="store_true", help="如果是目录，则递归处理")
    
    args = parser.parse_args()
    
    output_dir_abs = os.path.abspath(args.output)
    
    # 解析输入路径
    raw_input_files = []
    for item in args.input:
        if os.path.isdir(item):
            pattern = os.path.join(item, "**" if args.recursive else "", "*.*")
            found = glob.glob(pattern, recursive=args.recursive)
            raw_input_files.extend([os.path.abspath(f) for f in found if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))])
        elif "*" in item or "?" in item:
            found = glob.glob(item, recursive=args.recursive)
            raw_input_files.extend([os.path.abspath(f) for f in found if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))])
        else:
            raw_input_files.append(os.path.abspath(item))
            
    # 去重并过滤掉输出目录下的文件
    unique_files = {}
    out_dir_norm = os.path.normcase(output_dir_abs) + os.sep
    for f in raw_input_files:
        norm_f = os.path.normcase(f)
        if not norm_f.startswith(out_dir_norm):
            unique_files[norm_f] = f
            
    input_files = sorted(list(unique_files.values()))
    
    if not input_files:
        print("❌ 未找到有效的图片文件（或文件都在输出目录中）。")
        sys.exit(1)
        
    print(f"🚀 准备处理 {len(input_files)} 个文件...")
    
    offsets = tuple(args.offset)
    
    total_success = 0
    results = []
    
    for path, success, msg in batch_process_images(
        input_paths=input_files,
        rows=args.rows,
        cols=args.cols,
        output_root=output_dir_abs,
        template=args.template,
        offsets=offsets
    ):
        results.append((path, success, msg))
        if success:
            total_success += 1
    
    print("-" * 30)
    for path, success, msg in results:
        status = "✅" if success else "❌"
        print(f"{status} {os.path.basename(path)}: {msg}")
        
    print("-" * 30)
    print(f"🏁 完成！成功: {total_success} / 总计: {len(input_files)}")
    
    if total_success < len(input_files):
        sys.exit(1)

if __name__ == "__main__":
    main()