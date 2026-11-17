# 设计文档：易用性改造第二层，资料提议与登记（第一版，2026-11-17，第二稿）

依据：`requirements.md` 第二稿；`docs/易用性改造方案.md` 第 3 节；`docs/权限实测结果.md`；Claude 对第一稿的审阅（12b05ab，检查点 3，见第 9 节）。

读过的代码：`refcov/sources.py`（`register`、`_load_file`、`content_sha256`）、`refcov/store.py`（`locked`、`append_locked`、`next_seq_locked`、清单读写）、`refcov/coverage.py`（`scope_sources`、`required_for_path`、`required_set`）、`refcov/api.py`（`read`、`attach_session`、`gather`、`_spec_matches`、`_inactive_auto`、`plan_sync`、`status_line`）、`refcov/citations.py`、`refcov/cli.py`（`_add`）、`refcov_mcp/server.py`、`integrations/kiro/hook.py`（post-mcp）、`integrations/kiro/init.py`、`integrations/kiro/doctor.py`、`tests/test_core_names.py`、`tests/test_register.py`、`tests/test_mcp_server.py`、`tests/test_attach.py`。

Kiro 文档单元，经 MCP 的 `read_unit` 读过（2026-11-17）：`kiro-permissions/Defining-rules`、`Default-behavior`、`Approve-for-me`、`Interactive-approval-flow`、`Workspace-trust`、`CI-and-headless-environments`、`Approval-rule-tiers`、`Security-and-trust`。

状态：**已验收（2026-11-18）。** 第二稿直接实现，不再等审规格；Claude 审过代码通过（16d07b8，检查点 3）；用户在 install-test 里验收通过，见第 7 节和 DEVLOG 2026-11-18。Claude 对第一稿的答复见第 9 节。

## 1. 改动范围

| 文件 | 改什么 |
|---|---|
| `refcov/proposals.py`（新，只用标准库） | 提议的存取，`propose()`、`apply()`，效果说明（第 2 至 4 节） |
| `refcov/sources.py` | `register` 锁里的写入段抽成 `write_locked()`，`register` 和执行共用。`register` 的对外行为不变（第 3.3 节） |
| `refcov/store.py` | 常量 `PROPOSALS_DIR = "proposals"` 和 `proposals_dir` |
| `refcov/api.py` | `propose_sources()`、`apply_proposal()` 两个包装，返回文字；`attach_session()` 也认 `apply` 记录（第 3.4 节） |
| `refcov_mcp/server.py` | 两个工具。参数转交给 `api`，错误转成 ToolError，没有逻辑 |
| `integrations/kiro/init.py` | 打印两条权限规则（第 5 节） |
| `integrations/kiro/doctor.py` | 两条规则分别做文本查找（第 5 节） |
| `.gitignore` | 加 `.refcov/proposals/`（第 9 节第 2 条，Claude 同意） |
| `refcov/store.py`（`STATE_GITIGNORE`、`ensure_state_dir`） | 第一次写状态目录时写下状态目录里的 `.gitignore`，列出 `cache/`、`proposals/`、`errors.log`、`log.lock`、`report-last.json`；不列 `sources.json` 和 `log.jsonl`；已经存在就不动（排他创建，不覆盖）。锁、清单、提议写盘和 `errors.log` 写入都经过它。这一行是 16d07b8 验收后补的，Claude 2026-11-17 提出 |
| `tests/test_proposals.py`（新） | P1–P6、M1（手动删除）和固定例子（第 6 节） |
| `tests/test_permission_rules.py`（新） | 两条规则的打印、doctor 的提示 |
| `tests/test_mcp_server.py`（改） | 工具清单从四个变成六个；新增提议到执行的往返 |
| `README.md` | 第 3 步写两条规则和原因；信任句注明出处；局限段照 Kiro 文档改 |
| `site/index.html` | 第 7 段信任句的措辞（只观察到一次，改成 "in our test ... also showed as disabled"） |
| `docs/decisions/2026-11-17-检查点3审阅.md` | 开头两行改成"用户 2026-11-17 过目，按原样提交"；正文不动 |
| `tests/test_clean_install.py`（改，可选） | 项目路径带空格和中文的变体（默认跳过） |

不动：`refcov.toml`、`.kiro/` 下的文件、用户级权限文件、`.refcov/` 下已有的内容（清单和日志只在执行时增加内容）。

