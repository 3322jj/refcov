# 需求文档：镜头覆盖率应用 `apps/shot-coverage`（第二稿，2026-11-14 已按用户审阅修订）

EN summary: Draft requirements for the shot-coverage app, which proves "split and read" on a long reference video: ffmpeg scene detection splits the video into shot units, `read_unit` returns a keyframe image per shot, reads are recorded, and a shot strip shows which shots were read. The video is not registered itself: an app command runs scene detection once and writes a small Markdown shot list (video path, SHA-256, size, mtime, parameters, one section per shot), and the user registers that list with `refcov add --adapter shot`. Part 2 lists the changes this needs in the frozen core layer (`refcov/`, `refcov_mcp/`, `integrations/kiro/hook.py`): C1–C4 and C6 approved, C5 dropped. Status: second draft, 2026-11-14, revised after the user's review of checkpoints 1 and 3.

状态：**第二稿，2026-11-14**。检查点 1（应用需求）和检查点 3（动核心层）已由用户审阅：核心层批 C1、C2、C3、C4、C6，C5 不做、换成镜头清单；其余决定见末尾"已定和还没定的"。下一步：按 C1 → C2 → C3 做，用真实关键帧测过之后再做 C4、C6 和镜头适配器；适配器的设计文档写完后停一次给用户看。

## 简介

镜头覆盖率给一段长参考视频算"看过多少"：用 ffmpeg 场景检测把视频切成镜头单元，AI 经 MCP 工具按镜头读，每次读返回一张关键帧图片并记一笔，页面上用一排格子显示哪些镜头读过。它在整体讲法里负责"拆和读"，是视频对比试验的被测应用（`docs/应用定位和陷阱试验.md` 第 4 节）。

不做：理解画面内容的模型、剪辑功能、OCR。关键帧是给 AI 自己看的，应用不替它读画面。在线演示页另有规格。

**这份文档写的是需求，不是设计**：数字（阈值、关键帧尺寸、张数）都是初值，设计阶段用 EP01 实测后定。

## 术语

- **镜头（shot）**：两个硬切之间的一段。本应用的单元类型 `shot`。
- **硬切**：ffmpeg 场景检测（`select='gt(scene,T)'`）抓到的画面突变。推近、淡入淡出这类软切换大多检测不到（EP01 的标准答案里 65 处切换点只有 43 处是硬切，见 DEVLOG 2026-11-14），所以镜头单元 = 硬切镜头，**不是**每一个画面变化。
- **关键帧**：一个镜头里取出来给 AI 看的静态图片（JPEG）。
- **镜头清单**：应用对视频跑一次场景检测后生成的 Markdown 文件 `<视频名>.shots.md`：文件开头记视频的相对路径、SHA-256、大小、修改时间和检测参数，之后每个镜头一节，写起止时间。用户把**清单**（不是视频）登记成参考源；骨架的登记和读取主路径不改（2026-11-14 用户定，取代初稿的 C5）。
- **镜头条**：一排格子，一格一个镜头；读过的亮，没读的灰，被需求或剪辑方案引用的带标记（`docs/应用定位和陷阱试验.md` 第 7 节）。
- 其余术语沿用 `.kiro/specs/refcov-skeleton/requirements.md` 的术语表。

## 第一部分：应用本身

### 需求 1：把视频切成镜头单元
EN: Splitting a video into shot units

**用户故事：** 作为用户，我想把一段长视频自动切成镜头，以便 AI 不用自己发明切分工具，也能按镜头读完整段视频。
EN: As a user, I want a long video split into shots automatically, so that the AI does not have to invent its own splitting tool and can read the whole video shot by shot.

#### 验收标准

