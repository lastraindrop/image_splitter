# Image Splitter Pro — V15 综合审计报告

> 范围：总体架构工程分析 · 方向定位与竞品对比 · 完整 Code Review（含逐项 Bug 排查）· 落地化改造实施（V15）· 路线图
>
> 基线：commit `7086368`（V13/V14），约 6,900 行源码 + 6,300 行测试，44 个源文件。
> 结论先行：**架构成熟度高于其体量应有的水平，核心风险在"过度设计与实际消费者的落差"以及若干真实交互/语义缺陷**。本轮（V15）已修复全部 P0/P1 级发现，套件 481 测试，mypy 0 错误。

---

## 1. 执行摘要

| 维度 | 评级 | 一句话结论 |
|------|------|-----------|
| 架构分层 | ★★★★☆ | 五层清晰（engine / processors / core / ui / 入口），无循环依赖，ViewModel 解耦可迁移 |
| 一致性 | ★★★★☆ | 统一执行路径（Node Graph）基本达成；CLI/GUI/脚本三条入口收敛于同一管线 |
| 测试健康 | ★★★★★ | 481 测试 / 40 文件；本轮全量回归 478 通过，3 失败均为本机 Tk 环境/预存问题（已用 git stash 对照验证） |
| 类型安全 | ★★★★★ | mypy 0 错误（44 文件），含 `py.typed` PEP 561 标记 |
| 实用落地度 | ★★★☆☆ | 功能完备但发布链未闭合（占位 URL、无构建产物、GUI 批处理单线程） |
| 主要风险 | — | `props.py`（488 行）与 `EvaluationCache` 零消费者；宏沙箱文档已降级为"防误用"（正确的做法） |

**本轮修复（V15，均已含回归测试）**：
1. 链式语义：中间多输出算子（splitter）扇出——`grid_splitter|resizer` 现产出全部 4 格（原仅 1 格，静默丢弃）
2. 性能：单次算子调用的防御性整图拷贝从 3 次降为 1 次（实测验证）
3. GUI 启动即构建参数面板并遵循 `default_processor` 设置（原启动面板为空，需手动重选算子）
4. `settings.json`/`keymap.json` 非字典 JSON 崩溃 → 回退默认值
5. `smart_crop` 亮背景（白底扫描件/截图）识别——边框采样估计背景亮度
6. `import_preset` OSError 防护

---

## 2. 架构工程分析

### 2.1 分层与依赖方向

```
入口层   cli.py / gui.py            （组装 + 参数解析 + 进程/线程模型）
状态层   ui/_state.py GuiState      （框架无关 ViewModel，单向数据流）
引擎层   engine/*                   （registry / dispatcher / coercion /
                                     history / macro / presets / nodes /
                                     evaluator / data_blocks / adapter）
核心层   core.py                    （管线编排：发现→校验→执行→命名→保存）
算子层   processors/* + plugins/*   （纯函数式 BaseProcessor 子类）
```

依赖方向严格单向向下；`engine` 不依赖 `core`（`legacy_adapter` 与 `core`
之间的两个 late import 均为打破环而设，且有注释说明）。这是本项目最大的
结构性优点：**算子层对引擎零感知**，插件作者只需实现 `process()`。

### 2.2 设计模式盘点（与 Blender 哲学的对齐度）

| Blender 概念 | 本项目对应 | 对齐度评估 |
|--------------|-----------|-----------|
| Operator（一切操作皆算子） | `BaseProcessor` + `CommandDispatcher` DSL `op(k=v)` | 高。DSL 语法简洁（bare identifier 人体工学），AST 解析安全 |
| bpy.props 类型化属性 | `engine/props.py` 7 个描述符工厂 | **低——零消费者**。纯"预留"，488 行 YAGNI 负担 |
| ID Data Block | `ImageDataBlock`（命名/版本/引用计数） | 中。被执行路径真实使用，但 `users` 引用计数几乎无人调用，`release/close` 语义靠约定 |
| Node Graph / Compositor | `NodeGraph` + `ProcessorNodeAdapter` + `ChainAsGraph` | 中高。拓扑排序、脏传播、环检测齐备；但 GUI 尚无节点编辑器，图形仅是"内部执行表示" |
| Info Editor / Python Console | `ui/console.py` | 高。历史/补全/着色齐备 |
| Macro / 脚本化 | `MacroRecorder` + 沙箱回放 | 高。V14 已堵 `sys`/`pathlib` 逃逸并诚实降级文档措辞 |
| Keymap | `keymap.py` + typing-context 守卫 | 高 |

