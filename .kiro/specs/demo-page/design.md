# 设计文档：演示页 `site/`（第二稿，2026-11-17）

依据：`requirements.md` 第二稿（2026-11-17 修订：固定英文句，见需求 4.1、4.3、4.4、8.6）；`docs/演示页方案.md` 第 2–7 节；`docs/前端指南试验结果.md`、`docs/前端扩展试验结果.md`、`docs/GIS试验结果.md`、`docs/故事构思.md`。以上材料和下面引用的指南单元（`[ref:g-…]`）都经 RefCov 的 MCP 工具读过。

状态：第二稿。第 3 节（转换脚本）按这一版实现，读取事件另有显示名（见 3.2）；第 1 至 5 步已完成（见第 8 节），第 6 步检查点等 Claude 审阅。第一稿（`b126ca5`）经 Claude 审过，这一版按审阅意见改：输出流没有时间戳，去掉每个事件的时间；英文固定句；读取记录的字段。

## 1. 总览

演示页是一页静态页面：`site/index.html`、`site/style.css`、`site/app.js`，加上 `site/data/` 下的小 JSON。JSON 由 `site/convert_runs.py` 生成。这个脚本只用标准库，读仓库外的四次运行记录，写出 JSON。

页面只有英文（需求 12.3），不用框架，也不用构建工具（需求 12.1）。需求文档和本设计是中文；页面上的英文文字逐句对照需求写。

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
| 1 对照回放 | 2.1–2.5、1.4 | 左右两栏同时回放。左：W-H-03（不装），按输出流的先后显示工具调用和写文件，不画格子。右：WB-H-03（装上），82 个读取事件逐格亮起（格子是读取记录里的 82 个单元），然后写 `index.html`。下方并排列出四种写法，WB-H-03 用上 3 处、没用 `commandfor`，照实显示。每栏标明运行文件夹和编号、日期、模型、kiro-cli 版本、整次运行的总秒数。版本写作"3.3.0（推定：11-14 夜第一轮和 11-15 21:23 的 GIS 运行都记为 3.3.0；这两份记录本身没写版本）" | `demo-plan` 第 7 节；`fe-results` 第 2、3 节 |
| 2 五个任务 | 3.1–3.5 | 静态表，五行（账户设置页、FAQ、下拉菜单、深色模式、长文阅读页），每行列出不装和装上的结果。标出"读完后选了保守写法"和"不装也自己读了"。表下写明：五行都是 claude-haiku-5.5 的结果（kiro-cli 3.3.0；账户设置页那行的版本是推定）；第一轮的自动选模型和 claude-sonnet-5.5 两组不在表里，结果见 `docs/前端指南试验结果.md` 第 3 节 | `fe-results` 第 3、5 节；`fe-ext-results` 第 2、4、5、7 节 |
| 3 拦 | 4.1–4.5 | G-01 回放：按输出流的先后显示直接读文件、计算，然后写 `answer.md` 被拦。拦截原因用固定英文句 "Write blocked by the RefCov gate: required units not read yet."，旁边注明 "(gate message, translated)"。24 格逐格亮起，然后写成。旁边放需求 4.4 的英文句。结果说明用需求 4.3 的英文句，不显示面积数字 | `gis-results` 第 1、5、7 节；`demo-plan` 第 3 节 |
| 4 拆 | 5.1–5.4 | 两组格子。镜头条：VB-01 的 46 个镜头，宽度按 `reference.shots.md` 里的起止时间，读过状态来自读取记录（46/46），不放关键帧。字段表：24 格（17 个清单单元加 7 个字典单元），只显示名字 | `app-positioning` 的 `要做的`、`对比试验（主要证据）` 小节；`docs/视频对比试验设计.md` 第 9 节 |
| 5 我们自己就是这么用的 | 6.1–6.4 | 施工账表（静态 HTML，每行和 `docs/施工账.md` 一致）；同一件活的额度（T1 0.18 对 4.77，T2 0.37 对 9.31）；一条 `git log before-haiku.. --grep "Kiro-Model: claude-haiku-5.5"` 命令；一句"Haiku 写的代码仍由 Claude 审阅" | `story` 第 5、6 节；`docs/施工账.md` |
| 6 我们没证明的 | 7.1–7.2 | 静态列表：读了不等于照做；GIS 上没测出"读了才做对"；补信息不补能力；次数少；测试条件（模型、版本、批次） | `story` 第 6 节；`app-positioning` 第 3 节 |
| 7 自己试 | 7.3–7.4 | 三步装法（运行安装脚本、写要读的材料、同步登记），链接到仓库 README 的 Setup 一节（`README.md` 里有 `## Setup`，锚点 `#setup`） | 仓库 `README.md` |

