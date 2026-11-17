# 设计文档：易用性改造第二层，资料提议与登记（第一版，2026-11-17）

依据：`requirements.md` 第一版；`docs/易用性改造方案.md` 第 3 节；`docs/权限实测结果.md`。

读过的代码：`refcov/sources.py`（`register`、`_load_file`、`content_sha256`）、`refcov/store.py`（`locked`、`append_locked`、清单读写）、`refcov/coverage.py`（`scope_sources`、`required_for_path`）、`refcov/api.py`（`_spec_matches`、`plan_sync`、`AUTO_ID`）、`refcov/cli.py`（`_add`）、`refcov_mcp/server.py`、`integrations/kiro/init.py`、`integrations/kiro/doctor.py`、`tests/test_core_names.py`。

Kiro 文档单元，经 MCP 的 `read_unit` 读过（2026-11-17）：`kiro-permissions/Defining-rules`、`Default-behavior`、`Approve-for-me`、`Interactive-approval-flow`、`Workspace-trust`、`CI-and-headless-environments`、`Approval-rule-tiers`、`Security-and-trust`。

状态：第一版，待 Claude 审（检查点 3）。未写代码。

## 1. 改动范围

| 文件 | 改什么 |
|---|---|
| `refcov/proposals.py`（新，只用标准库） | 提议的存取；`propose()` 和 `apply()`（第 2 至 4 节） |
| `refcov/sources.py` | 把 `register` 的锁里写入段抽成 `write_locked()`，`register` 和 `apply` 共用（第 3.3 节）。**核心层改动，需审** |
| `refcov/store.py` | 常量 `PROPOSALS_DIR = "proposals"` |
| `refcov/api.py` | `propose_sources(store, items)`、`apply_proposal(store, proposal_id, items)`，各自返回文字结果 |
| `refcov_mcp/server.py` | 两个工具：参数转交给 `api`，结果用文字块返回，不写逻辑 |
| `integrations/kiro/init.py` | 打印权限规则（第 5 节） |
| `integrations/kiro/doctor.py` | 文本查找权限规则（第 5 节） |
| `.gitignore` | 加 `.refcov/proposals/`。提议是本机状态，不进仓库。**需审** |
| `tests/test_proposals.py`（新）；`tests/test_init_kiro.py`、`tests/test_doctor.py`（改） | 第 6 节的性质和固定例子，权限提示的例子 |

不动：`refcov.toml`、`.kiro/` 下的文件、用户级权限文件。清单 `sources.json` 和日志只在执行时增加内容。

## 2. 提议文件

存在状态目录的 `proposals/` 下，文件名是 `<编号>.json`。编号为 `p-` 加 8 位随机十六进制。内容示例：

```json
{
  "id": "p-1a2b3c4d",
  "created": "2026-11-17T21:00:00+09:00",
  "status": "pending",
  "items": [
    {"path": "docs/guide.md", "sha256": "<64 位十六进制>", "source_id": "guide",
     "adapter": "markdown", "units": 12, "titles": ["第一节", "第二节"]}
  ],
  "effect": "<第 4 节的效果说明>",
  "applied_seq": null
}
```

- `status` 只有 `pending` 和 `applied` 两种。
- 写入时先写临时文件再替换，和清单一样。写一半出错不留坏文件。
- 提议不过期（第一版）。提议存着期间文件被改，执行时的校验值核对会拒绝，所以过期不会造成误登记。

## 3. 执行

### 3.1 校验值

用 `content_sha256(text)`（`refcov/sources.py`）：去掉 BOM，统一换行，再算 UTF-8 的 SHA-256。提议和清单用同一个算法。不用原始字节：同一份文件在 Windows（CRLF）和 CI（LF）上的原始字节不同。`content_sha256` 的文档字符串已经写明这一点。

### 3.2 `apply` 的顺序

1. 读提议文件。`status` 不是 `pending`，拒绝（已执行过）。
2. 核对参数：项数相同；按路径排序后，路径、校验值、编号逐项相同。任一不同，拒绝，并列出不一致的项。
3. 对每个文件：确认路径在仓库内、是 Markdown；读一次字节；解码；算校验值，和提议比对；用适配器拆分。任一步失败，拒绝，什么都不写。这里读到的字节留在内存里，后面的写入用它们，不再读文件。
4. 拿日志锁（`store.locked()`，2 秒）。锁里重新检查：提议仍是 `pending`；每个编号和路径都不在清单里。不满足，拒绝。
5. 写入：每个文件的字节写进缓存（文件名是校验值）；每个参考源追加一条 `register` 记录，格式和登记子命令相同；追加一条 `apply` 记录，含提议编号、参考源编号、路径、校验值；清单整份写入；提议文件改成 `applied`，记下 `applied_seq`。
6. 放锁，返回结果文字（第 4 节的效果说明，加上新增的参考源和单元数）。