### 2.3 值得肯定的工程决策

- **统一执行路径**：`process_image()` 与链式执行最终都经
  `_execute_via_graph()`/`ChainAsGraph` 走 Node Graph——三条入口不会分叉。
- **所有权契约明确**：V14 的 UUID 临时块 + V15 的
  `forget(close_image=False)` 借用语义，使"谁关闭图像"从隐式约定变为显式 API。
- **元数据驱动 UI**：dataclass `field(metadata=...)` → `get_ui_metadata()`
  → GUI 面板自动生成，新增算子真正做到 drop-in（example_plugin 验证了这条路）。
- **防御性纵深**：路径穿越拦截（`Path(name).name`）、JPEG 透明度展平、
  ICC 三级回退（context → cell.info → 原图）、P 模式调色板保护。

### 2.4 架构风险与债务（按优先级）

| # | 风险 | 影响 | 建议 |
|---|------|------|------|
| A1 | `props.py` 488 行零消费者；`EvaluationCache` 同样未接线 | 维护面扩大、误导贡献者 | 三选一：(a) 接入 processor 基类；(b) 移入 `engine/experimental/`；(c) 删除并在 PLAN 记录设计要点 |
| A2 | GUI 批处理单线程（CLI 却有 ProcessPoolExecutor） | 大批量 GUI 场景体验差 | 复用 CLI 并行路径；需先定义 abort 语义（cancel pending futures） |
| A3 | 双轨元数据：`adjuster`/`geometry` 手写 `get_ui_metadata()` 覆盖，类型与 config model 漂移 | 两处真相 | 收敛到 dataclass metadata（`width` 需要新的 "num-or-ratio" UI 类型） |
| A4 | `ProcessorRegistry` 重名策略为 warn-and-replace | 插件可静默顶替内置算子 | 拒绝或显式 opt-in（`allow_override=True`） |
| A5 | `ScriptEngine.process` 用目录前后快照差集推断产出文件 | 高并发/同名覆盖时推断失真 | 让 `process_image` 返回产出路径列表（签名变更，一次性付清） |
| A6 | 注册表 reset/scan 非原子（`register_all_processors` 先清后扫） | 理论上与工作线程竞态 | 扫描到临时 dict 再整体交换 |

---

## 3. 方向定位与竞品分析

### 3.1 定位陈述（现状）

> **面向高级个人用户的轻量本地批量图像处理框架**：Python 生态、
> 插件化算子 + 可组合管线 + 可回放脚本，"Blender 的可编程性 ×
> XnConvert 的开箱即用"。非目标：专业修图（Photoshop/GIMP）、
> 服务端高吞吐（libvips/imgproxy）。

### 3.2 竞品对照

| 项目 | 形态 | 优势 | 本项目可借鉴 | 本项目差异化 |
|------|------|------|--------------|--------------|
| **ImageMagick** | CLI 库事实标准 | 格式覆盖、成熟度、`convert a.png -resize 50% ...` 表达力 | 其"过滤器栈"语法即我们的 chain DSL；错误信息风格 | Python 原生可编程（插件即 .py）、GUI 与预览、无需系统级安装 |
| **XnConvert / IrfanView batch** | GUI 批处理 | 用户量大、格式广 | 其批处理步骤列表 UX（我们的 Pipeline Editor 更接近节点思想） | 键位/控制台/宏的"可编程工作台"气质；元数据驱动 UI |
| **ComfyUI** | 节点图工作台 | 生态爆发力（插件市场）、DAG 可视化 | 节点拖拽连线 UI、社区分发机制（我们的 roadmap 已列） | 体积小三个数量级、零 Web 栈依赖、CLI 优先 |
| **Blender Compositor** | 内置节点合成 | 数据块/版本/脏传播的参考实现 | 我们已吸收其核心抽象；剩下的是可视化编辑器 | 独立工具而非套件内模块 |
| **squoosh / squoosh-cli** | 单一压缩场景 | 极致场景化 | —— | 我们覆盖更广（split/watermark/border…），格式转换是子集 |
| **photoshop Actions/Droplets** | 商业闭源 | 宏 UX 标杆 | 动作面板录制/回放/导出交互 | 我们的宏生成可读 Python 脚本（更强） |

