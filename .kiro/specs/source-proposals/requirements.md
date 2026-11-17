# 需求文档：易用性改造第二层，资料提议与登记（第一版，2026-11-17，第二稿）

EN summary: Requirements for the first version of layer 2 (second draft). The AI proposes Markdown reference files, and one write tool registers them only after the user approves an `ask` prompt; the arguments the user sees are checked against the stored proposal. Registration only adds sources, never changes or removes existing ones, and never edits refcov.toml. init prints two permission rules: the read tools are allowed, and apply_proposal asks every time; doctor checks both in the text of the user-level file. Deletion, updates and scope changes stay outside this version. Accepted in install-test on 2026-11-18.

状态：**已验收（2026-11-18）。** 第二稿（2026-11-17）实现后，Claude 审过代码通过（16d07b8，检查点 3）；用户在 install-test 里验收，F 项改文字后重测通过，A 到 F 全部通过（见 DEVLOG 2026-11-18）。第一稿由 Claude 审过：通过（12b05ab，检查点 3），按审阅意见改完直接实现。第二稿的改动：需求 2（锁里再确认编号和路径，执行结果带调用编号）、需求 3（单元数按核心层算）、需求 4（两条规则，doctor 分别查，README 写明）、需求 5（不提供删除命令，手动删除后照常工作，有测试）、需求 6（测试清单）。设计写在 `design.md`，第 9 节是 Claude 的答复和对应的处理。

文字出处（未登记，待转换）：`docs/易用性改造方案.md` 第 3.2、3.3 节；`docs/权限实测结果.md` 第 3、4 节；用户在聊天里的指示（2026-11-17，还没有存成 `docs/decisions/` 下的文件，等用户过目）。Kiro 文档的权限单元已登记，出处写成 `[ref:…]`。

## 简介

现在把资料登记进 RefCov 要用终端命令，那是用户做的事。第二层让用户在 Kiro 里用自然语言说"把它登记成参考资料"：AI 先整理出一份提议，用户在 Kiro 的权限弹窗里批准，登记才发生。第一版只收 Markdown，只新增参考源，不改已有资料，不改必看范围，不改配置。

## 术语

- **提议**：`propose_sources` 生成的一份待批准记录，存在状态目录里。
- **校验值**：`refcov.sources.content_sha256` 的结果，即去掉 BOM、统一换行后的 UTF-8 文本的 SHA-256。清单里记的校验值用同一个算法。
- **批准框**：Kiro 对 MCP 工具调用弹出的确认。它只显示工具名；参数显示在它上方的工具卡片里。
- **必看范围**：必看集合，以及 `[[scope]]` 规则限定的参考源范围（见 `refcov/coverage.py`）。

## 第一部分：提议

### 需求 1：提议（只读，停在提议为止）
EN: Proposal: read-only, stops at a proposal

**用户故事：** 作为用户，我想让 AI 把我给的 Markdown 资料整理成一份提议，以便批准前看清它会登记什么。
EN: As a user, I want the AI to turn the Markdown files I give it into a proposal, so that I can see what will be registered before I approve.

#### 验收标准

1. THE `propose_sources` SHALL 只接收仓库里的 `.md` 和 `.markdown` 文件（UTF-8）。路径可以相对仓库根目录，也可以是仓库内的绝对路径。网址、视频和其他格式 SHALL 拒绝，并说明原因。
2. THE `propose_sources` SHALL 拒绝下面几种情况，并说明是哪一项、怎么办：解析符号链接后不在仓库内的文件；路径已在清单里的文件；被 `[sources]` 的通配符匹配的文件（这些由 `refcov sync` 登记）；编号不合规则的（只能是小写字母、数字和短横线，不能以 `f-` 开头），或编号已在清单里的；同一份提议里重复的路径或编号。
3. WHEN 文件通过检查，THE 提议 SHALL 记下每个文件的路径、完整校验值、拟用的参考源编号、拆出的单元数和标题，以及需求 3 规定的效果说明。
4. THE `propose_sources` SHALL 只在状态目录里存下这份提议。它 SHALL NOT 改清单、配置或必看范围，也 SHALL NOT 登记任何资料。提议不过期；执行时的校验值核对保证旧提议不会误登记。
5. IF 任一文件被拒绝或读不了，THE 命令 SHALL 不存提议，并说明是哪个文件。

出处：文字出处 `docs/易用性改造方案.md` 第 3.2 节（未登记，待转换）

## 第二部分：执行