**格子的视觉语言。** 每格是一个 `<li>`，三种状态：读过（实心、符号 ✓）、没读（描边、符号 ·）、被拦（符号 !，闪一下）。颜色不是唯一的线索：符号和文字都写。无障碍名是单元名加状态，例如 "read: Focus indicators"（需求 13.5）。第 1 段右栏和第 3 段的格子共用一个组件。单元名是 ID 把 `-` 换成空格的结果。

**回放机制。** 事件按输出流的先后排，一个一个走，每步固定间隔（约 220 毫秒）。页面不显示每个事件的时间：输出流里没有时间戳，只有读取记录带时间。页面只显示整次运行的总秒数：W-H-03 39 秒，WB-H-03 126 秒，G-01 91 秒，取自各自的状态文件；VB-01 301 秒，取自批次文件，并注明"用时是按日志时间补算的"（批次文件里 `status_reconstructed` 为真）。进入视口时自动播放一次；有"Replay"按钮。开了减少动态效果时，不播放，直接显示结束状态，并附一段文字说明。

## 3. 转换脚本（需求 8）

### 3.1 输入

- 运行记录在仓库外。根目录由命令行参数 `--runs` 给出。脚本里不写默认路径，也不写任何本机路径：仓库是公开的。
- 四次运行（需求 10 的固定选择，按"该批次的第一次"），每次读的文件：

| 运行 | 输出流（每行 `{type, data}`） | 状态文件 | 工作区 | 读取记录 |
|---|---|---|---|---|
| W-H-03（不装） | `webhaiku-20261115-173415/W-H-03.jsonl` | `…/W-H-03.status.json` | `…/W-H-03/index.html` | 无（没有 RefCov） |
| WB-H-03（装上） | `webrefcovhaiku-20261115-173528/WB-H-03.jsonl` | `…/WB-H-03.status.json` | `…/WB-H-03/index.html` | `…/WB-H-03/` 下的状态目录 |
| G-01（拦） | `gis-20261115-213112/G-01.jsonl` | `…/G-01.status.json` | 不读 | `…/G-01/` 下的状态目录 |
| VB-01（拆） | 无 | `20261114-180540/VB-01.pgrade.json` 和 `VB-01.status.json` | `…/VB-01/reference.shots.md` | `…/VB-01/` 下的状态目录 |

- 读取记录只用 `type` 为 `read` 和 `block` 的记录。`register`、`sync`、`session` 是模板准备阶段的记录，不用。字段（Claude 核对过 WB-H-03 和 G-01）：
  - 每条有 `type`、`seq`、`time`、`session`。
  - `read` 有 `source`、`unit`、`call`、`unit_sha256`。
  - `block` 有 `target`、`count`、`missing`、`gate`。`missing` 只取个数，不输出内容。
- 输出流只用这几样东西：`type` 为 `sessionUpdate` 的记录；`data.update.sessionUpdate` 为 `tool_call` 和 `tool_call_update`（工具调用和它的结果）；`agent_message_chunk`（只用来判断有没有汇报）。工具名取 `data.update.title`，例如 `@refcov/read_unit`、`Write File`、`Replace in File`、`Read File`。读单元的 ID 取自 `@refcov/read_unit` 调用的 `rawInput`（`source` 和 `unit`）。写文件只取 `rawInput.path` 的文件名，不取目录。
- 不读，也不输出：`answer.md`、`edit-plan.md`、`reference.mp4`，其他工作区文件；`rawInput.text`（写入的内容）；`locations`（绝对路径）；`agent_thought_chunk`（思考）；`agent_message_chunk` 的正文；`diff`；提示词；shell 工具的 `title`（那是模型写的描述，只用固定标签）。
- 已核对的范围（只看名字和计数，不看内容）：流的顶层键是 `type` 和 `data`；`@refcov/read_unit` 在 WB-H-03 有 82 次，全部 `completed`，82 个不同的单元；在 G-01 有 24 次 `completed`；`Write File` 在 G-01 有一次 `failed`（被拦的那次），之后一次 `completed`。流里没有时间戳。

