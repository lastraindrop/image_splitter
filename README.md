# 通用图像处理平台 (Advanced Image Processor)

一个对齐 Blender 操作符哲学、具备高性能多核并发能力的图像处理框架。支持网格切割、自定义线切、缩放、画布调整等多种功能。

## 🌟 核心功能

- **一切皆操作符 (Operators)**：底层逻辑与 UI 彻底解耦。支持 Blender 风格的操作符调用日志与指令分发。
- **动态 UI 适配**：GUI 采用 **Metadata-Driven (元数据驱动)** 技术。添加新功能只需增加插件，界面会自动生成参数面板。
- **高性能引擎**：CLI 版本默认开启 **多进程并行 (Multi-processing)**，处理效率领先同类工具 4-8 倍。
- **工业级安全性**：严格执行 Pillow 句柄管理，内置 **路径穿越 (Path Traversal)** 拦截，确保系统环境安全。
- **自定义线切割**：超越简单的网格，支持在任意像素位置进行横向或纵向的精确分割。
- **画布高级调整**：支持画布扩充 (Padding)、裁剪 (Cropping) 及自定义背景色填充。
- **指令控制台 (Console)**：GUI 实时记录操作指令，方便学习与脚本复用。

## 🚀 快速开始

1. **安装环境**：
   ```bash
   pip install Pillow
   ```
2. **启动图形界面**：
   ```bash
   python gui.py
   ```
3. **使用命令行接口 (CLI)**：
   ```bash
   # 将 test.png 切割为 3x3 规格，并开启 8 进程并行加速
   python cli.py test.png -r 3 -c 3 -o ./output -j 8
   ```

## 📦 插件库 (Processors)
- `grid_splitter`: 基础网格分割。
- `custom_splitter`: 自定义坐标分割。
- `resizer`: 通用图像缩放。
- `canvas_adjuster`: 画布边界调整与填充。
- `color_adjuster`: **(New)** 亮度、对比度、饱和度、锐度调节。
- `text_watermark`: **(New)** 全象限文字水印叠加。
- `format_converter`: **(New)** WebP/JPEG/PNG 格式转换与质量控制。

## 📝 命名模板占位符
- `{filename}`: 原始文件名（不含扩展名）
- `{row}` / `{col}`: 当前行号/列号 (1开始)
- `{index}`: 全局序号 (01开始)
- `{ext}`: 文件后缀
- `{anchor}`: 对齐位置（如 TL, BR, center）
- `{text}`: 水印文字内容
- `{quality}`: 导出质量参数

## 🛠 开发扩展
本项目支持极简的插件开发。只需继承 `BaseProcessor` 并实现逻辑，即可自动获得 CLI 支持与 GUI 自动渲染面板。详情请参阅 [DEVELOPER.md](./DEVELOPER.md)。
