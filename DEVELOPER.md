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
3. **重要 (参数对齐协议)**: 在 `process()` 返回的 `context` 字典中，需包含该处理器的核心元数据（如 `anchor`, `text` 等），以支持用户在命名模板中动态引用（见下文）。
4. 系统核心 `register_all_processors()` 会自动扫描并完成加载。无需手动在 `core.py` 中注册。
5. 运行 `python gui.py` 或 `cli.py` 即刻生效。

## Context 注入协议 (Parameter Consistency)
为了通过“动态对齐”解决外部变量命名冲突，规定：处理器必须将能唯一描述该次操作的参数注入到返回的 `context` 中。
- **目的**: 允许命名模板 `{filename}_{anchor}_{index}` 在任何处理器下都能正确工作。
- **示例**: 若提供了 `anchor` 参数，必须在 `return [(img, {"anchor": anchor, ...})]` 中同步导出。

## 测试与质量 (Testing Standards)

- **执行指令**：`$env:PYTHONPATH='.'; pytest tests` 
- **核心全量测试集 (V5.0)**：
  - `test_engine_v4.py`: 插件自动发现与协议一致性。
  - `test_processors_expanded.py`: 深度参数组合适配。
  - `test_cli.py`: 高并发与递归扫描。
  - `test_dispatcher.py`: 指令链式分发分流稳定性。

---

## 路线图 (Roadmap)

### 📈 已完成 (Done)
- [x] **V4.0 架构升级**：完全解耦的插件自动发现机制。
- [x] **功能库大扩容**：集成色彩、水印、格式转换三大新核心模块。
- [x] **V5.0 压力测试集**：实现 100% 通过率的大规模并发集成测试。
- [x] **动态参数协议**：通过 Context 注入解决动态对齐与模板一致性问题。

### 🗓 短期计划 (Short-Term Goals)
- [ ] **可视化 Pipeline 编辑器**：允许用户在 GUI 中拖拽处理器卡片，构建复杂的处理链。
- [ ] **智能边缘裁剪集成**：基于物体识别或显著性检测的自动居中切割。
- [ ] **增强预览绘制协议**：为 `ColorAdjuster` 提供直方图等实时数据反馈。

### 🚀 长期计划 (Long-Term Goals)
- [ ] **跨平台 WASM 发行版**：支持浏览器端直接进行高性能纯离线处理。
- [ ] **分布式处理中台**：通过 RPC 协议将巨型渲染任务分发至多个节点。