## 2. 提议文件

状态目录下 `proposals/`，文件名是 `<编号>.json`。编号为 `p-` 加 8 位随机十六进制。

```json
{
  "id": "p-1a2b3c4d",
  "created": "2026-11-17T21:00:00+09:00",
  "status": "pending",
  "items": [
    {"path": "docs/guide.md", "sha256": "<64 位十六进制>", "source_id": "guide",
     "adapter": "markdown", "units": 12, "titles": ["第一节", "第二节"]}
  ],
  "effect": "<第 4 节的效果说明，已算好单元数>",
  "applied_seq": null
}
```

- `status` 只有 `pending` 和 `applied` 两种。
- 写入时先写临时文件再替换，和清单一样。写一半出错不留坏文件。
- 提议不过期（第 9 节第 5 条）。提议存着期间文件被改，执行时的校验值核对会拒绝，所以旧提议不会误登记。

## 3. 执行

### 3.1 校验值

用 `content_sha256(text)`（`refcov/sources.py`）：去掉 BOM，统一换行，再算 UTF-8 的 SHA-256。提议和清单用同一个算法（第 9 节第 3 条）。不用原始字节：同一份文件在 Windows（CRLF）和 CI（LF）上的原始字节不同。

### 3.2 `apply` 的顺序

1. 读提议文件。编号格式不对、文件不存在，拒绝。`status` 不是 `pending`，拒绝（已执行过，并给出 `applied_seq`）。
2. 核对参数：项数相同；按路径排序后，路径、校验值、编号逐项相同。任一不同，拒绝，并列出不一致的项。
3. 对每个文件：确认路径在仓库内、是 Markdown（和 `_load_file` 一样）；读一次字节；解码；算校验值，和提议比对；用适配器拆分。任一步失败，拒绝，什么都不写。这里读到的字节留在内存里，后面的写入用它们，不再读文件。
4. 拿日志锁（`store.locked()`，2 秒）。锁里重新检查：提议文件仍是 `pending`；每个编号和路径都不在清单里（第 9 节第 1 条）。不满足，拒绝。
5. 写入，都在锁里：
   - 每个参考源调用 `write_locked()`（第 3.3 节）：写缓存（文件名是校验值），追加一条 `register` 记录，在内存里的清单上放好条目。
   - 取 `seq = next_seq_locked()`，追加一条 `apply` 记录：`{"type": "apply", "call": "c-<seq>", "proposal": "<编号>", "sources": ["…"], "items": [{"source": "…", "path": "…", "sha256": "…"}], "session": null}`。`session` 由第 3.4 节补记。
   - 清单整份写入（`store.write_sources`）。
   - 提议文件改成 `applied`，记下 `applied_seq`（就是 `apply` 记录的 `seq`）。
6. 放锁，返回执行结果（第 3.4 节的最后一行是 `refcov-call: c-<seq>`）。

日志排在清单前面，和 `register` 一样。第 5 步在清单写完之后、提议改成 `applied` 之前中断时，提议还是 `pending`，但它的编号已经在清单里。再执行会在第 4 步被拒绝，所以不会重复登记。

### 3.3 `write_locked`（第 9 节第 1 条的条件）

`register` 锁里的写入段抽成函数（名字和签名以代码为准）：

```python
def write_locked(store, manifest, source_id, stored, data, sha, adapter_name, units, old) -> (entry, changed)
```

它拿着日志锁调用：写缓存、追加 `register` 记录、在内存里的清单上替换 `old` 或追加条目。它不写清单文件，调用方写完以后调用 `store.write_sources(manifest)`。

- `register` 的对外行为不变：同样的顺序（缓存、日志、清单），同样的记录字段，同样的"来源和校验值都没变就不写"。现有的登记测试（`tests/test_register.py` 等）不改期望。
- 执行在第 3.2 节第 4 步已经确认"编号和路径都不在清单里"，所以不会走到替换的分支。

### 3.4 会话补记

接入层的 post-mcp 钩子已经对所有 `mcp_refcov_*` 工具的返回做这件事：返回文字的最后一行是 `refcov-call: c-<数字>` 时，把会话 ID 补记到对应的记录上。执行结果也这样写，所以执行的会话也能查出来。

