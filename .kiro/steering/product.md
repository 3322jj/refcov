---
inclusion: always
---

# 产品：RefCov

EN summary: RefCov computes coverage for reference material: sources are split into units, the AI fetches units through MCP tools, each fetch is recorded, and coverage comes only from those records (direct file reads do not count). The core gives a tool-independent pass/fail; in Kiro, hooks block writes and task starts until it passes. Requirements must cite units; RefCov lists phantom requirements, ignored units and ghost units. The pitch (changed 2026-11-14) is split, read, gate: the shot-coverage app (video) shows splitting and reading and carries the main evidence, the layer-coverage app (GIS) shows gating and requirement sources; the "set a trap" trial is dropped, the conditions where RefCov helps (large, costly material that is only a means) are stated plainly, and "faster and cheaper" is claimed only after the video comparison trial. Must-haves are the skeleton, coverage, the three-layer write gate, two apps and an online replay demo; public claims stay within what the system does. Scope is frozen from 2026-11-13; new ideas go to the DEVLOG "later" section.

## 是什么

RefCov 给参考材料算"覆盖率"。代码有测试覆盖率，参考材料也该有。

- 把参考材料（文档、视频、地理数据）拆成单元，例如章节、镜头、图层的坐标系。
- AI 经 MCP 工具按单元取材料，每取一个记一笔。AI 也能直接读文件，但不算看过。覆盖率只根据记录算，不采信 AI 的自述。
- 核心层给出与工具无关的达标判断。在 Kiro 里，没看够就由钩子拦住写文件和任务开工。
- 需求要标明出自哪个单元。程序列出没标出处的需求（幻影需求）、看过但没被引用的单元（被忽略单元）、必看但没看过的单元（幽灵单元）。

## 对外讲法（拆、读、拦；2026-11-14 改，依据 `docs/应用定位和陷阱试验.md` 第二版第 3 节）

一句话：**AI 读了多少参考材料，应该是一个数字，而不是一句"我看过了"。**

- **拆**：视频按镜头、数据按字段、文档按章节，拆成单元，AI 不用自己发明切分工具。
- **读**：一个单元经 MCP 读一次记一笔，读了多少一目了然。
- **拦**：AI 判断"够了"但其实没读够时，Kiro 钩子拦住写文件和任务开工。
- 出处：规格里的每条需求标明出自哪个单元；没标的列成幻影需求，引用了没读的单元就不达标。Kiro 已经能检查需求有没有矛盾、代码对不对，RefCov 补的是更前面一环：需求是不是真的来自用户给的材料。

两个应用各管一半证据：镜头覆盖率（视频）证明拆和读，承担主要证据；图层覆盖率（GIS）证明拦和出处。"设陷阱等 AI 出错"的试验已结束，不再讲"抓到 AI 出错了多少次"。

**适用条件照实说**：材料小、点名让它读时，强模型本来就会读（6 次 GIS 试验全对），RefCov 只多一份记录；材料大、读一遍很贵、材料只是手段而不是任务本身时，RefCov 才有用。"更快、更省"要等视频对比试验的结果，没测出来不说；测出来对我们不利的也照报。试验结果随模型变，对外只说"在某模型上测得"。不要讲成"又一个防止 AI 撒谎的工具"。

只讲做得到的：记录看过什么、算覆盖率、在 Kiro 里拦住自带的写文件工具和任务开工、其余情况事后标红。不说"不准写文件""换了工具关卡也还在""AI 只能经工具取材料""shell 写的文件也拦得住"（实测拦不住，`docs/验证结果.md` 第 8 项）。镜头只按硬切算，软切换里的画面在同一个镜头单元里，不说"看过每个画面"。RefCov 防偷懒和虚报，不防蓄意伪造记录。演示页和视频只展示严格模式。写文件关卡在仓库自己开发里的拦截是事先安排的，不说成"抓到"；意外抓到的是保护检查（`docs/关键时刻清单.md`）。

## 给谁用

- 用 AI 编程助手、并且给了它参考材料的开发者，例如拿参考视频做剪辑工具、拿 GIS 数据做分析的人。
- 比赛评委（Kiro 团队）：看在线演示页。

参赛类别：Kiroween 2026 Skeleton Crew。截止北京时间 2026-12-05 06:00。

## 必须有

1. 骨架：核心层（单元模型、读取记录、覆盖率、出处检查、开工凭证、报告、MCP 服务、文档适配器）+ Kiro 接入层。
2. 覆盖率计算。
3. 写文件关卡：三层，核心层达标判断（与工具无关，开工凭证只做记录）→ 钩子拦截 → 写入后记录。
4. 两个应用：`apps/shot-coverage`（参考视频，按镜头；证明拆和读，承担主要证据）和 `apps/layer-coverage`（地理数据，按图层属性；证明拦和出处）。
5. 在线演示页：回放真实会话记录，HTTPS，在线到 2027-01-29。
6. 需求出处检查：列出幻影需求、被忽略单元、幽灵单元；需求引用了没看过的单元就不达标（需求 6）。

power 打包：评估过，不做（`docs/冲刺计划.md` 第 6 节）；对照实验是"应该有"；抽查考试、Crew 面板页是"有余力"。详细需求见 `.kiro/specs/refcov-skeleton/requirements.md`；镜头应用的需求在 `.kiro/specs/shot-coverage/requirements.md`（第二稿，用户 2026-11-14 审阅）。分工、检查点和砍单顺序见 `docs/冲刺计划.md`。

## 范围冻结

**从 2026-11-13 起不加新功能。** 只做上面清单和已定稿规格里的内容。

开发中想到的新点子（包括用户随口提的、agent 自己想到的），不要动手做，记进 `docs/DEVLOG.md` 的"以后再做"一节：一行写点子，一行写为什么现在不做。用户明确说"这个现在就做"才例外，并在 DEVLOG 里记下这次例外。