### 3.2 输出

四个文件：`site/data/w-h-03.json`、`wb-h-03.json`、`g-01.json`、`vb-01.json`。键排序，`ensure_ascii=True`，缩进 2，结尾一个换行。

结构示意（数字由脚本算出，这里只示意字段）：

```json
{
  "blocks": 1,
  "date": "2026-11-15",
  "events": [{"kind": "tool", "label": "file-read"}],
  "id": "G-01",
  "kiro_cli": {"basis": "record", "value": "3.3.0"},
  "model": "claude-haiku-5.5",
  "must_read": {"read": 24, "total": 24},
  "run_folder": "gis-20261115-213112",
  "schema": 1,
  "seconds": 91,
  "seconds_reconstructed": false,
  "tool_calls": 40
}
```

字段说明：

- `id`：`W-H-03`、`WB-H-03`、`G-01`、`VB-01` 之一。`run_folder` 只写文件夹名，不写盘符和上级路径。`date` 从文件夹名的 8 位日期得出。`model` 取状态文件的 `model`（VB-01 取它的状态文件）。
- `kiro_cli`：`value` 是版本号。`basis` 是 `inferred`（W-H-03、WB-H-03，3.3.0，需求 2.2 的推定）、`record`（G-01，状态文件的 `kiro_cli`，去掉 "kiro-cli " 前缀），或 `record-batch-start`（VB-01，批次文件的 `kiro_cli_at_batch_start`，3.1.0）。
- `seconds`：W-H-03、WB-H-03、G-01 取状态文件的 `seconds`；VB-01 取批次文件的 `seconds`（301）。`seconds_reconstructed` 对 VB-01 取批次文件的 `status_reconstructed`（真），其余为假。
- `tool_calls`：输出流里 `tool_call` 记录的个数（W-H-03 为 1）。VB-01 没有输出流，取批次文件的 `tool_calls`（73）。
- `blocks`：读取记录里 `block` 的个数。没有读取记录的 W-H-03 为 0。
- `must_read`：`total` 和 `read`。有拦截记录时，`total` 取第一条 `block` 的 `missing` 个数（G-01 为 24）；没有拦截记录时，`total` 等于读到的不同单元数（WB-H-03 为 82，VB-01 为 46）。`read` 是读到的不同单元数。W-H-03 没有这一项（没有 RefCov）。
- `events`：W-H-03、WB-H-03、G-01 有，按输出流的先后排（第 3.3 节）。读单元的事件另带 `display`：由单元 ID 得出的显示名，去掉 `<br>` 之类的布局标签、HTML 实体和 `**` 粗体标记，连字符换成空格，截到 80 个字符。页面用它作格子的名字（第 2 节）；字段表只显示这个名字。
- `needles`：只有 W-H-03、WB-H-03 有（第 3.5 节第 6 条）。
- `shots`：只有 VB-01 有，是 `{id, start, end, read}` 的列表，按 `reference.shots.md` 里的顺序。`read` 表示这个镜头在读取记录里出现过。

### 3.3 事件和固定词表

事件只有五类（需求 8.3），`kind` 和 `label` 都在下表里：

| kind | label | 来源 |
|---|---|---|
| `tool` | `tool-call` | 输出流的工具调用，标题不是下面几种 |
| `tool` | `file-read` | 标题 `Read File`（直接读文件，不算看过） |
| `tool` | `mcp-call` | 标题以 `@refcov/` 开头、又不是读单元（`list_units`、`check`） |
| `read` | `unit-read` | 标题 `@refcov/read_unit`，状态 `completed`；`unit` 是 `source/unit`，截短到 80 个字符 |
| `write` | `write:index.html`、`write:answer.md`、`write:edit-plan.md` | 标题 `Write File` 或 `Replace in File`，状态 `completed`；文件名只从这三个里取 |
| `blocked` | `gate:required-units-unread` | 输出流里状态 `failed` 的写文件，与读取记录里的 `block` 一一对应（见下） |
| `final` | `final-report` | 最后一个 `tool_call` 之后有 `agent_message_chunk`。只表示有汇报，不带文字 |

