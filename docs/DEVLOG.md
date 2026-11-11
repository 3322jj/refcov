# DEVLOG

## 以后再做

格式：一行写点子，一行写为什么现在不做（见 `.kiro/steering/product.md` 范围冻结）。这一节固定在最前面，日记照常按时间加在文件末尾。

- 给核心层设代码行数上限，写进需求 13，并用自动检查守住（外部审阅 C 节末尾的建议）。
  现在不做：用户这次没点名这一条；范围冻结前先把已定的条文改完。
- 把"豁免路径"并进范围规则（豁免 = 指向空参考源集合的规则），少一个概念。
  现在不做：行为不变，只是写法；用户选了保留现在的写法。
- 需求文档的标题改成 Kiro 规格工具认的英文结构（`### Requirement N`），出处检查的切分规则同步改。
  现在不做：只有 Analyze Requirements 碰到了这个限制，已用临时副本绕过；设计、任务阶段的 Kiro 功能如果也要求英文结构再改。
- 需求 12.1、12.2 要求经 MCP 的报告也给"本会话"数，但 MCP 服务拿不到会话 ID（实测），做不到。改成"经 MCP 的报告只给历史数"或"本会话一栏标不可用"。
  现在不做：需求已冻结；设计里先标"不可用"。
- 需求 8.3 只写了文件名 `DEVLOG.md`，没写路径，豁免哪个位置的文件有歧义。
  现在不做：需求已冻结；设计里先按 `**/DEVLOG.md` 处理。
- 需求 17.4 的对照实验另立规格（两组：严格模式下 `enforce` 开、关），写任务、数据和脚本。
  现在不做：对照实验是"应该有"，骨架规格只留数据（17.1–17.3）。
- 需求 3.5 原文写拆分 ID 加 `-2`；用户 2026-11-10 改成 `@2`（和重名后缀 `-2` 区分），需求原文要跟着改。
  现在不做：需求已冻结；设计按 `@2` 做，标了"偏离需求原文"。
- 需求 2.5 原文只把空白和方括号换成短横线；设计另把 `@` 也换掉，保证 `@` 只出现在拆分后缀里。
  现在不做：需求已冻结；设计里标了"偏离需求原文"。
- 需求 14.4 原文要拦"其他会写记录的 RefCov 入口"，但 `refcov add` 会写登记记录，用户决定放行。需求原文要改成"会清空、重建日志或写确认、配置的入口"。
  现在不做：需求已冻结；设计里标了"偏离需求原文"。
  2026-11-11 更新：用户改为 `add` 只能由用户跑（设计第二版审阅一.2），设计已不再偏离 14.4 原文，这一条不用再改需求。
- 哈希链查不出最后一行被改或被删（没有后一行去对 `prev`）。可以在报告里记下链头的哈希，下次报告时对一下。
  现在不做：设计和需求 11.4 只要求"随手改动留下痕迹"，不在已定范围里；先在局限里写明。
- `tests/test_gitignore.py` 只按规则来源的文件名是不是 `.gitignore` 判断。开发者的全局忽略文件叫 `~/.gitignore` 且命中 `.kiro` 时会误报失败。文件开头的说明写了"全局 excludesFile 不算失败"，代码其实没做到。可以改成只认仓库内的 `.gitignore`（`-v` 输出里仓库内的来源是相对路径）。
  现在不做：误报方向是失败，不会漏掉问题；CI 上没有全局忽略文件。

## 2026-11-10（第一步：验证 Kiro 钩子和 MCP）

- 环境：Kiro IDE 1.4.121，Windows。
- 用到的 Kiro 功能：钩子（PreToolUse、PostToolUse、PostFileCreate、PostFileSave、Stop、UserPromptSubmit）、MCP（自己写的零依赖服务）、子 agent。
- 证据：`hook-test/验证结果.md`、`hook-test/logs/hook-log.jsonl`、`hook-test/logs/mcp-image-answer.jsonl`。
- 试验里用来触发拦截的标记词，下文写作"标记词"。不写原词，是因为钩子检查整段输入，写进这里会把写日志这一步也拦掉。

### 结论

| 项 | 结论 |
| --- | --- |
| PreToolUse 拦截写文件（`fs_write` / `str_replace` / `fs_append`） | 成立（第二轮） |
| PreToolUse 拦截 shell | 成立 |
| 钩子能拿到工具名、参数、路径 | 成立 |
| Stop 附覆盖率 | 放弃（IDE 1.x 文档：不能拦截，输出到不了 agent） |
| UserPromptSubmit 把覆盖率送进上下文 | 成立 |
| MCP 返回图片，agent 能看到 | 成立，3x3 色块 9 格全对 |

### 文档和实测不一致的地方

1. **退出码。** actions 文档说"任何非 0 退出码都会拦住 Pre Tool Use"。实测只有退出码 2 能拦，退出码 1 时工具照常执行，agent 也收不到提示。IDE 1.x 钩子文档和 AWS Labs 的记录都说只有 2 能拦，和实测一致。
2. **PreToolUse 退出码 0 的 stdout。** 钩子文档没写清楚这点。实测 agent 收不到。只有 SessionStart / UserPromptSubmit 的 stdout 能送到。
3. **`write` 类别名。** types 文档说 `write` 代表所有写文件工具，问题单 kirodotdev/Kiro#4867 说它匹配不上。实测第二轮能匹配上，但匹配条件本来就按正则处理，带 write 的名字都会命中，所以不能说明类别功能好用。正式项目写精确工具名。
4. **写文件工具第一轮完全不触发。** 文档和 AWS Labs 记录都表明应该能触发。第一轮 15:15–15:21，三种匹配写法、6 次写入，全都没触发，日志里连记录都没有。第二轮 15:39 起全部触发，第一轮的老钩子也一起触发了。所以不是匹配名的问题，真实原因没查清。推测和"新一轮对话开始后才生效"有关，没有验证。
5. **"下次会话生效"。** `createHook` 的提示说新钩子下次会话才生效。实测 shell 类钩子几秒后就在本会话里生效了，但刚改完的几秒内会漏拦一次。

### 其他实测发现

- 钩子 stdin 是 JSON，字段有 `session_id`、`hook_event_name`、`cwd`、`tool_name`、`tool_input`。PostToolUse 另有 `tool_response`，文件事件是 `file_path`，UserPromptSubmit 是 `prompt`（用户消息全文）。
- 各工具的 `tool_input`：
  - `fs_write`：`{path, text}`
  - `str_replace`：`{path, oldStr, newStr, replace_all}`
  - `fs_append`：`{path, text}`
  - `read_file`：`{path, offset, limit}`
  - shell：`{command, description, cwd, run_in_background, timeout}`
- 子 agent 的工具调用也会触发工作区钩子，被拦时子 agent 收到同一段原因。
- 钩子看到的是整段输入，包括要写的正文。本次试验我自己的检查命令就因为含标记词被拦过。正式关卡只能按 `path` 判断。
- `read_file` 触发 PreToolUse，但不触发 PostToolUse。
- PostFileCreate / PostFileSave 能拿到路径，但输出到不了 agent，只能用来记日志。
- Windows 上的 Python 钩子要注意编码：
  - 输出要强制 UTF-8，否则中文原因是乱码。
  - stdin 要按字节读再按 UTF-8 解码。
  - 写日志前要转义特殊字符。有一次因为环境变量里有坏字符，脚本崩了，报错（退出码 1）也被当成 UserPromptSubmit 的输出送进了上下文。
- MCP 图片的送达方式：工具结果里只有文字部分，图片作为紧接着的一条单独消息送到。这条图片消息不触发 UserPromptSubmit。
- agent 不能写 `.kiro/settings/mcp.json`（被 Kiro 权限规则挡住），MCP 配置要用户手动加。

### 对设计的影响

- 关卡按三层做：MCP 开工凭证（主关卡）→ 钩子拦写文件和 shell（退出码 2 + stderr，按路径判断）→ 写完后记录、在报告里标红，不自动恢复。
- 第 4 条不一致说明钩子可能无声失效，所以钩子不能当唯一关卡。
- UserPromptSubmit 每次用户发消息时送一次覆盖率，一轮中途的变化靠 MCP 工具返回。
- 视频应用可以通过 MCP 按镜头返回关键帧图片。

### 还没做

- PreTaskExec 退出码 2 拦截任务开工，还没实测。（16:07 已实测成立，见下文）
- 文档适配器还没做，所以这一天的开发没有被 RefCov 自己管过，也没有被拦记录。

## 2026-11-10（下午续：清理试验钩子，准备 PreTaskExec，写骨架需求）

- 把往上下文塞假覆盖率的 UserPromptSubmit 探测钩子移到 `hook-test/hooks-disabled/`。之后用户发消息时上下文里不再出现那行试验文本，说明移走钩子文件就能立即停用它。
- PreTaskExec 试验已准备好：钩子 `.kiro/hooks/probe-pretask.json`，脚本 `hook-test/hooks/pretask.py`，规格 `.kiro/specs/pretaskexec-probe/`。本地用管道喂 stdin 自测过，放行返回 0，拦截返回 2。在 Kiro 里还没触发过，要等用户点 Start task。agent 自己没有改任务状态的工具，触发不了这个钩子。
- `gh auth status`：账号 3322jj 的令牌已失效，暂时建不了 GitHub 仓库。
- 用到的 Kiro 功能：规格流程（需求阶段）、钩子（`createHook` 创建 PreTaskExec 钩子）。
- 骨架需求文档草稿：`.kiro/specs/refcov-skeleton/requirements.md`，共 14 条需求。每条需求末尾手工标了出处，先按 RefCov 自己要求的格式写一遍。新仓库建好后搬过去。
- 文档适配器还没做，所以这一阶段读的材料仍然没被 RefCov 记录。

## 2026-11-10（傍晚：PreTaskExec 实测结果）

- 用户在 IDE 里点了两个任务的 Start task。任务 1 被退出码 2 拦住，没执行；任务 2 放行后执行了，生成了 `pretask-task2.txt`。结论：**PreTaskExec 能拦**。详见 `hook-test/验证结果.md` 第 5 项。
- 钩子 stdin 字段：`session_id`、`hook_event_name`、`cwd`、`spec_name`、`task_name`。

### 文档和实测不一致的地方（续）

6. **`spec_name` 字段。** 名字叫规格名，实际给的是 tasks.md 的完整路径。
7. **`task_name` 只有任务那一行。** 不含子项，所以 `_需求：…_` 这类写在子项里的引用钩子拿不到，要按路径自己读 tasks.md。
8. **被拦的任务状态停在 `[~]`。** 拦截后任务没有退回未开始状态。

### 其他

- 被拦时 IDE 有没有把 stderr 原因显示出来：用户确认会原样显示。原因文字是试验脚本写死的，正式关卡要按记录算。
- 已把剩下的探测钩子全部移到 `hook-test/hooks-disabled/`，没有删除。
- `gh auth status` 仍显示 3322jj 的令牌失效。

## 2026-11-10（晚上：建新仓库，改需求第二稿）

- 从这一条起，DEVLOG 在 `d:\agent\kiro\refcov\docs\DEVLOG.md` 继续记。前面的内容是从试验目录 kirohe 复制过来的，`验证结果.md` 也复制到了 `docs/`。
- 前两次 `gh auth status` 显示令牌失效，之后再查显示正常。同一时段 `gh api` 经常报 `EOF`、重试才成功，推测前面的"失效"是连不上 GitHub 时的误报，没有验证。
- 第一次提交 `a64d773` 用了个人邮箱，并已建公开仓库 `3322jj/refcov` 推上去。这一步做早了：用户随后要求提交者改成 GitHub noreply 邮箱，并且提交前、建仓库前都要先给他确认。已把本仓库的 git 身份改成 3322jj 的 noreply 邮箱（只改本仓库，没改全局）。经用户明确同意，第一次提交改写为 `51281a2`（内容不变，只改作者），用 `--force-with-lease` 覆盖远端。旧提交 `a64d773` 可能还能在 GitHub 上按哈希访问一段时间。用户要求：以后不经他明确同意不得强制推送。
- 需求文档从 kirohe 搬到 `.kiro/specs/refcov-skeleton/requirements.md`，按用户对 7 个问题的回复改成第二稿。PreTaskExec 的实测结果也写进去了（需求 10.6、10.7）。
- 用到的 Kiro 功能：规格流程（需求阶段第二轮）。

## 2026-11-10（夜：需求第三稿）

- 按用户对第二稿的 10 条审阅意见改成第三稿。新增需求 15（保护状态目录和配置）、16（轻量模式）、17（属性测试）、18（对照实验数据）。写文件关卡改为"必须持有有效凭证"。
- 改的过程中发现几个新问题，写进了文末待确认问题，最要紧的是：MCP 服务能不能拿到会话 ID（未实测）；RefCov 自己会写记录的命令可能被 AI 在 shell 里调用来伪造"看过"。
- 用户审过第三稿并回复了 6 个问题，据此改成第四稿：保护状态目录和配置的检查出错时拦截；写记录的入口只有 MCP 工具和钩子脚本；申请凭证要报任务；`enforce: false` 开关；记送出的单元数和图片数。
- 用到的 Kiro 功能：规格流程（需求阶段第三轮）。

