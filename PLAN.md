# 综合分析与发展计划 (Comprehensive Analysis & Roadmap)

> 本文档对 `image_splitter` 项目进行全方位的架构审计、代码审查、竞品分析，
> 并制定向 Blender 哲学对齐的完整实施计划。

---

## 一、架构工程分析

### 1.1 当前架构总览

```
image_splitter/
├── engine/                    # 核心引擎层 (Kernel)
│   ├── base.py                # 抽象基类 BaseProcessor / BaseConfig
│   ├── registry.py            # 插件注册中心 ProcessorRegistry
│   ├── dispatcher.py          # Blender 式命令解析与链式分发
│   └── config_coercion.py     # 强类型参数清洗引擎
├── processors/                # 处理插件集 (Plugin Layer)
│   ├── splitter.py            # 网格切割
│   ├── custom_splitter.py     # 自定义线切割
│   ├── resizer.py             # 比例缩放
│   ├── adjuster.py            # 画布调整
│   ├── color_adjuster.py      # 色彩调节
│   ├── filters.py             # 效果滤镜
│   ├── format_converter.py    # 格式转换
│   ├── geometry.py            # 几何变换
│   ├── metadata.py            # 元数据清理
│   └── watermark.py           # 文字水印
├── ui/
│   └── __init__.py
├── models.py                  # 数据校验模型 (Fail-Fast)
├── core.py                    # 任务流水线引擎
├── gui.py                     # 动态元数据驱动 GUI
├── cli.py                     # 高性能 CLI (多进程)
└── tests/                     # 测试套件 (69 项)
```

### 1.2 架构评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **模块解耦** | ★★★★☆ | engine / processors / 入口层 三层隔离清晰，处理器通过注册中心完全解耦 |
| **可扩展性** | ★★★★★ | 新处理器只需继承 BaseProcessor 并放入 processors/ 即自动发现，零配置接入 |
| **元数据驱动 UI** | ★★★★☆ | `get_ui_metadata()` 自描述参数，GUI 自动渲染，消除了 UI 硬编码 |
| **类型安全** | ★★★★☆ | 修复了 geometry enum 校验、resizer Fail-Fast、所有 `__post_init__` 注解 |
| **测试覆盖** | ★★★★★ | 136 项测试覆盖主要路径，含合规审计、参数契约、路径安全回归 |
| **错误处理** | ★★★★☆ | Fail-Fast 校验 + 路径穿越防护，但部分边界路径缺少精细化错误信息 |
| **资源管理** | ★★★★☆ | 全线 `with Image.open()` + cell close，dispatcher 链式 close 也已实现 |
| **代码风格** | ★★★★★ | Google Python Style Guide 全面合规审计已完成，导入排序/类型注解/行长度/文档字符串全部修复 |

### 1.3 架构优势

1. **Operator Pattern 执行良好**: 每个功能确实是独立的"操作符"，通过 Registry 统一管理，Dispatcher 支持字符串指令调用。
2. **自动发现机制成熟**: `register_all_processors()` 使用 `pkgutil.walk_packages` 扫描，动态导入并实例化，零配置。
3. **元数据协议完善**: `get_ui_metadata()` 返回结构化参数定义，GUI 根据此动态生成控件，CLI 也可利用。
4. **安全性达标**: 路径穿越拦截 (`safe_name = Path(name.replace('\\', '/')).name`)、ICC Profile 保留、透明度铺底。
5. **并发设计合理**: CLI 使用 `ProcessPoolExecutor` 真正的多进程，GUI 使用线程+Event 避免阻塞。

### 1.4 架构缺陷与风险

| 编号 | 缺陷 | 严重度 | 位置 |
|------|------|--------|------|
| A-1 | `ProcessorRegistry` 使用类变量 `_processors`，测试间可能状态泄漏 | ⚠️ 已缓解 | `engine/registry.py:6` |
| A-2 | 缺少 `pyproject.toml` / `setup.py`，项目不可作为包安装 | ✅ 已修复 | 项目根 |
| A-3 | `ui/` 空目录未使用，造成混淆 | 低 | `ui/` |
| A-4 | `processors/__init__.py` 仅导出 4 个处理器，与其余 6 个不一致 | ✅ 已修复 | `processors/__init__.py` |
| A-5 | 缺少统一日志配置入口，日志格式/级别分散 | ✅ 已修复 | 各模块 |
| A-6 | 无 undo/redo 机制，无操作历史栈 | 中 | 全局 |
| A-7 | 无用户配置持久化系统 (设置/偏好) | ✅ 已修复 | 全局 |
| A-8 | Dispatcher 的 `execute_chain` 不携带 output_dir/template，无法独立完成保存 | ⚠️ 部分修复 | `engine/dispatcher.py` |

---

## 二、方向定位与竞品分析

### 2.1 项目定位