1. WHEN 用户对一个视频文件运行应用的检测命令（初值：`shot-coverage detect <视频>`），THE 应用 SHALL 用 ffmpeg 场景检测切出镜头，生成镜头清单 `<视频名>.shots.md`（默认放在视频旁边，可用参数改位置）。镜头首尾相接、覆盖整段视频，没有空隙和重叠。场景检测只在这一步跑一次。
2. THE 镜头清单 SHALL 这样组织：第一个镜头之前是文件头，记视频的路径（相对仓库根目录；视频在仓库外时用绝对路径）、视频的 SHA-256、大小（字节）、修改时间、时长、检测参数（阈值、最短镜头时长）；之后每个镜头一个二级标题小节，标题就是镜头 ID，小节里写起止时间（秒，保留一位小数）。镜头适配器拆清单时，每个镜头小节是一个 `shot` 单元；文件头不是单元。
3. THE 单元 ID SHALL 由镜头起点的时间码生成，精确到 0.1 秒，例如起点 31.2 秒的镜头 ID 是 `shot-00-31-2`（格式：`shot-<分>-<秒>-<十分之一秒>`，分钟超过两位时照常多写），标题与 ID 相同。ID 不含空白和方括号（骨架需求 2.5）。
4. WHEN 同一个视频用同样的参数检测两次，THE 应用 SHALL 给出相同的 ID 和边界；WHEN 同一份清单拆两次，THE 镜头适配器 SHALL 给出相同的 ID（骨架需求 2.5）。
5. THE 场景检测阈值和最短镜头时长 SHALL 有默认值（初值：阈值 0.25，最短 0.5 秒，比最短还短的镜头并入前一个），并写进清单文件头，使清单能说明"这些镜头是按什么参数切出来的"。
6. THE `shot` 类型 SHALL 声明为严格模式必看，不设关键类型（骨架需求 2.2、2.4）。
7. WHEN 检测出的镜头数少于 2 或多于 300，THE 检测命令 SHALL 仍然生成清单，但提示"镜头数异常，检查阈值"。（上限 300 是初值。）
8. THE 项目文档（README 和镜头条页面） SHALL 写明局限：只切硬切，软切换（推近、淡入）里的内容在同一个镜头单元里，读了这个单元的关键帧不等于看过该镜头里的每个画面；一个镜头一张关键帧，看不到镜头里随时间出现的字。
9. THE README SHALL 另写一条局限：适配器文件是普通代码，改它的 `kinds` 声明能缩小必看集合；这和改核心层代码同类，属于"不防蓄意伪造"（骨架需求 11.4）。（用户 2026-11-14 审阅补）
10. THE 适配器文件 SHALL 在被导入时不做任何耗时的事（不调 ffmpeg、不算哈希、不读视频），因为写文件关卡的每次检查都会经 `_decls` 加载它；测试要守住这一点。（用户 2026-11-14 审阅补）

出处：定位文档第 4 节（镜头适配器：用 ffmpeg 场景检测切镜头，单元 ID 按时间码）；定位文档第 9 节第 3 条（照实报告）；DEVLOG 2026-11-14（判分口径补充：43 处硬切、22 处软切换）。

### 需求 2：读一个镜头：文字加关键帧
EN: Reading one shot: text plus keyframes

**用户故事：** 作为用户，我想让 AI 读一个镜头就能看到这个镜头的画面，以便它按镜头读完视频，不用自己抽帧。
EN: As a user, I want the AI to see a shot's picture when it reads that shot, so that it can read a video shot by shot without extracting frames itself.

#### 验收标准

1. WHEN AI 经 `read_unit` 读一个 `shot` 单元，THE 应用 SHALL 返回：一段文字（镜头编号、起止时间、时长、总镜头数）加关键帧图片。文字里不放任何对画面内容的描述。
2. THE 关键帧 SHALL 先定为每镜头 1 张，取镜头中点（用户 2026-11-14 定）。要不要给长镜头加第 2 张，等真实关键帧测过额度后再定。
3. THE 关键帧 SHALL 缩小到不超过 960 像素宽、JPEG 格式、质量固定，使单张约 50–150 KB。（尺寸和质量是初值，设计阶段按"读得清画面文字"和"额度"两头实测后定。）
4. THE 应用 SHALL 现取现用：读的时候才用 ffmpeg 从原视频按时间点取帧，不存盘，也不进缓存目录（需求 3.3、第二部分 C5）。
5. IF ffmpeg 找不到或取帧失败，THEN THE 应用 SHALL 报告原因，不返回内容，也不留读取记录（骨架需求 4.1 的"少算不多算"）。
6. THE 读取记录 SHALL 记下这次送出的图片张数（骨架需求 4.6）。