### 3.3 参考与学习点（可立即吸收）

1. **ImageMagick 的 `-write`/括号分支** → 链 DSL 未来可支持
   `op()(...)` 嵌套分组与中间落盘；当前 fan-out 语义（V15）是它的简化版。
2. **ComfyUI 的插件分发** → `pip install image-splitter-<plugin>` +
   入口点发现（`importlib.metadata.entry_points`），替代当前目录扫描，
   解决 A4 的同时获得生态位。
3. **XnConvert 的"输出选项"面板** → 输出模板/格式/质量应成为管线尾部的
   一等算子（`format_converter` 已是，但 GUI 未把它纳入 Pipeline 默认尾步）。
4. **GIMP 的 procedure database (PDB)** → 每个 processor 自动注册
   "自描述清单"（名称/参数/类型/范围），控制台 `?` 可查——我们已有
   `get_ui_metadata()`，只差一个内省命令。

### 3.4 路线图（修订版）

**短期（P1，1-2 轮）**
- [ ] 发布链闭合：替换 pyproject 占位 URL → tag `0.8.0` → sdist/wheel 构建 + `pip install` 冒烟（含 `[gui]` extra）
- [ ] GUI 批处理并行化（复用 CLI ProcessPoolExecutor；abort = cancel pending + 不中断运行中 future）
- [ ] `props.py`/`EvaluationCache` 去留决策（建议：移 experimental 或删除）
- [ ] Registry 重名策略硬化 + 插件入口点发现（`entry_points`）
- [ ] 真机 GUI 全手动冒烟（load → preview → batch → preset → macro → console → pipeline）
- [ ] 输出命名冲突策略：多文件同 stem + 每文件重置 `{index}` 会互相覆盖 → 加 `-1` 后缀或全局序号选项

**中期（P2，3-6 轮）**
- [ ] 可视化节点编辑器（拖拽连线；`ChainAsGraph` 已是求值内核，只缺视图层——GuiState 的设计正是为此预留）
- [ ] 大文件代理预览 + 交互式参考线放置（canvas 已有 guide 拖拽基础）
- [ ] 拖放文件进 GUI、插件热重载
- [ ] 每输出 context（row/col）贯穿链式命名（现为 `{stem}_chain_{idx}`）
- [ ] watchdog/队列目录模式（"监控文件夹→自动应用管线"，逼近落地生产力场景）

**长期（P3+）**
- [ ] 插件市场（GitHub topic + entry_points 约定即可起步，无需中心服务）
- [ ] WASM/浏览器离线版（Pillow 的 WASM 移植是硬前提，先评估）
- [ ] 分布式（RPC 多机）——仅在出现真实吞吐需求后启动

---

## 4. 完整 Code Review 结果

> 方法：全量人工阅读 44 个源文件（非抽样）；所有可疑点以运行时实验证实/证伪；
> 对照 481 项测试确认行为锚点。分级：P0 崩溃/数据丢失 · P1 功能错误 ·
> P2 健壮性 · P3 卫生/文档。

### 4.1 本轮发现并已修复（含回归测试 `test_v15_fixes.py`，16 项）

| ID | 级别 | 位置 | 问题 | 修复 |
|----|------|------|------|------|
| V15-1 | **P0(语义)** | `legacy_adapter.py` | 链中间多输出算子仅传递 `results[0]`，`grid_splitter(2x2)|resizer` 静默丢弃 3/4 输出；旧测试明知此事并标注"known limitation"，docstring 还残留"dispatcher 处理 fan-out"的过时描述 | 重写 `execute_chain` 为逐算子 flat-map 工作清单，后续算子作用于每个输出；更新过时测试为断言新语义 |
| V15-2 | P1(UI) | `gui.py __init__` | 启动仅 `state.set_processor()`，参数面板 0 控件（已实测复现），用户必须手动重选算子；且不遵循 `default_processor` 设置 | 启动即调用 `_on_processor_changed()`，并按设置选择启动算子 |
| V15-3 | P1(健壮) | `settings.py`/`keymap.py` | `settings.json` 为合法 JSON 但非字典（如 `[1,2]`）→ `dict \| list` TypeError 启动即崩；keymap 同类问题在 `.get("global")` 处 AttributeError | isinstance 校验 + 回退默认 + 警告日志 |
| V15-4 | P1(性能) | `core.py`/`legacy_adapter.py` | 每次算子调用 3 次整图防御拷贝（块拷贝 + ImageInputNode 拷贝 + ImageOutputNode 拷贝），内存峰值 ~3×、耗时上升 | 借用语义：块持有调用者图像不拷贝，`forget(close_image=False)`；去掉无消费者的 ImageOutputNode 往返。实测 3→1 次 |
| V15-5 | P1(功能) | `smart_crop.py` | 亮度路径假定暗背景（`p > threshold` 即内容），白底扫描件/截图（最常见场景）smart_crop 为 no-op | 边框条带采样估计背景亮度，`abs(p - bg) > threshold` 判内容；暗背景行为不变（测试锁定） |
| V15-6 | P2 | `presets.py` | `import_preset` 内 `save_preset` 的 OSError 未处理，违反其"失败返回 None"契约 | 捕获并返回 None |
| — | P3 | `test_chain_as_graph_all.py` | 过时测试文档化错误行为 | 重写为断言 fan-out 正确语义 |

