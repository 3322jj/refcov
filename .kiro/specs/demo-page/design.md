# 设计文档：演示页 `site/`（初稿，2026-11-17，等检查点审阅）

依据：`requirements.md` 第二稿（出处已改成引用）；`docs/演示页方案.md` 第 2–7 节；`docs/前端指南试验结果.md`、`docs/前端扩展试验结果.md`、`docs/GIS试验结果.md`、`docs/故事构思.md`。以上材料和下面引用的指南单元（`[ref:g-…]`）都经 RefCov 的 MCP 工具读过。

状态：本步只写设计。`site/` 没有建；转换脚本、页面、测试和发布工作流都还没写。

## 1. 总览

演示页是一页静态页面：`site/index.html`、`site/style.css`、`site/app.js`，加上 `site/data/` 下的小 JSON。JSON 由 `site/convert_runs.py` 生成。这个脚本只用标准库，读仓库外的四次运行记录，写出 JSON。

页面只有英文（需求 12.3），不用框架，也不用构建工具（需求 12.1）。需求文档和本设计是中文；页面上的英文文字在实现步骤里写，逐句对照需求。

| 路径 | 作用 | 依赖 |
|---|---|---|
| `site/index.html` | 八段内容，一页，语义化结构 | 无外部资源 |
| `site/style.css` | 版面、深浅色、格子样式、减少动态效果 | 无 |
| `site/app.js` | 读 `data/*.json`，回放第 1、3、4 段；键盘操作 | 无 |
| `site/data/w-h-03.json`、`wb-h-03.json`、`g-01.json`、`vb-01.json` | 转换脚本的输出（第 3 节） | 无 |
| `site/convert_runs.py` | 四次运行记录 → 上面四个 JSON | 标准库 |
| `tests/test_site_*.py` | 转换脚本、页面结构、数字、对比度（第 6 节） | pytest（开发依赖） |

## 2. 页面结构

八段，从上到下，锚点分别为 `#s0` 到 `#s7`。

| 段 | 需求 | 内容 | 数据来源 |
|---|---|---|---|
| 0 开头 | 1.2 | 一句话 "How much of your reference material did the AI actually read?"；一排 16 个格子：不装时 3 个亮、13 个灰；装上后 16 个全亮；数字照实写 | `fe-ext-results` 第 7 节 |
| 1 对照回放 | 2.1–2.5、1.4 | 左右两栏同时回放。左：W-H-03（不装），按记录显示过程，不画格子。右：WB-H-03（装上），82 格逐格亮起，然后写文件。下方并排列出四种写法，WB-H-03 用上 3 处、没用 `commandfor`，照实显示。每栏标明运行文件夹和编号、日期、模型、kiro-cli 版本。版本写作"3.3.0（推定：11-14 夜第一轮和 11-15 21:23 的 GIS 运行都记为 3.3.0；这两份记录本身没写版本）" | `demo-plan` 第 7 节；`fe-results` 第 2、3 节 |
| 2 五个任务 | 3.1–3.5 | 静态表，五行（账户设置页、FAQ、下拉菜单、深色模式、长文阅读页），每行列出不装和装上的结果。标出"读完后选了保守写法"和"不装也自己读了"。表下写明：五行都是 claude-haiku-5.5 的结果（kiro-cli 3.3.0；账户设置页那行的版本是推定）；第一轮的自动选模型和 claude-sonnet-5.5 两组不在表里，链接到 `docs/前端指南试验结果.md` 第 3 节 | `fe-results` 第 3、5 节；`fe-ext-results` 第 2、4、5、7 节 |
| 3 拦 | 4.1–4.5 | G-01 回放：写 `answer.md` 被拦（显示固定的关卡原因），24 格逐格亮起，然后写成。旁边一句照实的话（第 5 节）。不显示面积数字 | `gis-results` 第 1、5、7 节；`demo-plan` 第 3 节 |
| 4 拆 | 5.1–5.4 | 两组格子。镜头条：VB-01 的 46 个镜头，宽度按时长，全部读过（B 组 46/46），不放关键帧。字段表：24 格，17 个清单单元加 7 个字典单元，只显示名字 | `app-positioning` 的 `要做的`、`对比试验（主要证据）` 小节；`docs/视频对比试验设计.md` 第 9 节 |
| 5 我们自己就是这么用的 | 6.1–6.4 | 施工账表（静态 HTML，每行和 `docs/施工账.md` 一致）；同一件活的额度（T1 0.18 对 4.77，T2 0.37 对 9.31）；一条 `git log before-haiku.. --grep "Kiro-Model: claude-haiku-5.5"` 命令；一句"Haiku 写的代码仍由 Claude 审阅" | `story` 第 5、6 节；`docs/施工账.md` |
| 6 我们没证明的 | 7.1–7.2 | 静态列表：读了不等于照做；GIS 上没测出"读了才做对"；补信息不补能力；次数少；测试条件（模型、版本、批次） | `story` 第 6 节；`app-positioning` 第 3 节 |
| 7 自己试 | 7.3–7.4 | 三步装法（运行安装脚本、写要读的材料、同步登记），链接到仓库 README 的 Setup 一节（`README.md` 里有 `## Setup`，锚点 `#setup`） | 仓库 `README.md` |