## 2026-11-10（夜：MCP 会话 ID 小试验）

- 需求第四稿已提交推送（`ed83e46`）。第一次推送遇到 TLS 连接错误，重试成功，用的是普通推送。
- 试验结果：MCP 服务拿不到 Kiro 的会话 ID，而且两个会话共用同一个 MCP 进程（pid 39628 先后收到会话 A、会话 B 的调用）。详见 `docs/验证结果.md` 第 6 项。
- 结论：只能用需求 4.5 的备用方案。两个会话交替使用时可能记错会话，这个局限要写进需求。

### 文档和实测不一致的地方（续）

9. **握手方式。** Kiro 1.4.121 先发新版协议的 `server/discover`，服务不认识时另起一个进程，改用 `initialize`。这一点文档里没提到。

- 用到的 Kiro 功能：MCP（自写试验服务）、多会话。

## 2026-11-10（深夜：需求第五稿）

- 会话 ID 试验结果经用户确认，已提交并普通推送（`b2d98a3`）。
- 按用户对第四稿的意见改成第五稿：18 条需求、105 条细则 → 17 条需求、89 条细则。第五稿还没提交，等用户审阅。
- 判断规则调整（因为 MCP 拿不到会话 ID）：
  - 任务开工检查改为"任务引用的单元都有有效读取记录"，不限本次会话。
  - 凭证和读取记录里的会话 ID 只用于日志和回放，不参与任何判断。
  - "当前会话"文件保留，只用于记录。
  - 不在局限里补"一次只开一个会话"。上一条记录里"这个局限要写进需求"作废。
  - `server/discover` 握手的问题留到写 MCP 服务时再确认。
- 缩小范围：
  - 删掉"直接读取按范围合并"（第四稿需求 5）。直接读参考文件不算看过，在 UserPromptSubmit 和拦截原因里提示 AI 改用 MCP 工具。
  - 轻量模式不再记当前任务，凭证不按任务发。必看集合 = 需求文档里引用到的单元 + 关键类型单元。
  - 删掉"写入后发现状态目录被改就标红"（第四稿 11.2），需求 15 已经拦住。
- 第五稿重新编号。第四稿 → 第五稿的需求编号：1–4 不变，5 删除，6→5，7→6，8→7，9→8，10→9，11→10，12→11，13→12，14→13，15→14，16→15，17→16，18→17。
- 用到的 Kiro 功能：规格流程（需求阶段第五轮）。
- 用户审过第五稿，3 个问题的决定：
  1. "同一件事"保留会话（钩子拿到的会话 ID 可靠）。
  2. 严格模式必看集合 = 严格必看类型的单元 + 需求文档里引用到的单元（含可选类型），再按放宽项调整。改了需求 5.1，需求 15.2 补了放宽项引用。这样需求 16.5"轻量 ⊆ 严格"成立，16.5 不改。
  3. 删掉 kirohe 里那份空的 `requirements.md`。
- 第五稿定稿提交。

### 第一到第四稿已确认的决定

从需求文档文末挪到这里。"写进了"一列的编号按**第四稿**。

| 来源 | 决定 | 写进了 |
| --- | --- | --- |
| 11-10 回复二·1 | `d:\agent\kiro\refcov`，公开仓库，MIT | 本文所在仓库 |
| 11-10 回复二·2 | 凭证和写文件关卡认所有会话；任务开工前的重看只认本次会话（第五稿改为不限会话） | 需求 6.7、8.3、10.6 |
| 11-10 回复二·3 | 部分读取从严；分几次读合起来盖住也算（第五稿删除） | 需求 5.2、5.3、17.5 |
| 11-10 回复二·4 | 受控命令默认 `pytest`、`python`、`git commit`、`git push` | 需求 10.2 |
| 11-10 回复二·5 | 只豁免 `DEVLOG.md`；需求文档不豁免 | 需求 9.3、9.5 |
| 11-10 回复二·6 | MCP 用官方 SDK，单独模块 | 需求 14.3、14.4 |
| 11-10 回复二·7 | 同一件事 = 会话 + 关卡 + 目标路径 | 术语；需求 12.2 |
| 第二稿审阅·1 | 状态目录只准 RefCov 写，一律拦，不受上限影响 | 需求 9.3、9.4、15 |
| 第二稿审阅·2 | 配置只准用户改，报告列修改时间 | 需求 13.2、15 |
| 第二稿审阅·3 | 第 3 次放行要标红，JSON 里也有 | 需求 12.2 |
| 第二稿审阅·4 | 补两条 shell 局限 | 需求 12.5 |
| 第二稿审阅·5 | 豁免 RefCov 自己的命令 | 需求 10.3、10.4 |
| 第二稿审阅·6 | 读单元可返回图片 | 需求 2.1、4.1 |
| 第二稿审阅·7 | 写文件前必须有有效凭证 | 需求 8.4、8.5、10.1 |
| 第二稿审阅·8 | 属性测试 | 需求 17 |
| 第二稿审阅·9 | 轻量模式 | 需求 2.2–2.4、6、16、17.6–17.7 |
| 第二稿审阅·10 | 三组对照实验 | 需求 13.5、18 |
| 第三稿审阅·1 | 设计前先试验 MCP 能否拿到会话 ID；拿不到就由钩子写"当前会话"文件 | 需求 4.5；`docs/验证结果.md` 第 6 项 |
| 第三稿审阅·2 | PreTaskExec 放行的任务是当前任务；申请凭证要报任务，对不上就拒发（第五稿删除） | 需求 8.6、16.7 |
| 第三稿审阅·3 | 写记录的入口只有 MCP 工具和钩子脚本；shell 里调用一律拦 | 需求 15.3、15.4 |
| 第三稿审阅·4 | 额度手动抄；自动记送出的单元数和图片数 | 需求 4.6、18.3、18.4 |
| 第三稿审阅·5 | 保护检查出错时拦截；其余检查出错仍放行 | 需求 12.1、15.5、15.6 |
| 第三稿审阅·6 | `enforce: false` 只有用户能改；报告第一行写"关卡已关闭"，JSON 标明 | 需求 18.1、18.2 |

## 2026-11-10（深夜续：引导文档定稿，建 spec-auditor）

