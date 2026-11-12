# 需求文档：RefCov 骨架（第五稿，按外部审阅修订）

## 简介

RefCov 给参考材料算"覆盖率"：把参考材料拆成单元，记录 AI 实际取过哪些单元，按记录算出看过的比例。核心层给出与 AI 工具无关的达标判断，接入层据此拦截：在 Kiro 里，没看够就拦住写文件和任务开工。需求要标明出自哪个单元，程序检查没有出处的需求和没人引用的单元。

本规格只管**骨架**：

- **核心层**：参考源登记、适配器接口、读取记录、覆盖率、出处检查、开工凭证、报告、MCP 服务，再加一个文档适配器当入门示例。不出现任何 Kiro 专有的东西。
- **Kiro 接入层**：钩子配置和钩子脚本，只负责把 Kiro 的事件转给核心层。

视频应用、地理应用、power 打包、在线演示页、对照实验各有自己的规格，不在本文范围内。本文只保证它们需要的接口和数据格式。视频和地理适配器的单元类型声明写在各自应用的规格里。在线演示页和视频只展示严格模式。

骨架做好后，开发过程先用它管 agent 自己读比赛规则页和 Kiro 钩子文档。

每条需求末尾的"出处"写的是它来自哪份材料：

- "交接说明"：`d:\agent\kiro\kirohe\给Kiro的交接说明.md`（试验目录里，不进公开仓库）。
- "11-10 回复一"：用户 2026-11-10 对第一批开工问题的回复。
- "11-10 回复二"：用户 2026-11-10 对第一稿 7 个问题的回复。
- "第二稿审阅"：用户对第二稿的 10 条修改意见。
- "第三稿审阅"：用户对第三稿 6 个问题的回复。
- "第四稿审阅"：用户看过会话 ID 试验后对第四稿的修改意见（判断不按会话区分、合并重复、缩小范围）。
- "第五稿审阅"：用户对第五稿 3 个问题的回复。
- "外部审阅"：`docs/需求第五稿审阅.md`，按节号引用（A1、B1、C2 等）。
- "外部审阅回复"：用户 2026-11-10 对外部审阅的处理意见，按原消息的节号引用（"二·1"到"二·5"是用户的决定，"三"是照改清单，"四"是会话归属实测的要求）；"疑问 1"到"疑问 6"是用户对 agent 6 个疑问的回复。
- "分析"：对第五稿跑 Analyze Requirements 得到的问题和用户的选择，见 `docs/DEVLOG.md` 2026-11-10 的表（"分析 #1"到"分析 #11"）。
- "权限文档"：Kiro 文档 <https://kiro.dev/docs/permissions/>，2026-11-10 读。
- "实测"：`docs/验证结果.md` 和 `docs/DEVLOG.md` 2026-11-10 的记录。

骨架做好后，这些出处会改成按 RefCov 自己的出处写法引用单元 ID。用户在聊天里给的要求存成 `docs/decisions/` 下的文件再登记（需求 6.1）。各稿已确认的决定和本次的逐条改动记在 `docs/DEVLOG.md`。

## 术语

- **参考源（source）**：一份参考材料，例如一个网页、一段视频、一份地理数据文件。
- **单元（unit）**：参考源拆出来的最小可核对部分，例如文档的一个章节、视频的一个镜头、一个图层的坐标系。每个单元有稳定的 ID，生成规则见需求 2.5。
- **单元类型（unit kind）**：例如 `section`、`shot`、`crs`、`extent`、`fields`、`validity`、`sample`。
- **适配器（adapter）**：负责一种材料的代码，把参考源拆成单元、读出单元内容、给出单元里可核对的事实。
- **模式（mode）**：`strict`（严格）或 `light`（轻量），在配置文件里设置，默认 `strict`。
- **关键类型（key kind）**：适配器声明的、轻量模式下也必看的单元类型。
- **必看单元（required unit）**：在当前模式和配置下，达标前必须看过的单元。计算规则只有一条，见需求 5.1。
- **本模式未要求的单元**：当前模式下不在必看集合里的单元。
- **读取记录（read record）**：一条"某个会话在某个时间经 MCP 工具读过某个单元"的记录。
- **有效读取记录**：记录里的单元内容校验值和该单元当前的校验值一致。
- **覆盖率（coverage）**：看过的单元数 ÷ 单元总数。另算必看单元覆盖率。
- **幽灵单元（ghost unit）**：必看但一次都没被看过的单元。
- **被忽略单元（ignored unit）**：看过了，但没被任何需求引用的单元。
- **幻影需求（phantom requirement）**：没有标出处的需求。
- **无效引用（invalid reference）**：引用的参考源或单元不存在。
- **开工凭证（start token）**：达标时由核心层发出的记录，用于记录和演示。写文件和任务开工都不以持有凭证为前提（需求 7.5）。
- **关卡（gate）**：在某个时机检查是否达标，不达标就拦住的检查点。
- **状态目录**：RefCov 存放缓存、读取记录、凭证、日志的本地目录。写入规则见需求 14。
- **配置文件**：RefCov 的配置（模式、放宽项、豁免项、关卡范围、`enforce`）。修改规则见需求 14.2。
- **规格文件**：`.kiro/specs/` 下的文件。
- **代码文件**：除规格文件、豁免路径、状态目录、配置文件以外，所有受关卡管的文件。
- **接入层（integration）**：把某个 AI 编程工具的事件转给核心层的薄层。本项目只做 Kiro 接入层。