**格子的视觉语言。** 每格是一个 `<li>`，三种状态：读过（实心、符号 ✓）、没读（描边、符号 ·）、被拦（符号 !，闪一下）。颜色不是唯一的线索：符号和文字都写。无障碍名是单元名加状态，例如 "read: Focus indicators"（需求 13.5）。第 1 段右栏和第 3 段的格子共用一个组件。

**回放机制。** 事件按记录的顺序一个一个走，每步固定间隔（约 220 毫秒），不按真实秒数走。页面旁边写的秒数来自 JSON 的 `t` 字段。进入视口时自动播放一次；有"Replay"按钮。开了减少动态效果时，不播放，直接显示结束状态，并附一段文字说明（例如 "24 of 24 units read; first write blocked; then written"）。

## 3. 转换脚本（需求 8）

### 3.1 输入

- 运行记录在仓库外。根目录由命令行参数 `--runs` 给出。脚本里不写默认路径，也不写任何本机路径：仓库是公开的。
- 四次运行（需求 10 的固定选择，按"该批次的第一次"）：
  - `webhaiku-20261115-173415\W-H-03`（不装）
  - `webrefcovhaiku-20261115-173528\WB-H-03`（装上）
  - `gis-20261115-213112\G-01`（拦）
  - `20261114-180540\VB-01`（拆）
- 每次运行只读这几样东西，按名字找，不扫整个目录：

| 文件或记录 | 取什么 |
|---|---|
| `<run>.status.json`（W-H-03、WB-H-03、G-01），`<run>.pgrade.json`（VB-01） | 模型、秒数、退出码；G-01 的 `kiro_cli` 字段；VB-01 的 `kiro_cli_at_batch_start` 字段 |
| `<run>.jsonl`（kiro-cli 输出流，每行 `{type, data}`） | 开始和结束的时间，工具调用（只取类型和工具名），最后汇报（只取"有没有"，不取文字） |
| 运行目录里的读取记录（状态目录，只读） | 必看单元的读取，写文件关卡的拦截 |
| 工作区里的 `index.html`（W-H-03、WB-H-03） | 四种写法是否出现，只输出布尔值 |
| 工作区里的 `reference.shots.md`（VB-01） | 46 个镜头的起止时间 |

- 不读，也不输出：`answer.md`、`edit-plan.md`、`reference.mp4`，其他工作区文件，模型的思考（`agent_thought_chunk`），消息正文（`agent_message_chunk`），文件差异（`diff`），提示词。
- 键名核对：status 和 pgrade 的键名、流的顶层键（`type`、`data`）、流里的类型名和更新类型已对照运行记录核对，只看名字，不看内容。状态目录里读取记录的字段名没有核对：这一步保护检查拦了一条命令，没有去读状态目录。实现步骤里用 RefCov 的 MCP 工具 `report` 和只读方式核对。

### 3.2 输出

- 四个文件：`site/data/w-h-03.json`、`wb-h-03.json`、`g-01.json`、`vb-01.json`。键排序，`ensure_ascii=True`，缩进 2，结尾一个换行。
- 每个文件的结构（示意，数值由脚本算出）：

```json
{
  "schema": 1,
  "id": "WB-H-03",
  "run_folder": "webrefcovhaiku-20261115-173528",
  "date": "2026-11-15",
  "model": "claude-haiku-5.5",
  "kiro_cli": {"value": "3.3.0", "basis": "inferred"},
  "seconds": 0,
  "tool_calls": 0,
  "must_read": {"total": 82, "read": 0},
  "blocks": 0,
  "needles": {"closedby": false, "user_invalid": false, "commandfor": false, "overscroll": false},
  "events": [{"t": 0.0, "kind": "start", "label": "run-started"}]
}
```

- `kiro_cli.basis` 取 `"record"`（来自运行记录：G-01、VB-01）或 `"inferred"`（W-H-03、WB-H-03，页面照需求 2.2 写推定的说明）。
- `run_folder` 只写文件夹名，不写盘符和上级路径；编号（如 `WB-H-03`）单独一个字段。

### 3.3 固定词表