**核心定位**: 一个轻量级、高度模块化的图像批处理框架，面向需要可编程、可扩展图像处理管道的开发者与高级用户。

**设计哲学对标**: Blender 的"一切皆操作符"——
- 功能 = 操作符 (Operator)
- 操作符可通过脚本/命令行/GUI 统一调用
- 用户可编写脚本组合操作符
- 插件系统允许第三方扩展

### 2.2 竞品对比

| 特性 | **本项目** | **ImageMagick** | **GIMP (Script-Fu)** | **Pillow (raw)** | **sharp (Node.js)** |
|------|-----------|----------------|---------------------|------------------|---------------------|
| 插件架构 | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★☆☆☆☆ | ★★☆☆☆ |
| CLI 并行 | ★★★★☆ | ★★★★★ | N/A | N/A | ★★★☆☆ |
| GUI 动态适配 | ★★★★☆ | N/A | ★★★☆☆ | N/A | N/A |
| 脚本可编程 | ★★☆☆☆ | ★★★★☆ | ★★★★★ | ★★★★★ | ★★★★☆ |
| 操作符链式调用 | ★★★★☆ | ★★★★★ (管道) | ★★☆☆☆ | ★★☆☆☆ | ★★★★☆ |
| 快捷键自定义 | ☆☆☆☆☆ | N/A | ★★☆☆☆ | N/A | N/A |
| 宏录制 | ☆☆☆☆☆ | N/A | ★★☆☆☆ | N/A | N/A |
| 批量处理 | ★★★★★ | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★★☆ |
| 学习曲线 | ★★★★★ (低) | ★★☆☆☆ (高) | ★★☆☆☆ (高) | ★★★★☆ | ★★★☆☆ |
| 轻量化 | ★★★★★ | ★★☆☆☆ | ★☆☆☆☆ | ★★★★★ | ★★★★☆ |

### 2.3 可学习的参考点

| 来源 | 学习点 | 适用性 |
|------|--------|--------|
| **Blender** | 操作符日志系统 (Info Editor) — 记录每一步操作为可复现的 Python 代码 | ★★★★★ 核心 |
| **Blender** | Keymap 系统 — 快捷键可由用户完全自定义并导入/导出 | ★★★★★ 核心 |
| **Blender** | Python Console — 内置交互式脚本执行环境 | ★★★★☆ 重要 |
| **Blender** | 插件系统 — 用户脚本可注册新操作符 | ★★★★★ 核心 |
| **ImageMagick** | `-pipe` 模式 — 流式处理巨量文件 | ★★★☆☆ 参考 |
| **GIMP** | Procedure Database (PDB) — 统一的函数调用数据库 | ★★★★☆ 重要 |
| **Photoshop Actions** | 动作录制/回放 — 宏系统参考 | ★★★★☆ 重要 |

### 2.4 未来路线图 (按优先级)

```
Phase 1 (当前) ──→ Bug 修复 + 架构硬化
Phase 2 (短期) ──→ 快捷键系统 + 脚本引擎 + 命令控制台
Phase 3 (中期) ──→ 宏录制/回放 + 操作历史 + 偏好持久化
Phase 4 (长期) ──→ 可视化 Pipeline 编辑器 + 插件市场
Phase 5 (远期) ──→ 分布式中台 + WASM 端
```

---

## 三、完整 Code Review 与 Bug 排查

### 3.1 确认的 BUG 列表

#### BUG-01: gui.py 缺少 `subprocess` 导入 (严重) ✅ **已修复**
- **位置**: `gui.py:263`
- **现象**: `open_output_dir()` 方法在非 Windows 平台调用 `subprocess.run()`，
  但文件顶部仅导入了 `tkinter, threading, platform`，**没有 `import subprocess`**。
- **影响**: 在 macOS/Linux 上点击"打开输出目录"按钮会触发 `NameError`。
- **修复方案**: 在 `gui.py` 顶部添加 `import subprocess`。

#### BUG-02: resizer 缺少 config_model 导致校验旁路 (中等) ✅ **已修复**
- **位置**: `processors/resizer.py`
- **现象**: `ImageResizer` 未覆写 `config_model` 属性，继承基类默认值 `None`。
  `core.py:112-116` 的模型校验因此被跳过，`width=0` 或 `height=-1` 等非法值
  不会被 Fail-Fast 拦截，而是传入 `process()` 后在 `int(orig_w * 0)` 处产出
  0 尺寸图像才报错。
- **影响**: 非法参数不会被模型层立即拦截，违背 Fail-Fast 原则。
- **修复方案**: 
  1. 在 `models.py` 中新建 `ResizeConfig` dataclass。
  2. 在 `ImageResizer.config_model` 中返回 `ResizeConfig`。

#### BUG-03: geometry 处理器静默忽略非标准旋转角度 (低) ✅ **已修复**
- **位置**: `processors/geometry.py:56-61`
- **现象**: 仅处理 90/180/270 三个角度。用户传入 `rotate=45` 时，
  整个旋转逻辑被静默跳过，不产生任何警告。