### 需求 2：执行（唯一的写入工具，只执行已提议的内容）
EN: Apply: the only write tool, which runs only what was proposed

**用户故事：** 作为用户，我想让批准框里的参数就是实际执行的内容，以便批准前能核对，批准后不会被换掉。
EN: As a user, I want the arguments in the approval card to be exactly what runs, so that I can check them before I approve and nothing can change them afterwards.

#### 验收标准

1. THE `apply_proposal` 的参数 SHALL 是提议编号，加上每个文件的路径、校验值和参考源编号。服务端 SHALL 核对：项数、路径、校验值和编号与存下的提议逐项一致。任一不一致就拒绝，并说明是哪一项。
2. WHEN 执行时，THE 命令 SHALL 对每个文件重新计算校验值。与提议不一致（文件在提议后改过）就拒绝，并要求重新提议。每个文件 SHALL 只读一次，核对和登记用同一份内容。
3. THE 同一份提议 SHALL 只能成功执行一次。已执行过的提议再次执行 SHALL 拒绝。
4. THE 执行 SHALL 只新增参考源。编号和路径都不在清单里的才登记；不改、不删已有的参考源；不写 `refcov.toml`。登记的写入和登记子命令共用同一段代码（设计第 3.3 节），登记的对外行为不变。
5. WHEN 执行拿到日志锁，THE 执行 SHALL 在锁里再确认提议仍是待执行，并且每个编号和路径都不在清单里。不满足就拒绝，清单、缓存和日志都不变。
6. IF 任一文件在核对阶段不通过，THE 执行 SHALL 全部不写：清单、缓存和日志都不变。
7. WHEN 执行成功，THE 日志 SHALL 多一条 `apply` 记录，含提议编号、参考源编号、路径和校验值。
8. THE 执行 SHALL 再次检查每个路径仍在仓库内、是 Markdown，不只信任提议里存的内容。
9. WHEN 执行成功，THE 执行结果的最后一行 SHALL 是 `refcov-call: c-<编号>`，和读取单元的结果一样。接入层据此把会话补记到 `apply` 记录上（设计第 3.4 节）。

出处：`docs/权限实测结果.md` 第 4 节（批准框只显示工具名，参数在工具卡片里，所以参数必须和提议逐项一致）；`docs/易用性改造方案.md` 第 3.2 节（未登记，待转换）

### 需求 3：登记对必看范围的影响（提议和执行结果都要写）
EN: What registration does to the required set, stated in the proposal and in the result

**用户故事：** 作为用户，我想在批准前知道这份资料会让哪些路径要先读它，以便写文件时不会被关卡意外拦住。
EN: As a user, I want to know before I approve which paths must read the new material first, so that the write gate does not block me by surprise.

#### 验收标准

1. THE 提议 和 执行结果 SHALL 写明两类路径的影响：未命中任何 `[[scope]]` 的路径，新资料的单元立即必看，写文件前要先读；命中 `[[scope]]` 的路径，只看那条规则列出的参考源，这次登记不增加它们要读的单元。
2. THE 单元数 SHALL 用核心层的必看集合算出：按提议时的模式（strict 或 light）、配置里的 `[relax]`，以及需求文档里已有的引用。算不出时，SHALL 写"最多 N 个"，N 是新增单元的总数。
3. THE 第一版 SHALL NOT 改 `[[scope]]` 和 `[relax]`。要让命中的路径也读新资料，用户要自己在配置里把这个参考源编号加进那条规则。AI 不改配置。
4. THE 提议 和 执行结果 SHALL 说明：在用户改配置之前，命中规则的路径不会要求读新资料。

出处：`docs/易用性改造方案.md` 第 3.2 节（未登记，待转换）；`refcov/coverage.py` 的 `scope_sources` 和 `required_for_path`（说明依据的规则，见设计第 4 节）

## 第三部分：权限和边界

### 需求 4：权限规则：init 打印两条，doctor 分别查
EN: Two permission rules: init prints them, doctor checks each one

**用户故事：** 作为用户，我想知道让资料读取不弹窗、让登记每次都弹窗各需要哪条规则，并能用一条命令看到它们有没有设好。
EN: As a user, I want to know which rules make reads silent and make each registration ask, and to check with one command that both are set.

#### 验收标准

