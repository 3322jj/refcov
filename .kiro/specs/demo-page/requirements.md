# 需求文档：演示页 `site/`（第二稿，2026-11-16）

EN summary: Requirements for the demo page in `site/`: one static HTML, CSS and JavaScript page, in English only, that replays four real session logs as eight segments, each labelled with its run, date, model and kiro-cli version. A standard-library script keeps the raw logs outside the repository and writes small JSON files with local paths, model thinking and standard-answer values removed and no key-frame images. The page follows the product's public-claim rules, runs no model, calls no backend and collects no visitor data, is hosted on GitHub Pages online until 2027-01-29, and is itself configured under RefCov, with Chrome guides chosen by the guide pack's retrieval rules before any page code is written.

状态：**第二稿，2026-11-16；2026-11-17 出处改成 `[ref:…]`，挑选者已定。** 按 Claude 对第一稿的审阅修改。依据 `docs/演示页方案.md`（main 已合进本分支，合并提交 `4807463`，方案现在本地就有；用户 2026-11-16 拍板：第 5 节五条照建议定；第 7 节定了回放用的四次运行）。设计写在 `design.md`（2026-11-17）；转换脚本和页面代码在后面的步骤做，`site/` 还没有建。

文字出处（未登记，待转换）：`.kiro/steering/product.md`（对外讲法和必须有）、仓库 `README.md`、`docs/施工账.md`、`docs/视频对比试验设计.md` 还没有登记，仍是文字写法；检查程序不把它们算作幻影。其余六份项目文档和 `app-positioning` 已登记，出处改成了 `[ref:…]`。产品引导文档是常驻引导，没有登记。

## 简介

演示页让评委在两分钟内看懂 RefCov 做了什么。它回放的是真实会话的记录，不是文字描述（方案第 1 节）。页面是一页、静态、只做英文，不做实时演示，不跑模型，不连后端，也不收集访客数据（方案第 6 节）。

## 术语

- **运行**：一次 kiro-cli 会话和它的 RefCov 记录，由文件夹和编号确定，例如 `WB-H-03`。
- **回放**：把一次运行的事件按时间顺序在页面上重放：工具调用、读单元、被拦、写文件、最后的汇报。
- **格子**：一个必看单元在页面上的一格。读过的亮，没读的灰，被需求引用的带标记（`app-positioning` 第 7 节）。
- **转换脚本**：放在 `site/` 里、只用标准库、把仓库外的运行记录转成小 JSON 的脚本。
- **标准答案的数值**：GIS 演示题的面积标准值。它只在仓库外的判分脚本里，页面和 JSON 都不放。

## 第一部分：页面

### 需求 1：八段，从上到下，一页
EN: Eight segments on one page, top to bottom

**用户故事：** 作为评委，我想在一页上从上到下看完八段内容，以便两分钟内看懂 RefCov 做了什么。
EN: As a judge, I want to read eight segments on one page from top to bottom, so that I understand what RefCov does in about two minutes.

#### 验收标准

1. THE 页面 SHALL 只有一页，从上到下依次为：0 开头、1 对照回放、2 五个任务、3 拦、4 拆、5 我们自己就是这么用的、6 我们没证明的、7 自己试。
2. THE 第 0 段 SHALL 有一句话 "How much of your reference material did the AI actually read?"，和一个数字：不装 RefCov 时 16 次里 13 次一份登记的指南都没打开；装上后 16 次都读完了全部必看单元。
3. THE 页面的视觉 SHALL 统一用一排格子：读过的亮，没读的灰，被拦的那一刻闪一下（减少动态效果时改为静态标记，见需求 13）。
4. THE 每段回放 SHALL 标明运行文件夹和编号、日期、模型和 kiro-cli 版本；各段的具体值见需求 2.2、4.2、5.2（方案第 6 节第 2 条）。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:app-positioning/7.-视觉语言]

### 需求 2：对照回放，左右并排，每段标明运行
EN: Side-by-side replay, with the run, date and model stated