出处：定位文档第 4 节（"一个单元：起止时间、一张关键帧（必要时首尾各一张）"）；`docs/验证结果.md` 第 4 项、第 9 项（MCP 图片在 IDE 和 CLI 里都能送达，但只测了小图）；骨架需求 4.1、4.6。

### 需求 3：单元校验值要覆盖画面
EN: Unit checksums must cover the picture

**用户故事：** 作为用户，我想在视频文件换了之后，旧的读取记录自动失效，以便覆盖率不会把"看过旧视频"算成"看过新视频"。
EN: As a user, I want old read records to become invalid when the video file changes, so that coverage never counts having seen the old video as having seen the new one.

#### 验收标准

1. THE 镜头单元的校验值 SHALL 由"视频文件的 SHA-256、镜头起止时间、检测参数"算出（适配器把这三样拼成单元的 `text`，核心层照常对它取 SHA-256）。视频文件变了，重新检测、重新登记后所有镜头的校验值都变，旧读取记录全部失效（骨架需求 1.4）。
2. THE 视频文件的 SHA-256 SHALL 在检测时算一次，写进镜头清单文件头；读取时不是每次都重算（941 MB 的文件算一遍要几秒，每读一个镜头算一次不可接受）。
3. THE 应用 SHALL NOT 把原视频复制进缓存目录。核心层的缓存里只有镜头清单（几 KB）；读的时候原视频必须还在清单记的路径上，不在就报错并提示重新检测和登记。（理由：对比试验的运行文件夹是复制模板建出来的，缓存里放 941 MB 会被复制到每一次运行里。）
4. WHEN AI 读一个镜头，THE 镜头适配器 SHALL 先比较视频文件当前的大小和修改时间与清单文件头是否一致。一致才取关键帧；不一致就重算视频的 SHA-256，和清单对不上就**拒绝读取，不返回内容，不留读取记录**（骨架需求 4.1 的"少算不多算"），提示重新检测和登记；重算后对得上（只是修改时间变了，例如复制过）就放行。

出处：定位文档第 4 节（对比试验的运行文件夹：材料用硬链接放进去）；骨架需求 1.4、4.1；DEVLOG 2026-11-13 夜（试验的布置：每次运行复制模板成新文件夹）。

### 需求 4：两步登记视频
EN: Two-step registration of a video

**用户故事：** 作为用户，我想先检测、再用同一个 `refcov add` 登记，以便不用学另一套登记命令，骨架的登记和读取主路径也不用改。
EN: As a user, I want to detect first and then register with the same `refcov add`, so that I do not learn a second registration command and the skeleton's registration and reading path stays unchanged.

#### 验收标准

1. THE 登记 SHALL 分两步：第一步 `shot-coverage detect <视频>` 生成镜头清单（需求 1.1）；第二步用户在终端运行 `refcov add <清单> --adapter shot --id <参考源ID>`。`refcov add` 登记的是清单，不是视频；清单是普通 `.md` 文件，要放在仓库里（骨架需求 1.1 的现有规则）。需要核心层支持 `--adapter`，见第二部分 C4。
2. THE `--adapter` SHALL 只在用户明确写出时才用；不写时照旧走文档适配器。不按扩展名自动选。
3. THE 视频文件 SHALL 可以放在仓库里被忽略的目录，也可以是硬链接，也可以在仓库外；不要求提交进公开仓库。
4. IF ffmpeg 或 ffprobe 不在 PATH 上，THEN `detect` SHALL 失败，消息写明缺哪个、怎么装，不生成清单。`refcov add` 登记清单不需要 ffmpeg；读取时才需要（需求 2.5）。
5. WHEN `detect` 成功，THE 命令 SHALL 打印镜头数、总时长、所用阈值、清单路径，以及下一步该运行的 `refcov add` 命令。
6. THE `detect` SHALL 在 8 分钟的 1080p 视频上用不超过 2 分钟完成（初值；实测定）。
7. WHEN 清单被重新检测覆盖后用户重新登记，THE 核心层 SHALL 按骨架需求 1.4 让旧读取记录失效（内容变了的单元）。

