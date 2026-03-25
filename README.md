# 图像网格切割工具 (Advanced Image Splitter)

一个专业级、高性能、支持多核并行的图像网格切割工具，提供流畅的图形用户界面 (GUI) 和强大的命令行接口 (CLI)。

## 🌟 核心功能
- **高性能切图**：CLI 版本默认开启**多进程并行 (Multi-processing)**，处理效率比传统工具快 4-8 倍。
- **极致预览体验**：GUI 采用**二级缩略图缓存 (Thumbnail Cache)** 技术，即使在 4K 巨图下调整网格也完全不卡顿，实现 60FPS 实时反馈。
- **资源安全保障**：底层严格执行 Pillow 句柄生命周期管理，防止“Too many open files”异常，具备工业级稳定性。
- **批量处理**：支持通配符、多文件、目录递归扫描。基于 Generator 与多进程架构，内存占用极低。
- **灵活命名模板**：支持 `{filename}`, `{row}`, `{col}`, `{index}`, `{ext}` 占位符，并包含预渲染检测逻辑。
- **精确边缘处理**：支持像素级 `Offsets` 边缘偏移，精准剔除不需要的边框。

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

## 📝 命名模板占位符
- `{filename}`: 原始文件名（不含扩展名）
- `{row}`: 当前行号 (1开始)
- `{col}`: 当前列号 (1开始)
- `{index}`: 全局序号 (01开始)
- `{ext}`: 文件原始后缀 (如 png, jpg)

## 📦 打包指南 (Windows)
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile gui.py
```