**用户故事：** 作为评委，我想看到同一个提示词、同一个最便宜的模型，装与不装的两份真实回放，并且知道它们来自哪次运行，以便我判断 RefCov 改变了什么。
EN: As a judge, I want to see the same prompt and the same cheap model run with and without RefCov side by side, and know which run each side comes from, so that I can judge what RefCov changes.

#### 验收标准

1. THE 第 1 段 SHALL 左右两栏同时回放两次运行：左边是不装 RefCov 的 `webhaiku-20261115-173415\W-H-03`，右边是装上 RefCov 的 `webrefcovhaiku-20261115-173528\WB-H-03`。
2. THE 第 1 段 SHALL 标明每栏的运行文件夹和编号、日期（2026-11-15，两次都是补跑）、模型（claude-haiku-5.5），以及 kiro-cli 版本，写作"3.3.0（推定：11-14 夜第一轮和 11-15 21:23 的 GIS 运行都记为 3.3.0；这两份记录本身没写版本）"，页面上照这样写。
3. THE 右栏 SHALL 显示格子一格格亮起（必看单元 82 个），然后才出现写文件事件。THE 左栏 SHALL 按运行记录显示它的过程；方案说"一次工具调用就写完"，这一点在转换脚本里对照运行记录核对，核对不过就改页面文字。
4. THE 第 1 段 SHALL 并排列出两份代码里四种指南写法的用上情况；右栏 SHALL 照实显示没用上的那一种（WB-H-03 用上 3 处，没用 `commandfor`）。
5. THE 第 1 段旁边 SHALL 写明指南的登记方式：第一轮的 8 份指南是 Claude 按任务挑的，挑的时候知道要测哪几种写法；前端扩展的 4 个任务由指南包自带的检索按规则选。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:demo-plan/7.-拍板结果和回放用的运行（用户-2026-11-16-定）]；[ref:fe-results/2.-材料和任务]；[ref:fe-results/3.-结果（kiro-cli-3.3.0，各-4-次）]；[ref:fe-results/4.-能说什么、不能说什么]；[ref:gis-results/7.-运行记录]；[ref:story/6.-必须照实交代]；[ref:fe-ext-results/7.-连同第一轮的任务一起看（5-个任务，Haiku-5.5）]

### 需求 3：五个任务的表，照实标出限制
EN: Five-task table, with its limits stated

**用户故事：** 作为评委，我想看到五个任务每个的结果，以及哪些地方没有达到预期，以便我不被只挑好结果的说法误导。
EN: As a judge, I want the result of each of the five tasks, including where it fell short, so that I am not misled by a selection of good results.

#### 验收标准

1. THE 第 2 段 SHALL 用一张表列出五个任务：第一轮的账户设置页，和前端扩展的 FAQ 手风琴、下拉菜单、深色模式、长文阅读页。每个任务列出：不装时打开了没打开登记的指南、用上几处写法；装上后读完了多少必看单元、用上几处写法。
2. THE 表 SHALL 照实标出"读完后选了保守写法"和"不装也自己读了"的任务和次数。
3. THE 表的数字 SHALL 与 `docs/前端指南试验结果.md` 和 `docs/前端扩展试验结果.md` 里的表一致。合计一行（不装 13/16 次没开指南，装上 16/16 读完，写法 9/58 → 39/58）SHALL 与 `docs/故事构思.md` 第 2 节一致。
4. THE 第 2 段 SHALL 写明每个数字来自哪份文档和哪一节。
5. THE 表 SHALL 写明：五行的数字都是 claude-haiku-5.5 的结果（kiro-cli 3.3.0；账户设置页那一行的版本是推定，见需求 2.2）。第一轮账户设置页的自动选模型和 claude-sonnet-5.5 两组不在表里，结果见 [前端指南试验结果](../../../docs/前端指南试验结果.md) 第 3 节（Haiku 的第一轮数字在第 5 节）。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:fe-results/3.-结果（kiro-cli-3.3.0，各-4-次）]；[ref:fe-results/5.-补测：最便宜的模型装上-RefCov（2026-11-14-夜）]；[ref:fe-ext-results/2.-结果]；[ref:fe-ext-results/4.-为什么-T2、T4-没达到门槛：读完了，但选了保守写法]；[ref:fe-ext-results/5.-为什么-T3-没测出：不装的自己就读了]；[ref:fe-ext-results/7.-连同第一轮的任务一起看（5-个任务，Haiku-5.5）]；[ref:story/2.-三幕]