出处：用户 2026-11-14 对本需求初稿的审阅（C5 改为镜头清单）；定位文档第 4 节（对比试验：装了 RefCov 的一组"镜头适配器 + MCP + 钩子"）；骨架需求 1.1、1.4、1.5；`docs/冲刺计划.md` 第 4 节（11-24–26：镜头应用的适配器）。

### 需求 5：镜头条页面
EN: The shot strip page

**用户故事：** 作为用户，我想一眼看出哪些镜头读过、哪些没读，以便知道 AI 看了多少视频，也让视频和演示页有统一的视觉。
EN: As a user, I want to see at a glance which shots have been read and which have not, so that I know how much of the video the AI saw and the video and demo page share one visual language.

#### 验收标准

1. THE 应用 SHALL 生成一个单文件 HTML 页面（不联网；是否用脚本留给设计定，2026-11-14 用户定）：一排格子，一格一个镜头，宽度按镜头时长成比例；读过的亮，没读的灰，被需求或剪辑方案引用的带标记。
2. THE 页面的数据 SHALL 只来自核心层的 JSON 报告和 `list_units`，不另算覆盖率（覆盖率只根据读取记录算，骨架需求 5.4）。
3. THE 页面 SHALL 显示：读过的镜头数 / 总镜头数、图片张数（来自读取记录）、需求 1.8 的局限一句话。
4. THE 页面 SHALL 能读一份日志快照并按时间顺序回放，格子逐个亮起。回放用什么实现（CSS 动画、预先生成的静态帧或少量脚本）留给设计定。在线演示页复用这个页面（演示页另有规格）。
5. THE 页面 SHALL NOT 嵌入关键帧或视频画面。（参考视频里有真实公司名字，进公开页面前要人工挑选；见需求 7.4。）

出处：定位文档第 7 节（视觉语言：一排单元格子）；定位文档第 4 节（页面：镜头条）；骨架需求 5.4、12。

### 需求 6：和关卡配合
EN: Working with the gates

**用户故事：** 作为用户，我想让 AI 在没读完镜头之前不能写剪辑方案，以便"读了多少"是一个数字，而不是一句"我看过了"。
EN: As a user, I want the AI blocked from writing the edit plan until the shots are read, so that "how much was read" is a number and not a claim.

#### 验收标准

1. THE 应用 SHALL 不新增关卡逻辑：写 `edit-plan.md` 前要读完全部镜头，由骨架的写文件关卡和严格模式的必看规则完成（骨架需求 5.1、8、9）。本应用只提供单元和声明。
2. THE 应用的 README SHALL 给出让它跑起来的最短步骤：装 ffmpeg、`shot-coverage detect`、在配置里声明适配器、`refcov add --adapter shot`、MCP 配置、复制钩子。不用 power：评估过，不做（`docs/冲刺计划.md` 第 6 节）。
3. WHEN 全部镜头必看会让一次读取超过 AI 的承受（例如 100 个镜头），THE 用户 SHALL 能用骨架的放宽项（骨架需求 5.3）缩小必看范围；应用不自己放宽。

出处：定位文档第 4 节（装了 RefCov 的一组：写 `edit-plan.md` 前要读完全部镜头）；骨架需求 5.1、5.3、8、9；`docs/冲刺计划.md` 第 6 节（一键安装降级）。

