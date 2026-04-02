# 图像网格切割工具 (Advanced Image Splitter)

一个专业级、高性能、支持多核并行的图像网格切割工具，提供流畅的图形用户界面 (GUI) 和强大的命令行接口 (CLI)。

## 🌟 核心功能
- **高性能切图**：CLI 版本默认开启**多进程并行 (Multi-processing)**，处理效率比传统工具快 4-8 倍。
- **极致预览体验**：GUI 采用**二级缩略图缓存**技术，在 4K 巨图下调整网格也完全不卡顿，并支持**实时切割尺寸看板**。
- **资源安全保障**：底层严格执行 Pillow 句柄生命周期管理，新增**路径穿越 (Path Traversal)** 拦截，确保系统路径安全。
- **架构解耦验证**：引入 `SplitConfig` 统一校验模型，实现 GUI、CLI 与 Core 层的参数动态对齐。
- **批量处理**：支持通配符、目录递归扫描。基于 Generator 架构，内存占用极低。
- **零副作用测试**：测试沙箱已迁移至项目本地 `tests/tmp_tests`，规避 Windows `/tmp` 权限报错问题。
- **Premium UX**：支持任务中途停止、丰富快捷键（Delete, Ctrl+A, Enter）以及现代化主题配色。

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