- `attach_session()` 原来只认 `read` 记录。改成也认 `apply` 记录（编号不同，检查相同）。
- 钩子从工具参数里取 `source` 和 `unit`；执行没有这两个参数，传 None，检查不做。
- 补记失败（例如拿不到锁）只写 `errors.log`，不影响执行结果。执行已经写进去了。

## 4. `propose` 的检查和效果说明

`propose` 只读清单和配置，不改它们。检查按下面的顺序：

1. **路径**：网址拒绝。其余交给 `_load_file`：相对仓库根目录，解析后仍在仓库内，后缀 `.md` 或 `.markdown`。清单里已有同一路径（`origin`）的拒绝。
2. **不被 `[sources]` 匹配**：用 `api._spec_matches`。它会遍历仓库，只在提议时做一次，可以接受。匹配的文件拒绝，说明"由 `refcov sync` 登记"。
3. **编号**：给了就用，没给由文件名生成（小写，非字母数字换成 `-`，去掉首尾的 `-`）。必须符合 `SOURCE_ID`，不能以 `f-` 开头（`AUTO_ID` 的前缀），清单里没有，本次提议里也没有重复。不自动加后缀，免得 AI 不知道用了哪个。
4. **读和拆**：读字节，UTF-8（允许 BOM）解码，用适配器拆分。第一版只有 `markdown`。
5. **效果说明**（第 4.1 节），然后写提议文件。返回编号、每个文件的路径、完整校验值、编号、单元数和标题，以及效果说明和执行方法。

一次提议可以包含多个文件，编号和路径都不能重复。

### 4.1 单元数怎么算

效果说明里的 N 是"新资料里，登记以后要读的单元数"。它用核心层的必看集合算，不直接写拆出的单元数（第 9 节答复第 8 条）：

1. 读当前的配置和清单（`api.gather` 的结果）。
2. 把新资料的条目加到清单的内存副本里，得到"登记以后"的清单。
3. 需求文档里的引用重新对一遍（`citations.check_requirements`，用"登记以后"的已知单元）。有效引用指向的单元都算被引用。
4. 用 `coverage.required_set(…)` 算必看集合（同样的模式，同样的 `[relax]`，同样的自动源排除）。
5. N 是必看集合里属于新参考源的单元数。

算的过程中任何一步出错，就写"最多 N 个"，N 是新增单元的总数。

### 4.2 效果说明的文字

固定文字，两段，数字和编号替换进去：

> 登记后，没有命中任何 `[[scope]]` 的路径要先读完新资料的 {N} 个单元，写文件前关卡才放行。命中 `[[scope]]` 的路径只看配置里列出的参考源，这次登记不增加它们要读的单元。要让它们也读新资料，需要用户在 `refcov.toml` 的对应规则里加上编号 {ids}。
> （单元数按提议时的模式、配置和需求文档算。）

## 5. 权限规则（接入层）

**服务名**：`.kiro/settings/mcp.json` 的 `mcpServers` 里，`args` 含 `refcov_mcp` 的那一项的键名。找不到时用 `refcov`。

**init** 在 `run` 结束时打印下面的两条规则，不写任何文件。两条都写在用户级权限文件里（`~/.kiro/settings/permissions.yaml`）：

```yaml
rules:
  - capability: mcp
    match: ["refcov/list_units", "refcov/read_unit", "refcov/check", "refcov/report", "refcov/propose_sources"]
    effect: allow
  - capability: mcp
    match: ["refcov/apply_proposal"]
    effect: ask
```

- 读取类工具逐个列名字，不用 `refcov/*`，免得以后新加的写入工具被顺带放行。
- allow 规则的作用：没有它，每读一个单元都弹窗（`Default-behavior`：其余动作默认弹窗）。本仓库不弹，是因为权限文件里存过 `read_unit` 和 `list_units` 的 allow（用户以前点过 Always allow）。新用户没有这些条目。
- ask 规则的作用：`apply_proposal` 每次弹窗，弹窗里没有 Always allow（第 0 步实测）。

**doctor**：`permission_checks(服务名, 路径)` 读用户级权限文件（默认 `~/.kiro/settings/permissions.yaml`，测试里可以换路径）。两条规则分别查。