### 需求 7：依赖边界、测试和素材
EN: Dependency boundary, tests and material

**用户故事：** 作为开发者，我想让 ffmpeg 只出现在这个应用里，并且测试不依赖真实素材，以便核心层保持只用标准库、CI 在 Linux 和 Windows 上都能跑。
EN: As a developer, I want ffmpeg to appear only in this app and the tests to avoid real footage, so that the core stays standard-library-only and CI runs on Linux and Windows.

#### 验收标准

1. THE ffmpeg 和 ffprobe SHALL 只在 `apps/shot-coverage` 里被调用；核心层和接入层不得 import 或假设它们已安装（`.kiro/steering/tech.md`）。已有的 `tests/test_core_names.py` 一类检查要覆盖这一条。
2. THE 单元测试 SHALL 用 ffmpeg 的合成源（`lavfi`，例如用 `color` 和 `testsrc` 拼出已知切点的几秒视频）现场生成测试视频，不把任何视频提交进仓库。
3. WHEN 测试环境没有 ffmpeg，THE 依赖 ffmpeg 的测试 SHALL 跳过并写明原因，CI 的 Linux 和 Windows 作业都装 ffmpeg 来跑它们。
4. THE 仓库 SHALL NOT 含 EP01（`reference.mp4`）的任何帧或截图，含真实公司名字；README 和页面的示例只用合成视频的镜头条。进参赛视频或演示页的画面要先挑过镜头。
5. THE 属性测试 SHALL 覆盖：镜头首尾相接且覆盖全片；同一视频同一参数拆两次结果相同；单元 ID 满足骨架需求 2.5。

出处：`.kiro/steering/tech.md`（ffmpeg 只在 `apps/shot-coverage`）；骨架需求 2.6、13、16；定位文档第 9 节第 5 条（EP01 有真实公司名字）。

### 需求 8：为对比试验留数据
EN: Data for the comparison trial

**用户故事：** 作为用户，我想在对比试验里直接拿到两组该比的数字，以便结果可信、可复核。
EN: As a user, I want the numbers the two trial groups are compared on straight from the records, so that the result is credible and reproducible.

#### 验收标准

1. THE 报告 SHALL 给出：必看镜头数、读过几个、送出的图片张数、被拦次数（骨架需求 17.3 已有，本应用不重复实现，只验证在视频上数得对）。
2. THE 应用 SHALL 提供一个小脚本，从运行文件夹的读取记录里数出"读过几个镜头、几张图"，供判分脚本使用（判分脚本和标准答案在仓库外，不进本规格）。
3. 试验的任务、判定规则、次数在跑之前写进 DEVLOG（`docs/冲刺计划.md` 第 10 节），不在本规格里定。

出处：定位文档第 4 节（对比试验：记有没有交出结果、用时、额度、看了多少镜头）；骨架需求 17.3、17.4；`docs/冲刺计划.md` 第 10 节。

## 第二部分：要动骨架核心层的部分

EN: Part 2: changes to the frozen core layer. Reviewed by the user on 2026-11-14: C1, C2, C3, C4 and C6 approved, C5 (registration and reading of large binary sources) not done and replaced by the shot-list design in requirement 4. Order: C1, C2, C3, then a real-keyframe test in the CLI and the IDE (item 10 of docs/验证结果.md); only if real keyframes arrive, C4, C6 and the shot adapter. Each change is its own commit with all existing tests passing.

冲刺计划预计只动两处：`api.read` 和 `read_unit` 返回图片。读代码后发现核心层现在只能登记和读 UTF-8 的 Markdown，初稿列了六处。**用户 2026-11-14 审阅结论：批 C1、C2、C3、C4、C6；C5 不做**，换成"镜头清单"方案（需求 1、3、4）：视频不进核心层，核心层登记的是一份小 Markdown。逐处写清：为什么要动、动哪里、怎么测、风险。

范围保证：核心层仍只用标准库；不 import 任何适配器和 ffmpeg（骨架需求 2.6、13.4）；文档适配器的行为和现有测试一律不变。