### 需求 4：拦，GIS 只留关卡组的一次运行
EN: The gate: one GIS run where the write was blocked before reading

**用户故事：** 作为评委，我想看到一次真实的拦：AI 想写答案，被关卡拦下，读完必看单元，再写成，以便我看到关卡做了什么，也看到它没有改变答案。
EN: As a judge, I want to see a real block: the AI tries to write its answer, the gate stops it, the required cells are read, and then the answer is written, so that I see what the gate does and that it did not change the answer.

#### 验收标准

1. THE 第 3 段 SHALL 回放 `gis-20261115-213112\G-01`（GIS 只留关卡组正式批次的第一次）：写 `answer.md` 被拦，并显示关卡给的原因 → 必看单元的格子一格格亮起（24 格）→ 写成。
2. THE 第 3 段 SHALL 标明运行文件夹和编号、日期（2026-11-15）、模型（claude-haiku-5.5）、kiro-cli 版本（3.3.0，见 `gis-20261115-213112\G-01.status.json` 的 `kiro_cli` 字段）。
3. THE 第 3 段 SHALL 只显示"写出 answer.md，在标准值 ±3% 内"，不显示面积数字。
4. THE 第 3 段 SHALL 在旁边放一句照实的话："在这份数据上模型自己也会查字典；RefCov 让'查过'变成能核对的数字。"
5. THE 页面 SHALL NOT 说 RefCov 让答案变对，也 SHALL NOT 说拦让答案变对（三轮 GIS 试验都没测出，见 `docs/GIS试验结果.md`）。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:demo-plan/3.-回放的数据从哪来]；[ref:demo-plan/7.-拍板结果和回放用的运行（用户-2026-11-16-定）]；[ref:app-positioning/5.-图层覆盖率-`apps/layer-coverage`：拦和出处]；[ref:gis-results/1.-一句话]；[ref:gis-results/5.-为什么-GIS-上测不出来]；[ref:gis-results/7.-运行记录]

### 需求 5：拆，两个应用的格子，不放关键帧
EN: Splitting: the two apps' grids, without key-frame images

**用户故事：** 作为评委，我想看到两个应用各自怎样把材料拆成格子，以便我理解"拆"的作用，而不看到视频里的画面。
EN: As a judge, I want to see how each app splits its material into cells, without seeing any video frame, so that I understand the split.

#### 验收标准

1. THE 第 4 段 SHALL 显示两组格子：镜头条（视频对比试验批次 `20261114-180540` 的 `VB-01`，46 个镜头，宽度按时长），和 24 格字段表（GIS 清单：15 个字段、坐标系、范围，以及 7 个字典单元）。
2. THE 镜头条 SHALL 标明运行和日期（2026-11-14）、模型（claude-sonnet-5.5；视频对比试验用的是 Sonnet 5.5，不是 Haiku）、kiro-cli 版本（3.1.0，批次 `20261114-180540` 开始时的版本，见 `20261114-180540\VB-01.pgrade.json` 的 `kiro_cli_at_batch_start` 字段）。
3. THE 第 4 段 SHALL NOT 放任何关键帧图片，也 SHALL NOT 放视频里的画面文字或真实公司名（`app-positioning` 第 9 节第 5 条）。
4. THE 镜头条 SHALL 只标出镜头的起止时间和读过的状态。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:demo-plan/3.-回放的数据从哪来]；[ref:app-positioning/要做的]；[ref:app-positioning/对比试验（主要证据）]；[ref:app-positioning/9.-风险和待验证]

