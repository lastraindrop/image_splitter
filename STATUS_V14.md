# STATUS V14.0 — 交互路径深度审查与 P1/P2 缺陷清零

**日期**: 2026-09-04
**版本**: 0.7.1（pyproject / `__init__.__version__` 同步）
**基线**: V13.0（443 tests）→ V14.0（465 tests, 39 files）

---

## 1. 审计范围与方法

- 全量源码走读（core / engine / processors / ui / cli / gui / script_engine）
- 架构评审：分层、依赖方向、全局状态、并发模型、扩展成本
- **动态实证**：每个疑似 BUG 均编写最小复现脚本，实证后才确认（沿用 V13 方法论）

## 2. 确认并修复的问题

### P1（功能性缺陷，全部实证）

1. **BORDER-2｜dashed 边框是视觉空操作**
   先 `ImageOps.expand(fill=color)` 画实心边框，再用**同色**虚线叠加 —
   实测 solid vs dashed **0 像素差异**。
   **修复**: 边框区先填 gap 底色（RGBA→透明 / RGB→白），再绘制彩色 dash。
   RGBA 输入保持透明 gap，RGB 输出 gap 为白。

2. **MACRO-2｜宏录制的 pipeline/console 链不可回放**
   GUI 以伪算子 `pipeline_chain` 录制链式操作，生成的脚本调用
   `engine.process(input_files, 'pipeline_chain', ...)`，回放必现
   `Unknown operator`（实证）。
   **修复**: `MacroRecorder._generate_script` 识别伪算子，生成
   `engine.chain(input_files, spec, output_dir)`。回放端到端实证通过。

3. **KEY-2｜全局快捷键穿透输入框**
   键位全部绑定在 toplevel；Tk bindtags 传播使焦点在 Entry 内按
   `<Delete>` 时**同时**触发"删除选中文件"（独立 Tk 实验证实）。
   **修复**: 新增 `_is_typing_context()` 焦点守卫（CTk 输入类 +
   `winfo_class` 双通道，覆盖 CTkComboBox/CTkEntry 内部 tk.Entry），
   输入焦点期间抑制全部全局动作。

4. **LEAK-2｜`_execute_via_graph` 异常路径泄漏临时数据块**
   无 try/finally；processor 抛异常后 `__proc_input__`（含全尺寸图像
   拷贝）残留注册表（实证）。V13 的 LEAK-1 只修了 ChainAsGraph。
   **修复**: 求值与结果收集包入 try/finally，finally 中清理临时块。

5. **CLI-2｜settings 的 default_rows/default_cols 不生效**
   fallback 硬编码 `rows=3, cols=3`；settings 值只进了 argparse help。
   **修复**: 默认值注入移至 coercion 之前，优先级变为
   显式 `-r/-c` > preset/--set > settings 默认值。
   回归测试实证：settings 设 5x4 → 实际输出 20 块。

### P2（一致性/边缘，全部修复）

6. **GUI-2｜启动忽略 settings 模板**（`on_close` 却会写回 → 读写不对称）。
   现启动时从 settings 恢复 `state.output_template`。
7. **CLI-3｜`--preset-list` 强制要求 input 位置参数**。input 改 `nargs="?"`，
   信息型旗标不再被必填校验拦截。
8. **CHAIN-2｜链式路径丢失源 ICC profile**（core 路径保留而 chain 路径
   丢弃，宽色域屏偏色）。`ScriptEngine.chain` 与 GUI `_run_chain_thread`
   均已透传 `icc_profile`。
9. **PRESET-2｜预设名含 Windows 非法字符（如冒号）时裸抛 OSError**。
   `_preset_path` 升级为正则全面净化（`<>:"/\|?*` + 控制符 + 首尾
   点空格），净化后无字母数字回退为 `unnamed`。
10. **PRESET-3｜CLI `--preset-save` 把会话噪声（output_dir/template）
    存入预设**。快照现排除这两个字段。
11. **WM-1｜水印字形原点偏移**。`textbbox((0,0))` 的 ascender 偏移未补偿，
    边缘锚定时文字视觉位置漂移/贴边裁切。绘制点补偿 `(x-bbox[0], y-bbox[1])`。

### 架构加固

- **A1｜临时数据块去共享命名**: `__proc_input_*__` / `__chain_*__` 改为
  per-call UUID 后缀。锁只保护 dict 操作不保护逻辑命名冲突 — 固定名在
  类级注册表中是并发隐患（GUI 线程 × 未来插件后台任务）。顺带移除
  ChainAsGraph 清理中的 `__proc_` 前缀全局扫描（会误删并发执行的块）。
- **LOG-1｜GUI 滚动文件日志**: 新增 `setup_file_logging()`，
  `~/.image_splitter/logs/gui.log`（1MB × 3 备份）。GUI 用户此前完全
  无法感知 stderr 诊断。

## 3. 新增回归测试（tests/test_v14_fixes.py，22 项）

dashed≠solid 像素差异 / gap 采样点（PIL line 端点闭区间）/ RGBA 透明
gap / 端到端保存；宏脚本生成 `engine.chain` / 端到端回放；焦点守卫
（真实事件路径 `event_generate` + 离屏映射 `focus_set`，withdrawn 窗口
与 `focus_force` 在 Windows 测试环境下不可靠 — 已在测试内注释）；
异常零泄漏 / 成功零泄漏 / 命名唯一性；CLI settings 默认值端到端
（5x4=20 块）/ 显式参数覆盖；`--preset-list` 免 input / 缺 input 仍报错；
链式 ICC 保留；预设名净化四例 + 回环；预设快照排除噪声字段；
水印视觉 padding。

## 4. 质量门

| 检查 | 结果 |
|------|------|
| pytest | **464 passed, 1 skipped**（既有 headless skip）|
| mypy `image_splitter --ignore-missing-imports` | 0 errors（44 files）|
| ruff check（CI 同参） | All checks passed |

## 5. 遗留与建议（未列入本轮）

- GUI 批处理为单线程顺序执行；并行化建议复用 CLI ProcessPoolExecutor
  路径（需处理 config pickle 与 abort 语义），建议单独一轮 + 真机冒烟。
- props.py 实验系统零集成（~490 行），建议设定弃用决策点。
- macro "sandbox" 是防误操作护栏而非安全边界（getattr 白名单 +
  `__subclasses__` 逃逸路径存在），文档应如实降级表述。
- pyproject URLs 仍为 example.com 占位，发布前需替换真实仓库地址。