### C1：`api.read` 真的调用适配器的 `read`，并记下图片张数

**为什么：** 适配器接口的 `read(data, name, unit_id)` 能返回文字和图片（`refcov/sources.py` 的 `Image`，骨架需求 2.1），但 `api.read` **从来没调用过它**：它在 `split` 的结果里取单元，`texts = [found.text]`，读取记录的 `images` 写死为 0，返回的 `ReadResult.images` 写死为 `[]`。

**动哪里：** `refcov/api.py` 的 `read()`（调用 `adapter.read`，把返回列表里的 `str` 放进 `texts`、`Image` 放进 `images`；`images=len(images)`、`text_units=len(texts)` 写进记录；`ReadResult.images` 填上）。`ReadResult` 的字段已有 `images`，不用改类型。**`adapter.read` 要在拿日志锁、追加记录之前调用**：适配器抛任何异常（视频改了、ffmpeg 取帧失败）都转成 `ReadError`，不返回内容、不写记录（需求 2.5、3.4）。

**怎么测：**
- 现有测试不改一行就要继续过：`tests/test_api.py` 里 `r.images == []` 和记录里 `"images": 0` 对文档适配器仍成立。
- 新测试：用一个假适配器（测试里现造，返回一段文字加两个 `Image`）登记并读，断言 `ReadResult.images` 有两张、记录里 `images == 2`、`text_units == 1`、哈希链完整、报告的"图片 N 张"对得上（`coverage.py` 已经在累加 `images`）。
- 假适配器的 `read` 抛异常时：抛 `ReadError`、日志不多一行、哈希链不变。
- `text()` 仍以 `refcov-call:` 行结尾（设计 5），图片不进这段文字。

**风险：** 低。文档适配器的 `read` 现在每次重新 `split` 一遍再取单元；改成调用 `read` 后，结果必须和现在逐字相同（上面第一条测试守住）。

### C2：MCP 的 `read_unit` 把图片一起送出去

**为什么：** `refcov_mcp/server.py` 的 `read_unit` 返回 `str`，图片到不了 AI。

**动哪里：** 只改 `read_unit`：返回"一个文字块 + 若干图片块"（官方 SDK 的 FastMCP 支持返回含 `Image` 的列表）。文字块仍是 `api.read(...).text()`，`refcov-call:` 仍是文字块的最后一行。没有图片时，返回内容和现在完全一样。

**怎么测：**
- 进程内调用 MCP 工具，断言文字块、图片块数量和 MIME 类型；没有图片的单元返回值和现在逐字相同。
- **CLI 和 IDE 里各用真实关键帧测一次**：模型能否读出关键帧里的画面文字。2026-11-14 的 `docs/验证结果.md` 第 9 项只证明了 CLI 里小色块图能送达；真实关键帧（几十到上百 KB）会不会被截断、缩小、拒收，**这条还没测**。C4 还没做时，核心层选不了镜头适配器，所以这次测试用一个试验启动脚本：它在临时目录里建一个仓库，用真实的 `api.read` 和 `refcov_mcp`，只把"适配器"换成从 EP01 隔离副本取帧的试验适配器。结果写进验证结果第 10 项。

**风险：** 中。工具返回图片后，Kiro 对工具结果的处理（截断、额度）没有文档，只能实测。

### C3：会话补记钩子要认得"带图片的工具返回"

**为什么：** `integrations/kiro/hook.py` 的 `response_text`／`_block_text` 从 `tool_response` 里取文字找 `refcov-call:` 行。带图片后，`tool_response` 的形状（字符串、列表、块里有没有 base64）没有实测过；认不出文字时它只写 `errors.log` 然后放行，结果是**这次读取没有补上会话**，报告里"会话未知"计数会涨，但不会崩。