| 字段 | 允许的值 | 来源 |
|---|---|---|
| `kind` | `start`、`tool`、`read`、`blocked`、`write`、`final`、`end` | 见下面的映射 |
| `label`（`start`） | `run-started` | 流的 `runStarted` |
| `label`（`tool`） | `tool-call` | 非 RefCov、非写文件的工具调用 |
| `label`（`read`） | `unit-read` | 经 MCP 读到的必看单元 |
| `label`（`blocked`） | `gate:required-units-unread` | 写文件关卡的拦截 |
| `label`（`write`） | `write:index.html`、`write:answer.md`、`write:edit-plan.md` | 写文件，文件名只从这三个里取 |
| `label`（`final`） | `final-report` | 最后的汇报，不带文字 |
| `label`（`end`） | `run-finished` | 流的 `runFinished`，`t` 为记录的秒数 |
| `unit` | 单元 ID，截短到 80 个字符；页面显示时把 `-` 换成空格 | 读取记录 |

映射规则：

- 流里的 `tool_call` 按工具名分类：写文件工具且文件名在上面的三个里，是 `write`；MCP 读取是 `read`（单元来自读取记录，不来自流）；其余是 `tool`。
- 被拦的写文件是 `blocked`，然后同一文件的成功写入是 `write`。
- 不用的记录：`agent_thought_chunk`、`agent_message_chunk` 的正文、`text`、`content`、`select`、`custom-agent`、`session_info_update`、`available_commands_update`、`config_option_update`、`tool_call_update`（结果文字不用）、`diff`。

### 3.4 截短和精度

- 单元 ID 最多 80 个字符，超出截断并加 `…`。
- 时间 `t` 保留一位小数。
- 没有自由文字。所有字符串都在第 3.3 节的词表里，或者是单元 ID，或者是文件夹名。
- 每个 JSON 文件不超过 60 KB。

### 3.5 写出前的检查

全部通过才写出。先写到临时文件，再替换。任何一项失败，退出码 2，不写任何文件。

1. 本机路径：字符串里不能有盘符（`[A-Za-z]:` 后跟斜杠或反斜杠）、反斜杠、`/Users/`、`/home/`，也不能含当前用户名（用户名取自环境，只用来检查，不写进 JSON）。
2. 词表：每个字符串都在第 3.3 节的词表里，或是单元 ID，或是文件夹名。其余一律报错。
3. 答案：脚本不打开 `answer.md`。G-01 的 JSON 没有任何面积或答案的数值字段。测试用一个哨兵数字放在夹具的 `answer.md` 里，输出中不能出现它（第 6 节）。
4. 大小：每个文件不超过 60 KB。
5. 可重跑：同一输入两次运行，输出的字节相同（需求 8.5）。

四种写法的判断：脚本里写四个模式，与判分脚本的规则一致，只输出是否出现，不输出 `index.html` 的内容。

### 3.6 运行方式

`python site/convert_runs.py --runs <运行根目录>`。输出写到 `site/data/`，输出目录固定在 `site/` 下，不接受其他路径。

## 4. 发布（需求 14）

选 A：GitHub Actions 工作流。工作流只上传和部署 `site/` 目录，不做构建。使用 GitHub 官方的 `actions/upload-pages-artifact` 和 `actions/deploy-pages`。触发条件：推送到 `main`，以及手动触发。工作流文件是 `.github/workflows/pages.yml`，它不在当前允许写入的范围里，需要用户批准。

一次性设置（用户做）：仓库 Settings → Pages → Build and deployment → Source 选 "GitHub Actions"。

地址：`https://3322jj.github.io/refcov/`（按仓库名推算，上线前核对）。

备选，不选：

- B：`gh-pages` 分支放 `site/` 的内容。要同步一个额外的分支，每次手动推。
- C：从 `main` 的 `/docs` 发布。页面在 `site/`，把页面挪进 `docs/` 会和材料混在一起。

时间：合进 `main` 之后，按方案第 4 节，计划在 11-24 到 11-27 之间。东京服务器只作备用。在线到 2027-01-29（需求 14.2）。

## 5. 深浅色、手机和无障碍（需求 13）

