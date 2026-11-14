---
inclusion: always
---

# 产品：RefCov

EN summary: RefCov computes coverage for reference material: sources are split into units, the AI fetches units through MCP tools, each fetch is recorded, and coverage comes only from those records (direct file reads do not count). The core gives a tool-independent pass/fail; in Kiro, hooks block writes and task starts until it passes. Requirements must cite units; RefCov lists phantom requirements, ignored units and ghost units. The pitch (changed again 2026-11-14 night) is "the AI reads the reference material before it acts, and how much it read is a number": the main evidence is the front-end guide trial, where Kiro's default model selection and claude-haiku-5.5 opened none of 210 guides in every run and wrote from memory, while with RefCov installed they read all 82 required units every time and used the guide practices (Haiku at about a tenth of Sonnet's credits); the shot-coverage app (video) shows splitting and reading on large material; the only evidence for "gate" is still the CLI gate check, because in the front-end trial the status-line prompt and MCP reads did the work and the gate never blocked. The conditions where skipping appears (a domain the model thinks it knows, a task that can be finished without checking, a default or cheap model) and the small sample (2-4 runs per group, one task, kiro-cli 3.3.0) are stated plainly, and "faster and cheaper" is not claimed for the video trial because median credits were not lower. Must-haves are the skeleton, coverage, the three-layer write gate, two apps and an online replay demo; public claims stay within what the system does. Scope is frozen from 2026-11-13; new ideas go to the DEVLOG "later" section.

## 是什么

RefCov 给参考材料算"覆盖率"。代码有测试覆盖率，参考材料也该有。

- 把参考材料（文档、视频、地理数据）拆成单元，例如章节、镜头、图层的坐标系。
- AI 经 MCP 工具按单元取材料，每取一个记一笔。AI 也能直接读文件，但不算看过。覆盖率只根据记录算，不采信 AI 的自述。
- 核心层给出与工具无关的达标判断。在 Kiro 里，没看够就由钩子拦住写文件和任务开工。
- 需求要标明出自哪个单元。程序列出没标出处的需求（幻影需求）、看过但没被引用的单元（被忽略单元）、必看但没看过的单元（幽灵单元）。

## 对外讲法（2026-11-14 夜改；依据 `docs/进展总结-2026-11-14.md` 第 3 节和 `docs/前端指南试验结果.md`；定稿前过检查点 4）

一句话：**AI 读了多少参考材料，应该是一个数字，而不是一句"我看过了"。**

对外的故事（草稿）：

> 项目里放着规范，AI 却凭记忆写代码，汇报里对规范只字不提。装上 RefCov，同样的模型先读完必看的规范再动手，指南推荐的写法基本全用上。最便宜的模型装上它，推荐写法的采用率和不装的 Sonnet 5.5 相当，额度约为十分之一。

这个故事**必须同时交代**（写在同一段或紧挨着的一段里）：

- 只在一个任务上测得（账户设置页：确认对话框加表单校验）、kiro-cli 3.3.0，每组 2–4 次；是描述，不是统计结论。
- "效果相当"只指四种指南写法（用没用上），页面在浏览器里好不好用没有测。
- 登记哪 8 份指南是人按任务挑的，四种写法所在的指南都在里面；真实项目里团队也要登记和当前工作相关的规范。
- 起作用的是发消息时的状态行提示和 MCP 读取，**写文件关卡一次也没拦**。
- Kiro 默认的自动选模型，每次实际用的是哪个模型日志里看不到。
- 不装时 Sonnet 5.5 自己会去读相关指南（每次 6–7 份）；不看规范的是自动选模型和 Haiku 5.5。

**偷懒什么时候出现**（试验里归纳的，三个条件同时满足）：AI 自以为熟悉的领域；不查也能交差（老写法照样能跑）；默认或便宜的模型。条件不满足时没有测出偷懒：GIS 陷阱 6 次、网店约定 6 次、随口提问 6 次、120 份工单 2 次、视频对比 6 次，强模型（多为固定的 Sonnet 5.5）都认真读了；这些题要么能靠搜索直接找到答案，要么不查就做不对。对外照实说这个边界，不讲成"AI 总会偷懒"。

拆、读、拦各自靠什么证据：