规则：

- 读单元：输出流里 `completed` 的 `@refcov/read_unit` 调用，和读取记录里 `read` 的记录，按（`source`，`unit`）比较，个数和集合都必须相同（第 3.5 节）。
- 被拦的写文件：输出流里状态为 `failed` 的写文件，个数必须与读取记录里 `block` 的个数相同，按顺序一一对应。拦截事件放在那次失败写文件的位置。对应时，`target` 的文件名必须与失败写文件的文件名相同。
- 没有其他事件。运行的开始和结束不是事件，只影响 `seconds`。

### 3.4 截短

- 单元 ID（`source/unit`）最多 80 个字符，超出截断并加 `…`。
- 没有时间字段，没有自由文字。所有字符串要么在词表里，要么是单元 ID，要么是由单元 ID 得出的显示名（见 3.2 的 `display`），要么是文件夹名、日期、模型、版本号。

### 3.5 检查

全部通过才写出。先写到临时文件，四个文件都生成后再替换。任何一项失败，退出码 2，不写任何文件。错误信息只写计数和固定词，不写内容。

1. 计数：读单元（输出流和读取记录）的个数和集合相同；拦截（失败的写文件和 `block` 记录）的个数相同，文件名相同。
2. 必看数：有 `must_read` 的运行，`read` 等于 `total`。VB-01 的读取集合等于镜头清单的 ID 集合（46 个）。
3. 词表：`kind`、`label` 在第 3.3 节；`unit` 不超过 80 个字符；`run_folder` 只含字母、数字、点、下划线和连字符；`model` 形如 `claude-…`；`kiro_cli.value` 是版本号；`basis` 在三个值之内；`shots[].id` 形如 `shot-…`。
4. 本机路径：所有字符串里不能有盘符（字母后跟冒号和斜杠或反斜杠）、反斜杠、`/Users/`、`/home/`，也不能含当前用户名作为路径段。
5. 答案：脚本不打开 `answer.md`。数值字段只有这几个：`schema`、`seconds`、`tool_calls`、`blocks`、`must_read.total`、`must_read.read`、`shots[].start`、`shots[].end`。出现别的数值字段就报错。测试用一个哨兵数字放在夹具的 `answer.md` 里（第 6 节）。
6. 四种写法：W-H-03、WB-H-03 的 `index.html` 里查四个模式（`closedby="any"`、`:user-invalid`、`commandfor=`、`overscroll-behavior`），与判分脚本的规则一致，只输出是否出现，不输出文件内容。期望：W-H-03 为 0/4，WB-H-03 为 3/4（没有 `commandfor`）。不一致不报错，但输出计数，由人核对。
7. 大小：每个文件不超过 60 KB。
8. 可重跑：同一输入运行两次，字节相同（需求 8.5）。

### 3.6 运行方式

`python site/convert_runs.py --runs <运行根目录>`。输出固定写到 `site/data/`，不接受其他路径。

## 4. 发布（需求 14）

选 A：GitHub Actions 工作流。工作流只上传和部署 `site/` 目录，不做构建。使用 GitHub 官方的 `actions/upload-pages-artifact` 和 `actions/deploy-pages`。触发条件：推送到 `main`，以及手动触发。工作流文件是 `.github/workflows/pages.yml`。写入范围已由用户批准（2026-11-17），在页面步骤之后写。

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
| `tests/test_site_convert.py` | 下面的测试列表 | 8.2–8.6 |
| `tests/test_site_page.py` | 八段按顺序出现；没有外部资源（`script` 只能是 `app.js`；`link`、`img`、`iframe` 不能指向 http 或 https）；页面文字没有中文字符；每个格子有无障碍名 | 1.1、12.3、13.5 |
| `tests/test_site_numbers.py` | 第 0、2、5 段的数字与测试里的一份数字表一致，表里每个数字在注释里写出出处（文档和节）；施工账表的每行与 `docs/施工账.md` 一致；字段表的 17 个清单单元 ID 与 `apps/layer-coverage/bayside.fields.md` 一致 | 1.2、3.3、5.1、6.1 |
| `tests/test_site_contrast.py` | 从样式表读两组颜色变量，算 WCAG 对比度，正文不低于 4.5，非文字不低于 3 | 13.4 |