## 需求

### 需求 1：参考源登记和本地缓存
EN: Source registration and local cache

**用户故事：** 作为用户，我想登记参考材料并把原文缓存在本地，以便工具能拆单元，同时不把有版权的原文提交到公开仓库。
EN: As a user, I want to register reference material and cache the originals locally, so that the tool can split them into units without committing copyrighted originals to the public repo.

#### 验收标准

1. WHEN 用户登记一个参考源（本地文件路径或网址），THE 核心层 SHALL 把原文存到状态目录下的缓存目录，并在清单文件里记下：来源路径或网址、抓取日期、内容校验值（SHA-256）、所用适配器、拆出的单元 ID 和标题。
2. THE 骨架 SHALL 在仓库的 `.gitignore` 里忽略缓存目录，清单文件不忽略。
3. THE 骨架的 `.gitignore` SHALL NOT 忽略 `.kiro` 目录及其任何内容，并有一项自动检查验证这一点。
4. WHEN 某个参考源重新抓取后校验值变了，THE 核心层 SHALL 重新拆单元，内容变了的单元的旧读取记录不再有效。
5. IF 抓取或读取参考源失败，THEN THE 核心层 SHALL 报告失败原因，且不改动已有清单。

出处：11-10 回复一第 4 条；交接说明·比赛硬性要求（仓库根目录要有 `/.kiro`）；交接说明·核心功能 1。

### 需求 2：适配器接口
EN: Adapter interface

**用户故事：** 作为想支持一种新材料的开发者，我想只写很少的代码就接进来，以便骨架能扩展到视频、地理数据和以后的新材料。
EN: As a developer adding a new kind of material, I want to plug it in with very little code, so that the skeleton extends to video, GIS data and future materials.

#### 验收标准

1. THE 适配器接口 SHALL 不超过三个函数：拆成单元、读一个单元、给出这个单元可核对的事实。"读一个单元"的返回值 SHALL 能同时包含文字和图片（例如视频关键帧）。
2. THE 适配器 SHALL 声明自己有哪些单元类型，并为每种类型声明两项：严格模式下是否默认必看；是否关键类型（轻量模式下必看）。
3. THE 文档适配器的默认声明 SHALL 是：章节严格模式必看，没有关键类型。视频和地理适配器的默认声明写在各自应用的规格里，不在本文范围内。
4. THE 关键类型 SHALL 一定也是严格模式下必看的类型。
5. WHEN 同一份内容被拆两次，THE 适配器 SHALL 给出相同的单元 ID。单元 ID SHALL 由单元标题生成：保留原文字（含中日韩文字），把空白和方括号换成短横线；生成的 ID 已被占用时，依次加 `-2`、`-3`……直到不重复。单元 ID SHALL NOT 含空白和方括号；单元标题不受限制。
6. THE 核心层 SHALL 不依赖任何具体适配器；视频和地理适配器的依赖（ffmpeg、geopandas）SHALL 只出现在各自的应用里。

出处：[ref:dec-review-reply/三-照改的审阅条目] [ref:dec-questions-reply/疑问-2-单元-ID-保留中日韩文字]；交接说明·加强项 5；11-10 回复一第 3 条；第二稿审阅第 6、9 条；实测（MCP 返回的图片 agent 能看到）；外部审阅 A7、A8、A10。

### 需求 3：文档适配器
EN: Document adapter

**用户故事：** 作为用户，我想把文档按章节拆成单元，以便先拿规则页和钩子文档试用骨架，并在演示里一屏展示"支持一种新材料只要写这么多"。
EN: As a user, I want documents split into section units, so that I can try the skeleton on the rules page and hook docs first, and show on one screen how little code a new material needs.

#### 验收标准

1. WHEN 输入是 Markdown 文档，THE 文档适配器 SHALL 按标题拆成章节单元，单元标题取原标题；超长的章节按需求 3.5 拆成几个单元。
2. THE 文档适配器 SHALL 只用 Python 标准库。
3. THE 文档适配器的代码 SHALL 控制在 50 行左右（不含注释和空行），超出时在设计文档里说明原因。
4. IF 输入不是 Markdown（例如 HTML 网页、PDF），THEN THE 核心层 SHALL 在登记时拒绝，按需求 1.5 报告"不支持该格式"，不改动清单。网页要先转成 Markdown 再登记；有现成 Markdown 地址的直接登记那个地址（例如 Kiro 文档的 `https://kiro.dev/docs/hooks.md`）。
5. WHEN 一个章节超过长度上限，THE 文档适配器 SHALL 把它拆成几个单元：第一个沿用原标题和原 ID，后面的标题依次是"原标题 (2)""原标题 (3)"……，ID 是原 ID 加 `-2`、`-3`……，撞上已有 ID 时按需求 2.5 继续加后缀。长度上限在设计阶段定。
6. WHEN Markdown 文档里一个标题都没有，THE 文档适配器 SHALL 把整篇当成一个单元，标题取文件名；超长时按需求 3.5 拆分。