日志排在清单前面，和 `register` 一样。第 5 步在清单写完之后、提议改成 `applied` 之前中断时，提议还是 `pending`，但它的编号已经在清单里。再执行会在第 4 步被拒绝，所以不会重复登记。

### 3.3 为什么不直接调 `register`

`register` 对已有编号做替换（`sources[sources.index(old)] = entry`）。执行只能新增，所以不能直接调它。做法：把 `register` 锁里的写入段抽成 `write_locked(store, source_id, origin, data, sha, adapter, units)`，`register` 和 `apply` 都调用它。`apply` 在锁里先检查"不存在"。`register` 的对外行为不变，用户的登记子命令照旧。这一处是核心层改动，要 Claude 审。

## 4. `propose` 的检查和效果说明

`propose` 只读清单和配置，不改它们。检查按下面的顺序：

1. **编号**：符合 `SOURCE_ID`；不以 `f-` 开头（`AUTO_ID` 的前缀，自动登记用它）；清单里没有。没给编号时由文件名生成：小写，非字母数字换成 `-`，去掉首尾的 `-`。生成的结果不合规则时拒绝，要求给编号。不自动加后缀，免得 AI 不知道用了哪个。
2. **路径**：规范化方式和 `_load_file` 一样：相对仓库根目录，解析后仍在仓库内，后缀是 `.md` 或 `.markdown`。清单里的 `origin` 用规范化后的 `/` 分隔路径比较。
3. **不被 `[sources]` 匹配**：用 `api._spec_matches`。它会遍历仓库，只在提议时做一次，可以接受。匹配的文件拒绝，并说明"由 `refcov sync` 登记"。
4. **读和拆**：读字节，UTF-8 解码（允许 BOM），用适配器拆分。第一版只有 `markdown`。出错则拒绝。
5. **写提议**：每个文件的路径、校验值、编号、单元数和标题，以及效果说明。返回编号，并提示："用 `apply_proposal` 执行，参数必须与这份提议逐项相同。"

一次提议可以包含多个文件。编号和路径都不能重复。

效果说明是固定文字，需求 3 要求的两类路径都写在里面：

> 登记后，没有命中任何 `[[scope]]` 的路径要先读完新资料的 {N} 个单元，写文件前关卡才放行。命中 `[[scope]]` 的路径只看配置里列出的参考源，这次登记不增加它们要读的单元。要让它们也读新资料，用户需要在 `refcov.toml` 的对应规则里加上编号 {ids}。

`{N}` 是新增单元数，`{ids}` 是新增的参考源编号。

## 5. 权限规则（接入层）

**init**：`run` 结束时打印下面的规则，不写任何文件。

```yaml
rules:
  - capability: mcp
    match: ["<服务名>/apply_proposal"]
    effect: ask
```

服务名是 `.kiro/settings/mcp.json` 的 `mcpServers` 里，`args` 含 `refcov_mcp` 的那一项的键名。找不到时打印 `refcov`。

**doctor**：`permission_checks(服务名)` 读 `~/.kiro/settings/permissions.yaml`。

- 文件不存在：给提示，修法是打印那段规则。
- 文件存在：按行切成规则块。每个 `- capability:` 开头的行起一块，到下一块为止。有一块同时含 `capability: mcp`、`match` 行里有 `"<服务名>/apply_proposal"`、`effect: ask`，就提示"有这条规则"。否则提示缺少，并给出规则文字。
- 两种情况都是 `hint`，不算问题，不影响退出码。不判断用户的其他规则。

局限：只认块式写法（每个键一行）。写成花括号样式的规则，doctor 查不到。提示会写明"没找到；如果用了别的写法，请自己核对"。

依据：`Defining-rules` 说明规则写在用户级文件里，仓库里的文件注入不了规则。`Default-behavior` 说新建权限文件是在默认规则上加。

## 6. 测试：性质

