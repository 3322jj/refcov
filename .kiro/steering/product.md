---
inclusion: always
---

# 产品：RefCov

EN summary: RefCov computes coverage for reference material: sources are split into units, every read through MCP is recorded, and coverage counts only those records, with a tool-independent pass or fail that Kiro hooks enforce before writes and task starts. The pitch keeps one claim, "how much reference material the AI reads is a number", told in three layers: the standard is in the materials, not in model memory; models often know new practices but keep old habits; RefCov makes the model read the registered materials first. The evidence is five front-end tasks (without RefCov 13 of 16 runs opened no registered guide; with it 16 of 16 read every required unit; guide practices 9/58 rising to 39/58), and the gate blocked premature writes in the extension trial and in the GIS gate-only group, but no GIS trial showed reading turning a wrong answer right. The public text therefore claims reading, records and gate behavior, never correct answers, new-practice adoption, or RefCov filling capability gaps, and it keeps each trial's limits (one-task first trial, small runs, kiro-cli 3.3.0; browser checks show pages work in every group, so the claim is "follows the project's standards", not "pages are better with RefCov"). Must-haves and the scope freeze from 2026-11-13 are unchanged.

## 是什么

RefCov 给参考材料算"覆盖率"。代码有测试覆盖率，参考材料也该有。

- 把参考材料（文档、视频、地理数据）拆成单元，例如章节、镜头、图层的坐标系。
- AI 经 MCP 工具按单元取材料，每取一个记一笔。AI 也能直接读文件，但不算看过。覆盖率只根据记录算，不采信 AI 的自述。
- 核心层给出与工具无关的达标判断。在 Kiro 里，没看够就由钩子拦住写文件和任务开工。
- 需求要标明出自哪个单元。程序列出没标出处的需求（幻影需求）、看过但没被引用的单元（被忽略单元）、必看但没看过的单元（幽灵单元）。

## 对外讲法（2026-11-15 改：三层故事，依据 `docs/故事构思.md` 和 `docs/前端指南试验结果.md` 第 6 节；定稿前过检查点 4）

一句话：**AI 读了多少参考材料，应该是一个数字，而不是一句"我看过了"。**

对外的故事分三层（用户 2026-11-15 定）：

> 项目的标准写在你给的材料里，不在模型的记忆里。模型常常知道新写法，却照老习惯写（前端指南试验，`docs/前端指南试验结果.md` 第 6 节）。有些新东西它不知道：测到一例，弹框时背后不滚动的 `overscroll-behavior` 写法，claude-haiku-5.5 和自动选模型都不知道，claude-sonnet-5.5 知道。团队自己的约定它更不可能知道（常识推理：团队私有的约定不在模型的训练数据里，没有单独测）。RefCov 让它先读完你登记的材料再动手。

视频和 README 的结构按 `docs/故事构思.md` 的三幕写。同题对照的额度以 main 上 `0dbac19` 的第 5 节为准：Opus 5.5 为 4.77（T1）和 9.31（T2），Haiku 5.5 为 0.18（T1）和 0.37（T2），各 1 次。

这个故事**必须同时交代**（写在同一段或紧挨着的一段里）：