- **影响**: 用户可能认为操作已生效，实际图像未被修改。
- **修复方案**: 在 `process()` 中添加角度合法性校验，非 0/90/180/360 时抛出
  `ValueError("仅支持 0/90/180/270 度旋转")`，或在 UI 元数据中将其约束为 enum。

#### BUG-04: processors/__init__.py 导出不全 (低) ✅ **已修复**
- **位置**: `processors/__init__.py`
- **现象**: 仅导出 `GridSplitter, ImageResizer, CustomLineSplitter, CanvasAdjuster`，
  缺少 `ImageColorAdjuster, SimpleFilterProcessor, ImageFormatConverter,
  GeometryProcessor, MetadataProcessor, TextWatermark`。
- **影响**: 如果有人通过 `from image_splitter.processors import ImageColorAdjuster`
  直接导入会失败。虽然自动发现机制不依赖此导入，但作为公共 API 接口不一致。
- **修复方案**: 补全所有处理器的导出。

#### BUG-05: dispatcher.execute_chain 未关闭原始输入图像 (低) ✅ **已修复**
- **位置**: `engine/dispatcher.py:69`
- **现象**: 条件 `if img != image: img.close()` 正确跳过原始图像的关闭，
  但 dispatcher 本身不拥有原始图像的生命周期，调用者需自行关闭。
  如果调用者忘记关闭，在链式处理大量图像时可能造成资源泄漏。
- **影响**: 在外部调用者不遵循规范时可能导致内存泄漏。
- **修复方案**: 在 `execute_chain` 文档中明确说明调用者的资源管理责任，
  或在方法内部对结果图像做深拷贝后关闭所有中间产物。

#### BUG-06: CLI 的 --set 参数值均为字符串，依赖 coercion 转换 (设计缺陷) ✅ **已修复**
- **位置**: `cli.py:118,44`
- **现象**: `--set rows=3` 传入的 `3` 是字符串 `"3"`，而非整数。
  虽然 `coerce_processor_config` 最终会转换，但如果处理器未在
  `get_ui_metadata()` 中声明该参数，coercion 不会处理它，
  字符串会直接流入 `process()`。
- **影响**: 对于未声明元数据的自定义参数，类型不正确。
- **修复方案**: CLI 应在构建 config 时对已知参数做预转换，
  或在 README 中说明 `--set` 值均为字符串。

#### BUG-07: MetadataProcessor 对 Palette 模式图像处理不完整 (低) ✅ **已修复**
- **位置**: `processors/metadata.py:56`
- **现象**: `Image.new(image.mode, image.size)` 后 `paste(image)` 对
  Palette ('P') 模式图像可能丢失调色板信息，因为新创建的 'P' 图像
  有默认调色板而非原图的调色板。
- **影响**: 'P' 模式图像清理元数据后可能颜色异常。
- **修复方案**: 对 'P' 模式先转为 'RGBA' 再处理，或在 paste 前复制调色板。

#### BUG-08: 批量处理 GUI 中 stop_event 无法中断正在执行的单张处理 (设计局限) ⚠️
- **位置**: `gui.py:294-305`
- **现象**: `batch_process_images` 生成器在每张图片完成后 yield，
  `stop_event` 在两张图之间检查。如果单张图片处理时间很长，
  用户点击"中断"后需要等待当前图片处理完成才能响应。
- **影响**: 大图处理时中断响应延迟。
- **修复方案**: 在 `process_image` 内部增加对 abort callback 的轮询支持，
  或在处理器层面支持取消。此为增强功能，非紧急。

#### 本次会话新增的 BUG 与修复

| 编号 | BUG | 严重度 | 文件 | 状态 |
|------|-----|--------|------|------|
| BUG-09 | watermark.py `process()` 缺少 return 语句，导致 `NoneType` 错误 | 🔴 致命 | `processors/watermark.py:89` | ✅ 已修复 |
| BUG-10 | CLI `--script`/`--chain` 模式引用未定义变量 `output_dir` | 🔴 严重 | `cli.py:96,102` | ✅ 已修复 |
| BUG-11 | script_engine `chain()` 无上下文管理器（内存泄漏）+ 结果未保存 | 🟠 严重 | `script_engine.py:80` | ✅ 已修复 |
| BUG-12 | geometry.py 重复注释行 | 🟡 低 | `processors/geometry.py:61` | ✅ 已修复 |