1. THE `refcov init` SHALL NOT 写用户级权限文件。它在仓库外，是用户的安全设置。它 SHALL 打印两条规则：第一条 `capability: mcp`，`effect: allow`，`match` 逐个列出 `<服务名>/list_units`、`<服务名>/read_unit`、`<服务名>/check`、`<服务名>/report`、`<服务名>/propose_sources`；第二条 `capability: mcp`，`match: ["<服务名>/apply_proposal"]`，`effect: ask`。服务名取 `.kiro/settings/mcp.json` 里指向 RefCov 服务的那一项的键名，通常是 `refcov`。
2. THE `refcov doctor` SHALL 用文本查找用户级权限文件（`~/.kiro/settings/permissions.yaml`），两条规则分别查。缺哪条，就给哪条的提示和修法。提示不算问题，不影响退出码。它 SHALL NOT 判断用户的其他规则。
3. IF 缺少 allow 规则，THE `doctor` 的提示 SHALL 写明："读资料时每次都会弹窗"，并列出缺的工具名。
4. THE 文档 SHALL 写明：Kiro 对 MCP 工具默认弹窗；弹窗里可以选 Always allow，选了以后就不再问；显式的 `ask` 规则下，弹窗不提供 Always allow（第 0 步实测）。两条规则分别解决"读取不弹窗"和"登记每次都弹窗"。
5. THE README 第 3 步 SHALL 写明这两条规则、放的位置、init 不替用户写这个文件，以及各自的原因。

出处：[ref:kiro-permissions/Defining-rules]（规则格式；用户级文件的位置，仓库里的文件注入不了规则）；[ref:kiro-permissions/Default-behavior]（新建权限文件是在默认规则上加，不替换；其余动作默认弹窗）；[ref:kiro-permissions/Interactive-approval-flow]（Allow 与 Always allow 的含义）；文字出处 `docs/权限实测结果.md` 第 3 节（实测，未登记，待转换）

### 需求 5：第一版不做的事
EN: What the first version leaves out

**用户故事：** 作为维护者，我想让第一版只做能测清楚的部分，以便 11-22 前做完，不留半截功能。
EN: As a maintainer, I want the first version limited to what can be tested fully, so that it is done by 11-22 with nothing half-built.

#### 验收标准

1. THE MCP 服务 SHALL NOT 提供：更新已有资料、删除参考源、缩小必看范围、改 `[[scope]]` 或 `[relax]`、登记网址、登记视频；也 SHALL NOT 把现有的同步函数原样暴露。
2. THE 第一版 SHALL 只收 Markdown。视频和网址留给第二版。
3. THE 第一版 SHALL NOT 写用户级权限文件，也 SHALL NOT 改 `refcov.toml`。
4. THE 第一版 SHALL NOT 分开显示两种变化：钩子看到的写入操作，和哈希比对出的文件变化。
5. THE 第一版 SHALL NOT 提供删除登记的命令。误登记的参考源由用户手动从清单里删。手动删除以后，`report`、`check` 和状态行 SHALL 照常工作、不报错。这一条有固定测试（设计第 6 节，M1）。

出处：`docs/易用性改造方案.md` 第 3.2 节（未登记，待转换）

### 需求 6：边界和测试
EN: Layer boundary, and the properties that the tests check

**用户故事：** 作为维护者，我想让新代码不把 Kiro 的名字带进核心层，并且关键性质有测试，以便接入层以后可以换。
EN: As a maintainer, I want the new code to keep Kiro names out of the core layer and the key properties tested, so that the integration layer can change later.

#### 验收标准

1. THE 提议和执行的逻辑 SHALL 放在核心层，只用标准库。MCP 服务 SHALL 只做参数转交和文字输出，不直接写清单。
2. THE 核心层和 MCP 服务的源码 SHALL 不出现 `tests/test_core_names.py` 列出的名字（工具名、事件名、`.kiro`）。权限规则的文字 SHALL 放在 `integrations/kiro/`。
3. THE 测试 SHALL 用 Hypothesis 检验设计第 6 节的 P1 至 P6：执行只新增；参数与提议不一致必拒；文件变了必拒；同一提议第二次必拒；提议不改清单、配置和必看集合；执行失败不留痕迹。另有固定测试 M1：手动删除清单里的一项以后，`report`、`check` 和状态行照常工作。
4. THE 测试 SHALL 覆盖两条权限规则的打印和 doctor 的提示，以及 MCP 工具清单（六个工具）和一次提议到执行的往返。
5. THE 验收 SHALL 由用户在 Kiro 里做（设计第 7 节）。自动测试不替代它。

出处：`.kiro/steering/tech.md`（核心层只用标准库；Kiro 的名字只放在接入层）；`.kiro/steering/testing.md`（每条性质至少一个 `@given` 测试）