- 测得的范围：第一轮只在一个任务上测过（账户设置页：确认对话框加表单校验）。之后又做了前端扩展的 4 个任务（FAQ 手风琴、下拉菜单、深色模式、长文阅读页），共 5 个任务，kiro-cli 3.3.0，每组 3–4 次；是描述，不是统计结论。按事先写下的门槛，5 个任务里 2 个在写法上测出明显差别。
- 5 个任务合计：不装 RefCov 时 16 次里有 13 次一份登记的指南都没打开就写完了；装上 RefCov 后 16 次都读完了全部必看单元；指南的写法用上的比例从 9/58 升到 39/58。
- "效果相当"只在第一个任务（账户设置页）上比过，只指四种指南写法（用没用上）：Haiku 装上 RefCov 是 14/16，和不装的 Sonnet 5.5 相同（每组 4 次，见 `docs/前端指南试验结果.md` 第 5 节）。
- 浏览器实测（第 5b 节，无界面 Chrome 点过五组共 20 份页面）：五组的页面基本都能用，不装 RefCov 时功能也做得出来，只是不按项目规范写。所以对外讲"照项目规范写"，不讲"装了页面才好用"。
- 登记哪 8 份指南是人按任务挑的，四种写法所在的指南都在里面；真实项目里团队也要登记和当前工作相关的规范。
- 第一轮前端试验里，起作用的是发消息时的状态行提示和 MCP 读取，写文件关卡一次也没拦。之后的前端扩展试验里，装上 RefCov 的 12 次有 4 次被关卡拦下；GIS 只留关卡的一组 5 次也都被拦下。拦下的都是先读后拦，读完才写。
- Kiro 默认的自动选模型，每次实际用的是哪个模型日志里看不到。
- 不装时 Sonnet 5.5 自己会去读相关指南（每次 6–7 份）；不看规范的是自动选模型和 Haiku 5.5。
- Haiku 写的代码仍要审：能力测试里 T2 有几处比 Opus 粗糙。故事里说"由 Claude 在检查点审阅"，不讲"Haiku 自己就够了"。
- 前后两半做的是不同的活，难度不同，总额度不能直接对比；要比就比同题对照（故事构思第 5 节）的同一件活。
- RefCov 补的是信息缺口（项目规范、模型知道却不用的新写法、团队约定），不补能力缺口（规划长流程、用好专业库）。GIS 三轮试验都没测出"读了才做对"，结果见 `docs/GIS试验结果.md`。
- 读完之后，模型会因为浏览器支持度选保守写法（前端扩展试验里，下拉菜单和长文阅读页有的运行读完后仍选了保守写法）。RefCov 保证读，不保证照做。
- 材料一眼能找到、看起来正对题时（深色模式任务、GIS 字典），不装 RefCov 的模型也会自己去读。
- RefCov 保证"读了"，不保证"读懂了"。
- 登记哪些材料是人挑的；RefCov 不会自己去找最新指南。
- 第一幕的画面是实验记录，不是真实用户的项目。

**偷懒什么时候出现**（试验里归纳的，三个条件同时满足）：AI 自以为熟悉的领域；不查也能交差（老写法照样能跑）；默认或便宜的模型。条件不满足时没有测出偷懒：GIS 陷阱 6 次、网店约定 6 次、随口提问 6 次、120 份工单 2 次、视频对比 6 次，强模型（多为固定的 Sonnet 5.5）都认真读了；这些题要么能靠搜索直接找到答案，要么不查就做不对。对外照实说这个边界，不讲成"AI 总会偷懒"。

拆、读、拦各自靠什么证据：

- **拆**：视频按镜头、数据按字段、文档按章节，拆成单元，AI 不用自己发明切分工具。证据：镜头应用（视频，7 分 40 秒，46 个镜头）；视频对比试验（各 3 次）里装了镜头应用的一组三次都读完 46 个镜头，文字准确率和不装的一组一样（都是 100%），用时中位数更短（301 对 899 秒），但额度中位数没有更低（8.38 对 7.68），所以**不讲"更快更省"**。
- **读**：一个单元经 MCP 读一次记一笔，读了多少一目了然。主要证据：前端指南试验和前端扩展试验（见上）。
- **拦**：AI 判断"够了"但其实没读够时，Kiro 钩子拦住写文件和任务开工。证据有三处：CLI 关卡验证（qwen3-coder-next 先拦后读，`docs/验证结果.md`）；前端扩展试验（装上 RefCov 的 12 次里 4 次先读后拦，`docs/前端扩展试验结果.md`）；GIS 演示的只留关卡组（5 次都先拦后读，`docs/GIS试验结果.md`）。第一轮前端指南试验和视频试验里关卡都没有触发。拦下以后模型都读完才写，但 GIS 只留关卡组读完后数字没有变。
- **出处**：规格里的每条需求标明出自哪个单元；没标的列成幻影需求，引用了没读的单元就不达标。Kiro 已经能检查需求有没有矛盾、代码对不对，RefCov 补的是更前面一环：需求是不是真的来自用户给的材料。