### 3.2 代码健康性评估

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 所有处理器均有 `name` | ✅ | snake_case，唯一 |
| 所有处理器均有 `display_name` | ✅ | 唯一 |
| 所有处理器均有 `category` | ✅ | 属于预定义集合 |
| 所有处理器均有 `tool_tip` | ✅ | 非空 |
| 所有处理器均有 `get_ui_metadata` | ✅ | schema 合规 |
| 所有处理器均可通过默认配置运行 | ✅ | 136/136 测试通过 |
| 路径穿越防护 | ✅ | `safe_name` 提取 |
| ICC Profile 保留 | ✅ | save 时检测并传递 |
| 透明度铺底 | ✅ | JPEG/WEBP 前处理 |
| 内存释放 (cell close) | ✅ | process_image finally 块 |
| 日志规范 (logging vs print) | ⚠️ | gui.py/CLI 中存在 print，合理；core.py 已用 logging |
| 跨平台路径处理 | ✅ | 全线 pathlib |
| 并发安全 | ✅ | 多进程隔离 + 线程 Event |

---

## 四、实施计划 — Blender 哲学对齐

### 4.1 总体目标

将 `image_splitter` 从"好用的小工具"升级为"可编程的图像处理平台"，
对齐 Blender 的核心设计哲学：

> **一切皆操作符，操作符可脚本化，界面可自定义，插件可扩展。**

### 4.2 需新增的系统模块

```
image_splitter/
├── engine/
│   ├── base.py               # (已有) 无需改动
│   ├── registry.py           # (已有) 无需改动
│   ├── dispatcher.py         # (已有) 微调 — 支持保存
│   ├── config_coercion.py    # (已有) 无需改动
│   ├── keymap.py             # [新增] 快捷键映射系统
│   ├── history.py            # [新增] 操作历史栈 (Undo/Redo)
│   ├── script_engine.py      # [新增] 脚本执行引擎
│   └── macro.py              # [新增] 宏录制与回放
├── processors/               # (已有) 修复后无改动
├── ui/
│   ├── __init__.py           # [新增]
│   ├── console.py            # [新增] 命令控制台面板
│   ├── keymap_editor.py      # [新增] 快捷键编辑器面板
│   └── preferences.py        # [新增] 偏好设置面板
├── core.py                   # (已有) 微调
├── gui.py                    # (已有) 重构 — 接入新系统
├── cli.py                    # (已有) 微调
├── models.py                 # (已有) 新增 ResizeConfig
├── settings.py               # [新增] 全局设置管理
├── plugins/                  # [新增] 用户插件目录
│   ├── __init__.py
│   └── example_plugin.py     # 示例插件
├── pyproject.toml            # [新增] 项目打包配置
└── tests/
    ├── (已有测试保留)
    ├── test_keymap.py         # [新增]
    ├── test_history.py        # [新增]
    ├── test_script_engine.py  # [新增]
    ├── test_macro.py          # [新增]
    ├── test_settings.py       # [新增]
    ├── test_bug_fixes.py      # [新增] 验证所有 BUG 修复
    └── test_integration.py    # [新增] 端到端集成测试
```

### 4.3 各阶段详细计划

---

### Phase 1: BUG 修复 (预计修改 7 个文件)

> ✅ **已完成** — 共修复 12 个 BUG，涉及 8 个文件

#### 1.1 修复 BUG-01: gui.py 添加 subprocess 导入
- **文件**: `gui.py`
- **位置**: 第 1-5 行导入区域
- **操作**: 在 `import platform` 后添加 `import subprocess`
- **验证**: 新增测试 `test_bug_fixes.py::test_open_output_dir_no_import_error`

#### 1.2 修复 BUG-02: resizer 添加 config_model
- **文件 1**: `models.py` — 新增 `ResizeConfig` dataclass
  ```python
  @dataclass
  class ResizeConfig:
      width: float = 1.0
      height: float = 1.0
      def __post_init__(self):
          if self.width <= 0 or self.height <= 0:
              raise ValueError("缩放比例必须大于 0")
  ```
- **文件 2**: `processors/resizer.py` — 添加 `config_model` 属性和导入
- **验证**: 新增测试验证 `width=0` 被 Fail-Fast 拦截

#### 1.3 修复 BUG-03: geometry 角度校验
- **文件**: `processors/geometry.py`
- **位置**: `process()` 方法顶部
- **操作**: 添加 `if angle not in (0, 90, 180, 270): raise ValueError(...)`
- **同步**: 在 `get_ui_metadata()` 中将 rotate 改为 enum 类型，options=[0,90,180,270]
- **验证**: 新增测试验证非法角度被拒绝

#### 1.4 修复 BUG-04: processors/__init__.py 导出补全
- **文件**: `processors/__init__.py`
- **操作**: 补充所有 10 个处理器的 import 和 __all__
- **验证**: 测试 `from image_splitter.processors import *` 不报错

#### 1.5 修复 BUG-07: MetadataProcessor Palette 模式处理
- **文件**: `processors/metadata.py`
- **位置**: `process()` 方法
- **操作**: 对 'P' 模式先转为 'RGBA' 处理后再转回
- **验证**: 新增 'P' 模式测试用例

