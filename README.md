# 图像网格切割工具 (Advanced Image Splitter)

一个轻量、精准、支持批量处理的图像网格切割工具，提供图形用户界面 (GUI) 和命令行接口 (CLI)。

## 🌟 核心功能
- **精确切割**：采用浮点坐标映射，确保除不尽时图像像素不丢失。
- **批量处理**：支持多文件选择、通配符匹配及文件夹递归。
- **动态预览**：在 GUI 中实时查看切割网格和边缘偏移。
- **灵活命名**：通过模板引擎实现高度自定义的文件命名。
- **边缘偏移**：支持在切割前剔除边缘无效边框。

## 🚀 快速开始
1. **安装环境**：
   ```bash
   pip install Pillow
   ```
2. **启动图形界面**：
   ```bash
   python gui.py
   ```
3. **使用命令行**：
   ```bash
   # 将 test.png 切割为 3x3 规格，并在边缘扣除 10 像素偏移
   python cli.py test.png -r 3 -c 3 -o ./output --offset 10 10 10 10
   ```

## 📝 命名模板说明
在设置中可以使用以下占位符：
- `{filename}`: 原始文件名（不含扩展名）
- `{row}`: 当前行号 (1开始)
- `{col}`: 当前列号 (1开始)
- `{index}`: 全局序号 (01开始)
- `{ext}`: 文件原始后缀

## 📦 打包指南 (Windows)
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile gui.py
```
