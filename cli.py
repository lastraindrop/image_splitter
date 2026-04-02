import argparse
import sys
import os
import glob
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# 确保在 cli 脚本所在目录外运行时也能正确找到核心模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import split_image_core
from models import SplitConfig
from typing import List, Tuple

def main():
    parser = argparse.ArgumentParser(description="网格图片切割工具 (高性能 CLI 版)")
    
    # 输入支持多个文件或通配符
    parser.add_argument("input", nargs="+", help="输入图片路径、通配符或目录")
    parser.add_argument("-r", "--rows", type=int, required=True, help="切割的行数")
    parser.add_argument("-c", "--cols", type=int, required=True, help="切割的列数")
    parser.add_argument("-o", "--output", default="./output", help="输出文件夹路径 (默认: ./output)")
    parser.add_argument("-t", "--template", default="{filename}_{index}", help="命名模板 (默认: {filename}_{index})")
    parser.add_argument("--offset", nargs=4, type=int, default=[0, 0, 0, 0], metavar=('L', 'T', 'R', 'B'), help="边缘偏移量: 左 上 右 下")
    parser.add_argument("--recursive", action="store_true", help="如果是目录，则递归处理")
    default_jobs = os.cpu_count() or 1
    parser.add_argument("-j", "--jobs", type=int, default=default_jobs, help=f"并行任务数 (默认: {default_jobs})")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output).resolve()
    
    # 解析输入路径
    raw_input_files = []
    extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    
    for item in args.input:
        item_path = Path(item)
        if item_path.is_dir():
            pattern = "**/*" if args.recursive else "*"
            found = item_path.glob(pattern)
            raw_input_files.extend([f.resolve() for f in found if f.suffix.lower() in extensions])
        elif "*" in item or "?" in item:
            # 处理通配符
            found = glob.glob(item, recursive=args.recursive)
            raw_input_files.extend([
                Path(f).resolve() for f in found 
                if Path(f).is_file() and Path(f).suffix.lower() in extensions
            ])
        else:
            if item_path.exists():
                raw_input_files.append(item_path.resolve())
            
    # 去重并过滤掉已经在输出目录下的文件 (防无限递归)
    unique_files = sorted(list(set(raw_input_files)))
    input_files = []
    for f in unique_files:
        try:
            # 如果 f 在 output_dir 下，relative_to 不会抛出异常
            f.relative_to(output_dir)
        except ValueError:
            # 不在 output_dir 下，属于需要保留的输入文件
            input_files.append(f)
    
    if not input_files:
        print("❌ 未找到有效的图片文件。")
        sys.exit(1)
        
    print(f"🚀 准备处理 {len(input_files)} 个文件 (并发数: {args.jobs})...")
    
    offsets = tuple(args.offset)
    total_success = 0
    
    # 使用进程池加速 CPU 密集型切割任务
    # 注意: Windows 下 ProcessPoolExecutor 需要在 if __name__ == "__main__" 下运行，这里 main 已经被包裹
    config = SplitConfig(
        rows=args.rows,
        cols=args.cols,
        output_dir=str(output_dir),
        template=args.template,
        offsets=offsets
    )
    
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        # 准备任务
        futures = [
            executor.submit(
                split_image_core, 
                str(f), config
            ) for f in input_files
        ]
        
        # 收集结果
        for f_path, future in zip(input_files, futures):
            try:
                success, msg = future.result()
                status = "✅" if success else "❌"
                print(f"{status} {f_path.name}: {msg}")
                if success:
                    total_success += 1
            except Exception as e:
                print(f"❌ {f_path.name}: 运行时异常 - {e}")
        
    print("-" * 30)
    print(f"🏁 完成！成功: {total_success} / 总计: {len(input_files)}")
    
    if total_success < len(input_files):
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()