- 文件不存在：两条都给提示。
- 文件存在：按行切成规则块，每个 `- capability:` 开头的行起一块，到下一块为止。
  - allow 规则：有一块同时含 `capability: mcp`、`effect: allow`，并且五个读取工具的名字都在里面：算有，给"有"（ok）。否则给提示，列出缺的名字，并写明"读资料时每次都会弹窗"。
  - ask 规则：有一块同时含 `capability: mcp`、`effect: ask`，并且 `<服务名>/apply_proposal` 在里面：算有。否则给提示，写明"登记时可能出现 Always allow；选了以后就不再问"。
- 两条都是 `hint`，不算问题，不影响退出码。不判断其他规则。
- 局限：只认块式写法（每个键一行）。写成花括号样式的规则，doctor 查不到，提示会说明"没找到；如果用了别的写法，请自己核对"。

依据：`Defining-rules` 说规则写在用户级文件里，仓库里的文件注入不了规则。`Default-behavior` 说新建权限文件是在默认规则上加。

## 6. 测试

### 6.1 性质（Hypothesis 生成输入，性质写在 docstring 里）

| 编号 | 性质 | 输入 |
|---|---|---|
| P1 | 执行只新增：执行前后，清单里已有的每一项逐字节不变，项数只增不减 | 随机的已有清单（若干参考源），随机的新文件和提议 |
| P2 | 参数与提议不一致必拒，清单不变 | 随机提议；随机改动参数的一处（路径、校验值、编号、项数、顺序） |
| P3 | 文件内容变了必拒，清单不变。只改换行（LF 和 CRLF 互换）不算内容变化：校验值按统一换行后算，所以这种改动照常执行（固定例子 CRLF/LF 覆盖） | 随机文件内容和改动位置 |
| P4 | 同一提议第二次执行必拒，清单不变 | 随机提议，执行两次 |
| P5 | 提议不改清单、配置和必看集合：提议前后 `sources.json` 和配置文件的字节相同，必看集合相同 | 随机配置（含 `[[scope]]` 和 `[relax]`），随机文件 |
| P6 | 执行中任一文件核对失败，清单、缓存和日志都不变 | 多文件提议，随机让其中一个失败 |

### 6.2 手动删除（M1，固定测试）

这一条是第 9 节第 6 条的前提。步骤：登记两个参考源；用 `api.read` 读一个单元；手工用 JSON 从清单里删掉第二个参考源的条目；然后调用 `api.report`、`api.check`（不带路径，带路径）、`api.status_line` 和 `api.list_units`。这些都要返回结果，不抛异常，状态行里仍有"RefCov"。如果其中任何一个出错，M1 失败，手动删除的办法不能用，停下来告诉 Claude。

### 6.3 固定例子

每个都要有：非 Markdown 拒；仓库外的路径拒；指向仓库外的符号链接拒（Windows 上建符号链接需要权限，没有权限时跳过并注明）；网址拒；`f-` 开头的编号拒；已登记的路径拒；被 `[sources]` 匹配的文件拒；编号重复拒；CRLF 和 LF 的同一份文件校验值相同；执行后日志里有一条 `apply` 记录，含提议编号；执行结果的最后一行是 `refcov-call: c-<编号>`，并且 `call_from_text` 能认出来。

### 6.4 权限规则和 MCP

- `tests/test_permission_rules.py`：init 打印两条规则，服务名取 mcp.json 里的键（改名后跟着变）；init 不写用户级权限文件（用临时目录设 `USERPROFILE` 和 `HOME`，前后比较，目录必须还是空的）；doctor 的四种情况：文件不存在、两条都有、allow 缺一个工具名、ask 没有。
- `tests/test_mcp_server.py`：工具清单是六个；一次提议到执行的往返（经 stdio 子进程）。

`tests/test_core_names.py` 自动覆盖新文件。

## 7. 用户验收

状态：**已验收（2026-11-18）。** 2026-11-17 第一轮只有 F 项没过；F 项改文字后，2026-11-18 用新模板重测通过，A 到 F 全部通过。2026-11-18 的重测按第 6 步的写法做：只说登记，不提工具名。结果见 DEVLOG 2026-11-17 和 2026-11-18。

由用户在 Kiro 里做，自动测试不替代它。在 `D:\agent\kiro\refcov-trial\install-test` 里：