- 深浅色：`:root { color-scheme: light dark; }`，颜色用 CSS 变量。`@media (prefers-color-scheme: dark)` 换一组变量。跟随系统，页面上不做切换按钮（需求 13.1 只说跟随系统）。有 `color-scheme` 的元素会跟随系统的配色，见 [ref:g-component-specific-light-dark-theme/Basic-implementation]。
- 对比度：正文 4.5:1；大字、格子边框和符号 3:1（WCAG 1.4.3 和 1.4.11）。见 [ref:g-color/Contrast]。第 6 节的测试按这两条算。
- 焦点：所有能操作的元素都有 `:focus-visible` 外框，3px，外偏移 3px，与相邻颜色的对比至少 3:1。不用 `outline: none` 之后不给替代。见 [ref:g-accessibility/Focus-indicators]。
- 动态效果：默认是静止的。动画写在 `@media (prefers-reduced-motion: no-preference)` 里，不先写动画再用 `animation: none` 取消。减少动态效果时，格子直接显示结束状态（需求 13.6）。见 [ref:g-accessibility/11.-Motion-and-Preferences]。逐格亮起用固定间隔，即 stagger，见 [ref:g-dynamic-sibling-animations/Creating-a-stagger-animation]。
- 手机：格子用 CSS 网格，`repeat(auto-fill, minmax(…))`，能换行。第 1 段两栏在窄屏下竖排。第 2、5 段的表在窄屏下改成卡片，每个单元格前面用伪元素写列名（见 [ref:g-responsive-table/3.-Responsive-Stacked-Layout]）。宽度用容器查询，视口单位用 `dvh`（见 [ref:g-responsive-design/Overall-best-practices]）。
- 结构：`<html lang="en">`，一个 `<main>`，每段是 `<section>` 带标题，页首有跳过链接到 `main`。
- 文字：只有英文（需求 12.3）。

## 6. 测试（需求 12 和 8 等）

| 测试文件 | 检查什么 | 对应需求 |
|---|---|---|
| `tests/test_site_convert.py` | 两次运行字节相同；本机路径检查；词表检查；哨兵数字不出现在输出里（夹具的 `answer.md` 里放一个哨兵）；截短；四个 JSON 的结构 | 8.2–8.6 |
| `tests/test_site_page.py` | 八段按顺序出现；没有外部资源（`script` 只能是 `app.js`；`link`、`img`、`iframe` 不能指向 http 或 https）；页面文字没有中文字符；每个格子有无障碍名 | 1.1、12.3、13.5 |
| `tests/test_site_numbers.py` | 第 0、2、5 段的数字与测试里的一份数字表一致，表里每个数字在注释里写出出处（文档和节）；施工账表的每行与 `docs/施工账.md` 一致；字段表的 17 个清单单元 ID 与 `apps/layer-coverage/bayside.fields.md` 一致 | 1.2、3.3、5.1、6.1 |
| `tests/test_site_contrast.py` | 从样式表读两组颜色变量，算 WCAG 对比度，正文不低于 4.5，非文字不低于 3 | 13.4 |

手动检查（不进 CI）：无界面 Chrome 打开页面，没有脚本错误（需求 12.4）；在深色和浅色设置下各看一次。

CI 在 Linux 和 Windows 上跑全部测试。这些测试只用标准库和 pytest，不用 Chrome，不读 `D:` 下的文件，夹具都在临时目录里。

测试文件的位置：pyproject 里 `testpaths` 只有 `tests`，所以测试要放在 `tests/test_site_*.py`，CI 才会跑到。这要求把 `tests/test_site_*.py` 加进允许写入的范围，等用户批准；批准前不写测试。

## 7. 不做的（需求 15）

不跑模型，不连后端，不收集访客数据，不加载第三方脚本、字体、统计代码或广告。不做实时演示。不放关键帧，不放视频画面文字，不放真实公司名。不做中文版。

## 8. 实现顺序（之后的步骤，本步不做）

1. 用户批准两处写入范围：`tests/test_site_*.py` 和 `.github/workflows/pages.yml`。
2. 读完 `site/**` 的指南单元（182 个，严格模式要求）。
3. 转换脚本和 `tests/test_site_convert.py`，先写测试。
4. 页面：HTML、CSS、JS，然后页面测试。
5. 发布工作流（批准后）。
6. 检查点：Claude 审阅。之后由用户合并 `main`，并在仓库设置里打开 Pages。

## 9. 待定

1. 固定句的语言。需求 4.3 和 8.6 的固定句是中文"写出 answer.md，在标准值 ±3% 内"，但页面只有英文（需求 12.3）。设计里的英文版本是 "Wrote answer.md, within ±3% of the standard value."。需要 Claude 确认，并决定需求里的中文句要不要改。
2. 需求 4.4 那句照实的话的英文版本，草稿为 "On this data the model checks the dictionary on its own; RefCov makes 'checked' a number you can verify."，同样需要确认。
3. 写入范围：`tests/test_site_*.py` 和 `.github/workflows/pages.yml`，见第 6 节和第 4 节。
4. 状态目录里读取记录的字段名，实现前核对（见第 3.1 节）。
5. W-H-03 和 WB-H-03 的版本是推定（需求 2.2），页面照推定的说明写。
6. Pages 的 Source 要用户在仓库设置里改一次。
7. 视频对比试验设计要不要登记（需求 7.1 的出处）。