"设陷阱等 AI 出错"的试验已结束，不再讲"抓到 AI 出错了多少次"。试验结果随模型变，对外只说"在某模型上测得"。不要讲成"又一个防止 AI 撒谎的工具"。

只讲做得到的：记录看过什么、算覆盖率、在 Kiro 里拦住自带的写文件工具和任务开工、其余情况事后标红。不说"不准写文件""换了工具关卡也还在""AI 只能经工具取材料""shell 写的文件也拦得住"（实测拦不住，`docs/验证结果.md` 第 8 项）。不说"最便宜的模型和最贵的模型一样好"（对比的是 Sonnet 5.5，不是最贵的模型）；不说"全部用上"（Haiku 装上后是 7/8，Sonnet 不装是 14/16）。镜头只按硬切算，软切换里的画面在同一个镜头单元里，不说"看过每个画面"。RefCov 防偷懒和虚报，不防蓄意伪造记录。演示页和视频只展示严格模式。写文件关卡在仓库自己开发里的拦截是事先安排的，不说成"抓到"；意外抓到的是保护检查（`docs/关键时刻清单.md`）。

另外几条不说：不说"模型不会新技术"（直接问时，Haiku 和自动选模型答得对四种里的三种，见前端指南试验第 6 节）；不说 RefCov 会自己去找最新指南（材料由用户登记）；不说 RefCov 提升了模型的 GIS 能力，或在 GIS 题上让答案变对（三轮 GIS 试验都没测出，`docs/GIS试验结果.md`）；不说"装了 RefCov 就会用上新写法"（读完之后用不用，是模型的决定）。

## 给谁用

- 用 AI 编程助手、并且给了它参考材料的开发者，例如拿参考视频做剪辑工具、拿 GIS 数据做分析的人。
- 比赛评委（Kiro 团队）：看在线演示页。

参赛类别：Kiroween 2026 Skeleton Crew。截止北京时间 2026-12-05 06:00。

## 必须有

1. 骨架：核心层（单元模型、读取记录、覆盖率、出处检查、开工凭证、报告、MCP 服务、文档适配器）+ Kiro 接入层。
2. 覆盖率计算。
3. 写文件关卡：三层，核心层达标判断（与工具无关，开工凭证只做记录）→ 钩子拦截 → 写入后记录。
4. 两个应用：`apps/shot-coverage`（参考视频，按镜头；证明拆，大材料读得全）和 `apps/layer-coverage`（地理数据，按图层属性；证明拆、拦和出处，由 Haiku 在 RefCov 管着写完，分支 `phase2-haiku`，待合并）。主要证据不在应用里：前端指南试验用的是骨架自带的文档适配器。
5. 在线演示页：回放真实会话记录，HTTPS，在线到 2027-01-29。优先回放前端指南试验的一对会话（不装：二三十秒交差、一份规范没看；装了：先读完 82 个单元再动手）。
6. 需求出处检查：列出幻影需求、被忽略单元、幽灵单元；需求引用了没看过的单元就不达标（需求 6）。

power 打包：评估过，不做（`docs/冲刺计划.md` 第 6 节）；对照实验是"应该有"；抽查考试、Crew 面板页是"有余力"。详细需求见 `.kiro/specs/refcov-skeleton/requirements.md`；镜头应用的需求在 `.kiro/specs/shot-coverage/requirements.md`（第二稿，用户 2026-11-14 审阅）。分工、检查点和砍单顺序见 `docs/冲刺计划.md`。

## 范围冻结

**从 2026-11-13 起不加新功能。** 只做上面清单和已定稿规格里的内容。

开发中想到的新点子（包括用户随口提的、agent 自己想到的），不要动手做，记进 `docs/DEVLOG.md` 的"以后再做"一节：一行写点子，一行写为什么现在不做。用户明确说"这个现在就做"才例外，并在 DEVLOG 里记下这次例外。
