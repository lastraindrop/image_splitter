# 开发者指南 (Developer Guide)

本项目旨在提供一个高度模块化、具备工业级性能与安全性的通用图像处理框架。

## 核心架构 (Core Architecture)

项目已全面迁移至 **Operator-Based (基于操作符)** 的设计哲学，对齐 Blender 等专业创作软件的设计逻辑。

```text
image_splitter/
├── engine/           # 核心引擎 (通用调度与分发)
│   ├── base.py       # 抽象基类 (BaseProcessor, BaseConfig)
│   ├── registry.py   # 插件注册中心 (ProcessorRegistry)
│   ├── operator.py   # 操作符接口 (Operator)
│   └── dispatcher.py # 命令解析与链式分发 (CommandDispatcher)
├── processors/       # 处理插件集 (高度可扩展)
│   ├── splitter.py   # 基础网格切割插件
│   ├── custom_splitter.py # 自定义线切割插件
│   ├── resizer.py    # 图片缩放插件
│   └── adjuster.py   # 画布调整与填充插件
├── core.py           # 任务流水线引擎 (与 Registry 深度绑定)
├── models.py         # 参数校验模型 (Fail-Fast 准则)
├── gui.py            # 动态 UI 平台 (基于 Metadata 自动渲染)
├── cli.py            # 高性能 CLI (多进程并发)
└── tests/            # 自动化测试套件
```

## 核心设计准则

1. **一切皆操作符 (Operator Pattern)**：
   - 每一个处理功能（如切割、缩放）都被抽象为一个 `Processor` 插件。
   - 核心引擎通过 `Registry` 发现插件，并通过 `CommandDispatcher` 支持字符串形式的指令调用（如 `split(rows=3) | resize(w=512)`）。

2. **UI 动态对齐 (Dynamic Metadata-Driven UI)**：
   - 处理器通过 `get_ui_metadata()` 自描述所需参数。
   - `gui.py` 根据元数据自动渲染输入控件，彻底消除了 UI 层的硬编码。
   - 任何 Core 层的参数变动会自动同步至 UI，确保了**参数一致性**。

3. **资源绝对安全**：
   - 全线采用 `with Image.open(...)` 上下文管理。
   - 裁切副本在处理完成后立即 `close()`，严格控制内存峰值。

4. **Fail-Fast 校验准则**：
   - 所有外部输入必须在执行 I/O 前完成类型、范围及物理合法性校验。
   - 模型层 (`models.py`) 负责统一的参数结构化，核心层 (`core.py`) 负责业务逻辑校验。

## 扩展一个新功能

1. 在 `processors/` 目录下新建 Python 脚本，继承 `BaseProcessor`。
2. 实现 `process()` 核心逻辑和 `get_ui_metadata()` 参数定义。
3. 在 `core.py` 中调用 `ProcessorRegistry.register()` 进行注册。
4. 运行 `python gui.py`，新功能将自动出现在下拉列表中，且参数面板自动生成。

## 测试与质量 (Testing Standards)

- **执行指令**：`$env:PYTHONPATH='.'; python -m unittest discover tests` (Windows)
- **覆盖范围**：
  - `test_core.py`: 基础网格逻辑。
  - `test_custom_splitter.py`: 不规则线条切割。
  - `test_adjuster.py`: 画布增添与裁剪。
  - `test_dispatcher.py`: 命令解析与分发。
  - `test_new_fixes.py`: 参数校验与格式安全性。

---

## 路线图 (Roadmap)

### 📈 已完成 (Done)
- [x] **高性能并发重构**：多进程并行加速。
- [x] **安全性加固**：路径穿越拦截与格式安全性修复。
- [x] **通用框架迁移**：引入 `BaseProcessor` 与 `Registry` 体系。
- [x] **Blender 式操作符设计**：实现 `CommandDispatcher` 指令分发系统。
- [x] **动态 UI 革命**：基于元数据自动生成参数面板，消除硬编码。
- [x] **自定义线切割**：支持任意坐标的横纵切割。
- [x] **画布调整功能**：支持增添、裁剪与自定义颜色填充。

### 🗓 短期计划 (Short-Term Goals)
- [ ] **参数联动预设系统**：支持用户保存/加载常用的操作序列 (Presets) 为本地脚本。
- [ ] **多帧/动图支持**：支持 GIF 和 WebP 动图的帧提取与分层切割。
- [ ] **冲突策略配置**：在批量重名时支持覆盖/跳过/自动重命名等策略。
- [ ] **增强预览图层**：为缩放和画布调整提供实时 Canvas 图形反馈。

### 🚀 长期计划 (Long-Term Goals)
- [ ] **AI 内容感知切割**：集成 AI 模型自动识别主体并进行聚焦分割。
- [ ] **处理管线扩展 (Pipeline)**：支持复杂的多步处理链（如：缩放 -> 旋转 -> 切割 -> 水印）。
- [ ] **云端同步预留**：架构层预留 Restful API 钩子，支持跨设备同步处理脚本。
