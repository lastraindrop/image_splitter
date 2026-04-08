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
    └── test_operator_compliance.py # 架构合规性审计脚本
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
3. **重要 (参数对齐协议)**: 在 `process()` 返回的 `context` 字典中，需包含该处理器的核心元数据（如 `anchor`, `text` 等），以支持用户在命名模板中动态引用（见下文）。
4. 系统核心 `register_all_processors()` 会自动扫描并完成加载。无需手动在 `core.py` 中注册。
5. 运行 `python gui.py` 或 `cli.py` 即刻生效。

## Context 注入协议与强类型校验 (Parameter Consistency)
为了通过“动态对齐”解决外部变量命名冲突并确保 UI 交互的稳定性，规定：
- **Context 注入**: 处理器必须将核心参数（如 `rotate`, `text`）注入返回的 `context` 中，以支持命名模板的动态变量。
- **强类型约定**: `get_ui_metadata` 必须包含 `type` 字段 (`int`, `float`, `bool`, `str`)。
  - `gui.py` 会根据 `type` 自动选择控件（如 `bool` 对应勾选框）。
  - `gui.py` 在执行前会进行强制转换与校验，确保输入数据不破坏后端 Operator 的运行。
- **系统级变量**: `core.py` 默认提供 `{w}`, `{h}`, `{index}`, `{filename}` 变量。

### 增量实践（已落地）

为避免前端/dispatcher/processor 三层的类型漂移，项目新增了一套轻量级的 coercion 实践：

- 已新增 `engine/config_coercion.py`，提供 `coerce_processor_config(processor, raw_config)`，用于把来自 GUI/CLI/dispatcher 的原始输入统一转换为处理器期望的类型与键名。
- 请在每个处理器的 `get_ui_metadata()` 中为每个字段显式提供 `default` 值（即使为 `null` 或空值），以保证 coercion 并避免运行时 KeyError。
- 已有自动化测试位于 `tests/test_config_coercion.py` 与 `tests/test_parameter_contract.py`（新增），用于保证元数据完整性和默认值的 coercion 行为。

短期约束:

- 任何新增处理器必须包含完整的 `name` / `type` / `default` /（可选）`options` 字段。
- 若某字段需要多语义支持（如既可为比例又可为像素），建议在 `type` 上使用 `str` 并在 `process()` 中使用明确的解析逻辑，同时在 `get_ui_metadata()` 文案中清晰注明预期格式。

## 测试与质量 (Testing Standards)

- **执行指令**：`$env:PYTHONPATH='.'; pytest tests` 
- **核心全量测试集 (V5.0)**：
  - `test_engine_v4.py`: 插件自动发现与协议一致性。
  - `test_processors_expanded.py`: 深度参数组合适配。
  - `test_cli.py`: 高并发与递归扫描。
  - `test_dispatcher.py`: 指令链式分发分流稳定性。
  - `test_operator_compliance.py`: **架构审计** - 验证所有插件的协议合规性。

---

## 路线图 (Roadmap)

### 📈 已完成 (Done)
- [x] **V4.0 架构升级**：完全解耦的插件自动发现机制。
- [x] **功能库大扩容**：集成几何变换、滤镜、元数据清理、水印等 10+ 核心模块。
- [x] **架构合规审计**：实现自动化插件协议检测（Compliance Testing）。
- [x] **UI 交互增强**：自适应控件（勾选框/文本框）与强类型参数校验。
- [x] **路径自修复**：解决跨目录启动时的 ModuleNotFoundError 导入问题。

### 🗓 短期计划 (Short-Term Goals)
- [ ] **可视化 Pipeline 编辑器**：允许用户在 GUI 中拖拽处理器卡片。
- [ ] **宏录制与控制台 (Macro Console)**：实时显示操作指令并支持保存为脚本。
- [ ] **Keymap 绑定系统**：支持用户自定义快捷键触发操作符。

### 🚀 长期计划 (Long-Term Goals)
- [ ] **跨平台 WASM 发行版**：支持浏览器端直接进行高性能纯离线处理。
- [ ] **分布式处理中台**：通过 RPC 协议将巨型渲染任务分发至多个节点。