### 需求 6：我们自己就是这么用的，施工账和同一件活的额度对比
EN: "We used it on ourselves": the build ledger and the same-task cost comparison

**用户故事：** 作为评委，我想看到 Haiku 在 RefCov 管着下做的应用的施工记录，以及同一件活的额度对比，以便我知道这个项目本身是怎么做出来的。
EN: As a judge, I want the build ledger of the Haiku-built app and the same-task cost comparison, so that I can see how this project was built.

#### 验收标准

1. THE 第 5 段 SHALL 列出 `docs/施工账.md` 每件活的日期、任务、模型、额度（"未知"照写）、测试、读了几个单元、被拦几次。
2. THE 第 5 段 SHALL 列出同一件活 Opus 和 Haiku 的额度：T1 为 0.18 对 4.77，T2 为 0.37 对 9.31，与 `docs/故事构思.md` 第 5 节一致。
3. THE 第 5 段 SHALL 指向 Haiku 写的提交：`git log before-haiku.. --grep "Kiro-Model: claude-haiku-5.5"`。合并 main 以后，`before-haiku..phase2-haiku` 里会混进 Claude 的文档提交，所以不用它。
4. THE 第 5 段 SHALL 照实写：Haiku 写的代码仍由 Claude 在检查点审阅，不讲"Haiku 自己就够了"（`docs/故事构思.md` 第 6 节）。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；`docs/施工账.md`（未登记，待转换）；[ref:story/5.-同题对照：同一件活，Opus-和-Haiku-各花多少]；[ref:story/6.-必须照实交代]

### 需求 7：我们没证明的，和自己试
EN: What the project did not show, and how to try it

**用户故事：** 作为评委，我想看到这个项目没有证明什么，以及我自己怎么试，以便我不会高估它，也能自己装起来看。
EN: As a judge, I want to see what the project did not prove and how to try it myself, so that I do not overrate it and can install it.

#### 验收标准

1. THE 第 6 段 SHALL 写明：读了不等于照做；GIS 上没测出"读了才做对"；补的是信息，不补能力；次数少，是描述而不是统计；前端和 GIS 的结果在 kiro-cli 3.3.0 上测得（账户设置页那组补跑的版本是推定，见需求 2.2），是 claude-haiku-5.5 的结果（第一轮前端另有自动选模型和 claude-sonnet-5.5 两组）；视频试验用 claude-sonnet-5.5，两批分别在 kiro-cli 3.1.0 和 3.3.0 上跑（`docs/视频对比试验设计.md` 第 9 节）。
2. THE 第 6 段 SHALL 写明适用条件：小材料、点名时，强模型本来就会读，RefCov 只多一份记录；材料大、贵、是手段而不是任务本身时，价值最大（`app-positioning` 第 3 节）。
3. THE 第 7 段 SHALL 写三步装法：运行 `setup.py`，在 `refcov.toml` 里写要读的材料，运行 `refcov sync`；并链接到仓库 README 的 Setup 一节。
4. THE 第 7 段的步骤 SHALL 与 README 的 Setup 一节一致，以 README 为准。

出处：[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:app-positioning/3.-对外讲法]；[ref:story/6.-必须照实交代]；`docs/视频对比试验设计.md` 第 9 节（未登记，待转换）；仓库 `README.md`（未登记，待转换）

### 需求 8：回放数据，标准库脚本，小 JSON，只放该放的
EN: Replay data: a standard-library script that writes small JSON, keeping only what may be published

**用户故事：** 作为维护者，我想让页面只读仓库里的小 JSON，原始记录留在仓库外，以便数据可以公开，也可以重新生成。
EN: As a maintainer, I want the page to read only small JSON files in the repository, with the raw records kept outside, so that the data can be public and can be regenerated.

#### 验收标准