出处：[ref:dec-review-reply/三-照改的审阅条目] [ref:dec-questions-reply/疑问-4-超长章节拆分] [ref:dec-analysis-answers/分析-#3-不支持的格式]；交接说明·加强项 2、5；11-10 回复一第 3 条；第二稿审阅第 9 条；外部审阅 A9、C3。

### 需求 4：通过工具读取单元并记录
EN: Reading units through tools, with records

**用户故事：** 作为用户，我想让 AI 按单元取材料，并且每取一个就记一笔，以便覆盖率只根据记录算。
EN: As a user, I want the AI to fetch material unit by unit with a record for every fetch, so that coverage is computed from records only.

#### 验收标准

1. WHEN AI 通过 MCP 工具读取一个单元，THE 核心层 SHALL 返回单元内容（文字，以及适配器给出的图片），并追加一条读取记录：时间、单元 ID、单元内容校验值、本次调用的编号。会话 ID 由需求 4.5 补记。
2. （已删除：分页返回。改为拆单元时限制单元大小，见需求 3.5。出处：外部审阅 C3。）
3. THE 读取记录 SHALL 只追加、不修改，用 JSON Lines 存在状态目录里。每条记录 SHALL 带上一条记录的校验值，连成哈希链，报告里显示链是否完整（需求 12.2）。哈希链只能让随手追加或改动留下痕迹（需求 11.4）。
4. THE 读取记录 SHALL 包含回放所需的全部信息，供在线演示页按时间顺序重现每个单元何时被看。
5. WHEN Kiro 调用 RefCov 的 MCP 工具（钩子里的工具名形如 `mcp_refcov_<工具名>`），THE 接入层 SHALL 用挂在这些工具上的 PostToolUse 钩子，把钩子输入里的 `session_id` 补记到这次调用产生的读取记录或凭证上，按工具参数和返回内容对上是哪一次调用。补记是追加一条新记录，不改原记录（需求 4.3）。IF 某次调用没有对应的 PostToolUse 记录（例如钩子失效），THEN 这条记录的会话记为"未知"，报告里单独计数。会话 ID 只用于显示、记录和回放（需求 5.7），不参与达标判断。不再使用"当前会话"文件。
6. THE 读取记录 SHALL 记下每次送出的文字单元数和图片数，供对照实验估算额度（需求 17.3）。
7. WHEN AI 绕开 MCP 工具直接读参考文件（例如 Kiro 的 `read_file` 或 shell 命令），THE 核心层 SHALL 不把它算作看过，也不为此增加读取记录。
8. THE 核心层 SHALL NOT 根据 AI 的文字自述增加读取记录。

出处：[ref:dec-review-reply/三-照改的审阅条目] [ref:dec-review-reply/四-实测-MCP-工具的-PostToolUse] [ref:dec-questions-reply/疑问-3-哈希链的说法]；交接说明·核心功能 2；交接说明·仓库结构（在线演示页回放真实会话记录）；第二稿审阅第 6 条；第三稿审阅第 1、4 条；第四稿审阅；实测（MCP 服务拿不到会话 ID，多个会话共用一个 MCP 进程；MCP 工具的 PostToolUse 每次触发并带准确会话 ID 和参数）；外部审阅 B1、B6、C3。

### 需求 5：覆盖率和必看策略
EN: Coverage and the required-unit policy

**用户故事：** 作为用户，我想默认要求看完全部单元，并能按需放宽，以便严格是默认值，放宽是有意的选择。
EN: As a user, I want every unit required by default with optional relaxations, so that strict is the default and relaxing is a deliberate choice.

#### 验收标准

1. THE 核心层 SHALL 按下面这一条规则算必看集合，两种模式都用：
   - 必看集合 = 基础集合 − 放宽项 + 被需求引用的单元。
   - 基础集合：严格模式下是各适配器声明为严格模式必看的类型的单元；轻量模式下是所有参考源中关键类型的单元（需求 15.2）。
   - 被需求引用的单元：需求文档里的有效引用指向的单元，含可选类型（例如样本行）。被需求引用的单元永远必看，放宽项移不掉它们。
2. THE 其他条文说到必看集合时 SHALL 一律指需求 5.1 的结果，不另定规则（需求 6.5、15.2、16.3 引用本条）。
3. WHERE 用户在配置文件里放宽某个参考源、某种单元类型或某个单元，THE 核心层 SHALL 在两种模式下都按需求 5.1 把它们移出基础集合，并在报告里列出所有放宽项。放宽项只能缩小必看集合；在放宽范围内但被需求引用的单元仍然必看，报告里注明。
4. THE 核心层 SHALL 只根据有效读取记录计算覆盖率和必看覆盖率。
5. THE 覆盖率 SHALL 在 0% 到 100% 之间；同一单元被读多次只算一次。
6. WHEN 必看单元全部看过，THE 核心层 SHALL 判定达标；否则判定不达标并列出还差的必看单元。
7. THE 核心层 SHALL 认所有会话的有效读取记录。覆盖率、达标、发凭证、任务开工检查都不按会话区分。报告和 UserPromptSubmit 那一行 SHALL 同时显示"本会话看过"和"历史上看过"两个数（需求 9.8、12.2），这两个数只用于显示。

出处：[ref:dec-review-reply/二·3-本会话和历史两个数] [ref:dec-review-reply/三-照改的审阅条目] [ref:dec-analysis-answers/分析-#10-放宽项的方向]；11-10 回复一第 3 条；11-10 回复二第 2 条；第二稿审阅第 9 条；第四稿审阅；第五稿审阅第 2 条；交接说明·核心功能 2；外部审阅 A3、A10、B6。

### 需求 6：需求出处检查
EN: Requirement citation checks

**用户故事：** 作为用户，我想让规格里每条需求标明出自哪个单元，并检查出幻影需求和被忽略单元，以便需求真的来自我给的材料。
EN: As a user, I want every requirement in a spec to cite the unit it came from, with phantom requirements and ignored units detected, so that requirements really come from the material I supplied.

#### 验收标准

1. THE 骨架 SHALL 定义一种在需求文档里标注出处的写法（引用单元 ID），并写进引导文档。用户在聊天里给的要求 SHALL 这样当出处：每次回复存成 `docs/decisions/` 下的一个 Markdown 文件，一条意见一个小标题，登记成参考源，按普通单元引用，不另设出处类型。文件进公开仓库，存之前先给用户过目。
2. WHEN 检查一份需求文档，THE 核心层 SHALL 列出没有标出处的需求，标为幻影需求。
3. WHEN 检查一份需求文档，THE 核心层 SHALL 列出看过但没被任何需求引用的单元，标为被忽略单元；必看但从没看过的单元标为幽灵单元。
4. WHEN 某条需求引用了不存在的单元 ID，THE 核心层 SHALL 把这条引用标为无效。
5. WHEN 某条需求引用了没有有效读取记录的单元，THE 核心层 SHALL 判定不达标。两种模式都适用。下面三个入口 SHALL 都按这一条判断，各自独立执行，缺一不可：申请开工凭证（需求 7.2）、写文件关卡（需求 9.1）、任务开工关卡（需求 9.6）。
6. WHILE 模式是 `strict`，WHEN 需求文档里有幻影需求或无效引用，THE 核心层 SHALL 判定不达标。WHILE 模式是 `light`，THE 核心层 SHALL 只在报告里列出，不影响达标。过渡期的文字出处报为"未转换"，不算幻影需求。
7. WHEN 写入目标是规格文件，THE 核心层 SHALL NOT 因需求 6.6 判定不达标。否则要补出处时，写需求文档本身会被拦住，AI 无路可走。写规格文件仍按需求 6.5 和 8.4 判断。

出处：[ref:dec-review-reply/二·2-幻影需求和无效引用影响达标；聊天要求怎么当出处] [ref:dec-analysis-answers/分析-#5-各关卡独立判断]；交接说明·核心功能 3（优先保证）；交接说明·加强项 6；第二稿审阅第 9 条；外部审阅 A6、A10。

### 需求 7：开工凭证（记录用）
EN: Start tokens (for records)

**用户故事：** 作为用户，我想让核心层给出与 AI 工具无关的达标判断和凭证，接入层据此拦截，以便换用别的 AI 工具时只需重写接入层，并且每次达标都留下可回放的记录。
EN: As a user, I want the core to produce a tool-independent pass/fail decision and tokens that the integration layer enforces, so that switching AI tools only means rewriting the integration layer and every pass leaves a replayable record.

#### 验收标准

1. WHEN AI 通过 MCP 工具申请开工凭证且达标，THE 核心层 SHALL 发出凭证，凭证记下：发放时间、模式、当时依据的单元及其校验值、当时配置文件的修改时间、会话 ID（按需求 4.5 补记）。会话 ID 只用于日志和回放，不参与任何判断。
2. WHEN AI 申请开工凭证但不达标，THE 核心层 SHALL 拒绝发放，并返回还差的单元 ID 和标题。
3. THE 核心层 SHALL 按需求 5.6 判断是否达标，并做需求 6.5、6.6 的检查。
4. WHEN 下列任一情况发生，THE 核心层 SHALL 让凭证失效：凭证所依据的单元内容变了；登记了新的参考源；配置文件在发证之后被修改。
5. THE 写文件关卡和任务开工关卡 SHALL 在检查时按目标路径或任务现算是否达标（需求 8.1、9.1、9.6），不以是否持有凭证为准。凭证只用于记录和演示。
6. THE 凭证的发放和达标判断 SHALL 不依赖钩子；拦截依赖接入层。

出处：[ref:dec-review-reply/二·5-钩子写入时现算是否达标] [ref:dec-review-reply/三-照改的审阅条目]；交接说明·第一步的补充（关卡做成三层，第 1 层）；交接说明·加强项 7；11-10 回复二第 2 条；第二稿审阅第 7 条；第四稿审阅；外部审阅 A1、A4。

### 需求 8：关卡范围规则
EN: Gate scope rules

**用户故事：** 作为用户，我想规定"写哪些文件之前要看完哪些参考源"，以便例如写钩子代码之前必须先看完钩子文档。
EN: As a user, I want to define which sources must be read before which files are written, so that, for example, hook code cannot be written before the hook docs are read.

#### 验收标准

1. THE 配置文件 SHALL 能把目标路径的匹配模式对应到需要看完的参考源，写文件关卡按这个对应关系现算是否达标。
2. WHERE 没有为某个路径配置规则，THE 核心层 SHALL 要求全部参考源达标。
3. THE 核心层 SHALL 默认豁免 `DEVLOG.md` 和 `docs/decisions/**`；用户可以在配置里增减豁免路径，报告里列出全部豁免项。豁免的意思是"写这个文件不检查是否达标"。
4. WHILE 模式是 `strict`，THE 核心层 SHALL NOT 默认豁免规格文件；按目标路径判断不达标时，写需求文档也要被拦。
5. WHEN 关卡判断某次写入，THE 核心层 SHALL 只根据目标路径判断，不看写入的正文。

出处：[ref:dec-review-reply/二·2-幻影需求和无效引用影响达标；聊天要求怎么当出处] [ref:dec-review-reply/二·5-钩子写入时现算是否达标] [ref:dec-analysis-answers/分析-#4-严格模式下写需求文档] [ref:dec-analysis-answers/分析-#4-附：默认豁免]；交接说明·加强项 2；11-10 回复二第 5 条；第二稿审阅第 1、9 条；实测（钩子看到整段输入，正式关卡只能按 `path` 判断）；外部审阅 A4。

### 需求 9：Kiro 接入层的关卡钩子
EN: Gate hooks in the Kiro integration layer

**用户故事：** 作为用户，我想在 Kiro 里自动拦住没看够材料时的写文件和任务开工，以便 AI 没看够就动不了手。
EN: As a user, I want Kiro to automatically block file writes and task starts while required material is unread, so that the AI cannot act before reading enough.

#### 验收标准

1. WHEN Kiro 调用 `fs_write`、`str_replace` 或 `fs_append`，且目标路径不是豁免路径，且按目标路径判断不达标（需求 8.1；规则同需求 5.6、6.5、6.6、6.7），THE 接入层 SHALL 用退出码 2 拦截，并在 stderr 写明还差哪些单元，或有哪些幻影需求和无效引用。
2. （已删除：shell 受控命令关卡。出处：外部审阅 C2。）
3. （已删除：RefCov 只读命令的豁免，随 9.2 删除。）
4. （已删除：MCP 服务和钩子脚本不受受控命令检查影响，随 9.2 删除。）
5. THE 接入层的钩子 SHALL 用精确工具名匹配，不用类别名。
6. WHEN Kiro 触发 PreTaskExec，THE 接入层 SHALL 按 `spec_name` 给出的 tasks.md 路径和 `task_name` 找到这个任务，收集它直接引用的单元和它引用的需求所标的单元。这些单元中有任何一个没有有效读取记录，或者按需求 6.6 不达标，就用退出码 2 拦截，并在 stderr 列出要读的单元。IF 找不到对应任务，THEN THE 接入层 SHALL 放行（退出码 0），把"任务未找到，未检查"记进日志，并在报告里单独列出。匹配任务时 SHALL 忽略状态标记（`[ ]`、`[~]`、`[x]`）和首尾空白。
7. WHEN PreTaskExec 拦截了一个任务，THE 接入层 SHALL 在 stderr 里提醒用户：这个任务在 tasks.md 里会停在"进行中"，读完再点 Start task 前可能要手动改回未开始；接入层 SHALL NOT 自己改 tasks.md。
8. WHEN 用户发送消息，THE 接入层 SHALL 通过 UserPromptSubmit 钩子把一行简短报告写到 stdout（退出码 0）：当前模式、必看单元里本会话看过和历史上看过的数量、是否达标、还差的必看单元数和其中前 5 个。
9. THE 第 1、6 条的拦截原因和第 8 条的输出 SHALL 都附一句提示：参考材料要用 RefCov 的 MCP 工具读，直接读文件不算看过（需求 4.7）。
10. THE 接入层 SHALL 只做事件转换和退出码映射，判断逻辑全部在核心层。

出处：[ref:dec-review-reply/二·3-本会话和历史两个数] [ref:dec-review-reply/二·5-钩子写入时现算是否达标] [ref:dec-review-reply/三-照改的审阅条目] [ref:dec-analysis-answers/分析-#6-找不到任务]；交接说明·核心功能 4；交接说明·第一步的补充第 1–4 条；11-10 回复二第 2、4 条；第二稿审阅第 5、7 条；第四稿审阅；实测（只有退出码 2 能拦；UserPromptSubmit 的 stdout 能到 agent；PreTaskExec 能拦且 stderr 原样显示，`task_name` 不含子项，`spec_name` 是 tasks.md 路径，被拦任务停在 `[~]`）；外部审阅 A4、A10、C2。

### 需求 10：写入后记录（第 3 层）
EN: Post-write records (layer 3)

**用户故事：** 作为用户，我想在钩子漏拦时也能事后发现没看够材料时写过的文件，以便钩子无声失效时不被蒙在鼓里，同时不丢我的文件。
EN: As a user, I want writes made while material was unread to be found afterwards even if a hook missed them, so that a silently failing hook does not leave me unaware, and no file of mine is lost.

#### 验收标准

1. WHEN 接入层收到写文件工具的 PostToolUse 事件，且写入时按目标路径判断不达标，THE 核心层 SHALL 记下这次写入，并在报告里标红。IF 判断不了写入时是否达标（例如检查本身出错），THEN THE 核心层 SHALL 照样记下并标红，标为"无法判断"，不写成"不达标"。
2. THE 骨架 SHALL NOT 自动恢复或删除任何文件。
3. WHEN 接入层收到文件保存事件，且分不清是用户手动保存还是 AI 写入，THE 核心层 SHALL 只记录，在报告里标为"来源不明"，不标红。用户自己保存文件 SHALL NOT 被记成没看够材料时的写入。

出处：[ref:dec-review-reply/二·5-钩子写入时现算是否达标] [ref:dec-analysis-answers/分析-#2-用户手改不受保护影响] [ref:dec-analysis-answers/分析-#7-写入后判断不了是否达标]；交接说明·第一步的补充（关卡第 3 层）；第二稿审阅第 1、2 条；实测（写文件钩子第一轮无声失效）；外部审阅 A4。

### 需求 11：安全设计
EN: Safety design

**用户故事：** 作为用户，我想让这个工具自己出错时不卡住我，被反复拦时让 AI 停下来问我而不是自动放行，以便它帮忙而不添乱，也没法被硬闯。
EN: As a user, I want the tool to stay out of my way when it fails itself, and to make the AI stop and ask me after repeated blocks instead of letting it through, so that it helps without getting in the way and cannot be forced past by retries.

#### 验收标准

1. IF 核心层或接入层脚本自身出错，THEN THE 接入层 SHALL 放行（退出码 0），把错误写进状态目录里的日志，且不把报错内容写到 stdout。需求 14 的保护除外：它出错时拦截（见需求 14.5）。
2. WHEN 同一会话里对同一目标（写文件的路径，或任务）第 2 次及以后被拦，THE 接入层 SHALL 在拦截原因里加一句"停下来，向用户说明情况"。THE 接入层 SHALL NOT 因为拦截次数多而放行；用户要放行，自己把 `enforce` 改成 `false`（需求 17.1）。
3. THE 接入层脚本 SHALL 按字节读 stdin 并按 UTF-8 解码，stdout 和 stderr 强制 UTF-8 输出。
4. THE 项目文档 SHALL 写明以下局限：
   - 覆盖率证明"看过"，不证明"看懂"。
   - 本工具防的是偷懒和虚报，不防蓄意伪造记录的 AI。AI 有 shell，能读写磁盘上任何文件。读取记录的哈希链（需求 4.3）和 shell 命令的文本匹配（需求 14.4）只能让随手追加或改动留下痕迹、挡住顺手的修改，文本匹配也会有漏网。
   - 钩子可能无声失效（实测第一轮出现过）。
   - 钩子配置不受需求 14 保护，依赖 Kiro 自己的规定：AI 用写文件工具写 `.kiro/hooks/` 时，Kiro 每次都要用户确认，任何配置都去不掉这一步（权限文档"Always asks"；托管云沙箱里有例外，本地 IDE 不适用）。用 shell 命令写这个目录会不会也要确认，文档没写，没测。接入层脚本按普通代码文件走关卡；钩子配置和接入层脚本的变化在报告里标红（需求 12.2）。
   - 用 shell 命令写文件（例如 `Set-Content`、`echo >`）可能拦不住，只能靠第 3 层事后记录发现。
   - 需求 14.5 管不到解释器启动失败的情况（例如 Python 没装、脚本有语法错误）：这时退出码不是 2，拦不住。
   - 直接读参考文件（`read_file` 或 shell 命令）不算看过，只有经 MCP 工具读取才计入覆盖率。所以 AI 直接读过的材料还得用工具再读一遍才能达标，覆盖率只会少算，不会多算。

出处：[ref:dec-review-reply/二·1-取消第三次自动放行] [ref:dec-review-reply/三-照改的审阅条目] [ref:dec-questions-reply/疑问-1-钩子配置不加进需求-14] [ref:dec-questions-reply/疑问-3-哈希链的说法]；交接说明·核心功能 5；11-10 回复二第 7 条；第二稿审阅第 3、4 条；第四稿审阅；实测（Windows 编码问题；退出码 1 的报错被送进上下文）；外部审阅 A2、A9、B1、B2；权限文档。

### 需求 12：覆盖率报告
EN: Coverage report

**用户故事：** 作为用户，我想随时看到一份覆盖率报告，以便知道看了多少、差什么、被拦过几次。
EN: As a user, I want a coverage report on demand, so that I know how much was read, what is missing, and how often the AI was blocked.

#### 验收标准

1. THE 核心层 SHALL 通过命令行和 MCP 工具两种方式给出报告。
2. THE JSON 报告 SHALL 包含：当前模式；每个参考源的覆盖率和必看覆盖率，各给本会话和历史两个数；幽灵单元；本模式未要求的单元（单独列出，不算达标，不计入幽灵单元数）；被忽略单元；幻影需求；无效引用；放宽项（含在放宽范围内但被引用、仍然必看的单元）和豁免项；配置文件最后修改时间；凭证发放和失效记录；拦截记录；没看够材料时发生的写入（含"无法判断"和"来源不明"）；"任务未找到，未检查"的任务；需求 14 的保护拦下的每次写入和命令；读取记录的哈希链是否完整；钩子配置文件和接入层脚本的校验值，和上一次报告相比有变化的标红。各类记录覆盖全部历史，每条带时间和会话 ID。
3. THE JSON 报告 SHALL 是唯一的数据源；给人看的文字版由它生成，两者内容一致。
4. THE 文字版 SHALL 有一个一行的简短形式，供 UserPromptSubmit 钩子使用（内容见需求 9.8）。

出处：[ref:dec-review-reply/二·1-取消第三次自动放行] [ref:dec-review-reply/二·3-本会话和历史两个数] [ref:dec-review-reply/三-照改的审阅条目] [ref:dec-questions-reply/疑问-1-钩子配置不加进需求-14] [ref:dec-analysis-answers/分析-#9-报告覆盖的范围]；交接说明·核心功能 2、4；交接说明·仓库结构（在线演示页）；第二稿审阅第 2、3、9、10 条；外部审阅 B1、C6。

### 需求 13：不绑死 Kiro，依赖轻
EN: Not tied to Kiro, light dependencies

**用户故事：** 作为以后可能换用别的 AI 编程工具的用户，我想让核心层不依赖 Kiro，以便换工具时只写一个新的接入层。
EN: As a user who may switch AI coding tools later, I want the core to have no dependency on Kiro, so that switching tools only requires a new integration layer.

#### 验收标准

1. THE 核心层 SHALL NOT 出现 Kiro 专有的工具名、事件名或文件路径。
2. THE 核心层 SHALL 提供与工具无关的事件入口（读取、写入前检查、写入后记录、开工前检查、生成报告），接入层只调用这些入口。
3. THE 核心层的计算部分（单元模型、读取记录、覆盖率、出处检查、凭证）SHALL 只用 Python 标准库。
4. THE MCP 服务 SHALL 放在单独的模块里，使用官方 Python SDK（`mcp` 包）；运行时只有这个模块依赖第三方包。属性测试用的 Hypothesis 只是开发依赖，只有测试代码可以 import 它。
5. THE 核心层 SHALL 在 Windows 上运行，Python 版本不低于 3.11；持续集成里另在 Linux 上跑测试。

出处：[ref:dec-review-reply/三-照改的审阅条目] [ref:dec-analysis-answers/分析-#8-hypothesis-的-import]；交接说明·仓库结构（架构上的硬要求）；11-10 回复一第 3 条；11-10 回复二第 6 条；外部审阅 C5。

### 需求 14：保护状态目录和配置文件
EN: Protecting the state directory and the config file

**用户故事：** 作为用户，我想让 AI 改不了读取记录、凭证和配置，以便它没法顺手伪造"看过"或自己放宽关卡。
EN: As a user, I want the AI unable to change read records, tokens and config, so that it cannot casually fake "read" or loosen the gate itself.

本需求的保护一律生效：不看是否达标，不受豁免路径（需求 8.3）和 `enforce`（需求 17.1）影响。

#### 验收标准

1. WHEN Kiro 调用 `fs_write`、`str_replace` 或 `fs_append` 且目标路径在状态目录里，THE 接入层 SHALL 用退出码 2 拦截。
2. WHEN Kiro 调用 `fs_write`、`str_replace` 或 `fs_append` 且目标是配置文件，THE 接入层 SHALL 用退出码 2 拦截，并在 stderr 说明配置只能由用户手动修改。
3. THE 会写读取记录的入口 SHALL 只有两种：MCP 工具（按真实取出的单元记录），和由 Kiro 直接启动的钩子脚本。THE 核心层 SHALL NOT 把这类入口做成命令行子命令，也不提供让 AI 经 MCP 工具直接写读取记录、凭证或配置的入口。
4. WHEN Kiro 调用 shell 工具，且命令文本里出现状态目录路径、配置文件名、钩子脚本或其他会写记录的 RefCov 入口，THE 接入层 SHALL 用退出码 2 拦截。这是文本匹配，会有漏网（需求 11.4）。
5. THE 这几项保护 SHALL 只按目标路径或命令文本判断，放在接入层脚本的最前面，在加载其余核心代码之前完成。保护检查里的脚本内部异常 SHALL 一律按拦截处理（退出码 2），错误写到 stderr 和日志。解释器启动失败的情况管不到，写进局限（需求 11.4）。
6. THE 这几项保护 SHALL 只针对 AI 经 Kiro 工具发起的写入和命令。用户自己修改文件（不论在不在 Kiro 编辑器里）SHALL 无条件不受这些保护影响。

出处：[ref:dec-review-reply/三-照改的审阅条目] [ref:dec-analysis-answers/分析-#2-用户手改不受保护影响]；第二稿审阅第 1、2 条；第三稿审阅第 3、5 条；外部审阅 A9、B1。

### 需求 15：轻量模式
EN: Light mode

**用户故事：** 作为用户，我想在小任务上用轻量模式，只要求看需求里引用到的单元和关键单元，以便不为一点小改动读完全部材料，同时关键的坑（例如坐标系）仍然必看。
EN: As a user, I want a light mode for small tasks that only requires cited units and key units, so that a small change does not require reading everything while key pitfalls (such as the coordinate system) are still required.

轻量模式只影响必看集合的计算（需求 5.1），关卡在两种模式下行为相同。

#### 验收标准

1. THE 配置文件 SHALL 有 `mode` 项，取值 `strict` 或 `light`，默认 `strict`；修改规则见需求 14.2。
2. WHILE 模式是 `light`，THE 核心层 SHALL 把基础集合定为所有参考源中关键类型的单元，必看集合按需求 5.1 算。
3. （已删除：轻量模式下写规格文件不要求凭证。出处：外部审阅回复·二·4。）

出处：[ref:dec-review-reply/二·4-轻量模式的范围]；第二稿审阅第 9 条；第三稿审阅第 2 条；第四稿审阅；第五稿审阅第 2 条；外部审阅 C4。

### 需求 16：属性测试
EN: Property tests

**用户故事：** 作为用户，我想让核心计算有属性测试，以便关卡的结论在各种随机输入下都可信。
EN: As a user, I want property tests on the core calculations, so that gate decisions hold up under random inputs.

#### 验收标准

THE 核心层计算部分 SHALL 有用 Hypothesis 写的属性测试，至少覆盖以下性质：

1. 覆盖率和必看覆盖率始终在 0% 到 100% 之间。
2. 同一单元读多次只算一次：重复追加同一单元的读取记录，覆盖率不变。
3. 需求引用了没有有效读取记录的单元，一定判定不达标，不论放宽项怎么设（需求 5.1）。
4. 关卡结论只由读取记录和配置决定：输入里任意改动 AI 的文字（例如自述、写入正文），结论不变。
5. 同样的单元和配置下，轻量模式的必看集合一定是严格模式必看集合的子集。
6. 同样的记录下，严格模式达标，则轻量模式一定达标。

出处：交接说明·用 Kiro 功能时请注意（属性测试）；第二稿审阅第 8、9 条；外部审阅 A3。

### 需求 17：为对照实验留数据
EN: Data for the comparison experiment

**用户故事：** 作为用户，我想用两组（开关卡、不开关卡）对照实验比较效果，以便在提交材料里给出真实数字。
EN: As a user, I want a two-group comparison (gate on, gate off), so that the submission can report real numbers.

#### 验收标准

1. THE 配置文件 SHALL 有 `enforce` 项，默认 `true`；修改规则见需求 14.2。WHILE `enforce` 是 `false`，THE 核心层 SHALL 照常记读取记录和写入，写文件关卡和任务开工关卡一律放行；需求 14 的保护照常生效。
2. WHILE `enforce` 是 `false`，THE 文字报告第一行 SHALL 写"关卡已关闭"，JSON 报告 SHALL 有对应的标记。
3. THE 报告 SHALL 按会话给出每组需要的数字：看过的单元数、被拦次数、送出的文字单元数和图片数（需求 4.6）。
4. 用掉的额度不由 RefCov 计算，由用户从 Kiro 的用量界面手动抄下。实验只做两组：严格模式下 `enforce: true` 和 `enforce: false`。实验本身的任务、数据和脚本放在单独的规格里。

出处：[ref:dec-review-reply/二·4-轻量模式的范围] [ref:dec-analysis-answers/分析-#11-enforce-为-false]；第二稿审阅第 10 条；第三稿审阅第 4、6 条；交接说明·加强项 4；外部审阅 C4。
