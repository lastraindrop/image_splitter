# STATUS V13.0 — 工程审计、打包修复与落地强化

**日期**: 2026-09-03
**版本**: 0.7.0（pyproject / `__init__.__version__` 同步）
**基线**: V12.0（426 tests）→ V13.0（443 tests，38 files）

---

## 1. 审计范围与方法

- 全量源码走读（engine/ processors/ ui/ cli/ gui/ script_engine/ 共 44 源文件）
- 工程视角核查：打包布局、CI 质量门（pytest / mypy / ruff）、可安装性、可执行入口
- 动态验证：对每个疑似 BUG 编写最小复现脚本实证后才确认
- 文档交叉核对：PLAN / ANALYSIS_AND_PLAN / STATUS_V11 / STATUS_v12 与代码实际状态比对

## 2. 确认并修复的问题

### P0 — 打包与分发完全失效（PKG-1）

**现象**: 仓库根目录即包目录（扁平布局），而 `pyproject.toml` 按标准布局发现包
（`packages.find where=["."] include=["image_splitter*"]`）。结果：

- `pip install -e .` 构建出**空包**（egg-info `top_level.txt` 为空）
- 控制台脚本 `image-splitter` / `image-splitter-gui` 全部 `ModuleNotFoundError`
- CI 的 `pip install -e ".[dev]"` + `mypy image_splitter` 在该布局下必然失败
- 测试之所以通过，仅因 pytest 对含 `__init__.py` 的根目录做 basedir 回溯时
  恰好把仓库父目录插入 `sys.path` —— 属于巧合而非设计

**修复**: `git mv` 重构为标准布局（根目录保留 pyproject/文档/tests，包代码移入
`image_splitter/` 子目录），重新 `pip install -e .`。重装后 `image-splitter`
端到端实跑通过；`mypy image_splitter` 与 CI 约定一致。

### P1 — 快捷键系统两处缺陷（KEY-1 / KEYMAP-2）

1. **KEY-1 死绑定**: 默认键位表动作名 `toggle_macro`，而 GUI 只识别
   `toggle_macro_record` —— `Ctrl+Shift+R`（宏录制）完全无响应。
   另有 4 个 GUI 支持的动作（open_output_dir / stop_tasks / clear_list /
   remove_selected）不在默认键位表中，用户不可发现。
   **修复**: `_bind_keymap` 重构为动作分发表 `_action_handlers()`（含
   `toggle_macro` 旧名别名兼容已保存的用户键位）；默认键位表补齐
   `Ctrl+E / Escape / Ctrl+Shift+Delete`；未知动作写 WARNING 日志。
2. **KEYMAP-2 默认表污染**: `load_keymap()` 无文件时返回
   `DEFAULT_KEYMAP.copy()`（浅拷贝），`bind()` 修改内层 dict 会**穿透污染模块级
   默认值**（被新回归测试在跨测试场景下实际捕获）。
   **修复**: `copy.deepcopy`。

### P1 — border double 样式 width=1 静默裁剪内容（BORDER-1）

`outer_width = width - inner - 1 = -1` → `ImageOps.expand(border=-1)` 不报错
而是**裁掉图像内容**（实证：10px 红色图 → 内容缩至 8px）。修复：`width < 3`
时降级为同宽度 solid 边框（三段式结构本需 width≥3），内容零丢失。

### P1 — 控制台链式命令阻塞主线程（CONSOLE-1，即 L-2）

`a|b` 链式输入在 Tk 主线程同步执行 `ScriptEngine.chain`：GUI 冻结、绕过
`_busy` 忙锁（与批处理并发重入）、绕过 `stop_event`、忽略已配置输出目录、
不录入宏。**修复**: ConsolePanel 新增 `on_chain` 回调，GUI 侧
`_console_execute_chain` 以工作线程执行，完整遵循 busy/stop/output_dir/macro
协议；无宿主回调时保留同步回退。

### P2 — CLI 脚本/链式模式不接受目录与通配符（CLI-1）