- **拆**：视频按镜头、数据按字段、文档按章节，拆成单元，AI 不用自己发明切分工具。证据：镜头应用（视频，7 分 40 秒，46 个镜头）；视频对比试验（各 3 次）里装了镜头应用的一组三次都读完 46 个镜头，文字准确率和不装的一组一样（都是 100%），用时中位数更短（301 对 899 秒），但额度中位数没有更低（8.38 对 7.68），所以**不讲"更快更省"**。
- **读**：一个单元经 MCP 读一次记一笔，读了多少一目了然。主要证据：前端指南试验（见上）。
- **拦**：AI 判断"够了"但其实没读够时，Kiro 钩子拦住写文件和任务开工。**证据目前只有 CLI 关卡验证那一次**（qwen3-coder-next 先拦后读，`docs/验证结果.md`）；前端指南和视频试验里关卡都没有触发。要补"拦"，得单独跑"关掉状态行提示、只留关卡"的一组，还没做。
- **出处**：规格里的每条需求标明出自哪个单元；没标的列成幻影需求，引用了没读的单元就不达标。Kiro 已经能检查需求有没有矛盾、代码对不对，RefCov 补的是更前面一环：需求是不是真的来自用户给的材料。

"设陷阱等 AI 出错"的试验已结束，不再讲"抓到 AI 出错了多少次"。试验结果随模型变，对外只说"在某模型上测得"。不要讲成"又一个防止 AI 撒谎的工具"。

只讲做得到的：记录看过什么、算覆盖率、在 Kiro 里拦住自带的写文件工具和任务开工、其余情况事后标红。不说"不准写文件""换了工具关卡也还在""AI 只能经工具取材料""shell 写的文件也拦得住"（实测拦不住，`docs/验证结果.md` 第 8 项）。不说"最便宜的模型和最贵的模型一样好"（对比的是 Sonnet 5.5，不是最贵的模型）；不说"全部用上"（Haiku 装上后是 7/8，Sonnet 不装是 14/16）。镜头只按硬切算，软切换里的画面在同一个镜头单元里，不说"看过每个画面"。RefCov 防偷懒和虚报，不防蓄意伪造记录。演示页和视频只展示严格模式。写文件关卡在仓库自己开发里的拦截是事先安排的，不说成"抓到"；意外抓到的是保护检查（`docs/关键时刻清单.md`）。

## 给谁用

- 用 AI 编程助手、并且给了它参考材料的开发者，例如拿参考视频做剪辑工具、拿 GIS 数据做分析的人。
- 比赛评委（Kiro 团队）：看在线演示页。

参赛类别：Kiroween 2026 Skeleton Crew。截止北京时间 2026-12-05 06:00。

## 必须有

1. 骨架：核心层（单元模型、读取记录、覆盖率、出处检查、开工凭证、报告、MCP 服务、文档适配器）+ Kiro 接入层。
2. 覆盖率计算。
3. 写文件关卡：三层，核心层达标判断（与工具无关，开工凭证只做记录）→ 钩子拦截 → 写入后记录。
4. 两个应用：`apps/shot-coverage`（参考视频，按镜头；证明拆，大材料读得全）和 `apps/layer-coverage`（地理数据，按图层属性；证明出处，GIS 应用的需求还没开始）。主要证据不在应用里：前端指南试验用的是骨架自带的文档适配器。
5. 在线演示页：回放真实会话记录，HTTPS，在线到 2027-01-29。优先回放前端指南试验的一对会话（不装：二三十秒交差、一份规范没看；装了：先读完 82 个单元再动手）。
6. 需求出处检查：列出幻影需求、被忽略单元、幽灵单元；需求引用了没看过的单元就不达标（需求 6）。

power 打包：评估过，不做（`docs/冲刺计划.md` 第 6 节）；对照实验是"应该有"；抽查考试、Crew 面板页是"有余力"。详细需求见 `.kiro/specs/refcov-skeleton/requirements.md`；镜头应用的需求在 `.kiro/specs/shot-coverage/requirements.md`（第二稿，用户 2026-11-14 审阅）。分工、检查点和砍单顺序见 `docs/冲刺计划.md`。

## 范围冻结

**从 2026-11-13 起不加新功能。** 只做上面清单和已定稿规格里的内容。

开发中想到的新点子（包括用户随口提的、agent 自己想到的），不要动手做，记进 `docs/DEVLOG.md` 的"以后再做"一节：一行写点子，一行写为什么现在不做。用户明确说"这个现在就做"才例外，并在 DEVLOG 里记下这次例外。