- 新建了 5 个引导文档：`.kiro/steering/` 下的 `product.md`、`tech.md`、`devlog.md`、`testing.md`、`citation.md`。`product.md`、`tech.md`、`devlog.md` 总是加载。`testing.md` 在读到 `tests/**` 时加载，`citation.md` 在读到 `.kiro/specs/**` 时加载。用户审过，需求编号统一用第五稿。
  EN: Added five steering files; three are always loaded, testing.md and citation.md load on fileMatch (tests/**, .kiro/specs/**). Requirement numbers follow draft 5.
- 按用户意见改了 `product.md` 三处：
  - 删掉"装了 Kiro 的可以用 `demo/` 一分钟内亲手试"，计划里没有这一项。
  - 需求出处检查从"应该有"挪进"必须有"。
  - "Kiro 已经能检查需求有没有矛盾"这句先查文档。Kiro 文档 [Analyze Requirements](https://kiro.dev/docs/specs/analyze-requirements/)（2026-09-02 更新）写明规格需求阶段可以做跨需求分析，查逻辑矛盾、歧义、冲突约束、未说明的假设、漏掉的边界情况。所以这句保留。同一句里"代码对不对"的部分没有核实。
  EN: product.md: removed the demo/ hands-on line (not planned), moved citation checking to must-have, kept the "Kiro already checks requirements for contradictions" claim after confirming it in Kiro's Analyze Requirements doc.
- 建了自定义 agent `.kiro/agents/spec-auditor.md`（Markdown 格式，front matter 是配置，正文是系统提示词）。只给 `read` 工具，在对话里输出报告，不写文件。`resources` 里加了 `file://.kiro/steering/citation.md`。原因是 `citation.md` 只在读到 `.kiro/specs/**` 时才加载，加进 `resources` 后 agent 一启动就有。依据：[配置说明](https://kiro.dev/docs/custom-agents/configuration-reference/)。还没在 IDE 里切换到这个 agent 试过。
  EN: Created custom agent spec-auditor (read-only tools) that lists phantom requirements, malformed refs and unconverted text citations; citation.md is preloaded via resources. Not yet run in the IDE.
- 配置说明里和 spec-auditor 有关、要实测的两点：
  - `resources` 里的相对路径相对于哪个目录，文档没写清。`prompt` 的 `file://` 写明相对于 agent 配置文件所在目录，`resources` 的示例看起来相对于工作区根目录。现在按工作区根目录写，没有验证。
  - 子 agent 自己声明了 `file://` 资源时，用这些资源**代替**父 agent 的 `file://` 资源，不是叠加。
  EN: Unverified: whether relative file:// paths in resources resolve from the workspace root or the agent file's folder. Per docs, a sub-agent's own file:// resources replace the parent's.
- 用到的 Kiro 功能：引导文档（always / fileMatch 两种加载方式）、自定义 agent（Markdown 配置，`tools`、`resources`、`welcomeMessage`）。
  EN: Kiro features used: steering (always and fileMatch inclusion), custom agents (Markdown config with tools, resources, welcomeMessage).

## 2026-11-10（深夜续：spec-auditor 第一次试跑）

- 用户在 IDE 里信任 refcov 工作区并重新加载窗口后，Kiro 才加载了 `.kiro/agents/` 里的自定义 agent。
  EN: Kiro only loaded the workspace custom agent after the refcov folder was trusted in VS Code and the window was reloaded.
- 用户切到 spec-auditor，审了 `.kiro/specs/refcov-skeleton/requirements.md`（第五稿，17 条需求）。
  EN: The user ran spec-auditor on the draft-5 requirements (17 requirements).
- citation.md 能不能看到：报告没有直接说。报告按 citation.md 的规则做了分类（按 `### 需求 N：` 切分，文字出处算"未转换"、不算幻影需求，`[ref:…]` 按格式检查），推测 `resources` 里的 citation.md 加载成功了，所以按工作区根目录写的相对路径也是对的。没有单独问 agent 验证。
  EN: The report applied citation.md's rules, so the resource most likely loaded (and the workspace-root relative path likely works); this was inferred, not asked directly.
- 报告结果：幻影需求 0 条，格式错误 0 条（全文没有 `[ref:…]`），17 条需求全部是未转换的文字出处，用到的 8 个来源名都在文档开头的说明里。无效引用、读取记录、幽灵单元、被忽略单元都标了"无数据，未检查"，和提示词要求一致。
  EN: Result: 0 phantom requirements, 0 malformed refs, all 17 requirements still use text citations, all 8 source names are declared; registry-dependent checks were reported as "no data, not checked".
- 报告的人工判断部分指出 3 个问题，都还没处理：
  - "第四稿审阅"在需求 4、5、7、9、11、15 里没写条目号；"实测"没指到 `docs/验证结果.md` 的项号。转换成 `[ref:…]` 时对不到单元。
  - "11-10 回复二"第 1、3 条和"第五稿审阅"第 1、3 条没被任何需求引用。可能是没产生需求，也可能是漏标。
  - "交接说明·加强项 2"同时是需求 3（文档适配器）和需求 8（关卡范围规则）的出处，没对照原文确认。
  EN: Manual findings (not yet acted on): citations without item numbers, four reply items never cited, and one handover item cited by two unrelated requirements.
- 报告也说明了它查不了的：交接说明在工作区外，各稿审阅回复没有存成文件，所以没法核对出处内容。这和 citation.md 里"用户的审阅回复怎么当参考源，待设计阶段定"是同一个问题。
  EN: The auditor could not verify citation content because the handover note is outside the workspace and review replies are not stored as files; this is the same open question already listed in citation.md.
- 用到的 Kiro 功能：自定义 agent（只读工具 + `resources` 预加载引导文档）。
  EN: Kiro feature used: a custom agent with read-only tools and a preloaded steering file.

## 2026-11-10（深夜续：按外部审阅处理 D5、D2）

- 收到一份对第五稿的外部审阅，存为 `docs/需求第五稿审阅.md`（还没提交）。用户对其中几项做了决定，处理顺序是 D5 → D2 → 跑 Analyze Requirements → 改条文 → 实测 MCP 的 PostToolUse。
  EN: Received an external review of requirements draft 5 (docs/需求第五稿审阅.md, not yet committed); the user set the order: D5, D2, Analyze Requirements, clause edits, then an MCP PostToolUse test.
- D5：把 11-10 晚上那条记录里第一次提交用的姓名和邮箱改成"用了个人邮箱"，其余文字不变。邮箱仍在提交 `88f2b7b` 及之后各提交的 `docs/DEVLOG.md` 内容里，旧提交 `a64d773` 的作者字段里也有。是否改写历史、强制推送，等用户决定，还没动。
  EN: D5: replaced the name and personal email in the 11-10 evening entry with "a personal email". The address is still in DEVLOG.md as committed in 88f2b7b and later, and in the author field of the old commit a64d773; history has not been rewritten, pending the user's decision.
- 用户回复：改写历史的事由他自己处理，agent 不管。所以本仓库不改写历史、不强制推送。
  EN: The user will handle the history rewrite himself; the agent will not rewrite history or force-push.
- D2：新建英文 `README.md`；新建引导文档 `.kiro/steering/language.md`（总是加载），规定英文加在哪几处：README、每条需求的标题和用户故事下一行 `EN:`、每份引导文档开头一段 `EN summary:`、DEVLOG 每条要点下的 `EN:`。已给现有 5 份引导文档补了英文摘要。需求文档的 `EN:` 行还没加，等条文改完一起加，免得先译后改。
  EN: D2: added an English README.md and a new always-loaded steering file language.md defining where English goes; added English summaries to the five existing steering files. EN lines in requirements.md are deferred until the clause edits are done.
- 核对用户给的依据：Kiro [权限文档](https://kiro.dev/docs/permissions/)写明，写工作区和 `~/.kiro` 下的 agents、hooks、workflows、powers 目录"Always asks"，任何范围的允许规则都去不掉确认。唯一例外是托管云沙箱里、用户级不带限制的 `fs_write` 允许规则。文档讲的是写文件工具，用 shell 命令写这些目录会不会也要确认，文档没写，没测。
  EN: Checked Kiro's permissions doc: writes to .kiro/agents, hooks, workflows and powers always prompt and no allow rule removes the prompt, except inside the managed cloud sandbox with an unrestricted user-level fs_write allow. The doc does not say whether shell-command writes to those paths also prompt; not tested.
- 用到的 Kiro 功能：引导文档（新增 always 加载的 `language.md`）。
  EN: Kiro feature used: steering (new always-loaded language.md).

### 文档和实测不一致的地方（续）

10. **Analyze Requirements 要英文标题结构。** 用户在 IDE 里对第五稿点了分析，执行分析的会话回报：服务要求 `## Introduction`、`## Requirements`、`### Requirement N`、`**User Story:**` 这些英文标题，中文标题的文档在校验阶段就被拒了。[分析需求文档](https://kiro.dev/docs/specs/analyze-requirements/)（2026-09-02 更新）没提这项要求。这是那个会话的转述，具体报错原文我没看到。
  EN: Analyze Requirements rejected draft 5 at validation because its headings are Chinese; per the session that ran it, the service expects English headings (Introduction, Requirements, Requirement N, User Story). The Analyze Requirements doc does not mention this. Relayed by that session; the raw error was not seen.

- 处理：没改原文。另建了一份临时副本 `.kiro/specs/refcov-skeleton-analyze/requirements.md`，只把标题换成英文结构（17 个 `### Requirement N`、17 个 `**User Story:**`、17 个 `#### Acceptance Criteria`），正文仍是中文。分析在副本上跑，Kiro 按回答改的也是副本。副本不提交，用完删除。
  EN: Kept the original unchanged; made a temporary copy with only the headings converted to the English structure (17 requirements, body still Chinese). The analysis runs on the copy, so any edits Kiro makes land there. The copy will not be committed and will be deleted afterwards.

## 2026-11-10（深夜续：Analyze Requirements 在副本上运行，逐条记录）

- 副本上的分析跑起来了，问题逐条出现在聊天里。用户把每条问题贴给 agent，agent 给建议，用户在分析界面里选。下面按出现顺序记。分析还没结束，对照审阅 A 节的总结等全部问题出完再写。
  EN: Analysis now runs on the copy; questions arrive one by one, the user relays each to the agent, then picks an answer in the analysis UI. Listed in order below; the comparison with review section A comes after the analysis ends.

| # | 条文 | 分析问的 | 用户选的 | 和审阅 A 节 | 要改的条文 |
| --- | --- | --- | --- | --- | --- |
| 1 | 4.5 | 两个钩子都必须写当前会话，还是任一个写就行 | 任一个写即可 | A 节没有（A9、B6 说的是交替记错） | 视第 4 步实测，4.5 可能整条删 |
| 2 | 14.6 | 用户手改不受影响是无条件保证，还是有条件 | 无条件 | A 节没有 | 14.6 改为"用户自己的修改，不论在不在 Kiro 编辑器里"；需求 10 要分清 PostFileSave 是用户保存还是 AI 写入，待实测 |
| 3 | 3.1 | 既非 Markdown 也非 HTML 时怎么办 | 拒绝并报错 | 部分重合 A9（只管 Markdown） | 3.1 补：不支持的格式登记失败；没有标题的 Markdown 整篇一个单元，标题取文件名 |
| 4 | 8.4 | 严格模式下没豁免、没凭证的需求文档写入怎么办 | 拦截 | 重合 A1、A4 | 8.4 "没有有效凭证"改为"按路径判断不达标"；8.3 默认豁免加 `docs/decisions/**`（用户同意，保留 `DEVLOG.md` 豁免） |
| 5 | 6.5 | 申请凭证和 PreTaskExec 是各自独立拦，还是任一处拦住即可 | 各自独立 | 重合 A3、A10 | 6.5 写成一条规则，申请凭证、任务开工、写文件三个入口都按它判断 |
| 6 | 9.6 | 找不到任务时放行还是拦截 | 放行 | A 节没有 | 9.6 补：放行时记日志、报告里单独列"任务未找到，未检查"；匹配时忽略状态标记和首尾空白（细节留设计） |
| 7 | 10.1 | 写入后判断不了当时是否达标，记还是跳过 | 记录并标红 | A 节没有 | 10.1 条件按 A4 改为"写入时按路径判断不达标"；判断不了时也记，单独标"无法判断"，不写成"不达标" |
| 8 | 13.4 | 核心层生产代码能不能 import hypothesis | 不能，只有测试目录可以 | A 节没有 | 13.4 补一句"只有测试代码可以 import Hypothesis" |
| 9 | 12.2 | 报告里的记录是全部历史，还是只限本会话或本模式周期 | 全部历史 | 部分重合 B6（用户决定 3：同时显示本会话和历史两个数）、C6 | 12.2 补：记录覆盖全部历史，每条带时间和会话 ID；覆盖率同时给本会话和历史两个数 |
| 10 | 15.2 | 轻量模式下放宽项是缩小还是扩大必看集合 | 缩小 | 重合 A3 | 按 A3 写一条规则：放宽项只能缩小，且移不掉被需求引用的单元；关键类型单元可以放宽，报告里列出 |
| 11 | 17.1 | `enforce: false` 时是所有拦截都失效，还是只豁免关卡类规则 | 除需求 14 外全部放行 | A 节没有（和用户决定 1 相关） | 17.1 写明放行的是写文件关卡和任务开工关卡；需求 14 的保护（含 B1 的 shell 文本匹配）照常生效 |

  EN: Nine questions so far (4.5, 14.6, 3.1, 8.4, 6.5, 9.6, 10.1, 13.4, 12.2). Five are not in review section A (4.5 both-hooks, 14.6 user edits inside the Kiro editor, 9.6 task not found, 10.1 undeterminable status, 13.4 hypothesis imports); the rest overlap A1, A3, A4, A9, A10, B6, C6. The user also agreed to add docs/decisions/** to the default exemptions next to DEVLOG.md.
- 第 2 条牵出一个没测过的点：PostFileSave 在用户手动保存时也触发，AI 写文件时触发不触发没测过。并入第 4 步实测。
  EN: Untested: whether PostFileSave fires for agent writes as well as user saves; added to the step-4 test.
- 第 4 条讨论时用户问过 DEVLOG 有没有必要豁免。agent 的理由：被拦的那一刻正是要记日志的时候；DEVLOG 不是从参考材料推出来的；风险小。用户决定保留。
  EN: The user asked whether DEVLOG.md needs exempting; kept, because blocks happen exactly when the log must be written and the log is not derived from reference material.

### 分析结果和审阅 A 节对照

- 用户转来 11 条问题（上表）。另外 agent 建议用户把落在要删或要重写的条文（2.3、4.2、4.5、7.4、7.5、9.2–9.4、11.2、13.5、17 的三组实验）上的问题直接忽略、不转来。这类问题有没有、有几条，agent 不知道，所以下面说"分析没提到"的，只对转来的 11 条成立。
  EN: The user relayed 11 questions. Questions on clauses already slated for deletion or rewrite were to be dismissed without relaying, so "not raised" below only covers the 11 relayed questions.
- 分析结束后，把副本和原文比了一遍（只换标题后逐行对比）。Kiro 按回答改了 9 处：新增 3.4，改了 4.5、6.5、9.6、10.1、12.2、13.4、14.6、17.1。8.4 没改。改法都是在原句后面追加一句，把选中的答案原样写进去。
  EN: Diffing the copy against the original shows Kiro made 9 edits (new 3.4; appended sentences to 4.5, 6.5, 9.6, 10.1, 12.2, 13.4, 14.6, 17.1); 8.4 was unchanged. Each edit appends the chosen answer to the existing sentence.
- 对不上的一处：执行分析的会话事后报告说也改了 15.2（"放宽项只能缩小必看集合"），但 agent 比对时副本里 15.2 没变。可能是比对之后才写进去的，也可能是那个会话报告有误。agent 比对完就按计划删了副本（副本没进 git，删了找不回），所以查不清。15.2 的答案已记在上表，不影响后面改条文。
  EN: Mismatch: the analysis session later reported a 15.2 edit, but 15.2 was unchanged when the agent diffed the copy. The agent deleted the untracked copy right after diffing, so this cannot be checked; the 15.2 answer is in the table anyway.
- Kiro 改的条文不直接搬回原文，原因：有两处和 agent 建议的写法不同。10.1 写成"按没有有效凭证记录"，agent 建议单独标"无法判断"；9.6 只写了放行，没写记日志和报告里单列。其余几处还要按 A4（写入时按路径现算）、决定 1（删自动放行）改写。原文按上表"要改的条文"一列手工改。
  EN: Kiro's edits are not copied back: 10.1 records "no valid token" where the agent proposed a separate "undeterminable" label, 9.6 lacks logging, and most clauses must be rewritten anyway for decisions A4 and 1. The original is edited by hand from the table.
- 两边找到的问题类型不同：
  - 分析提的都是单条条文内部的边界情况和措辞歧义：找不到任务时怎么办（9.6）、判断不了时记不记（10.1）、生产代码能不能 import 开发依赖（13.4）、用户手改是不是无条件不受影响（14.6）。其中 6 条 A 节没有：4.5、9.6、10.1、13.4、14.6、17.1。
  - A 节提的大多是跨条文或整个系统的问题，转来的 11 条里一条都没碰到：A1（凭证其实拦不住写入，主关卡的说法过头）、A2（重试三次就能硬闯）、A4（申请凭证时没有路径参数）、A6（幻影需求不影响达标）、B1（用 shell 伪造读取记录）。A3 只碰到一半：15.2 问了放宽项是缩小还是扩大，没指出它和 6.5"被引用必看"冲突。A7 是两份引导文档之间的矛盾，A8 是 ID 生成方式的后果，都不在需求文档里，分析本来就看不到。
  EN: The two found different kinds of issues. The analysis raised edge cases and wording ambiguities inside single clauses; 6 of them (4.5, 9.6, 10.1, 13.4, 14.6, 17.1) are not in review section A. Section A's cross-clause and threat-model findings (A1 overstated gate, A2 retry bypass, A4 missing path on token request, A6 phantom requirements not affecting pass, B1 forged read records) did not appear in the 11 relayed questions; A3 was only half-raised. A7 and A8 involve steering files and ID generation, outside the requirements document.
- 结论：Analyze Requirements 适合查"这句话有几种读法"，查不出"AI 怎么绕过这条规则"和"这条规则说得比实际做到的强"。两种检查互补，不能互相替代。
  EN: Analyze Requirements is good at "this sentence can be read two ways", not at "how an AI would bypass this rule" or "this rule claims more than the system does"; the two reviews complement each other.
- 用户在中文版 IDE 里操作，agent 只知道英文菜单名（Continue、Analyze Requirements、Proceed to Design），中文名是猜的，靠位置描述让用户找到。
  EN: The user runs the Chinese-localized IDE; the agent only knew the English menu labels and guided by position.
- 用到的 Kiro 功能：Analyze Requirements（规格需求阶段的跨需求分析）。
  EN: Kiro feature used: Analyze Requirements.

## 2026-11-10（深夜续：按外部审阅和分析结果改条文）

- 只改点名的条文，没出完整第六稿。删掉的条文保留编号，写"（已删除：……）"，免得审阅、分析和 DEVLOG 里引用的编号对不上。标题改成"第五稿，按外部审阅修订"。第五稿原文见提交 `9dafb06`，下表"旧"一列是摘要。
  EN: Only the named clauses were edited; deleted clauses keep their numbers as "(deleted: ...)" so references in the review, the analysis and this log still line up. Full draft-5 text is in commit 9dafb06.
- 简介的出处列表加了四个来源名："外部审阅"（`docs/需求第五稿审阅.md`）、"外部审阅回复"（用户的处理意见，按原消息节号"二·1"到"二·5""三"，以及对 agent 6 个疑问的回复"疑问 1"到"疑问 6"）、"分析"（上面的表，#1 到 #11）、"权限文档"。
  EN: Added four source names to the introduction: the external review, the user's replies to it, the analysis table, and Kiro's permissions doc.

| 条文 | 旧 | 新 | 出自 |
| --- | --- | --- | --- |
| 简介 | 没看够就不发开工凭证、不准写文件 | 核心层给出与工具无关的达标判断，接入层据此拦截；视频、地理适配器的声明挪到各自规格；演示页和视频只展示严格模式 | 外部审阅 A1、A10；外部审阅回复·二·4 |
| 术语 | 有"同一件事"；凭证"写文件前必须持有"；配置含受控命令 | 删"同一件事"；凭证只用于记录和演示；配置去掉受控命令、加 `enforce`；新增"无效引用" | 外部审阅回复·二·1、二·5；外部审阅 C2 |
| 2.3 | 视频、地理、文档三种适配器的默认声明 | 只留文档适配器的；另两种挪到各自规格 | 外部审阅 A10 |
| 2.5 | 拆两次给出相同 ID | 加 ID 规则：由标题生成，保留中日韩文字，空白和方括号换成短横线，重名加 `-2`、`-3`；ID 不含空白和方括号 | 外部审阅 A7、A8；外部审阅回复·疑问 2 |
| 3.1 | Markdown 或 HTML | 只管 Markdown；超长章节按 3.5 拆 | 外部审阅 A9 |
| 3.4（新） | 无 | 非 Markdown 登记时拒绝；网页先转 Markdown；Kiro 文档登记 `.md` 地址 | 外部审阅 A9；分析 #3 |
| 3.5（新） | 无 | 超长章节拆成"原标题 (2)"，ID 加 `-2`；上限留设计 | 外部审阅 C3；外部审阅回复·疑问 4 |
| 3.6（新） | 无 | 没有标题的 Markdown 整篇一个单元，标题取文件名 | 分析 #3 |
| 4.2 | 分页时全部页返回才记为看过 | 删除 | 外部审阅 C3 |
| 4.3 | 只追加、JSON Lines | 加哈希链，报告显示是否完整；只能让随手改动留痕 | 外部审阅 B1；外部审阅回复·疑问 3 |
| 4.5 | 当前会话文件 | 没改，等第 4 步实测 | 分析 #1 |
| 5.1 | 严格必看类型 + 被引用单元，"再按放宽项调整" | 一条规则：基础集合 − 放宽项 + 被引用单元，两种模式共用；被引用单元永远必看 | 外部审阅 A3、A10；分析 #10 |
| 5.2 | 轻量模式按需求 15 | 其他条文说必看集合一律指 5.1 | 外部审阅 A10 |
| 5.3 | 两种模式都移出必看集合 | 移出基础集合；只能缩小；被引用的仍必看，报告注明 | 外部审阅 A3；分析 #10 |
| 5.7 | 不按会话区分 | 保留；加"报告和 UserPromptSubmit 那一行同时显示本会话、历史两个数" | 外部审阅 B6；外部审阅回复·二·3 |
| 6.1 | 定义出处写法 | 加：聊天里的要求存成 `docs/decisions/` 下的文件，一条意见一个小标题，按普通单元引用；存前给用户过目 | 外部审阅 A6；外部审阅回复·二·2 |
| 6.5 | 引用没看过的单元不达标，凭证和 PreTaskExec 拦 | 三个入口（申请凭证、写文件、任务开工）各自独立按这条判断 | 外部审阅 A10；分析 #5 |
| 6.6（新） | 幻影需求、无效引用只列出 | 严格模式下不达标；轻量模式只列出；文字出处算"未转换" | 外部审阅 A6；外部审阅回复·二·2 |
| 6.7（新） | 无 | 写规格文件不因 6.6 被拦 | agent 发现，见下 |
| 需求 7 标题、用户故事 | 主关卡；"钩子失效、换了工具关卡也还在" | 记录用；"核心层给判断和凭证，接入层据此拦截" | 外部审阅 A1 |
| 7.3 | 做 6.5 的检查 | 做 6.5、6.6 的检查 | 外部审阅回复·二·2 |
| 7.5 | 写文件关卡以持有有效凭证为准 | 写文件和任务开工按路径或任务现算，不看凭证；凭证只用于记录和演示 | 外部审阅 A4；外部审阅回复·二·5 |
| 7.6 | 凭证机制不依赖钩子 | 发放和判断不依赖钩子；拦截依赖接入层 | 外部审阅 A1 |
| 8.1 | 凭证的达标判断按对应关系做 | 写文件关卡按对应关系现算 | 外部审阅 A4 |
| 8.3 | 默认只豁免 `DEVLOG.md`；豁免 = 不需要凭证 | 默认豁免 `DEVLOG.md` 和 `docs/decisions/**`；豁免 = 不检查是否达标 | 分析 #4（用户同意） |
| 8.4 | 没有有效凭证时写需求文档也被拦 | 按路径判断不达标时被拦 | 外部审阅 A4；分析 #4 |
| 需求 9 用户故事 | 写文件、指定的 shell 命令和任务开工 | 写文件和任务开工 | 外部审阅 C2 |
| 9.1 | 没有覆盖该路径的有效凭证 | 按路径判断不达标（含 6.6），stderr 也列幻影需求和无效引用 | 外部审阅 A4；外部审阅回复·二·2 |
| 9.2–9.4 | shell 受控命令、只读命令豁免、MCP 和钩子不受影响 | 删除 | 外部审阅 C2 |
| 9.6 | 找任务、收集单元、拦截 | 加 6.6 检查；找不到任务时放行、记日志、报告单列；匹配忽略状态标记和首尾空白 | 分析 #6 |
| 9.8 | 模式、覆盖率、凭证状态、还差的必看单元 | 模式、本会话和历史两个数、是否达标、还差几个和前 5 个 | 外部审阅 A10、B6；外部审阅回复·二·3 |
| 9.9 | 第 1、2、6 条 | 第 1、6 条 | 外部审阅 C2 |
| 10.1 | 写入时没有有效凭证就记、标红 | 写文件工具的 PostToolUse；按路径判断不达标就记、标红；判断不了也记，标"无法判断" | 外部审阅 A4；分析 #7 |
| 10.3（新） | 无 | 分不清用户保存还是 AI 写入的文件保存事件，只记录、标"来源不明"、不标红 | 分析 #2 |
| 需求 11 用户故事 | 不反复拦同一件事 | 被反复拦时让 AI 停下来问用户，不自动放行 | 外部审阅 A2；外部审阅回复·二·1 |
| 11.2 | 同一件事拦两次后第 3 次放行，记"超过拦截上限后放行" | 同一会话对同一目标第 2 次起，原因加"停下来，向用户说明情况"；不因次数放行；放行由用户改 `enforce` | 外部审阅 A2；外部审阅回复·二·1 |
| 11.4 | 4 条局限 | 加 3 条：威胁模型（防偷懒和虚报，不防蓄意伪造）；钩子配置依赖 Kiro 的"Always asks"，shell 写入未测，接入层脚本按普通代码走关卡；解释器启动失败管不到 | 外部审阅 A9、B1、B2；外部审阅回复·三、疑问 1；权限文档 |
| 12.2 | 报告字段，含"超过拦截上限后放行的写入" | 删这一项；覆盖率给本会话、历史两个数；加哈希链状态、钩子配置和接入层脚本校验值（有变化标红）、"任务未找到"、"无法判断"、"来源不明"；记录覆盖全部历史，带时间和会话 ID | 外部审阅 B1、C1、C6；外部审阅回复·二·1、二·3、疑问 1；分析 #9 |
| 12.3 | 文字版和 JSON 版内容一致 | JSON 是唯一数据源，文字版由它生成 | 外部审阅 C6 |
| 13.4 | Hypothesis 只是开发依赖 | 加"只有测试代码可以 import 它" | 分析 #8 |
| 13.5 | Windows 和 Linux 都能运行 | Windows 上运行；持续集成里另在 Linux 上跑测试 | 外部审阅 C5 |
| 需求 14 开头 | 不受拦截次数上限影响 | 改为不受 `enforce` 影响 | 外部审阅回复·二·1 |
| 14.4 | 命令里出现钩子脚本或会写记录的入口就拦 | 加状态目录路径、配置文件名；写明是文本匹配，会有漏网 | 外部审阅 B1 |
| 14.5 | 检查本身出错时拦截 | 脚本内部异常一律按拦截处理；解释器启动失败写进局限 | 外部审阅 A9 |
| 14.6 | 用户在 Kiro 之外手动改配置不受影响 | 用户自己改文件（不论在不在 Kiro 编辑器里）无条件不受影响 | 分析 #2 |
| 需求 15 | 15.2 轻量必看集合定义；15.3 轻量模式写规格文件不要凭证 | 加说明"只影响必看集合计算"；15.2 只定基础集合；15.3 删除 | 外部审阅回复·二·4 |
| 16.3 | 引用没看过的单元一定不达标 | 加"不论放宽项怎么设" | 外部审阅 A3 |
| 需求 17 用户故事、17.4 | 三组 | 两组：严格模式下 `enforce` 开、关 | 外部审阅 C4；外部审阅回复·二·4 |
| 17.1 | 除需求 14 外一律放行 | 写明放行的是写文件关卡和任务开工关卡，需求 14 照常 | 分析 #11 |

  EN: Clause-by-clause changes (old summary, new summary, source) are in the table above. Main effects: tokens no longer gate writes (hooks compute pass/fail per path at write time); no automatic pass after repeated blocks; one required-set rule for both modes, and cited units can never be relaxed away; in strict mode phantom requirements and invalid references fail the check; shell command gating, paging and the HTML adapter were removed; light mode only affects the required-set calculation.
- 每条需求的标题和用户故事下加了 `EN:` 行（17 条）。验收标准、术语、出处行没加，按 `language.md`。
  EN: Added EN lines under all 17 requirement titles and user stories, per language.md.
- 同步改了引导文档：`citation.md`（ID 规则、聊天要求的存法、严格模式下幻影需求不达标、待定问题 1 和 3 已定）、`testing.md`（ID 里不含空白、含空白的 ID 被拒绝的测试，对应 A7）、`product.md`（"AI 只能经 MCP 工具取材料""不准写文件"改成做得到的说法；三层关卡第 1 层改为核心层达标判断）、`tech.md`（Linux 只在持续集成里跑；保护检查的内部异常一律拦截）。英文摘要一起改了。
  EN: Updated steering to match: citation.md (ID rule, decisions files, strict-mode phantom failure), testing.md (IDs never contain whitespace; such IDs are rejected), product.md (claims limited to what the system does), tech.md (Linux in CI only; protection checks block on internal errors).
- 核对了审阅 A9 的说法：`https://kiro.dev/docs/hooks.md` 和 `https://kiro.dev/docs/specs.md` 返回 200，`Content-Type: text/markdown`，所以 3.4 用了这个例子。
  EN: Verified that kiro.dev serves Markdown at .md URLs (hooks.md and specs.md return text/markdown).

### 和审阅不一致、或审阅没提到的地方

- **6.7 是 agent 改的时候发现的。** 严格模式下幻影需求要判不达标（二·2），而 8.4 又规定严格模式下写需求文档也要过关卡。两条合起来，只要需求文档里有一条幻影需求，补出处这次写入本身就会被拦住，AI 读多少材料都过不去。所以加了 6.7：写规格文件不因 6.6 被拦，仍按 6.5 和 8.4 判断。审阅和分析都没提到这一点。
  EN: Found while editing: strict-mode phantom failure (6.6) plus gating spec writes (8.4) would block the very write that adds the missing citation. Added 6.7: spec-file writes are not blocked by 6.6. Neither the review nor the analysis raised this.
- **A10 说"登记新参考源只应让范围包含它的凭证失效"，没采用。** 按 A4 的选择，申请凭证时不带路径，凭证依据的就是全部参考源（8.2），所以任何新参考源都在它的范围内。7.4 原样保留。
  EN: Did not adopt A10's narrower token invalidation: after A4, tokens carry no path and cover all sources, so any new source is in scope; 7.4 unchanged.
- **A5 没另改**（用户决定）。写文件和任务开工都现算，不看凭证，旧凭证有效也放不过去。
  EN: A5 needed no separate change: gates recompute instead of trusting tokens.
- **A6 审阅建议设一种"用户指示"出处类型，附原话或日期。** 用户选的是存成 `docs/decisions/` 下的文件、按普通单元引用。这样少一种出处类型，也让检查程序只认一种写法。
  EN: A6 suggested a separate "user instruction" citation type; the user chose decisions files cited as ordinary units instead.
- **B2 没加进需求 14**（用户决定）。原因是 Kiro 本身规定写 `.kiro/hooks` 每次都要确认，改成在 11.4 写明依赖这一条，报告里列校验值、有变化就标红。
  EN: B2 not added to requirement 14 (user's decision); relies on Kiro's always-ask rule, documented in 11.4, with checksums in the report.
- **C4 没砍**（用户决定，二·4）。轻量模式保留，但只影响必看集合计算。
  EN: C4 not cut; light mode stays but only changes the required-set calculation.
- **4.5 没改。** 等第 4 步实测：MCP 工具的 PostToolUse 稳定带会话 ID 的话，删掉"当前会话"文件。
  EN: 4.5 unchanged pending the step-4 test.

## 2026-11-10（深夜续：准备第 4 步实测）

- 试验文件放在 `experiments/mcp-posttooluse/`：`probe_server.py`（只用标准库的 stdio MCP 服务，工具 `read_unit`，每条消息记进 `logs/server.jsonl`）和 `hook_log.py`（把钩子输入原样记进 `logs/hooks.jsonl`，一律退出码 0）。本地用管道自测过：`server/discover` 回"方法不存在"，`initialize`、`tools/list`、`tools/call` 正常；钩子脚本能写日志，退出码 0。
  EN: Probe files are in experiments/mcp-posttooluse/: a stdlib stdio MCP server with one tool, read_unit, and a hook script that logs its stdin and always exits 0. Both passed a local pipe test.
- 用 `createHook` 建 4 个试验钩子时，Kiro 每个都弹了确认（和权限文档的"Always asks"一致）。用户批准了 3 个（PreToolUse、PostFileSave、PostFileCreate），拒绝了 PostToolUse 那个。PostToolUse 正是要测的，所以实测还没开始，等用户确认。用户说是点错了，agent 用同样参数重建，这次批准了，4 个试验钩子都已建好。
  EN: The user said the rejection was a misclick; the hook was recreated with the same parameters and approved, so all 4 probe hooks now exist.
  EN: Creating 4 probe hooks triggered a confirmation each time, matching the always-ask rule. The user approved 3 and rejected the PostToolUse one, which is the hook under test; the test has not started.

### 第 4 步实测：已经看到的（MCP 部分还没测）

- 4 个试验钩子建好后几秒内就在本会话生效，没等"下次会话"。和第 5 条不一致的记录相同。
  EN: The probe hooks took effect in this session within seconds, not at the next session start, same as mismatch #5.
- agent 用 `fs_append`、`str_replace` 改 DEVLOG 时都触发了 PostFileSave（20:33:34、20:34:25），输入里有 `session_id`、`file_path`、`cwd`、`hook_event_name`，没有工具名。
  EN: Agent edits via fs_append and str_replace fired PostFileSave with session_id, file_path, cwd and hook_event_name, but no tool name.
- agent 用 `fs_write` 新建 `sandbox/agent-write-1.txt`：PreToolUse（20:34:46）→ PostFileCreate、PostFileSave、PostToolUse（都在 20:34:54）。四条的 `session_id` 都是本会话，PostToolUse 带 `tool_response`。
  EN: One fs_write fired PreToolUse, then PostFileCreate, PostFileSave and PostToolUse (with tool_response), all carrying this session's ID.
- 还没测：用户手动保存时 PostFileSave 的输入和 AI 写入有没有区别（决定需求 10.3 能不能分清来源）；MCP 工具的 PostToolUse。
  EN: Not yet tested: whether a manual user save looks different in PostFileSave, and the MCP tool PostToolUse.
- MCP 部分，本会话（会话 A）：用户手动建了 `.kiro/settings/mcp.json`（服务名 `refcov`）。Kiro 先起进程 8812 发 `server/discover`，被回"方法不存在"后另起进程 4400 走 `initialize`，和 `docs/验证结果.md` 第 6 项相同。agent 调用 `read_unit` 3 次（其中 2 次同一批并行发出，参数里有一次含中文和方括号）：PreToolUse 3 条、PostToolUse 3 条，一次不少。钩子看到的工具名是 `mcp_refcov_read_unit`；6 条的 `session_id` 都是本会话；`tool_input` 和服务端收到的参数逐字一致；PostToolUse 的 `tool_response` 里有服务返回的文字。服务端的 `tools/call` 里仍然没有会话标识。
  EN: Session A: 3 read_unit calls (2 sent in parallel, one with CJK and brackets in arguments) produced 3 PreToolUse and 3 PostToolUse events. The hook tool name is mcp_refcov_read_unit; every event carried this session's ID; tool_input matched the server-side arguments exactly; PostToolUse included the server's text response. The server itself still received no session identifier.
- 还差：用户手动保存一次（对比 PostFileSave）；第二个会话调用一次。
  EN: Still to do: one manual save by the user, and one call from a second session.
- 会话 B（`sess_cc2f272f-…`，用户新开）调用 `read_unit` 一次（20:41:10）。PreToolUse、PostToolUse 各 1 条，`session_id` 是会话 B 的，不是会话 A 的；参数一致。服务端仍是进程 4400，返回"第 4 次调用"，再次证明多个会话共用一个 MCP 进程。会话 B 把加载工具和调用工具放在同一批发出，也成功了，和第 6 项试验时一样。
  EN: Session B called read_unit once; its Pre/PostToolUse events carried session B's ID, not A's, with matching arguments. The server was still pid 4400 ("call 4"), confirming one MCP process is shared across sessions.
- 20:41:33 Kiro 又起了一对新进程（15920 发 `server/discover`，20660 走 `initialize`），之后没有调用落到新进程上。原因不清楚，推测和新会话或配置刷新有关，没有验证。
  EN: At 20:41:33 Kiro started a new server pair (15920, 20660) that received no calls; cause unknown.
- 用户手动在编辑器里给 `sandbox/agent-write-1.txt` 加了"测试"并保存，文件内容确实变了，但 `hooks.jsonl` 里没有对应的 PostFileSave 记录。这次样本里，PostFileSave 只在 agent 写入时触发，用户手动保存没触发。只测了一次，原因没查。
  EN: A manual user save changed agent-write-1.txt but produced no PostFileSave event; in this sample PostFileSave fired only for agent writes. One trial, cause not investigated.

### 第 4 步结论

- **稳定**：4 次调用（会话 A 3 次，其中 2 次并行；会话 B 1 次），PostToolUse 4 次全触发，会话 ID 全部准确、两个会话区分开了，参数逐字一致。按用户的要求，改用它记会话归属，删掉"当前会话"文件。
  EN: Stable: 4 of 4 MCP calls across 2 sessions fired PostToolUse with the correct session ID and exact arguments. Per the user's rule, session attribution now uses this hook and the "current session" file is dropped.
- 条文改动：

| 条文 | 旧 | 新 | 出自 |
| --- | --- | --- | --- |
| 4.1 | 读取记录含会话 ID（MCP 服务填） | 读取记录含调用编号，会话 ID 由 4.5 补记 | 实测；外部审阅回复·四 |
| 4.5 | UserPromptSubmit、PreTaskExec 钩子写"当前会话"文件，MCP 服务从中取 | MCP 工具（`mcp_refcov_<工具名>`）的 PostToolUse 钩子追加一条补记记录写会话 ID，不改原记录；没对上的记为"未知"、报告单独计数；不再用"当前会话"文件 | 实测；外部审阅 B6；外部审阅回复·四 |
| 7.1 | 凭证记会话 ID | 会话 ID 按 4.5 补记 | 同上 |

  EN: Edited 4.1, 4.5 and 7.1: the MCP server records calls without a session; a PostToolUse hook on mcp_refcov_* tools appends a record with the session ID (append-only, keeping the hash chain); unmatched calls are counted as "unknown session".
- 10.3 没改：这次手动保存没触发 PostFileSave，"分不清来源时只记录、不标红"仍然是安全的写法。等样本多了再定要不要删。
  EN: 10.3 unchanged; the single manual-save trial did not fire PostFileSave, and the clause stays safe either way.
- 试验钩子 4 个（`.kiro/hooks/probe-*.json`）还在生效，每次写文件都会往 `experiments/mcp-posttooluse/logs/` 记一条，一律放行。
  EN: The 4 probe hooks are still active and log every write (always exit 0).
- 用到的 Kiro 功能：MCP（自写试验服务、工作区 `mcp.json`）、钩子（PreToolUse、PostToolUse、PostFileSave、PostFileCreate）、多会话。
  EN: Kiro features used: MCP (custom probe server, workspace mcp.json), hooks (Pre/PostToolUse, PostFileSave, PostFileCreate), multiple sessions.

## 2026-11-10（夜：收尾提交，需求冻结）

- 旧提交里仍有个人邮箱，用户决定不改写历史、不强制推送。
  EN: Old commits still contain a personal email; the user decided not to rewrite history or force-push.
- 4 个试验钩子从 `.kiro/hooks/` 挪到 `experiments/mcp-posttooluse/hooks-disabled/`，没删。用 shell 的 `Move-Item` 挪走时没有弹确认，说明权限文档的"Always asks"至少不管从这个目录往外移文件。往里写会不会确认没测。
  EN: Moved the 4 probe hooks to experiments/mcp-posttooluse/hooks-disabled/ (not deleted). The shell Move-Item out of .kiro/hooks did not prompt; shell writes into that folder remain untested.
- `.kiro/settings/mcp.json` 写进 `.git/info/exclude`，不写 `.gitignore`（比赛规则禁止忽略 `.kiro` 及其子目录）。`git check-ignore -v` 确认命中的是 `.git/info/exclude` 第 9 行。另加 `docs/mcp.example.json`，路径用占位符。README 的目录表补了外部审阅、`mcp.example.json`、`experiments/`。
  EN: .kiro/settings/mcp.json is excluded via .git/info/exclude (verified with git check-ignore), not .gitignore; docs/mcp.example.json uses a placeholder path. README layout table updated.
- 需求从这次提交起冻结。之后发现的需求问题只记进"以后再做"，不改需求。
  EN: Requirements are frozen from this commit; later issues go to the "later" section only.

## 2026-11-10（夜：提交推送，写设计，spec-auditor 审设计）

- 提交 `d04e8fa`（需求修订、README、language.md、外部审阅、`experiments/`、`docs/mcp.example.json`）。第一次 `git push` 报 TLS 连接错误，5 秒后重试成功，普通推送。需求从这次提交起冻结。
  EN: Committed d04e8fa; the first push failed with a TLS connect error, a retry 5 s later succeeded (normal push). Requirements are frozen from this commit.
- `docs/decisions/` 下整理了 4 个文件（对外部审阅的处理、对 6 个疑问的回复、Analyze Requirements 的回答、提交和进入设计），等用户过目，没提交。
  EN: Drafted 4 files under docs/decisions/ from the user's chat replies; awaiting review, not committed.
- 写了 `.kiro/specs/refcov-skeleton/design.md`：8 个模块、一个带哈希链的日志放所有记录、5 个 MCP 工具、7 个钩子文件（5 种事件）、单元 ID 和拆分规则（`#` 到 `###` 拆，超长 4000 字符）、属性测试的数据生成、先通"登记 → 拆 → MCP 读 → 记录 → 报告"再做关卡。
  EN: Wrote design.md: 8 modules, one hash-chained log for all records, 5 MCP tools, 7 hook files on 5 events, unit-ID and split rules (split at #–###, 4000-character limit), Hypothesis data generation, thin path before gates.
- 用 spec-auditor 审设计（作为子 agent 调用，提示词里让它改查"设计引用的需求编号是否存在、每条验收标准有没有对应、和需求冲突的地方、和 citation.md 是否一致"）。它查出：2 条验收标准没有对应（1.3、17.4）；6 处和需求冲突（AI 用 shell 跑 `refcov add`、`refcov init` 拦不住；经 MCP 的报告没有本会话数；按会话的数字不在默认报告；例子缺时间和会话；`DEVLOG.md` 的路径）；1 处设计内部不一致（英文摘要的钩子数写错）；3 处和 citation.md 不一致，其中拆分后 ID 撞车是真漏洞。报告原文和 agent 的处理建议附在 design.md 末尾，设计还没按它改。
  EN: Ran spec-auditor as a sub-agent on the design with a custom checklist. It found 2 uncovered criteria (1.3, 17.4), 6 conflicts with requirements, 1 internal inconsistency, and 3 mismatches with citation.md including a real ID-collision gap. The report and the agent's proposed fixes are appended to design.md; the design is not yet revised.
- spec-auditor 的提示词原本只会审需求文档的出处。这次在调用时另给了检查清单，它照做了，说明同一个只读 agent 可以按调用时的提示换审查对象。
  EN: spec-auditor was built to audit requirement citations; given a different checklist at call time it audited the design instead.
- 用到的 Kiro 功能：规格流程（设计阶段）、自定义 agent 当子 agent 调用。
  EN: Kiro features used: spec design phase, a custom agent invoked as a sub-agent.

## 2026-11-10（夜：设计第二版）

- 用户看过设计和 decisions，要求按 spec-auditor 的处理建议改，另加 5 条：shell 里跑 `refcov init`（和任何清空、重建日志的子命令）一律拦，`refcov add` 放行；拆分后缀用 `@2`、重名后缀用 `-2`；加 `git check-ignore` 测试（需求 1.3）；`docs/decisions/` 的文件列校验值、没确认的标红"待用户确认"，用户用 `refcov confirm` 确认；17.4 和"MCP 报告给不出本会话数"记进"以后再做"。
  EN: The user asked for the auditor's fixes plus five changes: block init (and any log-resetting subcommand) from the shell but allow add; `@2` for split parts and `-2` for duplicate headings; a git check-ignore test; checksum and user confirmation (`refcov confirm`) for docs/decisions files; two items to the later list.
- 改动（详见 design.md 末尾"报告的处理结果"表）：
  - 命令行 `init`、`confirm` 列进 `USER_ONLY`，`hook.py` 用正则拦 shell 里的这两个子命令；`hook.py` 不能 import 核心层，所以抄一份元组，用测试保持一致。
  - 新增第 3.6 节：钩子配置、接入层脚本、`docs/decisions/` 用同一套校验值办法，只差基准（上一次报告 / 最后一次 `confirm` 记录）。
  - 日志每行都带 `session`；报告例子补上时间和会话；`by_session` 进默认报告；经 MCP 的报告本会话一栏为"不可用"。
  - 默认豁免改成 `DEVLOG.md`、`**/DEVLOG.md`、`docs/decisions/**`。
  - 英文摘要的钩子数改对（7 个文件、5 种事件）。
  EN: Design changes: init/confirm are user-only and blocked in shell commands; new section 3.6 tracks checksums for hook files, integration scripts and decisions files with different baselines; every log line carries a session field; by_session is in the default report; MCP reports mark the session column unavailable; default exemptions cover DEVLOG.md anywhere; the EN summary hook count was fixed.
- 改的时候发现两点：
  - 用户要的"citation.md 的正则要能认 @"，现有正则 `[^\]\s]+` 本来就能匹配 `@`，所以正则没改，只在 citation.md 里写明。
  - 只换后缀还不够：标题里本身带 `@`（例如"退出码@2"）也会生成和拆分单元一样的 ID。所以生成 ID 时把标题里的 `@` 也换成 `-`。这比需求 2.5 原文多一个字符，记进了"以后再做"。
  EN: The existing citation regex already accepts `@`, so it was not changed. A heading that itself contains `@` could still collide with a split ID, so ID generation also replaces `@` with `-`; this goes beyond requirement 2.5's wording and is in the later list.
- `git check-ignore` 测试有个坑：本机的 `.kiro/settings/mcp.json` 是用户有意写进 `.git/info/exclude` 的，`git check-ignore` 也会报它被忽略。所以测试只把来自 `.gitignore` 的命中算失败（用 `-v` 看命中的规则来自哪个文件）。
  EN: git check-ignore also reports the deliberately excluded local mcp.json, so the 1.3 test only fails on matches whose source is a .gitignore file.
- `citation.md` 同步改：幻影需求改成"需求块里没有有效引用"，待定问题 2 定为需求级，补了 ID 生成规则和 `refcov confirm`。
  EN: citation.md updated: phantom = no valid reference anywhere in the requirement block; question 2 settled (requirement level); ID rules and refcov confirm added.
- 这次的回复也存成了 decisions 文件 `docs/decisions/2026-11-10-design-review.md`，还没给用户看，所以这次不提交它。
  EN: This reply was drafted as docs/decisions/2026-11-10-design-review.md; it has not been reviewed and is left out of this commit.

## 2026-11-10（夜：提交设计第二版，写 tasks.md）

- 提交 `c23e09f`（设计第二版、`citation.md`、DEVLOG、decisions 前 4 个文件），普通推送，一次成功。`2026-11-10-design-review.md` 没提交，等用户过目。
  EN: Committed c23e09f (design v2, citation.md, DEVLOG, the four reviewed decisions files) and pushed normally on the first try; the new decisions draft was left out pending review.
- 提交时发现 `experiments/mcp-posttooluse/logs/server.jsonl` 又变了：`.kiro/settings/mcp.json` 还指着试验服务，Kiro 一直连着它，日志在继续写。没提交这处变化。
  EN: server.jsonl kept changing because the workspace mcp.json still points at the probe server; that change was not committed.
- 写了 `tasks.md`，20 个任务。1–7 是最细通路（store 和哈希链、`.gitignore` 检查、ID 和文档适配器、`refcov add`、MCP 两个读工具、会话补记钩子、报告和一行简短报告），8 是检查点，9 开始用它管自己，10–12 出处检查、达标和属性测试，13–18 关卡，19 凭证，20 文档。逐条对过需求，每条未删除的验收标准至少出现在一个任务的 `_需求：…_` 里；对的时候发现 13.1（核心层不出现 Kiro 的名字）漏了，补进任务 12。
  EN: Wrote tasks.md with 20 tasks: 1–7 the thinnest path, 8 a checkpoint, 9 self-hosting, 10–12 citations, pass/fail and property tests, 13–18 gates, 19 tokens, 20 docs. Every non-deleted criterion appears in at least one task; 13.1 was missing at first and was added to task 12.
- README 目录表补了 `docs/decisions/`、`design.md`、`tasks.md`，还没提交。
  EN: README layout table now lists docs/decisions/, design.md and tasks.md (not committed yet).

## 2026-11-10（夜：tasks.md 按用户意见改，今天收工）

- 按用户意见改了 `tasks.md` 三处：最细通路（任务 1–7）的目标从 2026-11-12 改成 11-14，因为用户 11-12 要先写两个应用和演示页的需求；任务 18（任务开工关卡）、19（凭证）标成可选（`- [ ]*`）；写文件关卡挪到 `init`/`confirm`/校验值前面，两者编号对调，现在 15 是写文件关卡、16 是 `init`/`confirm`。上一条 DEVLOG 里的任务编号按旧顺序，不改。
  EN: tasks.md: the thin-path target moved from 2026-11-12 to 11-14 (the user writes the app and demo requirements on 11-12); tasks 18 and 19 are optional; the write gate moved ahead of init/confirm, so task 15 is now the write gate and 16 is init/confirm. Earlier DEVLOG entries keep the old numbering.
- `design.md` 第 10 节仍写"第 1–4 步在 2026-11-12 前跑通"，这次没改（用户只点名了 tasks.md），和 tasks.md 不一致，下次改设计时一起改。
  EN: design.md section 10 still says 2026-11-12; left unchanged this time and noted as an inconsistency.
- `docs/decisions/2026-11-10-design-review.md` 用户看过，定稿提交。
  EN: The user approved docs/decisions/2026-11-10-design-review.md; committed as final.
- 用户在 `.kiro/settings/mcp.json` 里关掉了试验服务。`experiments/mcp-posttooluse/logs/server.jsonl` 之后多出来的行没提交，用 `git checkout` 恢复成上次提交时的内容。
  EN: The user disabled the probe server in mcp.json; the extra lines in server.jsonl were discarded with git checkout, not committed.

## 2026-11-11（上午：按设计第二版的外部审阅改 design.md 和 tasks.md）

- 收到对设计第二版和任务清单（提交 `694d340`）的外部审阅，存为 `docs/设计第二版审阅.md`。审阅没有运行代码。用户定了三件事，其余指定照审阅改；不出设计第三版，只改 `design.md`、`tasks.md` 里对应的句子。
  EN: Received an external review of design v2 and tasks.md (commit 694d340), saved as docs/设计第二版审阅.md; the reviewer ran no code. The user decided three items and told the agent to apply the rest; only the matching sentences in design.md and tasks.md were edited, no design v3.
- 用户的三个决定：
  - 一.2：`refcov add` 加进 `USER_ONLY`，只有用户能在终端跑。原来放行的理由（重新登记只会让覆盖率变低）不成立：AI 可以用同一个 ID 登记一个很小的文件，把参考源变成一个单元，读一下就是 100%。设计第 6、8、11 节和任务 4、14 跟着改；"以后再做"里 14.4 那一条标了已不再偏离。
    EN: 1.2: refcov add joins USER_ONLY (user-only, blocked in AI shell commands). The old reason was wrong: re-registering a tiny file under the same ID makes one read reach 100%. Design §6, §8, §11 and tasks 4 and 14 updated; the 14.4 backlog item is marked resolved.
  - 三.1：砍掉 `refcov init`。配置由用户从 `integrations/kiro/refcov.example.toml` 手动复制（README 写一行，放进任务 1），状态目录第一次写入时自动建。原任务 16 改成可选。这也消掉了一.6（核心层命令行写死接入层路径）。
    EN: 3.1: refcov init is cut. The user copies the example config by hand (README line, task 1); the state directory is created on first write. Old task 16 becomes optional. This also removes issue 1.6 (core CLI hard-coding an integration-layer path).
  - 三.2：原任务 18（任务开工关卡）改成必做，排在原任务 16 前面。
    EN: 3.2: old task 18 (task-start gate) becomes required and moves ahead of old task 16.
- 任务编号：原 18 和原 16 对调，现在 16 是任务开工关卡（必做），18 是 `refcov confirm` 和文件校验值（可选，不含 `init`），17 不变。下面各条里的任务编号都按新编号。
  EN: Renumbering: old tasks 18 and 16 swapped. Task 16 is now the task-start gate (required), task 18 is refcov confirm plus file checksums (optional, no init); task 17 is unchanged. Task numbers below use the new numbering.
- 一.1（怎么找到代码和仓库根目录）：设计第 2 节新增几条。核心层不按当前目录找状态目录，根目录由调用方传入；`hook.py` 按自己的文件位置算根目录并放进 `sys.path`；MCP 服务用 `--root` 启动参数，`docs/mcp.example.json` 写出它；用 PATH 上的 `python` 跑 `pip install -e .`，写进 README。任务 1、5、6 跟着改，任务 6 的完成标志加"`.refcov/errors.log` 是空的"。
  EN: 1.1: design §2 now says the core never locates the state directory from the working directory; hook.py derives the repo root from its own path and puts it on sys.path; the MCP server takes --root; install with pip install -e . into the PATH python. Tasks 1, 5, 6 updated; task 6 now also requires an empty errors.log.
- 一.4（shell 文本匹配会拦住本项目的日常开发）：`.refcov`、`refcov.toml` 仍是出现就拦；`integrations/kiro`、`refcov_mcp` 改成只在被执行时拦（用 Python 运行 `hook.py`、`-m refcov_mcp`）。`git add integrations/kiro/hook.py`、`pytest tests/test_refcov_mcp.py` 能跑了。设计第 8 节第 2 步重写，任务 14 的测试加了这几条。
  EN: 1.4: .refcov and refcov.toml still block on any mention; integrations/kiro and refcov_mcp now block only when executed (python … hook.py, -m refcov_mcp), so git add on integration files and pytest on MCP tests pass. Design §8 step 2 rewritten; task 14 tests extended.
- 改一.4 时发现审阅没提到的一点：用管道把样例喂给 `hook.py` 自测，仍然是"用 Python 运行钩子脚本"，任务 14 之后照样被拦。所以设计里写明钩子脚本的自测改写成 pytest 测试（命令文本是 `pytest …`），测试用临时目录当仓库根目录；任务 7 的自动测试也按这个写法。另外 `py` 启动器、拼接字符串仍然匹配不上，归进需求 11.4 的局限。
  EN: Found while applying 1.4: piping a sample into hook.py is still "running the hook script" and stays blocked after task 14, so hook self-tests become pytest tests using a temp repo root (task 7 uses this). The py launcher and string concatenation still slip through, covered by the 11.4 limitations.
- 一.5（保护检查写错会把 Kiro 锁死）：设计第 8 节和任务 14 加逃生办法：用户把 `.kiro/hooks/refcov-pre-*.json` 移出 `.kiro/hooks/` 立即停用，README 写明。
  EN: 1.5: added an escape hatch to design §8 and task 14: moving .kiro/hooks/refcov-pre-*.json out of .kiro/hooks disables them at once; to be documented in the README.
- 一.7（`watch` 组的标红只出现一次）：随原任务 16（现在的任务 18）推后。设计 3.6 写明只有终端跑 `refcov report` 更新基准，钩子和 MCP 生成的报告只比较。改的时候发现：AI 在 shell 里跑 `refcov report` 也会更新基准，命令行分不出是谁在跑，留到做任务 18 时再定要不要拦。
  EN: 1.7: deferred with task 18. Design §3.6 now says only the terminal refcov report updates the watch baseline; hook and MCP reports only compare. Open point found while editing: an AI running refcov report in the shell would also update it; to be decided in task 18.
- 一.8（小处）全部写进设计：MCP 返回顺序是正文 → 提示 → `refcov-call:`，钩子只认最后一行；哈希按不含换行符的 UTF-8 内容算，换行固定 `\n`，`.gitattributes` 写 `*.jsonl -text`；路径和模式转小写后用 `fnmatchcase`；2 秒拿不到锁时 `api.read` 报错、不返回内容；shell 钩子匹配加 `execute_bash`（本机测不到）；`.gitignore` 加 `errors.log`、`log.lock`、`report-last.json`，`log.jsonl`、`sources.json` 照常提交。`.gitignore`、`.gitattributes` 的实际改动放进任务 1，这次没动。
  EN: 1.8: all small fixes went into the design: refcov-call is always the last line; hashes cover the line without its newline, LF only, *.jsonl -text; lowercase plus fnmatchcase; api.read fails if the lock is not acquired in 2 s; execute_bash added to the shell matcher (untestable here); errors.log, log.lock and report-last.json to be ignored. The .gitignore and .gitattributes edits themselves are in task 1, not done yet.
- 一.3（PostFileSave 去重和实测对不上）：按用户要求不先测，放进任务 17 第一步：实测 AI 用 shell 写文件时 PostFileSave 触不触发。不触发就不做 `refcov-file-save.json`；触发就让 PostToolUse 每次写入都记，"来源不明"在生成报告时按前后 10 秒判断。设计第 6、8、11 节写了两个分支。
  EN: 1.3: not tested now; task 17 starts by testing whether a shell write fires PostFileSave. If not, the PostFileSave hook is dropped; if yes, every write is recorded and "unknown source" is decided at report time within a 10-second window. Both branches are in design §6, §8, §11.
- 第二节（任务清单）全部照改：
  - 任务 4：自动测试改用 `tests/` 下的本地 Markdown 样例；登记 `kiro.dev` 改成手动检查，失败不算任务失败。
  - 任务 6：完成标志改成看日志（有 `read` 行、没有对应的 `session` 行）；"会话未知计数"挪到任务 7。
  - 任务 7：加一条自动测试，用 pytest 把 UserPromptSubmit 样例从 stdin 喂给 `hook.py`，查 stdout；AI 的转述只作旁证。
  - 任务 9：比赛规则页由用户存成本地 Markdown，放在 `.refcov/` 下、`cache/` 旁边，再登记。
  - 任务 10：测试改用固定样例文件，不用 `requirements.md`。
  - 任务 11：加最后一步，把 `requirements.md` 的文字出处换成 `[ref:…]`，结果记进 DEVLOG。
  - 任务 15：开头写明用户先手动建好带 `[[scope]]` 的 `refcov.toml`。
  - 持续集成从任务 12 提到任务 2，需求 13.5 跟着挪。
  - 设计第 10 节的目标日期 11-12 改成 11-14，和 tasks.md 一致（11-10 记过的不一致已消掉）。
  EN: Section 2 applied in full: task 4 tests use a local Markdown sample (kiro.dev registration is a manual check); task 6 checks the log directly and the unknown-session count moves to task 7; task 7 adds a pytest that pipes a UserPromptSubmit sample into hook.py; task 9 has the user save the rules page as local Markdown; task 10 tests use a fixed sample; task 11 ends by converting requirement citations to [ref:…]; task 15 starts with the user creating refcov.toml; CI moves from task 12 to task 2; design §10 target date changed from 11-12 to 11-14.
- 没照做的：三.4（凭证放最后）、三.5（`tokens`、`files` 两栏推后）、"骨架做到哪一步就转去做应用"，用户这次没点名。
  EN: Not applied because the user did not name them: 3.4 (tokens last), 3.5 (defer the tokens and files report fields), and the "switch to the apps after these tasks" suggestion.
- README 目录表补了 `docs/设计第二版审阅.md` 一行（`language.md` 要求目录变了同步改）。其余 README 改动（安装、复制配置、逃生办法、提交清单）按任务 1、14 做，这次没写。
  EN: README layout table gained a row for the new review file, per language.md. The other README additions (install, config copy, escape hatch, committing the manifest) belong to tasks 1 and 14 and were not written yet.
- 用到的 Kiro 功能：规格流程（设计、任务两份文件按审阅逐句修改，没有重新生成）。
  EN: Kiro feature used: the spec workflow, editing design.md and tasks.md sentence by sentence instead of regenerating them.

## 2026-11-11（下午：任务 1，项目结构和状态目录）

- 按 tasks.md 任务 1 建了 `pyproject.toml`（Python ≥ 3.11，运行依赖只有 `mcp`，开发依赖 `pytest`、`hypothesis` 放在 `[dev]`，命令行入口 `refcov`）、`refcov/`、`refcov_mcp/`（空包）、`integrations/kiro/refcov.example.toml`（按设计 3.4）、`tests/`。命令行 `refcov` 现在只有 `--version` 和帮助，子命令留给后面的任务。
  EN: Task 1: added pyproject.toml (Python ≥ 3.11, runtime dependency mcp only, pytest and hypothesis as the dev extra, console script refcov), the refcov/ and refcov_mcp/ packages (the latter empty), integrations/kiro/refcov.example.toml per design §3.4, and tests/. The refcov CLI only has --version and help so far.
- `refcov/store.py`：仓库根目录由调用方传入；状态目录 `.refcov/` 第一次写入时才建；`refcov.toml` 用 `tomllib` 读，不存在时用设计 3.4 的默认值；清单 `sources.json` 先写临时文件再替换；路径转成相对根目录的 `/` 形式、转小写后用 `fnmatchcase` 匹配；日志 `log.jsonl` 用 `log.lock`（`O_CREAT | O_EXCL`，50 毫秒重试，2 秒超时抛 `LockTimeout`，超过 10 秒的锁当残留删掉）加 `seq`、`time`、`session`、`prev` 哈希链，二进制追加，换行固定 `\n`。
  EN: refcov/store.py: the caller passes the repo root; .refcov/ is created on first write; refcov.toml is read with tomllib, falling back to the design §3.4 defaults; sources.json is written via a temp file and os.replace; paths are made root-relative with /, lowercased and matched with fnmatchcase; log.jsonl appends under log.lock (O_CREAT|O_EXCL, 50 ms retry, LockTimeout after 2 s, locks older than 10 s removed) with seq, time, session and a prev hash chain, written in binary with LF only.
- `.gitignore` 加了 `.refcov/errors.log`、`log.lock`、`report-last.json`（另加 `*.egg-info/`、`build/`，`pip install -e .` 会生成）；新建 `.gitattributes`，写 `*.jsonl -text`。`.kiro` 仍然没有被忽略。README 加了 Setup 一节（`pip install -e ".[dev]"`、复制配置），目录表和状态行按现状改了。
  EN: .gitignore now ignores .refcov/errors.log, log.lock and report-last.json (plus *.egg-info/ and build/ from the editable install); new .gitattributes with *.jsonl -text; .kiro is still not ignored. README gained a Setup section (pip install -e ".[dev]", copy the example config) and an updated layout table and status line.
- 测试 `tests/test_store.py` 14 个，全部通过（`D:\pyth\python.exe -m pytest`）：两个进程同时各追加 100 行，200 行 `seq` 为 1–200、链完整、锁文件已放掉（连跑 5 次都过）；改第 3 行后报"第 4 行起断开"；把换行改成 CRLF 后报断开；新鲜的锁拿不到时报错且日志不变；残留锁被删掉。这次没写属性测试，任务 1 不涉及需求 16 的性质。
  EN: tests/test_store.py has 14 tests, all passing under D:\pyth\python.exe: two processes appending 100 lines each give seq 1–200, an intact chain and no leftover lock (passed 5 runs in a row); editing line 3 reports "broken from line 4"; CRLF line endings break the chain; a fresh foreign lock times out with the log unchanged; a stale lock is removed. No property tests this time; task 1 touches none of the requirement 16 properties.
- 发现：改第 N 行时，断开报在第 N+1 行（第 N+1 行的 `prev` 对不上），不是第 N 行；最后一行被改或被删查不出来。代码注释里写明了，点子记进"以后再做"。
  EN: Finding: editing line N is reported as a break at line N+1 (that line's prev no longer matches), and edits to or removal of the last line go undetected. Documented in the code; an idea is in the backlog section.
- 问题 1（环境）：这个 shell 里 PATH 上的 `python` 是 `C:\msys64\mingw64\bin\python.exe`（3.12），没有 pip，也没有 `mcp`。装了 `mcp` 的是 `D:\pyth\python.exe`（也是 `py` 的默认）。这次把 `pip install -e ".[dev]"` 装进了 `D:\pyth\python.exe`，没有动 msys 的 Python。Kiro 钩子里的 `python` 实际是哪一个没测；如果是 msys 那个，任务 6 的钩子会 import 失败、无声放行。要用户决定：调整 PATH，还是钩子命令写明解释器。
  EN: Issue 1 (environment): in this shell the first python on PATH is C:\msys64\mingw64\bin\python.exe (3.12) with no pip and no mcp; D:\pyth\python.exe (also the py default) has mcp. The editable install went into D:\pyth\python.exe; the msys Python was left untouched. Which python Kiro hooks actually run was not tested; if it is the msys one, task 6 hooks will fail to import and silently allow. The user needs to choose between fixing PATH and naming the interpreter in hook commands.
  2026-11-11 更新：用户把 `D:\pyth` 放到系统 PATH 最前面并重启了 IDE。agent 的 shell 里 `python -c "import sys, mcp; print(sys.executable)"` 输出 `D:\pyth\python.exe`，`import mcp` 成功，`Get-Command python` 也指向它；`import refcov` 指向仓库里的 `refcov/__init__.py`（可编辑安装生效），14 个测试照常通过。钩子进程里的 `python` 是哪一个仍然没测，留到任务 6 用钩子实测。
  EN: Update 2026-11-11: the user put D:\pyth first on the system PATH and restarted the IDE. In the agent shell, python now resolves to D:\pyth\python.exe, import mcp works, import refcov points at the repo (editable install active), and all 14 tests pass. Which python a hook process runs is still untested; task 6 will check it with a real hook.
- 偏离示例的一处：`refcov.example.toml` 里 `[relax] units` 留空，设计 3.4 例子里的 `kiro-hooks/更新日志` 改成注释，免得复制后放宽一个还不存在的单元。
  EN: One deviation from the design example: [relax] units is empty in refcov.example.toml, with kiro-hooks/更新日志 kept only as a comment, so a copied config does not relax a unit that does not exist yet.
- 用到的 Kiro 功能：规格任务执行（子 agent 按 tasks.md 任务 1 执行）。
  EN: Kiro feature used: spec task execution, with a sub-agent running task 1 from tasks.md.

## 2026-11-11（晚：任务 2，.gitignore 检查和持续集成）

- 用户点 Start task 后，tasks.md 里任务 2 标成进行中；`tests/test_gitignore.py` 和 `.github/` 都是这次新建的。`tasks.meta.json` 里这次执行有两条记录（同一个 `executionId`，相隔约 3 分钟），各代表什么没有核实。
  EN: After the user clicked Start task, task 2 was marked in progress; tests/test_gitignore.py and .github/ were created in this run. tasks.meta.json holds two entries with the same executionId about 3 minutes apart; what each one means was not checked.
- `tests/test_gitignore.py`：遍历磁盘上 `.kiro` 下的所有文件（已跟踪、未跟踪都算），加上 3 个构造路径，用 `git check-ignore -v -z --no-index --non-matching --stdin` 一次查完，按输出里的规则来源判断：来源文件名是 `.gitignore` 且规则不以 `!` 开头才算失败；`.git/info/exclude` 和否定规则不算。用 `-z` 和 stdin 传路径，含中文、空格、方括号的文件名不会被 git 转义。找不到 git、git 出错或输出解析不了时 `pytest.fail`，不跳过。
  EN: tests/test_gitignore.py walks every file under .kiro on disk plus 3 constructed paths and checks them in one call to git check-ignore -v -z --no-index --non-matching --stdin. It fails only when the matching rule comes from a file named .gitignore and is not a negation; hits from .git/info/exclude and negation rules pass. Paths go through -z and stdin so names with CJK, spaces or brackets are not quoted by git. Missing git, a git error or unparsable output fail the test instead of skipping it.
- 另加 2 个用临时 git 仓库的测试，确认检查本身有效：根目录 `.gitignore` 写 `.kiro/hooks/`、`.kiro/specs/.gitignore` 写 `*.md` 时都被报出来；只在 exclude 里忽略、或 `.gitignore` 里先忽略 `*.json` 再 `!.kiro/**` 时不报。
  EN: Two extra tests on a temporary git repo show the check works: `.kiro/hooks/` in the root .gitignore and `*.md` in .kiro/specs/.gitignore are both reported; an exclude-only rule, or `*.json` followed by `!.kiro/**` in .gitignore, is not.
- 持续集成：`.github/workflows/ci.yml`，GitHub Actions 在 `ubuntu-latest` 上用 Python 3.11 和 3.12 跑 `pip install -e ".[dev]"` 和 `python -m pytest`，权限只给 `contents: read`。还没推送，CI 在 GitHub 上没跑过。
  EN: CI: .github/workflows/ci.yml runs pip install -e ".[dev]" and python -m pytest on ubuntu-latest with Python 3.11 and 3.12, with contents: read permission only. Not pushed yet, so CI has not run on GitHub.
- 本机（Windows，`D:\pyth\python.exe`）：`pytest tests/test_gitignore.py` 3 个通过，全量 `pytest` 17 个通过。实际仓库里 `.kiro/settings/mcp.json` 命中的是 `.git/info/exclude:9`，按设计不算失败。没有属性测试，任务 2 不涉及需求 16 的性质。
  EN: Locally (Windows, D:\pyth\python.exe): 3 tests in tests/test_gitignore.py and 17 in the full suite pass. In the real repo .kiro/settings/mcp.json matches .git/info/exclude line 9, which by design is not a failure. No property tests; task 2 touches none of the requirement 16 properties.
- 用到的 Kiro 功能：规格任务执行（子 agent 按 tasks.md 任务 2 执行）。
  EN: Kiro feature used: spec task execution, with a sub-agent running task 2 from tasks.md.
- README 的状态行和目录表补上了 `test_gitignore.py` 和 `.github/workflows/ci.yml`。
  EN: The README status line and layout table now mention test_gitignore.py and .github/workflows/ci.yml.
- 按用户要求把 `ci.yml` 里的 `actions/checkout@v4` 改成 `@v5`、`actions/setup-python@v5` 改成 `@v6`，Python 3.11、3.12 两个版本不变。提交 `ee011a4`。
  EN: Per the user, ci.yml now uses actions/checkout@v5 and actions/setup-python@v6; the Python 3.11 and 3.12 matrix is unchanged. Commit ee011a4.
- 问题 2（网络）：第一次 `git push origin main` 报 `TLS connect error: error:00000000:lib(0)::reason(0)`，原样重试一次就推上去了（`c51734a..ee011a4`），没有出现 workflow 权限错误。推送后 shell 里用 `Invoke-RestMethod` 查 GitHub API 连续两次报 `Received an unexpected EOF or 0 bytes from the transport stream`，改用 agent 的网页抓取工具查公开 API 才拿到结果。
  EN: Issue 2 (network): the first git push origin main failed with a TLS connect error; the same command succeeded on retry (c51734a..ee011a4), with no workflow-permission error. Invoke-RestMethod against the GitHub API then failed twice with an unexpected EOF; the public API was read with the agent's web fetch tool instead.
- CI 第一次运行（run 43016103431，push 触发）：`test (3.11)` 和 `test (3.12)` 两个作业都是 success，Install、Test 各步都成功，总共约 20 秒。结论来自公开 API 的 runs 和 jobs 接口；日志要登录才能下载，所以 Linux 上跑了几个测试没看到，只知道 pytest 退出码为 0。
  EN: First CI run (run 43016103431, on push): both test (3.11) and test (3.12) succeeded, every step including Install and Test, in about 20 s. Taken from the public runs and jobs API; logs need authentication, so the Linux test count was not seen, only that pytest exited 0.

## 2026-11-11（夜：任务 3，单元 ID 和文档适配器）

- 这次不是点 Start task 执行的：用户在聊天里让主 agent 直接做任务 3，tasks.md 的勾是 agent 手动打的，`tasks.meta.json` 没有这次的记录。
  EN: Task 3 was run by the main agent from a chat request, not via Start task; the agent ticked tasks.md by hand and tasks.meta.json has no entry for it.
- 写代码前 agent 先停下来问了两处设计没写清的地方，用户的决定已补进设计第 4 节第 2 条和 `citation.md` 第 2 条（英文摘要同步改）：
  EN: Before coding, the agent stopped on two gaps in the design; the user's decisions were added to design §4 item 2 and citation.md item 2 (English summary updated too):
  - 重名后缀撞上本身就叫"退出码-2"的标题时：先给每个标题保留它自己的 ID，重名的从 `-2` 起找空号，避开所有标题自己的 ID。"退出码""退出码""退出码-2"得到 `退出码`、`退出码-3`、`退出码-2`。理由：前面多出一个重名章节时，本身不重名的标题 ID 不变，已写好的引用不失效。
    EN: Duplicate suffixes skip every heading's own ID, so "退出码", "退出码", "退出码-2" become 退出码, 退出码-3, 退出码-2; adding a duplicate section never renames a heading that is itself unique.
  - 查重不区分大小写（`casefold`），ID 保留原大小写："Hooks""hooks"得到 `Hooks`、`hooks-2`。
    EN: Duplicate checks use casefold; IDs keep their case ("Hooks", "hooks" give Hooks, hooks-2).
- 新文件：`refcov/sources.py`（适配器接口 `split`、`read`、`facts` 三个函数，加 `name`、`kinds` 两项声明；`title_to_id`、`assign_ids`、`split_long`、`make_units`、`validate_unit_id`、`check_declarations`），`refcov/adapters/markdown.py`，`tests/test_sources.py`，`tests/test_markdown.py`。
  EN: New files: refcov/sources.py (adapter interface with split, read and facts plus name and kinds declarations; ID, split and validation helpers), refcov/adapters/markdown.py, tests/test_sources.py, tests/test_markdown.py.
- 按用户定的细则实现：先统一换行再拆分、算长度和 SHA-256；标题行最多 3 个空格缩进、1–3 个 `#`、后面是空白或行尾，收尾的 `#` 前面有空白才去掉（`## A#` 的标题是 `A#`）；``` 和 ~~~ 两种围栏，闭合要同一种字符、不短于开头、后面只有空白，没闭合的算到文件末尾；`>` 开头的行不当标题、正文照留；第一个标题前只有空白时不成单元；切点是 4000 字内最后一个空行（只含空格、制表符的行也算），前一段会只剩空白时改成硬切。另外两处 agent 自己定的：`#` 后面跟制表符也算标题；`split` 按 `utf-8-sig` 解码，开头的 BOM 去掉。
  EN: Implemented the user's rules: normalize newlines first; ATX headings with ≤3 leading spaces, 1–3 #, then whitespace or end of line, closing # removed only after whitespace; ``` and ~~~ fences closed by the same character with at least the same length, unclosed fences run to the end; > lines are never headings but stay in the body; a whitespace-only preamble is dropped; split after the last blank (or space/tab-only) line within 4000 characters, hard cut if that would leave a whitespace-only part. Agent's own choices: a tab after # also counts, and split decodes with utf-8-sig to drop a BOM.
- `markdown.py` 不含注释、文档字符串和空行是 38 行（全文 62 行），在 50 行以内，设计里不用写原因。
  EN: markdown.py is 38 lines excluding comments, docstrings and blank lines (62 in total), under the ~50-line target.
- 测试：两个新文件共 76 个，全量 93 个，本机全部通过（`D:\pyth\python.exe`）。完成标志 2 的样例（开头一段 `> ## Documentation Index` 引用，`#`、`##`、`###`、`####` 各级标题，代码块里有 `# 注释`）拆出 5 个单元，标题依次是 `hooks`（开头那段）、`Hooks`、`Exit codes`、`Matchers`、`Examples`，ID 依次是 `hooks-2`、`Hooks`、`Exit-codes`、`Matchers`、`Examples`，`####` 留在 `Matchers` 里。
  EN: 76 new tests, 93 in total, all passing locally. The completion sample (a leading "> ## Documentation Index" quote, #–#### headings, "# 注释" inside a code block) gives 5 units titled hooks (the preamble), Hooks, Exit codes, Matchers, Examples, with IDs hooks-2, Hooks, Exit-codes, Matchers, Examples; #### stays inside Matchers.
- 发现：kiro.dev 的 `.md` 页面开头的 `> ## Documentation Index` 引用块会成为一个单元，标题是文件名，也是严格必看的。按最初的写法它排在最前、先分 ID，拿走了 `hooks`，真正的 `# Hooks` 章节变成 `Hooks-2`。agent 报给用户后，用户决定：借文件名的单元最后分 ID，先给所有真标题分完，和真标题撞了（不分大小写）由它从 `-2` 起找空号；它在清单里仍排第一。现在 `# Hooks` 是 `Hooks`，开头那段是 `hooks-2`。改了 `assign_ids`、`make_units`（新参数 `borrowed`）和 `markdown.sections`，设计第 4 节第 5 条、`citation.md` 第 2 条各补了一句。
  EN: Finding: on kiro.dev .md pages the leading "Documentation Index" quote becomes its own strictly required unit named after the file. As first written it got its ID first, took "hooks", and pushed the real "# Hooks" section to Hooks-2. After the agent reported this, the user decided that a unit named after the file gets its ID after all real headings and takes the suffix on a (case-insensitive) clash, while staying first in the manifest. Now "# Hooks" is Hooks and the preamble is hooks-2. Changed assign_ids, make_units (new borrowed parameter) and markdown.sections; design §4 item 5 and citation.md item 2 each gained a sentence.
- 属性测试（7 条 `@given`，第 7 条是改借文件名单元时加的"借来的标题不抢真标题的 ID"）：没抓到代码里的错。agent 临时让 `assign_ids` 忽略 `borrowed`，第 7 条连跑 5 次都抓到，另用 `@example(["hooks", "Hooks"])` 固定了 kiro.dev 的情况。抓到的是测试自己的两个问题：
  EN: Property tests (7 @given tests; the 7th, "borrowed titles never take a real heading's ID", was added with the file-name change) found no bug in the code. With assign_ids temporarily ignoring borrowed, the 7th failed in 5 of 5 runs; @example(["hooks", "Hooks"]) pins the kiro.dev case. They exposed two problems in the tests themselves:
  - 第一次运行 2 个失败：`st.text` 的字母表里放了 `"\n\n"`、`"\r\n"` 这种多字符片段，Hypothesis 报 `InvalidArgument`。改成先生成片段列表再拼接。
    EN: First run: 2 failures because st.text was given multi-character alphabet entries ("\n\n", "\r\n"), which Hypothesis rejects with InvalidArgument; bodies are now built by joining a list of fragments.
  - agent 把 `assign_ids` 临时换成"先到先得"的做法，"本身不重名的标题保留自己的 ID"这条性质没抓到：原来的生成器很少让三个撞号的标题同时出现。加了一个只从 `a`、`A`、`a-2`、`A-2`、`a-3`、`a-2-2` 等里抽的小池子后，连跑 5 次都抓到了；另用 `@example(["a", "a", "a-2"])` 固定了这个情况。临时换实现又试了"不跳过空段"的切分，原来的性质就能抓到。
    EN: Swapping in a first-come assign_ids did not fail the "unique titles keep their own ID" property: the generator rarely produced the three colliding titles together. After adding a small pool (a, A, a-2, A-2, a-3, a-2-2, …) it failed in 5 of 5 runs, and @example(["a", "a", "a-2"]) pins the case. A split that allows empty parts was caught by the existing property.
- 局限（写进了 `markdown.py` 开头和 README）：下划线式标题（`===`、`---`）不拆；超长切分时代码块里的空行也可能被当成切点。另外：硬切时如果前 4000 字全是空白，会切出只含空白的段，属性测试里写明了这种情况允许。
  EN: Limits (noted at the top of markdown.py and in the README): setext headings are not split on; a blank line inside a code block can become a split point. Also, a hard cut can produce a whitespace-only part when the first 4000 characters are all whitespace; the property test allows exactly that case.
- 用到的 Kiro 功能：引导文档的 fileMatch 加载（读 `.kiro/specs/**` 时 `citation.md` 进了上下文，读 `tests/**` 时 `testing.md` 进了上下文）；规格流程（只按用户决定改 design.md 一条，没有重新生成）。
  EN: Kiro features used: fileMatch steering (citation.md loaded when the agent read .kiro/specs/**, testing.md when it read tests/**); the spec workflow, editing one design.md item per the user's decision without regenerating.