**动哪里：** 先实测，再决定动不动。读代码看，图片块没有 `text`，会被 `_block_text` 跳过，文字块照常处理，**可能不用改**。要做的是：确认 `errors.log` 和任何日志都不会写入 base64 原文（现在不写 `tool_response` 原文，保持）。

**怎么测：**
- 用真实的 PostToolUse 输入样例（在 IDE 里用 C2 做完的服务读一个带图片的镜头，把钩子输入存进 `experiments/`，像 `tests/test_hook.py` 现在用的真实样例那样）。样例里图片块的形状决定代码要不要改。
- 新增测试：带图片块的几种形状（字符串里夹图片、列表里有 image 块、对象里 `content` 有 image 块），补记会话成功、`errors.log` 里没有 base64。

**风险：** 低到中，取决于实测形状。可能是零代码改动加一个测试。

### C4：按名字选适配器，`refcov add` 能指定适配器（**已批，做法 A**）

**为什么：** 核心层写死只认 Markdown：`sources.register` 里 `from refcov.adapters import markdown`，`api._adapter(name)` 只认 `"markdown"`，`api._decls()` 只返回文档适配器的类型声明，`refcov add`（`refcov/cli.py`）没有选适配器的参数。镜头适配器放在 `apps/shot-coverage`，核心层不能 import 它（骨架需求 2.6），所以需要一个"按名字找到适配器"的办法。

**做法（用户 2026-11-14 选定：做法 A，配置里写适配器文件的路径）：**
- 配置文件加 `[adapters]` 一节，名字对**适配器文件的路径**（相对仓库根目录），例如 `shot = "apps/shot-coverage/adapter.py"`。不写点路径：`apps/shot-coverage` 带连字符，不能当包名导入。
- 核心层用 `importlib`（`spec_from_file_location`）在**需要时**从这个文件加载，自己不 import 任何具体适配器。文件要提供 `name`、`kinds`、`split`、`read`、`facts`（骨架需求 2.1、2.2）；缺哪项就报错说明，不崩。
- 配置文件只由用户修改（骨架需求 14.2），所以不增加新的 AI 可写入口；路径必须落在仓库里，不接受仓库外的路径。
- 清单里的 `adapter` 字段存适配器名；读取、算必看集合时按名字去配置里找路径。配置里没有这个名字（用户删了声明）时，读取报错并提示，**不**退回文档适配器。

**动哪里：** `refcov/sources.py`（`register` 接受适配器）、`refcov/api.py`（`_adapter`、`_decls`）、`refcov/cli.py`（`--adapter`）、`refcov/store.py`（读 `[adapters]`）、`integrations/kiro/refcov.example.toml`（加一段注释示例）。

**怎么测：** 用测试里的假适配器（不是 ffmpeg）走一遍：配置里声明 → `refcov add --adapter` 登记 → `list_units`、`read`、`check` 都认它的类型声明（`shot` 严格必看，影响必看集合）；路径在仓库外、文件不存在、缺必需项、配置里没有这个名字时都报错而不是崩；不写 `[adapters]` 时行为和现在完全一样；`tests/test_core_names.py` 仍然通过（核心层源码里没有应用的名字）。

**风险：** 中。涉及登记和读取两条主路径，必须保住所有现有测试。

**D1（适配器怎么拿到仓库根目录）已在设计里解决，不改核心层：** 镜头清单里视频的路径是相对仓库根目录的，适配器的 `read(data, name, unit_id)` 拿不到根目录；适配器从自己的文件位置往上找第一个含 `.git` 的目录（加载器保证适配器文件在仓库里）。见 `design.md` 第 3.2 节第 2 步。

**已做（2026-11-14，提交 `f344f5f`）：** `refcov/adapters/loader.py`；`sources.register`、`api._adapter`、`api._decls`、`refcov add --adapter`、`DEFAULT_CONFIG["adapters"]`；`tests/test_adapter_loader.py` 23 个测试。适配器必须自带依赖：加载时不改 `sys.path`，只能 import 标准库和 `refcov`。

### C5：登记和读取大的二进制材料（**不做**，用户 2026-11-14 定）

