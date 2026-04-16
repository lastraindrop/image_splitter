# 开发者指南 (Developer Guide)

本项目旨在提供一个高度模块化、具备工业级性能与安全性的通用图像处理框架。

## 核心架构 (Core Architecture)

项目已全面迁移至 **Operator-Based (基于操作符)** 的设计哲学，对齐 Blender 等专业创作软件的设计逻辑。

```text
image_splitter/
├── engine/           # 核心引擎 (通用调度与分发)
│   ├── base.py       # 抽象基类 (BaseProcessor, BaseConfig)
│   ├── registry.py   # 插件注册中心 (ProcessorRegistry)
│   └── dispatcher.py # 命令解析与链式分发 (CommandDispatcher)
├── processors/       # 处理插件集 (高度可扩展)
│   ├── splitter.py   # 基础网格切割插件
│   ├── custom_splitter.py # 自定义线切割插件
│   ├── resizer.py    # 图片缩放插件
│   └── adjuster.py   # 画布调整与填充插件
├── core.py           # 任务流水线引擎 (与 Registry 深度绑定)
├── models.py         # 参数校验模型 (Fail-Fast 准则)
├── gui.py            # 动态 UI 平台 (基于强类型 Metadata 自动渲染)
├── cli.py            # 高性能 CLI (支持路径自修复与并发)
└── tests/            # 自动化测试套件
```

## 核心设计准则

1. **一切皆操作符 (Operator Pattern)**：
   - 每一个处理功能（如切割、缩放）都被抽象为一个 `Processor` 插件。
   - 核心引擎通过 `Registry` 发现插件，并通过 `CommandDispatcher` 支持字符串形式的指令调用。

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

5. **代码风格与工程规范 (Google Python Style)**：
   - 全线遵循 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)。
   - 核心函数必须配备完整的 Google Style Docstrings (Args/Returns/Raises)。
   - 路径处理强制使用 `pathlib.Path` 以确保跨平台健壮性。
   - 逻辑层禁止使用 `print()`，统一采用标准 `logging` 模块。

## 扩展一个新功能
1. 在 `processors/` 目录下新建 Python 脚本，继承 `BaseProcessor`。
2. 实现 `process()` 核心逻辑和 `get_ui_metadata()` 参数定义。
3. **重要 (强类型模型绑定)**: 必须在 `models.py` 中定义对应的 `dataclass` 配置模型，并在处理器的 `config_model` 属性中关联。
4. **重要 (参数对齐协议)**: 在 `process()` 返回的 `context` 字典中，需包含该处理器的核心元数据（如 `anchor`, `text` 等），以支持用户在命名模板中动态引用。
5. 系统核心 `register_all_processors()` 会自动扫描并完成加载。
6. 运行 `python gui.py` 或 `cli.py` 即刻生效。

## Context 注入协议与强类型校验 (Parameter Consistency)
为了通过“动态对齐”解决外部变量命名冲突并确保 UI 交互的稳定性，规定：
- **模型驱动 (Model-Driven)**: 所有处理器参数必须通过 `models.py` 中的模型进行预校验。
- **coercion 机制**: 原始输入（CLI 字符串或 GUI 变量）必须通过 `coerce_processor_config` 进行物理类型转换，确保数据类型与 `config_model` 严格对齐。
- **Context 注入**: 处理器必须将核心参数注入返回的 `context` 中，以支持命名模板。
- **系统级变量**: `core.py` 默认提供 `{w}`, `{h}`, `{index}`, `{filename}` 变量。

### 增量实践（V5.5 交付版）

- **Pathlib 化**: 彻底解耦 `os.path`，核心逻辑不再依赖原始字符串路径。
- **日志审计**: `core.py` 已接入标准 `logging` 架构。
- **契约测试**: 强制执行 `test_parameter_contract.py`，确保所有插件的元数据与强制转换逻辑匹配。

---

## 路线图 (Roadmap)

### 📈 已完成 (Done)
- [x] **V4.0 架构升级**：完全解耦的插件自动发现机制。
- [x] **功能库大扩容**：集成几何变换、滤镜、元数据清理、水印等 10+ 核心模块。
- [x] **架构合规审计**：实现自动化插件协议检测（Compliance Testing）。
- [x] **UI 交互增强**：自适应控件（勾选框/文本框）与强类型参数校验。
- [x] **V5.5 工程重构**：全面适配 Google Python Style，引入 `pathlib` 与 `logging`。

### 🗓 短期计划 (Short-Term Goals)
- [ ] **静态类型审计 (Mypy)**：引入 `mypy` 进行全量类型扫描，消除 `Any` 类型遗留。
- [ ] **可视化 Pipeline 编辑器**：允许用户在 GUI 中拖拽处理器卡片。
- [ ] **宏录制与控制台 (Macro Console)**：实时显示操作指令并支持保存为脚本。

### 🚀 长期计划 (Long-Term Goals)
- [ ] **分布式处理中台**：通过 RPC 协议将巨型渲染任务分发至多个节点。
- [ ] **跨平台 WASM 发行版**：支持浏览器端直接进行高性能纯离线处理。