1. 重装分支版本：`uv tool install --reinstall git+https://github.com/3322jj/refcov@phase2-haiku`（合并后用 `main`）。
2. 在 Kiro 里重新加载窗口，让 MCP 服务用新版本。
3. 运行 `refcov init`，把打印的两条规则加进用户级权限文件。运行 `refcov doctor`，两条都应显示"有"。
4. 让 Kiro 读一个单元（`read_unit`）：应当没有弹窗。这一条验证 allow 生效。
5. 在仓库里放一份你从别处拿来的 Markdown（例如公开的指南）。不要让 AI 当场写它：AI 写一份再登记成依据，等于自己给自己出依据。
6. 只在 Kiro 里说"把它登记成参考资料"，不提工具名。Kiro 应当主动调用 `propose_sources` 和 `apply_proposal`，不需要你改配置或在终端跑命令。
7. 核对批准框（工具名 `apply_proposal`）和上方卡片的参数：路径、校验值、编号都和提议一致。
8. 点 Allow。运行 `refcov report`，应看到新参考源。执行结果里的效果说明应与实际的必看情况一致。
9. 用同一个提议再执行一次：必须被拒。
10. 再提议一份，提议后改动文件，再执行：必须被拒。
11. 再提议一份，批准框点 Deny：清单、缓存和日志都不变（前后比较）。
12. 可选：手工从清单里删掉刚登记的参考源，运行 `refcov report` 和 `refcov check`，都应照常输出（M1 的手工版）。

## 8. 局限（写进 README）

- 没有删除命令。误登记的参考源由用户手动从状态目录里的 `sources.json` 删（M1 测过：删除后报告、达标检查和状态行照常工作）。这一步不写日志。
- 命令行带 `--trust-all-tools` 或 `--trust-tools` 时没有确认（`CI-and-headless-environments`）。
- 批准框只显示工具名。参数在上方的工具卡片里，要用户看卡片。服务端只保证执行的参数等于卡片上的参数。
- `Approve for me` 只判断规则没有覆盖的动作（`Approve-for-me`）。`apply_proposal` 有显式的 `ask` 规则，所以它不替用户批准。
- 工作区没有信任时，Kiro 不加载 MCP 配置（`Workspace-trust`），这组工具也不可用。
- 登记的是资料，内容不审查。登记后它会进入 AI 的上下文，用户要自己判断资料可不可信。
- 规则查找只认块式写法（第 5 节）。
- 蓄意绕过挡不住：AI 可以绕开 MCP，直接写文件或调接口。对外不讲防绕过。

## 9. Claude 的答复（检查点 3）和处理

| 条目 | 答复 | 处理 |
|---|---|---|
| 1. `write_locked` | 同意；register 对外行为不变，现有登记测试不改期望也能过；apply 在锁里先确认编号和路径都不在清单里 | 第 3.2、3.3 节。M1 之外，现有 `test_register.py` 不改 |
| 2. `.gitignore` | 同意 | 第 1 节 |
| 3. `content_sha256` | 同意 | 第 3.1 节 |
| 4. 两种记录的字段 | 同意；可选：执行结果最后一行带调用编号，让 post-mcp 钩子补记会话 | 第 3.2 节第 5 步，第 3.4 节 |
| 5. 提议不过期 | 同意 | 第 2 节 |
| 6. 没有删除命令 | 同意，但加固定测试：手工删除后 report、check、状态行照常，出错就停下告诉 Claude | 第 5 节需求 5.5，第 6.2 节 M1 |
| 7. allow 规则 | 要加。init 打印两条，doctor 分别查，README 第 3 步写明 | 第 5 节，第 6.4 节，需求 4 |
| 8. 效果说明的单元数 | 用核心层的必看集合算，算不准写"最多 N 个" | 第 4.1 节 |
| 9. 验收 | 用 `--reinstall` 重装，重新加载窗口，两条规则都加，再加一步"读单元不弹窗" | 第 7 节 |
| 10. 小问题 | README 信任句注明出处；演示页第 7 段改措辞；README 局限段照 Kiro 文档改；可选：干净安装测试加空格和中文的路径 | 第 1 节 |
| 11. decisions 文件 | 开头两行改成"用户 2026-11-17 过目，按原样提交"，正文不动 | 第 1 节 |

第 4 条的 `refcov-call` 行是"顺手能做就做"。它依赖的现有机制（post-mcp 和 `attach_session`）已经存在，只需要 `attach_session` 认 `apply` 记录，所以做了。