#### 1.6 修复 BUG-06: CLI --set 值预转换
- **文件**: `cli.py`
- **位置**: config 构建段
- **操作**: 在 `register_all_processors()` 后获取当前处理器的 metadata，
  对 `--set` 传入的值做预转换
- **验证**: 新增测试 `--set rows=3` 传入后 config 中 rows 为 int

#### 1.7 清理 BUG-04 相关: 移除空 ui/ 或添加 __init__.py
- **文件**: `ui/__init__.py` (新建)
- **操作**: 创建空的 `__init__.py`，为后续 UI 模块占位

---

### Phase 2: 架构硬化 (预计修改/新增 3 个文件)

> ✅ **已完成** — pyproject.toml 已存在，Registry 已改造，日志配置已统一

#### 2.1 新增 pyproject.toml
- **文件**: `pyproject.toml` (新建)
- **内容**: 项目元数据、依赖声明、可选依赖 (dev/test)、entry_points (cli/gui 命令)
- **验证**: `pip install -e .` 成功，`image-splitter --help` 可用

#### 2.2 重构 ProcessorRegistry 为实例化设计
- **文件**: `engine/registry.py`
- **当前**: 类变量 `_processors: Dict` 共享状态
- **目标**: 提供 `get_global_registry()` 工厂函数，返回单例实例。
  保留类方法接口以兼容现有调用，内部委托给全局实例。
- **原因**: 类变量在测试重置时可能跨测试泄漏；实例化更易 mock 和测试
- **验证**: 现有 69 项测试全部通过 (兼容性)

#### 2.3 统一日志配置
- **文件**: 新增 `logging_config.py` 或在 `__init__.py` 中配置
- **操作**: 提供 `configure_logging(level, format)` 函数
- **验证**: CLI/GUI 启动后日志输出格式统一

---

### Phase 3: Blender 哲学核心系统 (预计新增 8 个文件)

#### 3.1 快捷键映射系统 (`engine/keymap.py`)

**设计**:
```python
class KeymapRegistry:
    """全局快捷键注册中心 (对齐 Blender Keymap)"""
    
    # 内部结构: { "global": { "<Control-o>": "operator:select_files", ... }, ... }
    
    @classmethod
    def bind(cls, context: str, key_sequence: str, action: str) -> None: ...
    @classmethod
    def unbind(cls, context: str, key_sequence: str) -> None: ...
    @classmethod
    def lookup(cls, context: str, key_sequence: str) -> Optional[str]: ...
    @classmethod
    def export_keymap(cls, path: str) -> None: ...  # 导出为 JSON
    @classmethod
    def import_keymap(cls, path: str) -> None: ...  # 从 JSON 导入
    @classmethod
    def reset_to_default(cls) -> None: ...
```

**默认绑定**:
| 快捷键 | 动作 |
|--------|------|
| Ctrl+O | select_files |
| Ctrl+Enter | run_batch |
| Delete | remove_selected |
| Ctrl+S | 保存当前配置 |
| Ctrl+Z | undo |
| Ctrl+Shift+Z | redo |
| F5 | 刷新预览 |
| Ctrl+K | 打开快捷键编辑器 |
| Ctrl+` | 打开控制台 |

**集成点**: `gui.py` 的 `_create_widgets` 中，从 `KeymapRegistry` 读取绑定并注册。
  用户可在 GUI 中通过快捷键编辑器修改，修改后自动持久化到 `~/.image_splitter/keymap.json`。

**修改位置**:
- `gui.py`: 删除硬编码的 `self.root.bind(...)`，改为从 KeymapRegistry 动态注册
- `gui.py`: 快捷键编辑器入口

**测试**: `test_keymap.py` — 测试绑定/解绑/查找/导入导出/重置/冲突检测

---

#### 3.2 操作历史栈 (`engine/history.py`)

**设计**:
```python
@dataclass
class HistoryEntry:
    timestamp: float
    operator_name: str
    config_snapshot: Dict[str, Any]
    input_files: List[str]
    description: str

class HistoryManager:
    """操作历史管理器 (Undo/Redo)"""
    
    def __init__(self, max_depth: int = 50): ...
    def push(self, entry: HistoryEntry) -> None: ...
    def undo(self) -> Optional[HistoryEntry]: ...
    def redo(self) -> Optional[HistoryEntry]: ...
    def can_undo(self) -> bool: ...
    def can_redo(self) -> bool: ...
    def clear(self) -> None: ...
    def get_history(self) -> List[HistoryEntry]: ...
    def export_log(self, path: str) -> None: ...
