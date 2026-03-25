# 开发者指南 (Developer Guide)

本项目的目标是提供一个高度模块化、易于维护和扩展的图像处理工具。

## 项目结构
```
image_splitter/
├── core.py       # 核心处理逻辑 (纯逻辑，无 UI 依赖)
├── cli.py        # 命令行入口 (由 argparse 提供)
├── gui.py        # 图形用户界面 (基于 tkinter 和 threading)
├── tests/        # 单元测试模块
└── README.md     # 用户文档
```

## 核心设计
1. **坐标计算**：
   核心公式为 `left = int(j * total_width / cols)`。通过先乘后除再取整的方式，将除不尽的余数均匀分配到各个切片中，避免累积误差。
   
2. **UI 并发**：
   `gui.py` 在执行批量处理时使用 `threading` 启动后台任务，并通过 `tk.after` 或更新 UI 保持响应。

3. **命名引擎**：
   使用 Python 原生 `str.format` 实现。确保在调用 `split_image_core` 前对文件名进行充分校验。

## 测试与质量
- 运行测试：`python -m unittest tests/test_core.py`
- 建议所有新核心逻辑都通过单元测试验证后再集成到 GUI。

## 扩展建议
- 添加多格式转换功能。
- 支持 WebP 无损压缩选项设置。
- 引入更复杂的边缘重叠 (Overlap) 功能。