初稿的 C5 想让核心层支持"不复制进缓存、按引用读取、清单里带适配器私有信息、读取时不重新拆分"。它改的是骨架需求 1 和 4 的主路径，是六处里风险最高的一处。

**为什么不做：** 镜头清单方案（需求 1、3、4）让核心层始终只登记一份几 KB 的 UTF-8 Markdown，初稿列出的四处"不成立"（整份复制进缓存、只收 `.md`、每次读取重读缓存并重拆、清单里没地方放适配器私有信息）对清单都**成立**，不用改：
- 缓存里放的是清单，不是 941 MB 的视频；
- 清单是 `.md`，且在仓库里；
- 每次读取重读缓存、重拆清单是毫秒级，场景检测只在 `detect` 里跑过一次；
- 起止时间写在清单每个镜头的小节里，适配器自己解析。

**代价（照实写）：** 视频文件有没有变，核心层看不见，只能靠适配器在**读取时**核对（需求 3.4）：视频变了就拒绝读取，不留记录。核心层不会因为视频变了而让旧记录自动失效；要等用户重新检测、重新登记，清单变了，旧记录才失效（骨架需求 1.4）。所以"视频换了但没重新检测"这种情况，靠读取时的拒绝兜住，不靠记录失效。

**对核心层的要求：** C1 里 `adapter.read` 在写记录之前调用，抛异常就不写记录（上面 C1），这是需求 3.4 的依靠。除此之外 C5 不动核心层。

### C6：测试里的"核心层名字检查"和 CI

**为什么：** 骨架需求 13 要求核心层不出现 Kiro 工具名、不 import 应用；任务 12 加了 `tests/test_core_names.py`。C4 的点路径配置是新增入口，要保证核心层源码里没有 `shot`、`ffmpeg` 这类字。CI 的 Linux 和 Windows 作业要装 ffmpeg 才能跑需求 7.3 的测试。

**动哪里：** `tests/test_core_names.py`（加禁用词）、`.github/workflows/ci.yml`（装 ffmpeg；不动核心层）。

**怎么测：** 在核心层源码里临时放一个 `import ffmpeg` 或 `"shot"` 字样，检查应当失败（改完还原）。

**风险：** 低。

### 改动顺序和停点

1. 用户已审阅（2026-11-14）：批 C1、C2、C3、C4（做法 A，路径写法）、C6；C5 不做。
2. 顺序：C1 → C2 → C3；做完先用真实关键帧（EP01 隔离副本里挑几个镜头）在 CLI 和 IDE 里各测一次，结果记进 `docs/验证结果.md` 第 10 项。**真实关键帧送得到，再做 C4、C6 和镜头适配器；送不到就停下报告**（可能的调整：缩小关键帧、一次只返回一张）。
3. 每一处单独提交，核心层现有测试全过才进下一处。
4. 镜头适配器的设计文档写完后停一次，给用户看。
5. 核心层改动期间，写文件关卡照常管着这些文件的写入；被拦就先读完还差的单元，不绕。

## 已定和还没定的

**已定（用户 2026-11-14）：**
1. C4 用做法 A，配置里写适配器文件的路径，用 `importlib` 从文件加载。
2. C5 不做，换成镜头清单。
3. 关键帧先每镜头 1 张（需求 2.2）。
4. 镜头条页面不必禁止脚本，不联网即可，实现留给设计（需求 5.1、5.4）。
5. 出处转换以后再做（文字出处暂时保留，检查程序报"未转换"，不算幻影需求）。

**还没定：**
1. **EP01 全部镜头必看与否**：阈值 0.25 在 EP01 上抓到 43 处硬切，约 44 个镜头，全部必看至少读 44 次、44 张图。等 C2 实测图片额度后定；要不要在对比试验里用放宽项缩小范围（需求 6.3）。
2. ~~D1：适配器怎么拿到仓库根目录~~ 已在 `design.md` 第 3.2 节解决。