1. THE 转换脚本 SHALL 只用 Python 标准库，放在 `site/` 里，读 `D:\agent\kiro\refcov-trial\runs\` 下需求 10 列出的四次运行，输出小 JSON 到 `site/`，JSON 进仓库。
2. THE 转换脚本 SHALL 把本机路径换成相对路径，去掉模型的思考过程，把长文本截短到固定长度（长度在设计里定）。
3. THE 事件 SHALL 限于五类：工具调用、读单元、被拦、写文件、最后的汇报。每个事件只带时间（秒）、类型、单元编号和固定词表里的短标签，不带模型写的自由文字。
4. THE JSON SHALL NOT 含标准答案的数值（GIS 的面积数字），也 SHALL NOT 含关键帧图片或视频画面的文字。
5. THE 转换脚本 SHALL 可以重跑：同样的运行记录，两次输出的字节相同。
6. THE 转换脚本 SHALL NOT 读 `answer.md` 的正文。THE GIS 那段 SHALL 只显示固定文字"写出 answer.md，在标准值 ±3% 内"。THE 转换脚本 SHALL 在写出前检查 JSON：不含本机路径，不含来自 `answer.md` 的文字。

出处：[ref:demo-plan/3.-回放的数据从哪来]；[ref:layer-readme/Source-and-terms-of-use]

### 需求 9：版权和隐私
EN: Copyright and privacy limits on what the page shows

**用户故事：** 作为维护者，我想让页面不侵犯数据和视频的版权，也不泄露隐私，以便页面可以长期在线。
EN: As a maintainer, I want the page to respect the data and video rights and not leak private information, so that it can stay online.

#### 验收标准

1. THE 页面 SHALL 只显示纽约数据的字段名，不显示字段的取值或原始行（方案第 3 节）。
2. THE 页面 SHALL 只显示 Chrome 指南的单元标题（指南为 Apache-2.0）。
3. THE 页面 SHALL NOT 放参考视频的关键帧、画面文字或真实公司名。
4. THE 页面 SHALL NOT 放访客数据，不加载第三方脚本、字体、统计代码或广告（方案第 6 节）。
5. THE 数据和字典的使用条款 SHALL 由 Claude 在上线前读完，并经用户确认后才上线；`apps/layer-coverage/README.md` 写明目前还没有读完。

出处：[ref:demo-plan/3.-回放的数据从哪来]；[ref:demo-plan/6.-不做的]；[ref:app-positioning/9.-风险和待验证]；[ref:layer-readme/Source-and-terms-of-use]

### 需求 10：四次运行，固定，不挑
EN: Four fixed runs, chosen by rule and not by result

**用户故事：** 作为评委，我想相信页面上的回放不是挑出来的，以便我知道好的和不好的结果都在。
EN: As a judge, I want to know the replays were not picked for their results, so that I can trust that good and bad results are both shown.

#### 验收标准

1. THE 页面 SHALL 只回放以下四次运行。选择规则是"该批次的第一次"，方案定下后不换：
   - 对照回放（不装）：`webhaiku-20261115-173415\W-H-03`；
   - 对照回放（装）：`webrefcovhaiku-20261115-173528\WB-H-03`；
   - 拦：`gis-20261115-213112\G-01`；
   - 拆（镜头条）：`20261114-180540\VB-01`。
2. THE 第 2 段的表 SHALL 列出五个任务的全部运行结果，不只列被选中的那几次。
3. THE 页面 SHALL 写明选择规则，并写明每次运行的记录文件夹。

出处：[ref:demo-plan/6.-不做的]；[ref:demo-plan/7.-拍板结果和回放用的运行（用户-2026-11-16-定）]；[ref:fe-ext-results/2.-结果]

### 需求 11：对外文字，只讲测出来的
EN: Public text states only what was measured

**用户故事：** 作为维护者，我想让页面上每句话都能追到测出来的结果，并且不说产品不说的那些话，以便评委不会被夸大的说法误导。
EN: As a maintainer, I want every sentence on the page to trace to a measured result and to avoid the claims the product must not make, so that judges are not misled by overstated claims.

#### 验收标准

1. THE 页面文字 SHALL 只讲测出来的。页面上每个数字 SHALL 附出处（文档和节）。
2. THE 页面文字 SHALL NOT 含 `.kiro/steering/product.md` 的"不说"清单中的任何说法。特别是：不说"不准写文件""换了工具关卡也还在""AI 只能经工具取材料""shell 写的文件也拦得住"；不说"最便宜的模型和最贵的模型一样好""全部用上""看过每个画面""更快更省""装了页面才好用"；不说"抓到了多少"（被拦几次，幻影需求几条）；不说"模型不会新技术"；不说 RefCov 会自己去找最新指南；不说"又一个防止 AI 撒谎的工具"；不说 RefCov 提升了模型的 GIS 能力，或在 GIS 题上让答案变对；不说"装了 RefCov 就会用上新写法"。
3. THE 页面文字 SHALL NOT 说 RefCov 能防蓄意伪造（`app-positioning` 第 3 节）。
4. THE 页面文字 SHALL 按"照项目规范写"讲，不讲"装了页面才好用"（`docs/前端指南试验结果.md` 第 5b 节）。

出处：`.kiro/steering/product.md` "对外讲法"（未登记，待转换）；[ref:app-positioning/3.-对外讲法]；[ref:app-positioning/9.-风险和待验证]；[ref:fe-results/5b.-补测：页面在浏览器里好不好用（2026-11-15）]

### 需求 12：技术约束，纯静态，只做英文
EN: Technical constraints: a static page in English only

**用户故事：** 作为维护者，我想让页面没有框架和构建步骤，也只有英文，以便它能直接托管，也容易维护。
EN: As a maintainer, I want the page to have no framework or build step and to be in English only, so that it can be hosted directly and is easy to maintain.

#### 验收标准

1. THE 页面 SHALL 用纯 HTML、CSS 和 JavaScript，不用框架，不用构建工具（不用打包器，不要 npm 构建步骤）。
2. THE 数据 SHALL 是同目录下的 JSON 文件，页面只读这些 JSON。
3. THE 页面 SHALL 只有英文，不做中文版（方案第 5 节第 4 条）。
4. THE 页面 SHALL 在无界面 Chrome 里打开时没有脚本错误。

出处：[ref:demo-plan/4.-怎么做]；[ref:demo-plan/5.-要用户拍板的]；[ref:demo-plan/7.-拍板结果和回放用的运行（用户-2026-11-16-定）]

### 需求 13：深浅色、手机和无障碍
EN: Dark and light themes, mobile layout and accessibility

**用户故事：** 作为评委，我想在任何设备和设置下都能看清页面，包括用键盘和屏幕阅读器，以便页面对所有人都能用。
EN: As a judge, I want the page readable on any device and setting, including by keyboard and screen reader, so that it works for everyone.

#### 验收标准

1. THE 页面 SHALL 跟随系统的深色和浅色设置，两种都清楚好看。
2. THE 页面 SHALL 在手机宽度下不溢出；格子能换行或缩放；文字可读。
3. THE 页面 SHALL 可以只用键盘操作，焦点可见。
4. THE 页面文字的对比度 SHALL 达到 WCAG AA。
5. THE 每个格子 SHALL 有文字替代：屏幕阅读器读出单元标题和状态（读过、没读、被拦）。
6. WHERE 用户设定了减少动态效果，THE 页面 SHALL 停止闪烁和动画，改用静态标记。

出处：[ref:app-positioning/7.-视觉语言]；[ref:demo-plan/2.-页面结构（一页，从上往下）]；[ref:demo-plan/4.-怎么做]

### 需求 14：托管和在线期限
EN: Hosting on GitHub Pages, online until 2027-01-29

**用户故事：** 作为维护者，我想让页面用 HTTPS 在 GitHub Pages 上线，并保持到 2027-01-29，以便评委随时能打开。
EN: As a maintainer, I want the page on GitHub Pages over HTTPS until 2027-01-29, so that judges can open it at any time.

#### 验收标准

1. THE 页面 SHALL 托管在 GitHub Pages，用 HTTPS 访问。
2. THE 页面 SHALL 在线到 2027-01-29。
3. THE 发布方式（从哪个分支、哪个目录发布）SHALL 在设计里定。

出处：[ref:demo-plan/4.-怎么做]；[ref:demo-plan/5.-要用户拍板的]；`.kiro/steering/product.md` "必须有"第 5 条（未登记，待转换）

### 需求 15：不做的事
EN: What the page does not do

**用户故事：** 作为维护者，我想让页面的范围只到回放为止，以便它不会变成需要维护的服务。
EN: As a maintainer, I want the page's scope to stop at replays, so that it does not become a service to maintain.

#### 验收标准

1. THE 页面 SHALL NOT 跑模型，SHALL NOT 连后端，SHALL NOT 收集访客数据（方案第 6 节第 1 条）。
2. THE 页面 SHALL 只做回放，不做实时演示；每段回放 SHALL 写明是哪一次运行、哪天、什么模型（方案第 6 节第 2 条）。
3. THE 页面 SHALL NOT 为了好看挑数字：回放的运行在方案定下后固定（需求 10）。

出处：[ref:demo-plan/6.-不做的]

### 需求 16：页面本身由 RefCov 管着写
EN: The page is itself written under RefCov

**用户故事：** 作为用户，我想让演示页本身也由 RefCov 管着写，以便页面本身是一个例子：最便宜的模型先读完指南再写。
EN: As a user, I want the demo page itself written under RefCov, so that the page is an example: the cheap model reads the guides before it writes.

#### 验收标准

1. THE 配置 SHALL 把 `site/**` 指向必看材料：Chrome 指南里和这页相关的几份，由指南包自带的检索规则选出，而不是凭印象挑。
2. THE 配置 SHALL 由用户改，AI 不改；用户运行 `refcov sync` 登记这些材料。
3. THE 必看材料 SHALL 在写页面代码之前配好。顺序是：本需求定稿；Claude 按检索规则选出指南；用户登记并运行 `refcov sync`；然后才写页面代码。
4. THE 配置 SHALL 用 `[[scope]]` 的 `paths = ["site/**"]` 写明页面文件夹，`sources` 填登记后生成的参考源编号。

出处：[ref:demo-plan/4.-怎么做]；[ref:demo-plan/7.-拍板结果和回放用的运行（用户-2026-11-16-定）]；[ref:fe-ext-results/7.-连同第一轮的任务一起看（5-个任务，Haiku-5.5）]

## 已定和还没定的

- 已定（用户 2026-11-16）：托管用 GitHub Pages；主角回放用第一轮账户设置页的 Haiku 一对；演示页也在 RefCov 管着写；只做英文；镜头条不放关键帧图片。
- 已定（方案第 7 节）：回放的四次运行和选择规则（需求 10）。
- 设计阶段定：发布方式（分支和目录）；转换脚本截短到多长；事件标签的固定词表；页面的具体布局、颜色和动效时长。
- 写页面代码之前：指南已选、已登记（用户 2026-11-17，`refcov.toml` 的 `site/**` 配置）。但 `site/**` 的材料还没全部读过：指南的 182 个单元在严格模式下要先读完（需求 16）。
- 已定（用户，2026-11-17）：登记哪些文档。演示页文件夹 `.kiro/specs/demo-page/**` 登记了六份项目文档和 `app-positioning`；`site/**` 另加 17 份 Chrome 指南（`docs/reference/chrome-guides/README.md` 写了选法）。产品引导文档没登记。
- 还没定，要用户拍板：`docs/视频对比试验设计.md` 要不要登记。它不在上面的六份里，所以 7 的出处先写成文字。
- 已定（用户，2026-11-17）：第一轮的 8 份指南是 Claude 按任务挑的，挑的时候知道要测哪几种写法。此前写成人挑的地方已更正（需求 2.5）；`.kiro/steering/product.md` 的对外讲法也一并改了。