```

**集成点**: `gui.py` 的 `run_batch` 成功后 push 一条记录；
  Ctrl+Z / Ctrl+Shift+Z 触发 undo/redo (重放操作)。

**注意**: 图像操作的 undo 不恢复文件，而是记录操作参数供用户回看和重放。

**测试**: `test_history.py` — 测试 push/undo/redo/clear/边界/max_depth

---

#### 3.3 脚本执行引擎 (`engine/script_engine.py`)

**设计**:
```python
class ScriptEngine:
    """用户脚本执行引擎"""
    
    def __init__(self, registry: ProcessorRegistry):
        self._registry = registry
        self._namespace = self._build_namespace()
    
    def _build_namespace(self) -> Dict[str, Any]:
        """构建脚本可用的命名空间"""
        return {
            "process": self._process_image,
            "chain": self._execute_chain,
            "batch": self._batch_process,
            "Image": Image,
            # 注册所有处理器为顶层函数
            "grid_splitter": partial(self._op_call, "grid_splitter"),
            "resizer": partial(self._op_call, "resizer"),
            # ... 自动注入所有已注册处理器
        }
    
    def execute(self, script: str) -> ScriptResult: ...
    def execute_file(self, path: str) -> ScriptResult: ...
    def validate(self, script: str) -> List[str]: ...
```

**用户脚本示例**:
```python
# user_script.py
chain("resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)")
batch(["img1.png", "img2.png"], "format_converter", format="WebP", quality=80)
```

**安全设计**:
- 脚本在受限命名空间中执行 (无 `__import__`, `open`, `os` 等)
- 提供白名单函数: `process`, `chain`, `batch`, `Image`
- 可选"信任模式"解除限制

**集成点**: GUI 控制台面板、CLI `--script` 参数、plugins/ 目录自动加载

**测试**: `test_script_engine.py` — 测试执行/安全沙箱/文件加载/错误处理

---

#### 3.4 宏录制与回放 (`engine/macro.py`)

**设计**:
```python
class MacroRecorder:
    """操作录制器"""
    
    def __init__(self):
        self._recording: bool = False
        self._steps: List[MacroStep] = []
    
    def start(self) -> None: ...
    def stop(self) -> str: ...  # 返回生成的脚本代码
    def record(self, operator: str, config: Dict) -> None: ...
    def is_recording(self) -> bool: ...

class MacroPlayer:
    """宏回放器"""
    
    @staticmethod
    def play(script: str, engine: ScriptEngine) -> List[Any]: ...
```

**集成点**: 
- GUI 工具栏添加"录制"按钮
- 每次用户执行操作时，如果录制状态开启，自动追加一步到宏
- 停止录制时生成 `.py` 脚本文件，可通过 ScriptEngine 回放

**测试**: `test_macro.py` — 测试录制/停止/回放/空录制/嵌套

---

#### 3.5 命令控制台 (`ui/console.py`)

**设计**:
```python
class ConsolePanel(ttk.Frame):
    """内嵌命令控制台 (对齐 Blender Python Console)"""
    
    def __init__(self, parent, script_engine: ScriptEngine): ...
    
    # UI 元素:
    # - 输出区域 (Text widget, 只读, 显示命令历史和输出)
    # - 输入框 (Entry, 用户输入命令)
    # - 状态指示器 (显示引擎状态)
    
    def execute_command(self, cmd: str) -> None: ...
    def append_output(self, text: str, tag: str = "output") -> None: ...
    def clear_output(self) -> None: ...
    def history_up(self) -> None: ...
    def history_down(self) -> None: ...
```

**交互设计**:
- 用户输入 `grid_splitter(rows=2, cols=2)` → 直接执行
- 用户输入 `chain("resizer(width=0.5) | grid_splitter(rows=2)")` → 链式执行
- 上下方向键浏览命令历史
- Tab 键自动补全操作符名称
- 输出区支持颜色标签 (正常/警告/错误)

**集成点**: `gui.py` 中添加为底部可折叠面板 (类似 Blender 的 Info Editor)

**测试**: 集成在 `test_gui_smoke.py` 中

---

#### 3.6 快捷键编辑器 (`ui/keymap_editor.py`)

**设计**:
```python
class KeymapEditorDialog(tk.Toplevel):
    """快捷键自定义编辑器"""
    
    def __init__(self, parent, keymap_registry: KeymapRegistry): ...
    
    # UI 元素:
    # - 搜索框
    # - 绑定列表 (Treeview: 快捷键 | 动作 | 上下文)
    # - 编辑区域 (按键捕获 + 动作选择)
    # - 按钮: 添加 / 删除 / 重置全部 / 导出 / 导入