`tests/test_site_convert.py` 的测试列表：

1. 两次运行，四个文件的字节相同。
2. W-H-03 只有一次工具调用；事件只有写 `index.html` 和汇报。
3. WB-H-03 的读取事件与读取记录的个数和集合相同。
4. G-01 先拦后读：失败的写文件对应一条 `block`，之后是读取，最后写成。
5. VB-01 的镜头来自清单文件，读过状态全部为真，用时取批次文件。
6. 读取不一致时退出码为 2，不写任何文件。
7. 拦截个数不一致时退出码为 2。
8. 不打开 `answer.md`；哨兵数字不出现在输出里。
9. 只用 `read` 和 `block` 记录；`register`、`sync`、`session` 里的假单元不出现在输出里。
10. 输出里没有本机路径，也没有模型写的标题文字（shell 命令的描述）。
11. 超长的单元 ID 截断到 80 个字符，并加 `…`。
12. 四种写法的布尔值正确（夹具的 `index.html`）。
13. 数值字段只有允许的几个。

夹具建在临时目录里，文件夹名和文件名与真实运行相同，内容是小的合成记录，不用真实记录。真实运行的核对（一次性，人工）：W-H-03 工具调用数 1；WB-H-03 读到 82 个；G-01 先拦后读，读到 24 个；VB-01 读到 46 个。

CI 在 Linux 和 Windows 上跑全部测试。这些测试只用标准库和 pytest，不用 Chrome，不读 `D:` 下的文件。pyproject 里 `testpaths` 只有 `tests`，所以测试放在 `tests/test_site_*.py`（写入范围已由用户批准，2026-11-17）。

手动检查（不进 CI）：无界面 Chrome 打开页面，没有脚本错误（需求 12.4）；在深色和浅色设置下各看一次。

## 7. 不做的（需求 15）

不跑模型，不连后端，不收集访客数据，不加载第三方脚本、字体、统计代码或广告。不做实时演示。不放关键帧，不放视频画面文字，不放真实公司名。不做中文版。

## 8. 实现顺序和状态

1. 用户批准两处写入范围：`tests/test_site_*.py` 和 `.github/workflows/pages.yml`（2026-11-17，已批准）。
2. 读完 `site/**` 的指南单元（182 个，严格模式要求）：本步完成。
3. 转换脚本和 `tests/test_site_convert.py`，先写测试：本步完成。
4. 页面：HTML、CSS、JS，然后页面测试：本步完成（`site/index.html`、`site/style.css`、`site/app.js`；测试 `tests/test_site_page.py`、`tests/test_site_numbers.py`、`tests/test_site_contrast.py`）。无界面 Chrome 打开页面，格子、镜头条和字段表都有内容，没有脚本错误（手动，不进 CI）。
5. 发布工作流：本步完成（`.github/workflows/pages.yml`，只上传 `site/`，不做构建）。
6. 检查点：Claude 审阅。之后由用户合并 `main`，并在仓库设置里打开 Pages。

## 9. 待定

1. 固定句：已定（用户与 Claude 审阅，2026-11-17），见需求 4.1、4.3、4.4、8.6。
2. 写入范围：已批准（2026-11-17）。
3. 读取记录的字段：已由 Claude 核对（WB-H-03 和 G-01）。转换脚本按这些字段写；真实运行里如有不符，脚本报错，不写文件。
4. 状态目录里的读取记录，第一次用真实运行跑时，字段名由脚本的检查确认。
5. W-H-03 和 WB-H-03 的版本是推定（需求 2.2），页面照推定的说明写。
6. Pages 的 Source 要用户在仓库设置里改一次。
7. 视频对比试验设计不登记（已定，2026-11-17）；7.1 的出处保持文字写法。
8. VB-01 的用时是按日志时间补算的，页面要注明（第 2 节）。