### 4.2 已核实为"非 Bug"的可疑点（证伪记录）

| 可疑点 | 结论 |
|--------|------|
| `_execute_via_graph` 输出块关闭是否会殃及 `pairs` | 否——out 块持有的是 `img.copy()`，与 adapter 原始输出无别名（V15 重构后此路径已移除） |
| `process_image` 中 `opened_cells.pop()` 资源泄漏 | 否——V13 已修（P1-9），逐 cell close 正确 |
| 调整器裁剪时负坐标 paste 越界 | 否——PIL paste 支持负坐标自动裁剪 |
| `adjuster` bg_color 4 元组 + RGB 模式冲突 | 否——`mode` 判定含 `len(bg_color) > 3` 分支 |
| 链中借用图像被误关 | 否（且 V15 显式化）：`ImageInputNode` 内部拷贝隔离了别名 |
| 宏沙箱 `getattr` 逃逸链 | 设计上已声明为"防误用非安全边界"（V14 文档降级）——定位诚实，可接受 |

### 4.3 遗留问题清单（未在本轮修改，建议排期）

| ID | 级别 | 位置 | 问题 |
|----|------|------|------|
| L-1 | P2 | `core.py` | 同 stem 多文件 + 每文件 `{index}` 重置 → 输出互相覆盖（CLI 批处理常见）；建议冲突自动加序或警告 |
| L-2 | P2 | `gui.py _console_execute` | 无文件时静默 return，控制台却打印 "[OK] Dispatched"（误导） |
| L-3 | P2 | `nodes.py BlendNode` | `opacity` 未验证 [0,1]；convert/resize 中间图未关闭（每求值泄漏 2 图，GC 兜底） |
| L-4 | P2 | `data_blocks.py` | `use()/unuse()` 非线程安全（README "fine-grained locking" 仅指注册表）；引用计数实际无调用者 |
| L-5 | P2 | `cli.py` | `--chain`/`-s` 模式忽略 `--preset`/`--set` 参数（无文档说明） |
| L-6 | P2 | `evaluator.py` | `EvaluationCache.invalidate/clear` 不关闭被逐出的图像（与 `put` 的逐出路径不一致）；且整体未接线（见 A1） |
| L-7 | P3 | `cli.py _discover_input_files` | 大小写混合扩展名（`.Jpg`）在 Linux 上漏检（glob 大小写敏感） |
| L-8 | P3 | `filters.py` LA 灰度分支 | split 后原样 merge——语义上 LA 本就是灰度，无害但代码有误导性 |
| L-9 | P3 | `gui.py _render_canvas` | 每次缩放 resize 产生新图未显式 close；`after` 回调在窗口销毁后可能抛 TclError |
| L-10 | P3 | `models.py AdjustConfig` | `width<=1` 视为比例、`>1` 视为像素的双关启发式已有文档，但 UI 提示不足（roadmap 已列显式单位参数） |
| L-11 | P3 | `history.export_log` | OSError 未包裹（与 presets 风格不一致） |
| L-12 | P3 | pyproject | `example.com` 占位 URL（roadmap 已列）；authors 占位 |

### 4.4 测试套件健康度

- 全量：**481 收集 / 478 通过 / 3 失败**；3 项失败（`test_gui_param_sync` 1 项 +
  `TestV14KeymapTypingGuard` 2 项）经 `git stash` 对照确认**在基线同样失败**，
  根因为 withdrawn 窗口的合成按键事件不可靠（conftest 注释自述需
  `map_offscreen=True`）与宿主 Tcl 环境缺损，非代码缺陷。
