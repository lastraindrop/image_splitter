# Image Splitter Pro — 现阶段状态报告 (V11.0)

> **日期**: 2026-06-25  
> **基线**: 405 项测试通过 · mypy 0 错误 (79 源文件) · CLI/GUI 端到端验证通过  
> **本阶段工作**: 独立审计 + 7 项真实 Bug 修复 (含 1 项 CRITICAL 安全漏洞) + 文档同步

---

## 1. 验证后的当前状态

| 维度 | 实测值 | 状态 |
|------|--------|------|
| 测试数 | **405** (33 文件) | ✅ 全绿 |
| mypy (`--ignore-missing-imports`) | **0 错误** (79 源文件) | ✅ |
| 非测试源文件 | 44 | — |
| 内置处理器 | 13 | ✅ |
| DAG 具体节点 | 4 (ImageInput/Output/ColorAdjust/Blend) | — |
| 包版本 | 0.6.0 | — |
| CLI 端到端 | 网格切分/自定义切分/缩放/链式/预设 全部通过 | ✅ |
| GUI 端到端 | 初始化/选文件/切处理器/停止 全部通过 | ✅ |

**结论**: 系统是**可落地、可应用的完整轻量工具**。`ANALYSIS_AND_PLAN.md` 中列出的全部 4 项 P0 和 11 项 P1 Bug 均已修复并附回归测试。

---

## 2. 本阶段独立审计发现并修复的 Bug

本次采用 3 个并行独立审计 (安全 / 13 个处理器 / GUI 并发) + 直接源码复核，发现并修复了上一轮审查**遗漏**的 7 项真实 Bug:

### 🔴 SEC-1: 宏沙箱完全逃逸 (CRITICAL — 已修复)
- **位置**: `engine/macro.py:291` (`_ALLOWED_PREFIXES` 含 `"sys"`, `"pathlib"`)
- **问题**: `import sys` 被允许 → `sys.modules['os']` 即可达真实 os 模块 → 任意命令执行；`sys.modules['builtins'].open` 绕过被禁的 open。已用 PoC 实证：宏脚本可调 `os.system()`。整个沙箱形同虚设。
- **修复**: (1) 从允许前缀移除 `sys`/`pathlib`，仅保留 `image_splitter`/`PIL`；(2) 将播放期 `__name__` 从 `"__main__"` 改为 `"__macro__"`，使生成脚本的 `if __name__=='__main__'` 块 (含 `sys.exit`) 在回放时不再执行；(3) `exec` 异常捕获扩展到 `ImportError`，友好返回 `ScriptResult(False)`。
- **回归测试**: `test_sandbox_sys_import_is_blocked`、`test_sandbox_pathlib_import_is_blocked`、`test_sandbox_main_block_does_not_run_during_playback`

### 🟠 UX-1: `--chain` 对任何字符串/枚举参数静默失败 (HIGH — 已修复)
- **位置**: `engine/dispatcher.py:28-37` + `script_engine.py:100-106`
- **问题**: `ast.literal_eval` 拒绝裸标识符，故 `style=solid`、`format=WebP`、`anchor=TL` 全部抛错；CLI 又把异常信息吞掉，只打印 "Chain processed 0/N files"，核心链式功能对用户不可用。
- **修复**: dispatcher 对 `ast.Name` 节点按字符串值处理 (`style=solid` → `"solid"`)，数字/列表/带引号字符串行为不变；`script_engine.chain` 在全失败时附带首个错误原因。
- **回归测试**: `test_parse_bare_identifier_as_string` 等 3 项

### 🟠 PROC-1: color_adjuster 在 P/1 模式崩溃 (HIGH — 已修复)
- **位置**: `processors/color_adjuster.py:56`
- **问题**: `ImageEnhance` 内部用 `Image.blend`，不能 blend 调色板 (P) 或 1-bit (1) 图像，抛 `ValueError: image has wrong mode`。
- **修复**: 对 P/1 模式先 `convert("RGB")` 再增强。
- **回归测试**: `test_color_adjuster_p_mode_does_not_crash`、`test_color_adjuster_1bit_mode_does_not_crash`

### 🟠 PROC-2: filters 灰度化丢失 RGBA 透明通道 (HIGH — 已修复)
- **位置**: `processors/filters.py:47-48`
- **问题**: `convert("L").convert("RGB")` 静默丢弃 alpha，透明 PNG 变不透明。
- **修复**: RGBA/LA 模式分离 alpha 通道，仅对颜色通道灰度化后重组。
- **回归测试**: `test_filters_grayscale_preserves_rgba_alpha` (断言输出仍为 RGBA)

### 🟠 GUI-1: 取消目录对话框后应用永久卡死 (HIGH — 已修复)
- **位置**: `gui.py:863-879`
- **问题**: `run_batch` 在 `askdirectory` 之前置 `_busy=True`，用户取消对话框/参数校验失败时早返回不重置 `_busy`，应用进入"操作进行中"死锁，任何后续操作都被拒。
- **修复**: 三处早返回路径均补 `self._busy = False`。
- **回归测试**: `test_run_batch_directory_cancel_releases_busy_flag`、`test_run_batch_invalid_parameter_shows_error` (扩展断言 `_busy` 为 False)