用 Hypothesis 生成输入。性质写在测试的 docstring 里。

| 编号 | 性质 | 输入 |
|---|---|---|
| P1 | 执行只新增：执行前后，清单里已有的每一项逐字节不变，项数只增不减 | 随机的已有清单（若干参考源），随机的新文件和提议 |
| P2 | 参数与提议不一致必拒，清单不变 | 随机提议；随机改动参数的一处（路径、校验值、编号、项数、顺序） |
| P3 | 文件内容变了必拒，清单不变（包括只改换行） | 随机文件内容和改动位置 |
| P4 | 同一提议第二次执行必拒，清单不变 | 随机提议，执行两次 |
| P5 | 提议不改清单、配置和必看集合：提议前后 `sources.json` 和 `refcov.toml` 的字节相同，必看集合相同 | 随机配置（含 `[[scope]]` 和 `[relax]`），随机文件 |
| P6 | 执行中任一文件核对失败，清单、缓存和日志都不变 | 多文件提议，随机让其中一个失败 |

固定例子，每个都要有：非 Markdown 拒；仓库外的路径拒；指向仓库外的符号链接拒（Windows 上建符号链接需要权限，没有权限时跳过并注明）；`f-` 开头的编号拒；已登记的路径拒；被 `[sources]` 匹配的文件拒；编号重复拒；CRLF 和 LF 的同一份文件校验值相同；执行后日志里有一条 `apply` 记录，含提议编号。

`tests/test_core_names.py` 会自动覆盖新文件。`test_init_kiro.py` 增加：init 不写用户级权限文件（前后比较）；打印的规则文字正确。`test_doctor.py` 增加三种状态：规则有、规则没有、`effect` 不是 `ask`。

## 7. 用户验收

由用户在 Kiro 里做，自动测试不替代它。在 `D:\agent\kiro\refcov-trial\install-test` 里：

1. 用 uv 装分支版本。合并前用 `git+https://github.com/3322jj/refcov@phase2-haiku`，合并后用 `main`。
2. 运行 `refcov init`，把打印的规则加进用户级权限文件。运行 `refcov doctor`，应报"有这条规则"。
3. 放一份新的 Markdown 在仓库里。在 Kiro 里用自然语言说"把它登记成参考资料"。
4. 核对批准框（工具名 `apply_proposal`）和上方卡片的参数：路径、校验值、编号都和提议一致。
5. 点 Allow。运行 `refcov report`，应看到新参考源。提议里的效果说明应与实际的必看情况一致。
6. 用同一个提议再执行一次：必须被拒。
7. 再提议一份，提议后改动文件，再执行：必须被拒。
8. 再提议一份，批准框点 Deny：清单、缓存和日志都不变（前后比较）。

## 8. 局限（实现后写进 README）

- 命令行带 `--trust-all-tools` 或 `--trust-tools` 时没有确认（`CI-and-headless-environments`）。
- 批准框只显示工具名。参数在上方的工具卡片里，要用户看卡片。服务端只保证执行的参数等于卡片上的参数。
- `Approve for me` 只判断规则没有覆盖的动作（`Approve-for-me`）。本规则是显式的 `ask`，所以它不替用户批准。
- 工作区没有信任时，Kiro 不加载 MCP 配置（`Workspace-trust`），这组工具也不可用。
- 登记的是资料，内容不审查。登记后它会进入 AI 的上下文，用户要自己判断资料可不可信。
- 第一版没有删除命令。误登记的参考源要用户从状态目录里的 `sources.json` 手动删除。这一步不写日志。
- 规则查找只认块式写法（第 5 节）。
- 蓄意绕过挡不住：AI 可以绕开 MCP，直接写文件或调接口。对外不讲防绕过。

## 9. 待 Claude 审（检查点 3）

1. `register` 的写入段抽成 `write_locked`（第 3.3 节）。
2. `.refcov/proposals/` 进 `.gitignore`（第 1 节）。
3. 校验值用 `content_sha256`（第 3.1 节）。
4. 执行时写的两种日志记录（`register` 和 `apply`）的字段（第 3.2 节第 5 步）。
5. 提议不过期（第 2 节）是否可接受。
6. 第一版没有删除命令（第 8 节）是否可接受。
7. 要不要给 `propose_sources` 也加 `allow` 规则。第一版没加。它和其他 RefCov 工具一样，没有规则时 Kiro 会弹窗（`Default-behavior`）。
