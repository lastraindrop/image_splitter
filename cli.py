# image_splitter/cli.py
import sys
import os
from pathlib import Path

# ---------------------------------------------------------
# 路径自修复：支持绝对导入 image_splitter
# ---------------------------------------------------------
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import multiprocessing
import glob
from concurrent.futures import ProcessPoolExecutor
from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return parsed


def _parse_set_option(raw: str):
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--set 必须使用 key=value 格式")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("--set 的 key 不能为空")
    return key, value

def main():
    parser = argparse.ArgumentParser(description="通用图像处理工具 (CLI 版)")
    
    # 核心参数
    parser.add_argument("input", help="输入文件、目录或通配符路径 (如: ./pics/*.png)")
    parser.add_argument("-o", "--output", default="./output", help="输出目录 (默认: ./output)")
    parser.add_argument("-p", "--processor", default="grid_splitter", help="处理器名称 (默认: grid_splitter)")
    parser.add_argument("--set", dest="set_items", action="append", default=[], type=_parse_set_option,
                        help="处理器参数，格式 key=value，可重复传入")
    
    # 网格切割兼容参数 (保留原有体验)
    parser.add_argument("-r", "--rows", type=_positive_int, help="网格切割的行数")
    parser.add_argument("-c", "--cols", type=_positive_int, help="网格切割列数")
    
    # 高级参数
    parser.add_argument("--offset", type=int, nargs=4, default=[0, 0, 0, 0], 
                        help="边缘偏移量: 左 上 右 下 (像素)")
    parser.add_argument("-t", "--template", default="{filename}_{index}", 
                        help="输出文件名模板 (默认: {filename}_{index})")
    parser.add_argument("-j", "--jobs", type=_positive_int, default=multiprocessing.cpu_count(),
                        help="并行进程数 (默认: CPU 核心数)")
    parser.add_argument("--recursive", action="store_true", help="是否递归搜索子目录")

    args = parser.parse_args()

    register_all_processors()
    processor = None
    try:
        processor = ProcessorRegistry.get(args.processor)
    except ValueError:
        print(f"[FAIL] 未找到处理器: {args.processor}")
        available = ", ".join([p.name for p in ProcessorRegistry.list_all()])
        print(f"[INFO] 可用处理器: {available}")
        sys.exit(1)

    # 1. 环境检查与输入解析
    input_files = []
    output_dir = Path(args.output).resolve()
    
    # 允许的后缀
    exts = ["jpg", "jpeg", "png", "bmp", "webp"]
    
    # 首先检查是否是直接存在的目录/文件
    p = Path(args.input)
    if p.is_dir():
        pattern = "**/*" if args.recursive else "*"
        for ext in exts:
            input_files.extend(p.glob(f"{pattern}.{ext}"))
            input_files.extend(p.glob(f"{pattern}.{ext.upper()}"))
    elif p.is_file():
        input_files.append(p)
    else:
        # 尝试通配符解析
        glob_matches = glob.glob(args.input, recursive=args.recursive)
        for g in glob_matches:
            gp = Path(g)
            if gp.is_file():
                if gp.suffix.lower().lstrip('.') in exts:
                    input_files.append(gp)
            elif gp.is_dir() and args.recursive:
                 for ext in exts:
                    input_files.extend(gp.glob(f"**/*.{ext}"))
                    input_files.extend(gp.glob(f"**/*.{ext.upper()}"))

    # 去重并排序
    input_files = sorted(list(set(input_files)))

    # 过滤掉输出目录及其子目录内的文件（防止死循环）
    try:
        input_files = [f for f in input_files if not f.resolve().is_relative_to(output_dir)]
    except ValueError:
        pass

    if not input_files:
        print(f"[INFO] 未找到有效的图片文件: {args.input}")
        sys.exit(1)

    print(f"[INFO] 准备处理 {len(input_files)} 个文件 (并发数: {args.jobs})...\n")

    total_success = 0

    config = {k: v for k, v in args.set_items}
    if args.rows is not None:
        config["rows"] = args.rows
    if args.cols is not None:
        config["cols"] = args.cols
    if args.offset != [0, 0, 0, 0]:
        config["offsets"] = tuple(args.offset)

    config["output_dir"] = str(output_dir)
    config["template"] = args.template

    if args.processor == "grid_splitter":
        if "rows" not in config:
            config["rows"] = 3
        if "cols" not in config:
            config["cols"] = 3
        if "offsets" not in config:
            config["offsets"] = tuple(args.offset)

    # 2. 并行执行处理
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(process_image, str(f), processor.name, config) for f in input_files]

        for f_path, future in zip(input_files, futures):
            try:
                success, msg = future.result()
                status = "[OK]" if success else "[FAIL]"
                print(f"{status} {f_path.name}: {msg}")
                if success:
                    total_success += 1
            except Exception as e:
                print(f"[FAIL] {f_path.name}: 运行时异常 - {e}")

    print("-" * 30)
    print(f"[DONE] 完成！成功: {total_success} / 总计: {len(input_files)}")
    
    if total_success < len(input_files):
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