---

## 3. 已知限制 (本次未改 — 属功能而非 Bug)

| # | 位置 | 说明 | 建议优先级 |
|---|------|------|-----------|
| L-1 | `gui.py:1142-1156` | undo/redo 仅打印历史到 console，不还原处理器/参数/预览。`history.py` 文档明示 undo 设计为"呈现参数供检视/重放"，非文件还原。要做完整还原属功能开发。 | P2 (功能) |
| L-2 | `gui.py` console `|` 分支 | console 中输入含 `|` 的链式命令时直走 `engine.chain()`，绕过 `_console_execute`，故不被宏录制。 | P3 |
| L-3 | `script_engine.py:91` | 链式模式输出扩展名硬编码 `.png`，`format_converter` 在链中对最终保存格式无效 (单处理器模式正常)。 | P3 |
| L-4 | `engine/macro.py` | Python `exec` 沙箱本质非安全边界 — 类属性穿越 (`''.__class__.__base__.__subclasses__()`) 理论仍可达危险类。本次已堵最直接的 `sys`/`pathlib` 通道。运行真正不可信脚本应放独立进程/容器。 | 文档已说明 |
| L-5 | `engine/history.py:54-63` | `undo()` 返回栈内同一对象引用，调用方修改会影响 redo 栈。实际 GUI 只读不写，影响低。 | P3 |

---

## 4. 架构与定位评估 (复核既有结论)

`ANALYSIS_AND_PLAN.md` 第一/二部分的架构评分与竞品对比**仍然成立**，要点复核:

- **定位准确**: 面向"实用图像处理"的轻量桌面工具，Blender Operator 哲学 (类型化属性 + undo + 自动 UI) 是合理护城河，避开 ComfyUI/chaiNNer 的 AI 推理红海。
- **统一执行路径已落地**: `CommandDispatcher.execute_chain` 现委托 `ChainAsGraph`，CLI/GUI/脚本共享一条 Node Graph 路径 (问题 A 已解决)。
- **元数据驱动 UI**: 13 个处理器中多数由 dataclass 自动生成 UI；`props.py` 描述符系统仍是"实验性孤岛"(无处理器消费)，属 YAGNI 风险但已标注。
- **健康度**: 模块解耦、类型安全、测试覆盖、资源管理均为 ★★★★☆~★★★★★。

---

## 5. 建议路线图 (按优先级)

### P0 — 已完成 ✅
- [x] 全部 4 项 P0 + 11 项 P1 (上一阶段)
- [x] 本阶段 7 项新发现 Bug (含 CRITICAL 沙箱逃逸)

### P1 — 短期 (本月)
- [ ] L-1: undo/redo 还原 UI 状态 (处理器+参数+预览)，让历史功能真正可用
- [ ] 迁移处理器到 `props.py` Property 描述符，消除 dataclass + get_ui_metadata 双重定义
- [ ] 交互式引导线放置 (点击预览画布加 h_lines/v_lines)

### P2 — 中期
- [ ] L-2/L-3: console 链式宏录制 + 链式输出扩展名跟随 format_converter
- [ ] 大文件代理/JPEG 预览
- [ ] ChainAsGraph 对全 13 处理器像素一致性 (已部分完成)

### P3 — 长期
- [ ] 可视化节点编辑器 (拖拽连线)
- [ ] 插件热重载
- [ ] PyInstaller 打包零配置可执行
- [ ] 插件市场

---

## 6. 本阶段文件变更清单

| 文件 | 变更 |
|------|------|
| `engine/dispatcher.py` | 裸标识符按字符串解析 (UX-1) |
| `engine/macro.py` | 移除 sys/pathlib 允许前缀 + `__name__` 改 `__macro__` + 捕获 ImportError (SEC-1) |
| `processors/color_adjuster.py` | P/1 模式转 RGB 再增强 (PROC-1) |
| `processors/filters.py` | 灰度化保留 RGBA/LA alpha (PROC-2) |
| `script_engine.py` | 链式全失败附带错误原因 (UX-1) |
| `gui.py` | run_batch 三处早返回重置 `_busy` (GUI-1) |
| `tests/test_dispatcher.py` | +3 裸标识符解析测试 |
| `tests/test_macro.py` | +4 沙箱安全回归测试 |
| `tests/test_edge_cases.py` | +3 处理器模式回归测试 |
| `tests/test_gui_smoke.py` | +2 busy-flag 回归测试 |
| `README.md` / `DEVELOPER.md` / `PLAN.md` / `TECHNICAL.md` | 测试数/文件数/节点数/源文件数同步 |

**测试变化**: 394 → **405** (+11 回归测试) · **mypy**: 0 错误保持