- 建议：这两个文件的用例补 `map_offscreen=True` 或改走焦点无关断言（例如
  直接测 `_is_typing_context()` 的 winfo_class 分支 + 用 `event_generate`
  之外的注入方式触发 handler）。
- 亮点：`test_chain_as_graph_all`（13 算子像素级等价）、`test_bug_fixes`
  （30 项回归锚点）、`test_operator_compliance`（参数契约审计）是同类项目
  中少见的"架构测试"。

---

## 5. V15 落地化改造实施记录

### 5.1 变更清单

| 文件 | 变更 |
|------|------|
| `engine/data_blocks.py` | `forget(name, *, close_image=True)` —— 所有权转移 API |
| `core.py` | `_execute_via_graph` 重构：借用输入、去掉 out 节点（3 拷贝→1） |
| `engine/legacy_adapter.py` | `ChainAsGraph` 重写为 flat-map 工作清单 + `_apply_op` 图步进；异常路径关闭中间图（V14-4 卫生对齐） |
| `gui.py` | 启动构建参数面板 + `default_processor` 生效 |
| `settings.py` / `keymap.py` | 非字典 JSON 回退默认 |
| `processors/smart_crop.py` | 边框采样背景估计（亮/暗背景通用） |
| `engine/presets.py` | `import_preset` OSError 防护 |
| `tests/test_v15_fixes.py` | 新增 16 项回归测试 |
| `tests/test_chain_as_graph_all.py` | 过时语义测试重写 |
| `README.md` / `PLAN.md` | chain fan-out 语义、smart_crop 说明、测试计数（481/40）、V15 历史与路线图同步 |

### 5.2 验证矩阵

| 验证项 | 结果 |
|--------|------|
| `pytest tests/` 全量 | 478 passed / 3 pre-existing env failures（stash 对照确认） |
| `mypy image_splitter --ignore-missing-imports` | 0 errors（44 files） |
| mid-chain fan-out e2e | `grid_splitter(2x2)|resizer(0.5)|format_converter(WebP)` → 4 个 .webp（原 1 个） |
| GUI 启动面板 | `winfo_children()` 从 0 → 有参数控件；`default_processor` 生效 |
| 拷贝计数 | `process_image(resizer)`：Image.copy 调用 3 → **1** |
| 借用语义 | 链执行后 caller 图像可 save（未关闭）；boom 算子无块泄漏 |
| smart_crop | 白底深色内容 → 正确裁剪 (50,50)；均匀图不裁；暗背景行为不变 |
| CLI 冒烟 | `-r 2 -c 2 -j 2` 并行成功，退出码语义正确 |

### 5.3 "轻量完整可落地"差距评估

当前距"普通用户可安装使用"还差（按阻塞程度）：
1. **发布链**（阻塞）：占位 URL、无 tag/构建产物。半天工作量。
2. **GUI 批处理并行**（体验）：CLI 已有，GUI 缺失。1 轮。
3. **打包分发**（可选但推荐）：PyInstaller onefile（GUI 用户免 Python 环境）；
   体积主要来自 Pillow（~10MB），可接受。
4. **L-1 输出覆盖**（数据安全）：建议随并行化一并处理。

完成 1+4 后即可对外发布 0.8.0；2、3 后是 1.0 的合理门槛。

---

## 6. 总评

这个代码库在 7k 行体量上做出了通常 3-5 倍体量项目才有的工程纪律：
统一执行路径、显式资源所有权、元数据驱动 UI、回归锚点测试、
诚实的文档定位（宏沙箱措辞、已知限制标注）。它的真正挑战不是
"写得对不对"，而是**"为未来预留的部分（props/cache/节点 UI）何时兑现
或何时放弃"**——这是所有 Blender 式 ambitions 工具的共同宿命。
V15 已把最伤用户的语义缺陷（fan-out 丢输出）、最伤资源的缺陷（3× 拷贝）
和最伤第一印象的缺陷（启动空面板）清零；下一步把发布链闭合，
它就是一个可以真正交到用户手里的工具。

---

## 7. V16 增量 —— "轻量完整可落地"收尾（本轮）

依据 §5.3 的差距评估，本轮完成了全部四项落地阻塞项与六项遗留修复。

### 7.1 交付清单

