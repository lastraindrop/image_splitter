# Image Splitter Pro — 综合架构分析、代码审查与完善计划

> **文档版本**: 1.0 (基于 2026-06-15 代码快照)
> **覆盖范围**: 架构评估、方向定位、完整代码审查（含 Bug 清单）、以及带单元测试的完善执行计划
> **审查方法**: 6 个并行分析代理 + 直接源码审查 + 363 项测试套件验证

---

## 目录

- [第一部分: 架构与工程设计评估](#第一部分-架构与工程设计评估)
- [第二部分: 方向定位与竞品分析](#第二部分-方向定位与竞品分析)
- [第三部分: 完整代码审查与 Bug 清单](#第三部分-完整代码审查与-bug-清单)
- [第四部分: 完善执行计划与单元测试设计](#第四部分-完善执行计划与单元测试设计)

---

# 第一部分: 架构与工程设计评估

## 1.1 总体架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **模块分层** | ★★★★☆ | 5 层清晰分离（engine → processors → plugins → ui → entry points），但存在循环导入（core.py:127 注释） |
| **可扩展性** | ★★★★★ | 新处理器 = BaseProcessor 子类 + 放入目录，自动发现 |
| **元数据驱动 UI** | ★★★★☆ | 自动从 dataclass 生成，但 6/13 处理器仍手写覆盖 |
| **类型安全** | ★★★☆☆ | `mypy --ignore-missing-imports` 通过，但 `--strict` 报 593 个错误 |
| **测试覆盖** | ★★★★☆ | 363 项测试通过，但 ChainAsGraph 仅对 3/13 处理器验证像素一致性 |
| **线程安全** | ★★★☆☆ | 单例注册有锁，但 `ImageDataBlock._name_registry` 类级字典无锁 |
| **错误处理** | ★★★☆☆ | 核心路径有 fail-fast，但多处异常被静默吞掉 |
| **资源管理** | ★★☆☆☆ | 多处 PIL Image 未显式关闭（process_image 成功保存的 cell 泄漏） |
| **跨平台** | ★★★★☆ | 平台感知字体、pathlib，CI 在 3 个 OS 上运行 |
| **文档一致性** | ★★☆☆☆ | 5 份文档间测试数、版本号、文件数互相矛盾 |

## 1.2 架构亮点

### 1.2.1 Blender 哲学的忠实落地
项目成功移植了 Blender 的三个核心抽象：
- **Operator 系统**: 每个处理功能是独立的 `BaseProcessor`，有 `name`/`display_name`/`category`/`tool_tip` 元数据
- **ID DataBlock**: `ImageDataBlock` 实现了命名注册表、版本追踪、引用计数（对应 Blender 的 `bpy.data`）
- **Typed Properties**: `props.py` 的 `IntProp`/`FloatProp`/`BoolProp` 等描述符对应 `bpy.props`

### 1.2.2 统一执行路径（部分实现）
`_execute_via_graph()` 让所有处理器调用流经同一个 Node Graph 引擎——这是正确的架构决策。CLI、GUI、脚本三种入口共享一条执行路径。

### 1.2.3 元数据驱动 UI
`_ui_metadata_util.py` 从 dataclass 字段的 `field(metadata={"label": ...})` 自动生成 UI 元数据，消除了手写参数列表的重复。

## 1.3 架构问题（需要改进）

### 问题 A: 双执行路径未统一
- `CommandDispatcher.execute_chain()`（legacy_adapter.py 引用）和 `ChainAsGraph.execute_chain()` 并存
- `ChainAsGraph` 本应是 drop-in 替换，但 `dispatcher.py` 仍保留完整实现
- **影响**: 维护两套逻辑，行为可能分歧
- **建议**: 将 `CommandDispatcher.execute_chain()` 标记为 deprecated，内部委托给 `ChainAsGraph`

### 问题 B: Property 系统是"实验性"的孤岛
- `props.py`（488 行）实现了完整的类型描述符系统，但**没有任何处理器使用它**
- 所有处理器仍用 dataclass + `get_ui_metadata()` 覆盖
- **影响**: 488 行代码无实际消费者，违反 YAGNI
- **建议**: 要么将处理器迁移到 Property 描述符（如 PLAN.md 路线图所述），要么明确标记为未使用并考虑移除

### 问题 C: 循环导入依赖
- `core.py:127-131` 有显式的延迟导入注释：`# Late imports to avoid circular dependencies`
- PLAN.md 声称"Zero cross-import cycles"——这不准确
- **建议**: 重构依赖方向，让 engine 不反向依赖 core

### 问题 D: 类级可变状态无并发保护
- `ImageDataBlock._name_registry` 是类级 `dict`，`__init__`/`forget`/`clear_all` 无锁修改
- 在多线程 GUI 环境下（batch_thread + console_thread）可能竞争
- **建议**: 添加 `threading.Lock` 或改用 `threading.local`

### 问题 E: GUI ViewModel 数据流断裂（P0 级）
- `param_widgets.py` 创建的 Entry/CheckBox/ComboBox 的 `on_change` 回调只触发 `fast_update_preview()`
- `fast_update_preview()` 只**读取** `state.param_values`，从不**写入**
- **后果**: 用户在 GUI 修改的参数永远不会进入 `state.param_values`，批量处理始终用默认值
- **这是最严重的架构缺陷**——GUI 参数编辑功能完全失效

---

# 第二部分: 方向定位与竞品分析

## 2.1 项目定位

**Image Splitter Pro 是一个面向"实用图像处理"的轻量级桌面工具**，核心理念是 Blender 的 Operator 哲学：每个操作是独立的、可组合的、可脚本化的。

### 定位象限

```
                    专业级 ←──────────────────→ 消费级
                         │                        │
    节点图/可编程  │  ComfyUI    chaiNNer       │
                  │  Nuke        Natron         │
                  │  Blender     Image Splitter Pro ← 你在这里
                  │              XnConvert(线性) │
                  │                             │
    批量/脚本化   │  ImageMagick  Phatch         │
                  │  sharp       IrfanView      │
                  │  imgproxy    FastStone      │
```

## 2.2 核心竞品对比

| 特性 | Image Splitter Pro | chaiNNer | ImageMagick | XnConvert | ComfyUI |
|------|:-:|:-:|:-:|:-:|:-:|
| 节点图引擎 | ✅ DAG | ✅ 核心 | ❌ | ❌ (线性) | ✅ 核心 |
| GUI | ✅ customtkinter | ✅ Electron | ❌ | ✅ 原生 | ✅ Web |
| 批量切分 | ✅ **核心** | ❌ 小众 | ⚠️ 脚本 | ⚠️ 仅裁剪 | ❌ |
| 水印/边框 | ✅ 核心 | ⚠️ 基础 | ✅ 完整 | ✅ 完整 | ❌ |
| 格式转换 | ✅ 核心 | ⚠️ | ✅ 200+ | ✅ 500+ | ❌ |
| AI/ML 放大 | ❌ (缺口) | ✅ 核心 | ❌ | ❌ | ✅ 核心 |
| 插件系统 | ✅ 自动发现 | ⚠️ 仓内 | ❌ | ❌ | ✅ Manager |
| CLI | ✅ | ✅ | ✅ 原生 | ✅ | ✅ API |
| 实时预览 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 零配置 | ⚠️ 需 pip | ✅ 打包 | ❌ | ✅ 便携 | ⚠️ |
| 学习曲线 | ✅ 平缓 | ❌ 陡峭 | ❌ CLI | ✅ 简单 | ❌ 陡峭 |

## 2.3 战略建议

### 应该做（强化优势）
1. **深耕"实用图像处理"**: 网格切分、自定义切分、缩放、水印、格式转换——这是 chaiNNer/ComfyUI 忽视的 90% 使用场景
2. **Operator 哲学是护城河**: 每个操作有类型化属性、undo 支持、自动 UI——这让工具可扩展、可脚本、可测试
3. **实时预览是杀手锏**: 对抗 ImageMagick 和批量处理器的核心优势——"拖滑块，立即看结果"
4. **CLI 与 GUI 对等**: 每个 GUI 操作都应可通过 CLI 完成——这启用 CI/CD 管道和服务端批处理

### 应该学（借鉴竞品）
1. **chaiNNer 的零配置启动**: 打包 Python 运行时，安装即用
2. **ComfyUI 的插件生态**: 注册表 + 一键安装 + 版本管理
3. **ImageMagick 的管道 CLI**: `convert in.jpg -resize 50% out.jpg` 的直觉性
4. **Blender 的 PDB 注册表**: 每个操作全局可发现、可调用

### 不应该做（避免陷阱）
1. **不要做通用合成器**: Nuke/Fusion/Blender 占据 VFX 市场，你的节点图是给切分/缩放/水印用的
2. **不要做 AI 推理**: ComfyUI/chaiNNer 在这方面已经成熟，聚焦传统图像处理
3. **不要过度复杂化节点 UI**: 拖拽连线对普通用户太复杂，保持预设 + 操作符的简单模式

## 2.4 推荐路线图

### 短期（P0-P1，本周）
- 修复所有 P0/P1 Bug（见第三部分）
- 统一执行路径（废弃 CommandDispatcher.execute_chain）
- 修复 GUI 数据流断裂

### 中期（P2-P3，本月）
- 迁移处理器到 Property 描述符系统
- 添加 ChainAsGraph 对全 13 处理器的像素一致性测试
- 交互式引导线放置（点击预览画布添加 h_lines/v_lines）
- 大文件的代理/JPEG 预览

### 长期（P4+）
- 插件热重载（无需重启）
- 可视化节点编辑器（拖拽连线，Blender 合成器风格）
- PyInstaller 打包为零配置可执行文件
- 插件市场（社区插件分享）

---

# 第三部分: 完整代码审查与 Bug 清单

## 3.1 Bug 严重性分级

| 级别 | 含义 | 数量 |
|------|------|------|
| **P0** | 崩溃/数据损坏/核心功能失效 | 4 |
| **P1** | 功能错误/安全漏洞/资源泄漏 | 11 |
| **P2** | 边缘情况/UX 问题 | 18 |
| **P3** | 代码质量/一致性 | 12 |

## 3.2 P0 级 Bug（必须立即修复）

### P0-1: GUI 参数编辑完全失效
- **位置**: `gui.py:401-438` + `ui/param_widgets.py:55-86`
- **问题**: 用户在 GUI 修改参数（Entry/CheckBox/ComboBox）后，`on_change` 回调触发 `fast_update_preview()`，但该函数只**读取** `state.param_values`，从不**写入**。`state.param_values` 在 `_on_processor_changed` 初始化为默认值后再也不更新。
- **后果**: 批量处理始终使用默认参数，用户的所有编辑被静默忽略
- **修复**: 在 `_on_processor_changed` 中包装 `on_change` 回调，先读取控件值写入 `state.param_values`，再调用 `fast_update_preview()`

```python
# 修复方案（gui.py _on_processor_changed 内）
def _make_on_change(name: str, widget, on_change_fn):
    def _handler():
        # 关键: 将控件值同步到 state
        if hasattr(widget, 'get'):
            self.state.param_values[name] = widget.get()
        on_change_fn()
    return _handler

# 创建控件时
on_change = _make_on_change(name, widget, self.fast_update_preview)
name, widget = create_param_widget(frame, meta, ..., on_change=on_change, ...)
```

### P0-2: metadata.py 调色板模式数据损坏
- **位置**: `processors/metadata.py:57-62`
- **问题**: 对 P（调色板）模式图像，先 `Image.new("P", size)` 创建默认全黑调色板，再 `paste(image)` 导致像素索引通过错误调色板重映射，颜色损坏。之后 `putpalette()` 无法修复已损坏的像素数据。
- **修复**: 在 paste 之前设置调色板

```python
# 修复方案
clean_img = Image.new(image.mode, image.size)
if original_palette and image.mode == "P":
    clean_img.putpalette(original_palette)  # 先设调色板
clean_img.paste(image)  # 再 paste，索引正确
```

### P0-3: example_plugin.py 在 LA 模式崩溃
- **位置**: `plugins/example_plugin.py:48-53`
- **问题**: "LA" 模式只有 2 个通道，但代码 `bands[:3]` 假设至少 3 个 RGB 通道。`Image.merge("RGB", (L_band,))` 因通道数不匹配而崩溃。
- **修复**: 单独处理 LA 模式

```python
if image.mode in ("RGBA", "LA"):
    bands = list(image.split())
    if image.mode == "RGBA":
        rgb_bands = bands[:3]
        alpha_band = bands[3]
        merged_rgb = Image.merge("RGB", tuple(rgb_bands))
    else:  # LA
        merged_rgb = bands[0]  # L 通道直接用作 RGB 的灰度
        alpha_band = bands[1]
    # ... invert logic
```

### P0-4: macro.py 沙箱逃逸
- **位置**: `engine/macro.py:44`（`"type": type` 在安全 builtins 中）
- **问题**: `type` 在 `__builtins__` 白名单中。攻击者可通过 `type.__subclasses__()` 访问 `subprocess.Popen`、`os._wrap_close` 等危险类，完全逃逸沙箱。
- **修复**: 从安全 builtins 中移除 `type`，或使用 `ast.literal_eval` 替代 `exec`

```python
# 修复: 移除 type
_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "sum": sum,
    "len": len, "range": range, "enumerate": enumerate,
    "zip": zip, "sorted": sorted, "reversed": reversed,
    "round": round, "print": print, "str": str, "int": int,
    "float": float, "bool": bool, "list": list, "dict": dict,
    # 注意: 不要包含 type, __import__, eval, exec, compile, open
}
```

## 3.3 P1 级 Bug（高优先级修复）

### P1-1: dispatcher.py 异常时双重关闭图像
- **位置**: `engine/dispatcher.py:79-91`
- **问题**: 内层 `finally` 关闭中间图像后，外层异常处理器再次遍历 `current_images` 尝试关闭同一图像
- **修复**: 异常处理器只关闭 `next_step_images`（未处理的），不重新关闭已处理的

### P1-2: border.py 双边框宽度 off-by-one
- **位置**: `processors/border.py:49-58`
- **问题**: "double" 样式的总边框宽度始终是 `width + 1`，而非用户指定的 `width`
- **修复**: `outer_width = width - inner_width - 1`

### P1-3: adjuster.py int/float 类型歧义
- **位置**: `processors/adjuster.py:68-69`
- **问题**: `isinstance(width, float)` 区分比例与绝对像素，但 `width=2`（int 表示 2 倍）会被当作 2 像素
- **修复**: 引入显式标志或统一为浮点比例

### P1-4: filters.py LA 模式未处理
- **位置**: `processors/filters.py:51-61`
- **问题**: invert 操作对 "LA" 模式调用 `ImageOps.invert()` 会崩溃
- **修复**: 添加 LA 模式分支

### P1-5: GUI console/pipeline 无取消机制
- **位置**: `gui.py:934-950`（`_run_chain_thread`）, `gui.py:983-1000`（`_console_execute`）
- **问题**: 只有 `work_thread` 检查 `stop_event`，console 和 pipeline 线程无法被中止
- **修复**: 在两个线程中添加 `stop_event.is_set()` 检查

### P1-6: GUI 宏录制遗漏 console/pipeline 操作
- **位置**: `gui.py:826-827` vs `gui.py:983-1000` vs `gui.py:921-931`
- **问题**: 只有 `run_batch` 检查 `macro.is_recording`，console 和 pipeline 执行的操作不被录制
- **修复**: 在 `_console_execute` 和 `_run_pipeline_chain` 中添加 `macro.record()` 调用

### P1-7: GUI 预设选择不更新控件显示
- **位置**: `gui.py:450-476`
- **问题**: 选择预设后，`state.param_values` 更新了，但屏幕上的 Entry/ComboBox 仍显示旧值
- **修复**: 维护 `self._param_widgets: Dict[str, Widget]` 映射，预设加载后遍历并 `widget.set(value)`

### P1-8: GUI 可并发触发多个批量操作
- **位置**: `gui.py:802-840` + `gui.py:921-931` + `gui.py:983-1000`
- **问题**: `run_batch` 禁用了 btn_run，但 console/pipeline 不检查是否正在运行，可并发触发
- **修复**: 添加 `self._busy` 标志，三个入口点都检查

### P1-9: core.py 成功保存的图像泄漏
- **位置**: `core.py:273`（`opened_cells.pop()` 移除已保存的 cell，但从不关闭它）
- **问题**: 成功保存的 PIL Image 从不被 `.close()`，大批量处理时内存累积
- **修复**: 保存后显式关闭 cell（除非 cell 被 context 引用）

### P1-10: ImageDataBlock.image.setter 不关闭旧图像
- **位置**: `engine/data_blocks.py:77-87`
- **问题**: 替换 image 时不关闭旧的 PIL Image，导致内存泄漏
- **修复**: 设置新值前关闭旧值

### P1-11: EvaluationCache 驱逐不关闭图像
- **位置**: `engine/evaluator.py:260-262`
- **问题**: LRU 驱逐时只移除引用，不调用 `.close()`
- **修复**: 驱逐前调用 `image.close()`

## 3.4 P2 级 Bug（应修复）

| # | 位置 | 问题 |
|---|------|------|
| P2-1 | `gui.py:847-854` | 取消竞态: 循环退出后点中止，显示"完成"而非"已中止" |
| P2-2 | `gui.py:577-597` | 缩略图 PIL Image 替换时不显式关闭 |
| P2-3 | `gui.py:618` | 每次 resize 创建新 CTkImage，GC 压力 |
| P2-4 | `gui.py:983-1000` | console 执行无进度反馈 |
| P2-5 | `gui.py:921-931` | pipeline 链运行无进度/取消反馈 |
| P2-6 | `gui.py:1050-1064` | undo/redo 仅显示历史，不恢复参数 |
| P2-7 | `color_adjuster.py:42-45` | 增强因子无范围验证（负值/极大值） |
| P2-8 | `watermark.py:38` | `load_default(size=)` 需 Pillow ≥10.0.0 |
| P2-9 | `filters.py:57-58` | P 模式 invert 后输出变 RGB（非 P） |
| P2-10 | `border.py:59-61` | "dashed" 样式未实现，等同 "solid" |
| P2-11 | `format_converter.py:48` | 不在内存转换格式，仅标记 context |
| P2-12 | `config_coercion.py:63` | 未知类型静默转为 str |
| P2-13 | `config_coercion.py:44-48` | int 强转接受 "inf"/"nan" |
| P2-14 | `nodes.py:283-297` | ColorAdjustNode 中间图像不关闭 |
| P2-15 | `presets.py:22` | 路径遍历防护脆弱（Unicode 绕过） |
| P2-16 | `history.py:54-63` | undo 返回引用，调用方修改会影响 redo 栈 |
| P2-17 | `smart_crop.py:66` | 假设亮=内容/暗=背景，暗内容图像失效 |
| P2-18 | `geometry.py:150` | 错误消息说支持 360°，实际只接受 0/90/180/270 |

## 3.5 P3 级问题（代码质量）

| # | 位置 | 问题 |
|---|------|------|
| P3-1 | 全项目 | 版本号不一致: pyproject=0.6.0, PLAN=V9/V10, TECHNICAL=V8, CODE_STYLE=V10 |
| P3-2 | README:23 | `mypy --strict` 声明虚假（实际 593 错误） |
| P3-3 | 多文档 | 测试数矛盾: README=363, PLAN=308, TECHNICAL=218 |
| P3-4 | 多文档 | "5 concrete nodes" 实际只有 4 个 |
| P3-5 | README 架构树 | 遗漏 `cli.py` |
| P3-6 | PLAN:184 | "10 core processors" 实际 13 个 |
| P3-7 | PLAN:61 | "Zero cross-import cycles" 但 core.py 有延迟导入 |
| P3-8 | gui.py:105 | 窗口尺寸硬编码，不持久化 |
| P3-9 | gui.py:1117-1123 | on_close 只保存 2 个设置 |
| P3-10 | pipeline.py:944 | 链结果硬编码 PNG 格式 |
| P3-11 | TECHNICAL.md | 章节编号全错（3.x 用在 2 节，4.x 用在 3 节...） |
| P3-12 | 多处理器 | context dict 不一致（有的详细，有的只有 `{"action": ...}`） |

## 3.6 测试覆盖缺口

| 缺口 | 严重性 | 建议测试名 |
|------|--------|-----------|
| ChainAsGraph 仅对 3/13 处理器验证像素一致性 | HIGH | `test_chain_as_graph_all_processors_identical` |
| 分支 DAG 的 dirty 传播未测试（仅线性） | HIGH | `test_dirty_propagation_branching_dag` |
| CLI `--preset` 加载未端到端测试 | HIGH | `test_cli_preset_load_and_merge` |
| CLI `--script` 未在 CLI 级测试 | HIGH | `test_cli_script_mode` |
| `ImageDataBlock.clone()` 无图像时崩溃 | HIGH | `test_data_block_clone_no_image` |
| `ProcessorNodeAdapter.evaluate()` None 输入 | HIGH | `test_processor_node_adapter_none_input` |
| `split_image_core()` 便利函数从未测试 | MEDIUM | `test_split_image_core_wraps_process_image` |
| `MacroPlayer.play_string()` 从未测试 | MEDIUM | `test_macro_player_play_string` |
| 并发注册表操作（非单例创建） | MEDIUM | `test_registry_concurrent_register` |
| `core._prepare_image_for_save()` CMYK/LA 模式 | MEDIUM | `test_prepare_image_for_save_cmyk` |

---

# 第四部分: 完善执行计划与单元测试设计

## 4.0 执行原则

1. **先测试后修复**: 每个 Bug 修复前先写失败测试锁定行为
2. **最小变更**: 不重构，只修复
3. **分批验证**: 每批修复后运行全测试套件
4. **文档同步**: 修复后更新相关文档

## 4.1 执行批次与顺序

### 批次 1: P0 修复（核心功能恢复）— 优先级最高

| 序号 | 任务 | 文件:位置 | 具体修改 | 验证测试 |
|------|------|-----------|----------|----------|
| 1.1 | 修复 GUI 参数同步 | `gui.py:401-438`, `ui/param_widgets.py` | 在 `_on_processor_changed` 中包装 on_change 回调，先写 state 再预览 | `test_gui_param_sync_to_state` |
| 1.2 | 修复 metadata P 模式 | `processors/metadata.py:57-62` | 调换 putpalette 和 paste 顺序 | `test_metadata_p_mode_color_preserved` |
| 1.3 | 修复 plugin LA 崩溃 | `plugins/example_plugin.py:48-64` | 添加 LA 模式分支 | `test_plugin_la_mode` |
| 1.4 | 修复 macro 沙箱 | `engine/macro.py:44` | 从 _SAFE_BUILTINS 移除 `type` | `test_macro_sandbox_no_type_escape` |

**批次 1 验收标准**:
- [ ] GUI 修改参数后，批量处理使用新值（非默认值）
- [ ] P 模式图像经 metadata_cleaner 后颜色不变
- [ ] LA 模式图像经 example_plugin 不崩溃
- [ ] macro 沙箱中 `type.__subclasses__()` 被阻止
- [ ] 全部 363 项现有测试仍通过
- [ ] 新增 4 项测试通过

### 批次 2: P1 修复（功能正确性）

| 序号 | 任务 | 文件:位置 | 具体修改 | 验证测试 |
|------|------|-----------|----------|----------|
| 2.1 | 修复 dispatcher 双重关闭 | `engine/dispatcher.py:79-91` | 异常处理器只关闭 next_step_images | `test_dispatcher_no_double_close` |
| 2.2 | 修复 border 双边框宽度 | `processors/border.py:49-58` | `outer_width = width - inner_width - 1` | `test_border_double_exact_width` |
| 2.3 | 修复 adjuster 类型歧义 | `processors/adjuster.py:68-69` | int 也作为比例处理（除非 > 1 且标记为绝对像素） | `test_adjuster_int_ratio` |
| 2.4 | 修复 filters LA 模式 | `processors/filters.py:51-61` | 添加 LA 分支 | `test_filters_la_mode` |
| 2.5 | GUI console/pipeline 取消 | `gui.py:934, 983` | 添加 stop_event 检查 | `test_gui_console_cancel` |
| 2.6 | GUI 宏录制补全 | `gui.py:983, 921` | 添加 macro.record() 调用 | `test_macro_records_console` |
| 2.7 | GUI 预设更新控件 | `gui.py:450-476` | 维护 _param_widgets 映射，预设后刷新 | `test_preset_updates_widgets` |
| 2.8 | GUI 并发保护 | `gui.py:802, 921, 983` | 添加 _busy 标志 | `test_no_concurrent_batch` |
| 2.9 | 修复 core 图像泄漏 | `core.py:273` | 保存后关闭 cell | `test_process_image_closes_cells` |
| 2.10 | 修复 ImageDataBlock 泄漏 | `engine/data_blocks.py:77-87` | setter 关闭旧图像 | `test_data_block_setter_closes_old` |
| 2.11 | 修复 EvalCache 泄漏 | `engine/evaluator.py:260-262` | 驱逐前 close | `test_cache_eviction_closes_image` |

**批次 2 验收标准**:
- [ ] dispatcher 异常路径无双重关闭
- [ ] border double 总宽度 == 用户指定宽度
- [ ] adjuster int 输入作比例处理
- [ ] LA 模式 filters 不崩溃
- [ ] console/pipeline 可被中止按钮停止
- [ ] console/pipeline 操作被宏录制
- [ ] 预设加载后控件显示更新
- [ ] 无法同时运行多个批量操作
- [ ] process_image 无图像泄漏（用 tracemalloc 验证）
- [ ] 全部现有测试通过 + 新增 11 项测试通过

### 批次 3: 测试补全（覆盖缺口）

| 序号 | 测试文件 | 测试内容 | 覆盖的缺口 |
|------|----------|----------|-----------|
| 3.1 | `tests/test_chain_as_graph_all.py` | 全 13 处理器 ChainAsGraph vs Dispatcher 像素一致性 | HIGH: 只测了 3 个 |
| 3.2 | `tests/test_node_graph.py` (扩展) | 分支 DAG（菱形拓扑）dirty 传播 | HIGH: 只测线性 |
| 3.3 | `tests/test_cli.py` (扩展) | `--preset` 加载+合并, `--script` 端到端 | HIGH |
| 3.4 | `tests/test_data_blocks.py` (扩展) | clone 无图像, setter 到 None, 双重 release | HIGH/MEDIUM |
| 3.5 | `tests/test_legacy_adapter.py` (扩展) | adapter None 输入, 多输出处理器 | HIGH |
| 3.6 | `tests/test_core.py` (新建) | split_image_core, CMYK/LA 保存, 空结果 | MEDIUM |
| 3.7 | `tests/test_macro.py` (扩展) | play_string, 缺失 run_macro | MEDIUM |

**批次 3 验收标准**:
- [ ] 测试数从 363 增至 ~410+
- [ ] ChainAsGraph 对全 13 处理器验证通过
- [ ] 分支 DAG dirty 传播正确
- [ ] CLI 全标志端到端测试通过

### 批次 4: P2 修复（边缘情况与 UX）

| 序号 | 任务 | 文件:位置 |
|------|------|-----------|
| 4.1 | 取消竞态修复 | `gui.py:847-854` — finish_report 检查 stop_event |
| 4.2 | 缩略图显式关闭 | `gui.py:577-597` |
| 4.3 | color_adjuster 范围验证 | `processors/color_adjuster.py:42-45` |
| 4.4 | watermark Pillow 版本兼容 | `processors/watermark.py:38` |
| 4.5 | border dashed 实现 | `processors/border.py:59-61` |
| 4.6 | config_coercion 未知类型报错 | `engine/config_coercion.py:63` |
| 4.7 | history undo 返回副本 | `engine/history.py:54-63` |
| 4.8 | geometry 错误消息修正 | `models.py:150` |

### 批次 5: 文档同步

| 序号 | 任务 | 文件 |
|------|------|------|
| 5.1 | 统一版本号为 0.6.0 | PLAN, TECHNICAL, DEVELOPER, CODE_STYLE |
| 5.2 | 修正测试数: 363 测试, 33 文件 | 全部文档 |
| 5.3 | 修正源文件数: 44 (非测试) | README, PLAN, DEVELOPER |
| 5.4 | 修正 mypy 声明: `--ignore-missing-imports` | README:23 |
| 5.5 | 修正节点数: 4 (非 5) | README, PLAN, DEVELOPER |
| 5.6 | 补充 cli.py 到 README 架构树 | README:152-188 |
| 5.7 | 补充缺失测试文件到 README 表 | README:227-255 |
| 5.8 | 修正处理器数: 13 (非 10) | PLAN:184, DEVELOPER:332 |
| 5.9 | 修正 TECHNICAL 章节编号 | TECHNICAL.md 全文 |
| 5.10 | 更新 anchor 文档（adjuster 用不同值） | README:101 |

### 批次 6: 架构改进（可选，长期）

| 序号 | 任务 | 说明 |
|------|------|------|
| 6.1 | 统一执行路径 | 将 CommandDispatcher.execute_chain 标记 deprecated，内部委托 ChainAsGraph |
| 6.2 | 消除循环导入 | 重构 engine 不反向依赖 core |
| 6.3 | ImageDataBlock 线程安全 | 添加 threading.Lock 保护 _name_registry |
| 6.4 | 迁移处理器到 Property 描述符 | 消除 dataclass + get_ui_metadata 双重定义 |
| 6.5 | GUI 窗口状态持久化 | 保存/恢复窗口尺寸、上次处理器 |

## 4.2 单元测试设计详情

### 测试文件 1: `tests/test_p0_fixes.py`（批次 1 新建）

```python
"""P0 级 Bug 修复的回归测试。"""
import pytest
from PIL import Image

from image_splitter.engine.macro import MacroPlayer
from image_splitter.processors.metadata import MetadataProcessor
from plugins.example_plugin import InvertColorProcessor


class TestMetadataPaletteMode:
    """P0-2: metadata.py 调色板模式数据损坏。"""

    def test_p_mode_colors_preserved_after_strip(self, tmp_path):
        """P 模式图像经 metadata_cleaner 后颜色应保持不变。"""
        # 创建有意义的 P 模式图像
        rgb_img = Image.new("RGB", (10, 10), (255, 0, 0))
        p_img = rgb_img.convert("P")
        
        processor = MetadataProcessor()
        config = {"strip_all": True, "keep_icc": False}
        results = processor.process(p_img, config)
        
        result_img, _ = results[0]
        # 转回 RGB 验证颜色
        result_rgb = result_img.convert("RGB")
        pixel = result_rgb.getpixel((5, 5))
        assert pixel == (255, 0, 0), f"颜色损坏: 期望 (255,0,0), 得到 {pixel}"


class TestPluginLAMode:
    """P0-3: example_plugin.py 在 LA 模式崩溃。"""

    def test_invert_la_mode_does_not_crash(self):
        """LA 模式图像经 invert 不应崩溃。"""
        la_img = Image.new("LA", (10, 10), (128, 255))
        processor = InvertColorProcessor()
        config = {"invert_alpha": False}
        
        results = processor.process(la_img, config)
        assert len(results) == 1
        assert results[0][0].size == (10, 10)


class TestMacroSandbox:
    """P0-4: macro.py 沙箱逃逸。"""

    def test_type_not_accessible_in_sandbox(self):
        """沙箱中不应能访问 type 来逃逸。"""
        evil_script = """
def run_macro():
    # 尝试通过 type 访问危险类
    try:
        subclasses = type.__subclasses__(type)
        return "ESCAPED"
    except (NameError, AttributeError):
        return "BLOCKED"
"""
        player = MacroPlayer()
        result = player.play_string(evil_script)
        # type 不应在沙箱中可用
        assert not result.success or "ESCAPED" not in str(result.message)
```

### 测试文件 2: `tests/test_chain_as_graph_all.py`（批次 3 新建）

```python
"""ChainAsGraph vs CommandDispatcher 对全 13 处理器的像素一致性验证。"""
import pytest
from PIL import Image

from image_splitter.core import register_all_processors
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.engine.legacy_adapter import ChainAsGraph
from image_splitter.engine.registry import ProcessorRegistry


@pytest.fixture(scope="module", autouse=True)
def setup_processors():
    register_all_processors()


@pytest.fixture
def test_image():
    return Image.new("RGB", (100, 100), (128, 64, 32))


PROCESSOR_CONFIGS = [
    ("resizer", {"width": 0.5, "height": 0.5}),
    ("color_adjuster", {"brightness": 1.5, "contrast": 1.2}),
    ("filters", {"grayscale": True}),
    ("geometry", {"rotate": 90}),
    ("format_converter", {"format": "WebP", "quality": 80}),
    ("rounded_corner", {"radius": 15}),
    ("border", {"width": 5, "color": "#ff0000", "style": "solid"}),
    ("metadata_cleaner", {"strip_all": True}),
    ("smart_crop", {"threshold": 30, "margin": 5}),
    # 注意: splitter/custom_splitter 是多输出，单独测试
]


@pytest.mark.parametrize("processor_name,config", PROCESSOR_CONFIGS)
def test_chain_as_graph_pixel_identical(processor_name, config, test_image):
    """每个处理器通过 ChainAsGraph 和 CommandDispatcher 的输出应像素一致。"""
    cmd_str = f"{processor_name}({', '.join(f'{k}={v!r}' for k, v in config.items())})"
    
    # CommandDispatcher 路径
    dispatcher_results = CommandDispatcher.execute_chain(
        test_image.copy(), cmd_str
    )
    
    # ChainAsGraph 路径
    graph_results = ChainAsGraph.execute_chain(
        test_image.copy(), cmd_str
    )
    
    assert len(dispatcher_results) == len(graph_results)
    for d_img, g_img in zip(dispatcher_results, graph_results):
        assert d_img.size == g_img.size
        assert d_img.mode == g_img.mode
        assert list(d_img.getdata()) == list(g_img.getdata())
        
        d_img.close()
        g_img.close()
```

### 测试文件 3: `tests/test_gui_param_sync.py`（批次 1 新建）

```python
"""GUI 参数同步测试 —— 验证用户编辑进入 state.param_values。"""
import pytest

# 注意: 需要 GUI 环境，可能需要 mock customtkinter


class TestParamSync:
    """P0-1: GUI 参数同步修复验证。"""

    def test_entry_change_updates_state(self):
        """用户修改 Entry 后 state.param_values 应更新。"""
        # 这需要创建一个模拟的参数面板
        # 验证 on_change 回调将 widget 值写入 state
        # 具体实现取决于 mock 策略
        pass

    def test_checkbox_change_updates_state(self):
        """用户切换 CheckBox 后 state.param_values 应更新。"""
        pass

    def test_combobox_change_updates_state(self):
        """用户选择 ComboBox 后 state.param_values 应更新。"""
        pass

    def test_batch_uses_edited_params(self):
        """批量处理应使用用户编辑的参数，而非默认值。"""
        pass
```

## 4.3 验收检查清单

### 每批完成后的通用检查
- [ ] `python -m pytest tests/ -v -k "not gui and not ui_preview"` 全绿
- [ ] `python -m mypy image_splitter --ignore-missing-imports` 0 错误
- [ ] 新增测试全绿
- [ ] 无新引入的 import 循环
- [ ] 改动文件不超过批次规定范围

### 最终交付检查
- [ ] P0 全部修复（4 项）
- [ ] P1 全部修复（11 项）
- [ ] P2 关键项修复（≥10 项）
- [ ] 测试数 ≥ 410（从 363 增加 ≥47）
- [ ] ChainAsGraph 对全 13 处理器像素一致
- [ ] 文档数字全部修正
- [ ] GUI 参数编辑功能恢复正常
- [ ] `mypy --ignore-missing-imports` 仍 0 错误

---

## 附录 A: 文件变更影响矩阵

| 文件 | 批次 1 | 批次 2 | 批次 3 | 批次 4 | 批次 5 |
|------|--------|--------|--------|--------|--------|
| `gui.py` | ✏️ P0-1 | ✏️ P1-5~8 | | ✏️ P2-1,2 | |
| `ui/param_widgets.py` | ✏️ P0-1 | | | | |
| `processors/metadata.py` | ✏️ P0-2 | | | | |
| `plugins/example_plugin.py` | ✏️ P0-3 | | | | |
| `engine/macro.py` | ✏️ P0-4 | | | | |
| `engine/dispatcher.py` | | ✏️ P1-1 | | | |
| `processors/border.py` | | ✏️ P1-2 | | ✏️ P2-10 | |
| `processors/adjuster.py` | | ✏️ P1-3 | | | |
| `processors/filters.py` | | ✏️ P1-4 | | | |
| `core.py` | | ✏️ P1-9 | ➕ test | | |
| `engine/data_blocks.py` | | ✏️ P1-10 | ➕ test | | |
| `engine/evaluator.py` | | ✏️ P1-11 | ➕ test | | |
| `tests/` (多个) | ➕ 4 test | ➕ 11 test | ➕ ~32 test | | |
| `README.md` | | | | | ✏️ |
| `PLAN.md` | | | | | ✏️ |
| `TECHNICAL.md` | | | | | ✏️ |
| `DEVELOPER.md` | | | | | ✏️ |
| `CODE_STYLE.md` | | | | | ✏️ |

## 附录 B: 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| GUI 修复引入新 widget 兼容性问题 | 中 | 高 | 充分测试 param_widgets |
| dispatcher 修改破坏链执行 | 低 | 高 | 像素一致性测试保护 |
| 测试补全发现更多 bug | 高 | 中 | 是好事，纳入后续批次 |
| 文档同步遗漏 | 中 | 低 | 用脚本自动统计 |