```

**交互**: 用户点击"捕获按键"后按下组合键，自动填入；
  选择关联动作，点击保存。

**测试**: 集成在 `test_keymap.py` 中

---

#### 3.7 偏好设置系统 (`settings.py` + `ui/preferences.py`)

**设计** (`settings.py`):
```python
class AppSettings:
    """全局设置管理器"""
    
    _DEFAULTS = {
        "output_dir": "./output",
        "default_processor": "grid_splitter",
        "template": "{filename}_{index}",
        "max_workers": 0,  # 0 = auto
        "theme": "dark",
        "language": "zh-CN",
        "confirm_on_exit": True,
        "auto_preview": True,
        "log_level": "WARNING",
    }
    
    def __init__(self, config_dir: Optional[str] = None): ...
    def get(self, key: str, default=None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def save(self) -> None: ...  # 持久化到 ~/.image_splitter/settings.json
    def load(self) -> None: ...
    def reset(self) -> None: ...
```

**集成点**: 
- `gui.py` 初始化时加载设置
- `cli.py` 读取默认值
- GUI 提供设置面板

**测试**: `test_settings.py` — 测试 get/set/save/load/reset/默认值

---

#### 3.8 用户插件系统 (`plugins/`)

**设计**:
```python
# plugins/ 目录结构
plugins/
├── __init__.py          # 插件加载器
└── example_plugin.py    # 示例插件

# example_plugin.py
from image_splitter.engine.base import BaseProcessor

class InvertColorProcessor(BaseProcessor):
    @property
    def name(self): return "invert_color"
    @property
    def display_name(self): return "反色 (Invert)"
    # ... 完整实现
```

**加载逻辑**: `register_all_processors()` 扫描 `plugins/` 目录，
  用户编写的处理器自动注册，与内置处理器完全平等。

**集成点**: `core.py` 的 `register_all_processors()` 增加对 `plugins/` 的扫描。

**测试**: `test_integration.py` — 测试外部插件加载

---

### Phase 4: GUI 重构整合 (预计修改 1 个文件)

#### 4.1 gui.py 整体重构

**目标布局** (对齐 Blender 窗口系统):
```
┌──────────────────────────────────────────────────────────────┐
│ 菜单栏: 文件 | 编辑 | 操作符 | 脚本 | 帮助                    │
├──────────┬───────────────────────────────────┬───────────────┤
│          │                                   │               │
│ 左面板   │       主预览工作区                 │  右面板        │
│ (处理器  │       (Canvas)                    │ (控制台)       │
│  选择 &  │                                   │               │
│  参数)   │                                   │               │
│          ├───────────────────────────────────┤               │
│          │       素材列表栏                   │               │
├──────────┴───────────────────────────────────┴───────────────┤
│ 状态栏 (进度条 | 状态文本 | 录制指示器)                        │
└──────────────────────────────────────────────────────────────┘
```

**修改点**:
1. 快捷键从硬编码改为 `KeymapRegistry` 驱动
2. 右侧添加可折叠的 `ConsolePanel`
3. 菜单栏添加: 文件(打开/保存配置), 编辑(撤销/重做/偏好),
   操作符(处理器列表), 脚本(运行脚本/录制宏)
4. 状态栏添加录制指示器 (红点)
5. `on_close` 时自动保存设置和 keymap

---

### Phase 5: 测试体系完善 (预计新增 7 个测试文件)

> ✅ **已完成** — 测试从 69 扩展到 136 项，新增 5 个测试文件

#### 5.1 test_bug_fixes.py — BUG 修复验证
```python
class TestBugFixes(unittest.TestCase):
    def test_bug01_subprocess_import(self): ...
    def test_bug02_resizer_config_model_rejects_zero(self): ...
    def test_bug03_geometry_rejects_invalid_angle(self): ...
    def test_bug04_processors_init_exports_all(self): ...
    def test_bug07_metadata_palette_mode(self): ...
    def test_bug06_cli_set_type_conversion(self): ...
```

#### 5.2 test_keymap.py — 快捷键系统
```python
class TestKeymap(unittest.TestCase):
    def test_bind_and_lookup(self): ...
    def test_unbind(self): ...
    def test_export_import_json(self): ...
    def test_reset_to_default(self): ...
    def test_conflict_detection(self): ...
    def test_empty_keymap(self): ...
    def test_invalid_key_sequence(self): ...
```

#### 5.3 test_history.py — 操作历史
```python
class TestHistory(unittest.TestCase):
    def test_push_and_undo(self): ...
    def test_redo_after_undo(self): ...
    def test_max_depth_eviction(self): ...
    def test_clear(self): ...
    def test_export_log(self): ...
    def test_empty_history_undo_returns_none(self): ...
```

#### 5.4 test_script_engine.py — 脚本引擎
```python
class TestScriptEngine(unittest.TestCase):
    def test_execute_simple_operator(self): ...
    def test_execute_chain(self): ...
    def test_sandbox_blocks_import(self): ...
    def test_sandbox_blocks_file_access(self): ...
    def test_execute_file(self): ...
    def test_syntax_error_reporting(self): ...
    def test_runtime_error_reporting(self): ...
    def test_validate_catches_errors(self): ...
```

#### 5.5 test_macro.py — 宏系统
```python
class TestMacro(unittest.TestCase):
    def test_record_and_generate_script(self): ...
    def test_empty_recording(self): ...
    def test_playback(self): ...
    def test_is_recording_state(self): ...
```

#### 5.6 test_settings.py — 设置系统
```python
class TestSettings(unittest.TestCase):
    def test_get_default(self): ...
    def test_set_and_get(self): ...
    def test_save_and_load(self): ...
    def test_reset(self): ...
    def test_unknown_key_returns_default(self): ...
```

#### 5.7 test_integration.py — 端到端集成
```python
class TestIntegration(unittest.TestCase):
    def test_full_gui_workflow_with_console(self): ...
    def test_cli_with_script_flag(self): ...
    def test_plugin_auto_discovery(self): ...
    def test_keymap_customization_affects_gui(self): ...
    def test_macro_record_and_replay(self): ...
    def test_settings_persist_across_sessions(self): ...
```

---

### 4.4 执行顺序与依赖关系

```
Phase 1 (Bug 修复)
  ├─ 1.1 gui.py + subprocess        ← 无依赖，可立即执行
  ├─ 1.2 resizer config_model       ← 无依赖
  ├─ 1.3 geometry 角度校验           ← 无依赖
  ├─ 1.4 processors/__init__.py     ← 无依赖
  ├─ 1.5 metadata palette           ← 无依赖
  ├─ 1.6 CLI --set 预转换            ← 无依赖
  └─ 1.7 ui/__init__.py             ← 无依赖
  [验证点: 全部 69 项旧测试通过 + 新增 BUG 修复测试通过]

Phase 2 (架构硬化)
  ├─ 2.1 pyproject.toml             ← 无依赖
  ├─ 2.2 Registry 实例化            ← 依赖 Phase 1 完成
  └─ 2.3 日志配置                   ← 无依赖
  [验证点: 全部测试通过 + pip install -e . 成功]

Phase 3 (Blender 核心系统)
  ├─ 3.1 keymap.py                  ← 无依赖
  ├─ 3.2 history.py                 ← 无依赖
  ├─ 3.3 script_engine.py           ← 依赖 3.1 (keymap 可被脚本调用)
  ├─ 3.4 macro.py                   ← 依赖 3.3 (宏生成脚本代码)
  ├─ 3.5 ui/console.py              ← 依赖 3.3 (需要 ScriptEngine 实例)
  ├─ 3.6 ui/keymap_editor.py        ← 依赖 3.1 (需要 KeymapRegistry)
  ├─ 3.7 settings.py + preferences  ← 无依赖
  └─ 3.8 plugins/                   ← 依赖 Phase 1.7 (ui/ 已初始化)
  [验证点: 每个子系统独立测试通过]

Phase 4 (GUI 重构)
  └─ 4.1 gui.py 整合                 ← 依赖 Phase 3 全部完成
  [验证点: GUI smoke tests + workflow tests 通过]

Phase 5 (测试完善)
  └─ 5.1-5.7 全部测试文件            ← 依赖 Phase 4 完成
  [验证点: 全量测试套件 >120 项通过]
```

### 4.5 预计工作量与风险

| Phase | 预计文件变更 | 预计新增代码行 | 风险 |
|-------|-------------|---------------|------|
| Phase 1 | 7 修改 | ~50 行 | 低 (纯修复) |
| Phase 2 | 3 修改 + 1 新增 | ~100 行 | 低 (兼容性重构) |
| Phase 3 | 8 新增 | ~800 行 | 中 (新系统设计) |
| Phase 4 | 1 重构 | ~300 行修改 | 中 (GUI 复杂度) |
| Phase 5 | 7 新增 | ~500 行 | 低 (测试编写) |
| **合计** | **~26 文件** | **~1750 行** | |

### 4.6 关键技术决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| 设置持久化格式 | JSON | 轻量、人类可读、Python 标准库支持 |
| 脚本沙箱实现 | `exec()` + 受限命名空间 | 无需额外依赖，足够安全 |
| 快捷键存储 | JSON (可导入/导出) | 与 Blender 的 keymap.py 思路一致 |
| GUI 框架 | 保持 tkinter | 轻量、零额外依赖、跨平台 |
| 历史栈深度 | 50 (可配置) | 平衡内存与实用性 |
| 插件发现 | pkgutil 扫描 | 已有机制，扩展到 plugins/ 目录 |

---

## 五、总结

本项目在架构层面已经具备良好的基础：Operator Pattern、元数据驱动 UI、自动发现机制、
Fail-Fast 校验等核心设计均已落地。136 项测试全通过说明核心逻辑健壮。

主要差距在于**可编程性**和**用户自定义能力**：缺少脚本系统、快捷键自定义、
宏录制、控制台等 Blender 式交互能力。

已完成的 Phase 1/2/5 将项目稳定基线从 69 提升到 136 项测试，修正了 12 个 BUG，全面对齐 Google Python Style。

当前增量已验证 337 行修改 + 5 个新测试文件