| 项 | 内容 | 验证方式 |
|----|------|---------|
| **共享并行运行器** | `core.run_parallel_batch()`：CLI 与 GUI 共用同一并发/中止/进度实现。`jobs<=1` 进程内顺序执行（测试确定性）；中止 = 取消未开始 futures，在途文件完成（单文件原子） | 4 项单元测试（顺序全成、预置中止、空输入、失败计数） |
| **GUI 批处理并行** | `work_thread` 改走共享运行器，并发度取 `max_workers` 设置；进度经 `root.after` 封送 | 冻结 exe 10 秒存活冒烟 + 测试锁定线程签名 |
| **`{batch}` 占位符（L-1）** | `process_image(..., batch_index)` → 模板变量 `{batch}`；CLI 发现同 stem 输入时预检告警并指引用 `{batch}` | 单元测试 + 安装版 CLI e2e（两个同 stem 文件 → `photo_01_*`/`photo_02_*` 零覆盖） |
| **Registry 重名策略（A4）** | 默认抛 `ValueError`；`allow_override=True` 显式替换（告警）。内置扫描严格、插件扫描 opt-in（文档化"可遮蔽内置"扩展点） | 更新 `test_bug_fixes` 锚点 + 2 项新策略测试 |
| **发布链闭合** | LICENSE 文件；pyproject 移除占位 URL/email（留下注释模板待填真实仓库）；版本 0.8.0 | `python -m build` 成功；**干净 venv** 安装 wheel：`image-splitter --preset-list` ✓、`image-splitter-gui --version` ✓（含 `[gui]` extra）、安装版 e2e 并行处理 ✓ |
| **PyInstaller 单文件** | `packaging/image_splitter.spec`（collect-all customtkinter、显式列出全部算子模块供 pkgutil 发现、`console=False`） | 构建成功；exe `--version` exit 0；完整 GUI 启动 10 秒存活 ✓ |
| **L 修复批** | L-7 发现大小写不敏感（`.Jpg`）；L-2 控制台拒绝分发不再误报 "[OK] Dispatched"；L-3 BlendNode opacity 钳制 [0,1] + 派生图关闭；L-6 缓存 invalidate/clear 关闭图像（与逐出路径一致）；L-9 画布 after 回调防 TclError | `test_v16_fixes.py` 17 项回归 |
| **props 决策落地** | 模块头 deprecated 标注："冻结实验 API，勿扩展勿依赖"；PLAN 记录决策 | 文档 |

### 7.2 验证矩阵（本轮）

| 检查 | 结果 |
|------|------|
| `pytest tests/` 全量 | **494 passed, 1 skipped, 3 failed** —— 3 项失败与本轮改动前基线完全一致（Tk 环境预存问题，stash 对照确认过） |
| `mypy image_splitter --ignore-missing-imports` | 0 errors（44 files） |
| `ruff check image_splitter/ --ignore=E501`（CI 同款） | All checks passed |
| `python -m build` | sdist + wheel 构建成功（0.8.0） |
| 干净 venv 安装冒烟 | 控制台脚本 + GUI 入口 + 安装版并行 e2e 全通过 |
| PyInstaller onefile | 构建 + 启动存活通过 |
| 测试规模 | **498 tests / 41 files**（较 V15 +17） |

### 7.3 发布操作手册（剩余手工步骤）

代码侧阻塞已全部清除。对外发布 0.8.0 仅剩纯手工动作：

1. 在 pyproject.toml 注释模板处填入真实仓库 URL，删除注释。
2. `git tag v0.8.0 && git push --tags`（或先发 PyPI：`python -m build && twine upload dist/*`）。
3. （可选）GitHub Release 附上 `dist/ImageSplitterPro.exe`；跨平台 exe 需在对应 OS 的 CI runner 中各跑一次 `pyinstaller packaging/image_splitter.spec`。
4. 真机手动 GUI 全流程冒烟一轮（load → preview → batch → preset → macro → console）——自动化已覆盖绝大部分，此步为发布纪律。

### 7.4 更新后的结论

V15 清零了"伤用户"的缺陷；V16 补齐了"到用户"的路径：单一并行实现、
输出覆盖防护、注册表策略硬化、可构建可安装可分发的完整链路
（wheel + 单文件 exe 双通道均经真实构建验证）。项目现在满足
"轻量、完整、可落地"的全部定义——剩下的只是按下发布按钮。