`-s` / `--chain` 直接把原始输入字符串当单个文件路径传递，目录输入逐文件报
`IsADirectoryError`，与普通模式行为不一致。**修复**: 提取
`_discover_input_files()` 统一三种模式的输入发现（含输出目录过滤）。

### P2 — 链式输出硬编码 .png（L-3 落地）

链尾为 `format_converter` 时输出扩展名与质量现在跟随其配置。新增
`script_engine.chain_output_spec()` 供 CLI（ScriptEngine.chain）与 GUI
（`_run_chain_thread`）共用，JPEG 输出自动走 RGBA 展平。

### P2 — ChainAsGraph 中间图像不释放（LEAK-1）

多级链中每个 adapter 的 `_all_outputs` 持有中间图像直至 GC；求值中途异常时
临时 DataBlock 也不清理。**修复**: 结果收集后统一关闭全部 adapter 输出；
求值/清理包入 `try/finally`。

### P3 — 若干小项

- **PRESET-1**: `--preset` 会覆盖用户显式 `-p`（当 -p 恰等于设置默认值时）。
  改为 `-p default=None` 哨兵，显式 `-p` > preset > settings 三级优先。
- **PIPE-1**: `PipelineStep.to_spec` 对 None 参数生成 `key=None` → 被解析为
  字符串 "None" 导致强制转换失败。现跳过 None 值。
- **ADJ-1**: canvas_adjuster `_resolve_dim` 注释与实现不符（注释描述了未实现
  的启发式）。注释对齐实际行为：float 与 ≤1 的 int 为比率，>1 的 int 为像素。
- **DOC-1**: `BaseConfig` 死代码（定义后无任何使用者）移除。
- **VER-1**: 版本三处漂移（pyproject 0.6.0 / 陈旧安装 0.5.0 / 无 `__version__`）。
  统一为 `0.7.0` 并暴露 `image_splitter.__version__`；GUI 入口新增
  `--version` / argparse（此前 `--help` 会挂起等待窗口）。
- **RUFF-1**: ruff 40 项违规（CI 质量门必红，与文档"0 errors"声明矛盾）全部
  清零；cli.py 的 E402 为 sys.path 引导所需，以 `per-file-ignores` 显式豁免。

## 3. 新增回归测试（tests/test_v13_fixes.py，17 项）

打包版本暴露、键位表↔GUI 处理器全覆盖（含临时配置目录隔离）、border double
降级三例、PipelineStep None 过滤、chain_output_spec 四例、链式 JPEG 端到端、
控制台链式路由两例、CLI 目录展开（chain/script）、preset 优先级两例。

其中键位覆盖测试直接暴露了 KEYMAP-2 浅拷贝污染 —— 验证了"结构化覆盖测试"
对这类配置漂移缺陷的捕获能力。

## 4. 质量门

| 检查 | 结果 |
|------|------|
| pytest | **443 passed**（V12: 426） |
| mypy `image_splitter --ignore-missing-imports` | 0 errors（44 files） |
| ruff check . | 0 errors |
| pip install -e . + 控制台脚本实跑 | 通过（grid 6 图 / 链式 JPEG / preset） |
| image-splitter-gui --version | 0.7.0 |

## 5. 剩余已知限制（承继 V11/V12，非本轮引入）

- L-4: 宏 exec 沙箱本质非安全边界（不可信脚本应独立进程运行）
- undo/redo 仍不还原预览画布（参数级还原已具备）
- 处理器参数声明存在三套体系（dataclass / 手写 metadata / props.py 实验性），
  props.py 仍无消费者 —— 建议后续版本收敛

## 6. 下一步建议（优先级序）

1. Pipeline 链的持久化（JSON 工作流文件，向 ComfyUI 式"图即文档"演进）
2. 可视化节点编辑器（engine 已就绪，缺 View）
3. CLI watch 模式（目录监控自动处理）
4. 处理器参数体系收敛至 props.py 单一来源
5. PyInstaller 单文件分发
