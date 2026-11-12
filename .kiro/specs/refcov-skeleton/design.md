# 设计文档：RefCov 骨架

EN summary: Design for the RefCov skeleton: 8 modules (7 core/MCP plus the Kiro integration layer), one hash-chained append-only log for all records, 5 MCP tools, 7 Kiro hook files on 5 events, the citation and unit-ID rules (`-2` for duplicate headings, `@2` for split parts), a 4000-character unit limit, checksum tracking for hook files and `docs/decisions/` (the latter confirmed by the user with `refcov confirm`), Hypothesis data generation for requirement 16, and a build order that delivers the thinnest path (register Markdown, split, read via MCP, record, report) before any gate.

对应需求：`.kiro/specs/refcov-skeleton/requirements.md`（第五稿按外部审阅修订，提交 `d04e8fa`，已冻结）。文中"需求 N.M"都指这份文档。设计中发现的需求问题记在 `docs/DEVLOG.md`"以后再做"，不改需求。设计第二版按 spec-auditor 的报告和用户 2026-11-10 的意见修改，和冻结需求原文不一致的地方在文中标"偏离需求原文"。2026-11-11 按外部审阅 `docs/设计第二版审阅.md` 和用户的决定改了对应的句子，不另出第三版，逐条改动记在 DEVLOG 2026-11-11。

## 1. 总体

```
用户 ──refcov add / confirm──▶ sources ──▶ adapters/markdown
                         │
                         ▼
AI ──MCP──▶ refcov_mcp ──▶ api ──▶ coverage ◀── citations
                              │        ▲
Kiro 钩子 ──▶ integrations/kiro ─┘        │
                              ▼        │
                            store（状态目录：清单、日志、缓存）
```

- 核心层 = `refcov/` 下 6 个模块 + `refcov_mcp/`。只有 `refcov_mcp` 依赖第三方包（`mcp`）；其余模块只用标准库（需求 13.3）。核心层不出现 Kiro 的工具名、事件名、路径（需求 13.1）。
- Kiro 的默认值（规格文件在哪、要算校验值的钩子文件在哪）不写进核心层，写在 `integrations/kiro/refcov.example.toml`，用户复制成配置文件。核心层只读配置。
- 所有记录（登记、读取、会话补记、凭证、拦截、写入、确认、错误）写进**同一个**只追加的日志文件，整条日志一条哈希链。这样只有一种存储格式、一个锁、一个完整性检查。
- 读取记录只有一个来源：`api.read` 在真的取出单元内容时追加。没有任何入口根据 AI 的文字（自述、写入正文）增加读取记录（需求 4.8）。
- 对照实验（需求 17.4）不在本设计范围，另立规格；本设计只提供它要的数字（需求 17.1–17.3）。

## 2. 模块（8 个）

| # | 模块 | 做什么 | 需求 |
| --- | --- | --- | --- |
| 1 | `refcov/store.py` | 状态目录布局；读配置（`tomllib`，只读）；读写清单；追加日志（文件锁 + 哈希链）；校验哈希链；算文件校验值 | 1.1、1.2、1.5、4.3、4.4、13.3、14.3 |
| 2 | `refcov/sources.py` | 适配器接口（3 个函数）；单元 ID 生成；登记参考源（抓取、缓存、拆单元、写清单）；不支持的格式在登记时拒绝 | 1.1、1.4、1.5、2.1–2.6、3.4、13.3 |
| 3 | `refcov/adapters/markdown.py` | 文档适配器：按标题拆章节、超长拆分、无标题整篇一个单元。只用标准库，目标 50 行左右 | 2.3、3.1–3.6 |
| 4 | `refcov/citations.py` | 解析需求文档：切分需求、提取 `[ref:…]`、识别文字出处；列出幻影需求、无效引用；解析 tasks.md 找任务和它引用的单元 | 6.1–6.4、9.6、13.3 |
| 5 | `refcov/coverage.py` | 纯计算：有效读取记录、必看集合（需求 5.1 那一条规则）、覆盖率、按路径或任务判断达标、被忽略单元、幽灵单元 | 5.1–5.7、6.3、6.5–6.7、8.1–8.5、13.3、15.2、16 |
| 6 | `refcov/api.py` | 与工具无关的入口（见第 6 节）；唯一写读取记录的地方；凭证发放和失效；拦截次数；文件校验值和确认；生成报告 JSON 和文字版；命令行 `refcov` | 4.8、7.1–7.6、10.1–10.3、11.1、11.2、12.1–12.4、13.2、13.3、17.1–17.3 |
| 7 | `refcov_mcp/server.py` | MCP 服务（官方 SDK，stdio），5 个工具，只调用 `api` | 4.1、4.7、7.1、7.2、12.1、13.4 |
| 8 | `integrations/kiro/` | `hook.py`（一个脚本，按事件分派）、`hooks/*.json`（钩子配置模板）、`refcov.example.toml`。先做保护检查，再 import 核心层 | 4.5、9.1、9.5–9.10、10.1、10.3、11.1、11.3、14.1–14.6 |

文件位置：

- 状态目录：仓库根目录 `.refcov/`。第一次写入时自动建（没有 `init` 命令）。`cache/` 被 `.gitignore` 忽略（已有）；`errors.log`（含报错堆栈和本机路径）、`log.lock`、`report-last.json` 也忽略（任务 1 加进 `.gitignore`）；`sources.json`（清单）和 `log.jsonl` 照常提交，在线演示页要回放日志（需求 4.4）。
- `.gitattributes` 加一行 `*.jsonl -text`，日志不做换行转换，换一台机器校验哈希链不会报断链（第 3.2 节）。
- 配置文件：仓库根目录 `refcov.toml`。由用户从 `integrations/kiro/refcov.example.toml` 手动复制，README 里写一行说明。
- 仓库根目录怎么定：核心层不按当前目录找状态目录，根目录由调用方传入。
  - `hook.py` 按自己的文件位置算出仓库根目录（`Path(__file__).resolve().parents[2]`），放到 `sys.path` 最前面再 import 核心层，并把它传给核心层。钩子的工作目录实测是工作区根目录，但不依赖这一点。
  - MCP 服务由 Kiro 的扩展宿主启动，工作目录不一定是工作区根目录（`docs/验证结果.md` 第 6 项），所以用启动参数接收：`python -m refcov_mcp --root <仓库根目录>`。`docs/mcp.example.json` 写出这个参数。
  - Python 用 PATH 上的那个（钩子命令里的 `python`），在它里面 `pip install -e .`。README 写明这一步。import 失败会被当成"自身出错"放行（第 8 节第 3 步），关卡会无声失效，所以任务 6 的完成标志包括 `.refcov/errors.log` 为空。
- 测试：`tests/`。只有 `tests/` 下的代码 import Hypothesis（需求 13.4）。
- `.gitignore` 检查（需求 1.3）：`tests/test_gitignore.py` 对 `.kiro` 下所有已跟踪和未跟踪的文件，加上几个构造的路径（`.kiro/specs/x/requirements.md`、`.kiro/hooks/x.json`、`.kiro/settings/mcp.json`），运行 `git check-ignore -v --no-index`。只要有一个命中的规则来自某个 `.gitignore` 文件，测试就失败。命中来自 `.git/info/exclude` 的不算失败：本机的 `.kiro/settings/mcp.json` 是用户有意写进那里的，而需求 1.3 只管 `.gitignore`。

## 3. 数据格式和例子

### 3.1 参考源清单 `.refcov/sources.json`

```json
{
  "version": 1,
  "sources": [
    {
      "id": "kiro-hooks",
      "origin": "https://kiro.dev/docs/hooks.md",
      "fetched": "2026-11-11T09:12:05+08:00",
      "sha256": "9f2c…e1",
      "adapter": "markdown",
      "registered_seq": 41,
      "units": [
        {"id": "Hooks", "title": "Hooks", "kind": "section", "sha256": "1a7b…", "chars": 812},
        {"id": "退出码", "title": "退出码", "kind": "section", "sha256": "c03d…", "chars": 3950},
        {"id": "退出码@2", "title": "退出码 (2)", "kind": "section", "sha256": "77e0…", "chars": 1210},
        {"id": "退出码-2", "title": "退出码", "kind": "section", "sha256": "5b19…", "chars": 640}
      ]
    }
  ]
}
```

- 上面的例子里，"退出码"这个标题在文档里出现了两次，第一个超长被拆成两段。拆出的第二段是 `退出码@2`，重名的第二个标题是 `退出码-2`，两者不会撞（第 4 节）。
- `registered_seq` 是登记时日志的序号，凭证失效判断用它（需求 7.4"登记了新的参考源"）。
- 单元的 `kind` 和"严格必看 / 关键类型"的声明来自适配器，不写进清单，避免两处不一致。
- 登记（`sources.register`，任务 4，用户 2026-11-11 的决定）：
  - 顶层 `sha256` 按去掉 BOM、换行统一成 `\n` 后的文本算（仓库 `core.autocrlf=true`，同一份 `.md` 在 Windows 和 CI 上原始字节不同）。缓存文件是 `.refcov/cache/<sha256>`，里面存原始字节；新内容写新文件，旧文件不删。
  - 抓取、解码、拆分在拿日志锁之前做完（抓网址最多等 10 秒，锁超过 10 秒会被当残留删掉）。锁里依次：读清单、比对、写缓存、追加 `register`、替换清单。日志排在清单前面：中途出错时宁可凭证提前失效，也不让清单变了而日志没记。拿不到锁时什么都不写。
  - 来源和 `sha256` 都没变时什么都不写（不记 `register`，免得凭证白白失效）。只换了来源时照常登记，`register` 记录里 `changed: false`。
  - 本地文件只认扩展名 `.md`、`.markdown`，必须在仓库里（先 `resolve()`，Windows 上不分大小写比较），`origin` 存相对仓库根目录、用 `/` 分隔的路径。网址按 Content-Type 认：`text/markdown`、`text/x-markdown` 接受，`text/plain` 只在路径以 `.md` 或 `.markdown` 结尾时接受，其余（含 `text/html`、没有 Content-Type）报"不支持该格式"。只认 UTF-8（允许 BOM）。
  - `register` 记录的字段：`source`、`origin`、`sha256`、`adapter`、`units`（单元数）、`changed`。

### 3.2 日志 `.refcov/log.jsonl`（读取记录在这里）

每行一条，所有行共用字段：`seq`（从 1 递增）、`time`（本地时间带时区）、`type`、`session`（知道时填，不知道时为 `null`）、`prev`（上一行原文的 SHA-256，第一行是 64 个 0）。哈希按上一行**不含换行符**的 UTF-8 字节算；写文件时换行固定用 `\n`（`open(..., newline="\n")`），`.gitattributes` 让 `*.jsonl` 不做换行转换。

读取记录（MCP 服务写，需求 4.1、4.6）。MCP 服务拿不到会话，所以 `session` 是 `null`：

```json
{"seq":57,"time":"2026-11-11T10:02:03+08:00","type":"read","session":null,"call":"c-57","source":"kiro-hooks","unit":"退出码","unit_sha256":"c03d…","text_units":1,"images":0,"prev":"5e81…"}
```

会话补记（PostToolUse 钩子写，需求 4.5）：

```json
{"seq":58,"time":"2026-11-11T10:02:03+08:00","type":"session","session":"sess_da80f038-…","call":"c-57","prev":"a4c9…"}
```

拦截（钩子写，需求 9.1、11.2）：

```json
{"seq":91,"time":"2026-11-11T10:40:12+08:00","type":"block","session":"sess_da80f038-…","gate":"write","target":"integrations/kiro/hook.py","count":2,"missing":["kiro-hooks/退出码@2"],"prev":"…"}
```

确认（用户在终端跑 `refcov confirm`，第 3.6 节）：

```json
{"seq":120,"time":"2026-11-11T11:05:00+08:00","type":"confirm","session":null,"path":"docs/decisions/2026-11-10-review-reply.md","sha256":"e4a0…","prev":"…"}
```

其他类型，字段从略，都带 `time` 和 `session`：`register`（登记）、`token`（凭证，见 3.3）、`token_refused`、`write`（写入后记录：路径、工具、判断结果 `fail` / `unknown` / `unknown_source`）、`task_not_found`、`protect`（需求 14 拦下的写入和命令）、`error`。

- 调用编号 `call` 就是这条读取记录的 `seq`，写进工具返回文字的最后一行（`refcov-call: c-57`）。PostToolUse 钩子从 `tool_response` 里取出它，对上是哪一次调用。实测里两次并行调用也是分开返回的，按编号对不会混。
- 报告里一条记录的会话：本行的 `session`；为 `null` 时取按 `call` 对上的 `session` 补记；都没有就算"未知"（需求 4.5）。
- 有效读取记录：`unit_sha256` 等于清单里该单元当前的 `sha256`（需求 1.4）。
- 写入时先拿 `log.lock`（`os.open` 加 `O_CREAT | O_EXCL`，每 50 毫秒重试，最多 2 秒；锁文件超过 10 秒视为残留，删掉重拿），读最后一行算 `prev`，追加，放锁。MCP 服务和钩子脚本是不同进程，必须加锁，否则哈希链会断。2 秒内拿不到锁时，`api.read` 让这次工具调用报错、不返回单元内容（少算不多算）；钩子脚本按第 8 节第 3 步的出错处理。
- 哈希链只能让随手追加或改动留下痕迹（需求 11.4）。报告里写"链完整"或"第 N 行起断开"。

### 3.3 凭证（日志里 `type: "token"` 的一行）

```json
{"seq":80,"time":"2026-11-11T10:30:41+08:00","type":"token","session":null,"token":"t-80","mode":"strict","units":{"kiro-hooks/Hooks":"1a7b…","kiro-hooks/退出码":"c03d…"},"config_mtime":"2026-11-11T09:00:00+08:00","prev":"…"}
```

- 会话 ID 由同一个 PostToolUse 钩子按 `call`（这里是 `t-80`）补记（需求 7.1、4.5）。
- 失效（需求 7.4）：`units` 里任一校验值和清单不一致；日志里有 `seq` 更大的 `register`；配置文件当前修改时间晚于 `config_mtime`。
- 凭证不参与任何拦截（需求 7.5），报告里列出发放和失效。

### 3.4 配置文件 `refcov.toml`

```toml
mode = "strict"          # strict | light（需求 15.1）
enforce = true           # 需求 17.1

# 哪些文件是需求文档、规格文件。Kiro 的值在 integrations/kiro/refcov.example.toml 里
requirements = [".kiro/specs/*/requirements.md"]
spec_files   = [".kiro/specs/**"]

# 要算校验值的文件（需求 12.2）。和上一次报告比，变了就标红
watch = [".kiro/hooks/refcov-*.json", "integrations/kiro/**"]

# 要算校验值、并且要用户确认的文件。和最后一次 refcov confirm 比，新文件或变了就标红"待用户确认"
confirm = ["docs/decisions/**"]

# 豁免：写这些文件不检查是否达标（需求 8.3）。写了就覆盖默认值
exempt = ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"]

[relax]                  # 放宽项（需求 5.3），只能缩小必看集合
sources = []
kinds   = []
units   = ["kiro-hooks/更新日志"]

[[scope]]                # 关卡范围（需求 8.1）
paths   = ["integrations/kiro/**"]
sources = ["kiro-hooks"]
```

- 路径一律转成相对仓库根目录的 `/` 分隔形式，路径和模式都转成小写，再用 `fnmatch.fnmatchcase` 匹配。不用 `fnmatch.fnmatch`：它在 Windows 上不分大小写、在 Linux 上分，持续集成里结果会不一样。`*` 也能跨 `/`，所以 `docs/decisions/**` 能匹配子目录。`**/DEVLOG.md` 不匹配根目录的 `DEVLOG.md`（前面要有 `/`），所以根目录那个单独列。需求 8.3 只写了文件名，默认值按"任何位置叫 `DEVLOG.md` 的文件"处理。
- 一个路径命中多条 `scope`，取这些规则的参考源并集；一条都不命中，要求全部参考源（需求 8.2）。
- 命中的 `scope` 里有清单里没有的参考源（例如写错成 `kiro-hoooks`）：按全部参考源处理，宁可多要求，不因写错变宽松。这是往需求 8.2 同一方向的扩展（外部审阅 2026-11-12，用户同意）。`sources = []` 保持原样（只要求被引用的单元），只提示。`scope` 和 `[relax]` 里写了清单里没有的参考源、单元类型或单元，都列进报告的 `config_problems`；`[relax]` 写错本来不会变宽松，只提示，不改判断。
- 配置文件不存在时用默认值：`mode = "strict"`、`enforce = true`、`exempt` 和 `confirm` 为上面的值、其余为空。`requirements` 为空时，出处相关的检查报"未配置需求文档"，不算达标失败；配置了模式但一个文件都没匹配到时报"配置了 X，但没找到文件"，同样不算达标失败。
- 命中 `requirements` 的文档一条需求都没解析出来（标题格式认不出），列进报告的 `empty_requirement_docs`。严格模式下按不达标处理，轻量模式只列出，目标是规格文件时不因此不达标（需求 6.7）。**偏离需求原文**：需求 6.6 只列了幻影需求和无效引用（外部审阅 2026-11-12，用户同意）。

### 3.5 报告 JSON（`refcov report --json`，需求 12.2）

```json
{
  "version": 1,
  "generated": "2026-11-11T10:35:00+08:00",
  "session": "sess_da80f038-…",
  "session_available": true,
  "mode": "strict",
  "enforce": true,
  "pass": false,
  "sources": [
    {"id": "kiro-hooks", "units": 14, "read_history": 9, "read_session": 3,
     "required": 14, "required_read_history": 9, "required_read_session": 3}
  ],
  "missing": [{"source": "kiro-hooks", "unit": "退出码@2", "title": "退出码 (2)"}],
  "ghost_units": ["kiro-hooks/退出码@2"],
  "not_required_units": [],
  "ignored_units": ["kiro-hooks/Hooks"],
  "phantom_requirements": [],
  "invalid_refs": [{"doc": ".kiro/specs/refcov-skeleton/requirements.md", "requirement": "9", "ref": "kiro-hooks/exit"}],
  "unconverted_requirements": [{"doc": ".kiro/specs/refcov-skeleton/requirements.md", "requirement": "1"}],
  "requirement_docs": [".kiro/specs/refcov-skeleton/requirements.md"],
  "requirement_patterns": [".kiro/specs/*/requirements.md"],
  "empty_requirement_docs": [],
  "config_problems": [{"where": "scope 第 1 条 sources", "value": "kiro-hoooks", "note": "清单里没有这个参考源，这条规则按全部参考源处理"}],
  "relaxed": {"sources": [], "kinds": [], "units": ["kiro-hooks/更新日志"], "cited_but_relaxed": []},
  "exempt": ["DEVLOG.md", "**/DEVLOG.md", "docs/decisions/**"],
  "config_mtime": "2026-11-11T09:00:00+08:00",
  "tokens": [{"token": "t-80", "time": "2026-11-11T10:30:41+08:00", "session": "sess_…", "valid": false, "invalid_reason": "config_changed"}],
  "blocks": [{"seq": 91, "time": "2026-11-11T10:40:12+08:00", "session": "sess_…", "gate": "write", "target": "integrations/kiro/hook.py", "count": 2}],
  "writes": [{"seq": 95, "time": "2026-11-11T10:41:02+08:00", "session": "sess_…", "path": "src/x.py", "tool": "fs_write", "result": "fail"}],
  "tasks_not_found": [],
  "protected": [{"seq": 97, "time": "2026-11-11T10:42:30+08:00", "session": "sess_…", "kind": "shell", "target": "Add-Content .refcov/log.jsonl …"}],
  "unknown_session_calls": 0,
  "by_session": [
    {"session": "sess_da80f038-…", "first": "2026-11-11T09:20:00+08:00", "units_read": 9, "blocks": 2, "text_units": 11, "images": 0},
    {"session": "unknown", "units_read": 0, "blocks": 0, "text_units": 0, "images": 0}
  ],
  "chain": {"ok": true, "lines": 120},
  "files": [
    {"path": ".kiro/hooks/refcov-pre-write.json", "group": "watch", "sha256": "…", "status": "unchanged"},
    {"path": "docs/decisions/2026-11-10-review-reply.md", "group": "confirm", "sha256": "e4a0…", "status": "confirmed"},
    {"path": "docs/decisions/2026-11-11-x.md", "group": "confirm", "sha256": "…", "status": "unconfirmed"}
  ]
}
```

- 例子里所有记录都带 `time` 和 `session`（需求 12.2），字段省略只在第 3.2 节"其他类型"那一句。
- `by_session` 在默认报告里，给出对照实验每组要的数字（需求 17.3）。文字版只列最近 5 个会话，JSON 列全部。
- 经 MCP 的 `report` 工具调用时，服务不知道调用者是哪个会话：`session` 是 `null`，`session_available` 是 `false`，各 `read_session` 字段是 `null`，文字版写"本会话：不可用"。这和需求 12.1、12.2 的原文不一致，是需求本身做不到的地方，已记进"以后再做"。命令行和 UserPromptSubmit 那一行有会话 ID，给出两个数。
- JSON 是唯一数据源，文字版由它生成（需求 12.3）。文字版第一行：`enforce = false` 时写"关卡已关闭"（需求 17.2），否则写模式和是否达标。
- 一行简短形式（需求 9.8、12.4），例如：
  `RefCov 严格模式 未达标：必看单元 本会话 3/14，历史 9/14；还差 5 个：kiro-hooks/退出码@2、…；1 个 decisions 文件待用户确认。参考材料要用 RefCov 的 MCP 工具读，直接读文件不算看过。`

### 3.6 文件校验值和用户确认（`files`，任务 18，可选）

钩子配置、接入层脚本（需求 12.2）和 `docs/decisions/` 下的文件用同一套办法：每次生成报告时，对 `watch` 和 `confirm` 两组路径下的每个文件算 SHA-256，和一个基准比较，结果写进 `files`。两组只差在基准：

| 组 | 基准 | `status` 取值 | 标红 |
| --- | --- | --- | --- |
| `watch` | 上一次在终端跑 `refcov report` 时存下的 `.refcov/report-last.json`。钩子和 MCP 生成的报告只比较、不更新基准，否则 UserPromptSubmit 每条消息都会刷新基准，标红只出现一次 | `unchanged`、`changed`、`new`、`removed` | `changed`、`removed`；`new` 在第一次报告时不标红，之后标红 |
| `confirm` | 日志里这个路径最后一条 `confirm` 记录 | `confirmed`、`unconfirmed`（没确认过，或确认后改过）、`removed` | `unconfirmed` 标红并写"待用户确认"；`removed` 标红 |

- AI 在 shell 里跑 `refcov report` 同样会更新基准（命令行分不出是谁在跑）。要不要拦，做任务 18 时再定。
- `report-last.json` 只是缓存，被删了就全部按"首次"处理，`watch` 组不标红；`confirm` 组的基准在日志里，不受影响。
- `docs/decisions/**` 仍然豁免写文件关卡（需求 8.3）。确认不影响达标，只影响报告和一行简短报告里的提示。
- 用户确认的方式：在终端里跑 `refcov confirm <文件>…`。它算出每个文件当前的校验值，追加 `confirm` 记录，并打印"已确认 N 个文件"。不带参数时列出所有 `unconfirmed` 的文件，不确认任何文件。
- AI 用 shell 跑 `refcov confirm` 一律拦（第 8 节第 2 步）。MCP 工具里没有确认。用户在 Kiro 之外的终端里跑不经过钩子，不受影响（需求 14.6）。

## 4. 单元 ID 和拆分规则

定下 `citation.md` 的待定问题和超长字数。

1. **从标题生成 ID**（需求 2.5）：从单元标题开始，把连续的空白、`[`、`]`、`@` 换成一个 `-`，去掉首尾的 `-`。其余字符原样保留，包括中日韩文字和大小写。结果为空时用 `section`。
   - `@` 也换掉，是为了让 `@` 只出现在拆分后缀里，标题里的 `@` 不会造出和拆分单元一样的 ID。这比需求 2.5 原文多了一个字符，属于偏离需求原文，已记进"以后再做"。
2. **重名**：同一参考源里，按文档顺序，第二个起依次加 `-2`、`-3`……；加了后缀还重名（例如另有一个标题本来就叫"退出码-2"），继续往后数，直到不重复。
   - 先给每个标题保留它自己生成的 ID；重名的从 `-2` 起找空号，空号要避开已给出的 ID，也要避开所有标题自己的 ID（包括文档后面才出现的）。例如顺序是"退出码""退出码""退出码-2"时，第二个"退出码"是 `退出码-3`，"退出码-2"保留 `退出码-2`。这样前面多出一个重名章节时，本身不重名的标题 ID 不变，已写好的引用不会失效（用户 2026-11-11 的决定）。
   - 查重不区分大小写（Python `casefold` 比较），ID 保留原来的大小写。例如"Hooks""hooks"依次是 `Hooks`、`hooks-2`（用户 2026-11-11 的决定）。
3. **超长拆分**（需求 3.5）：单元正文（不含标题行）超过 **4000 个字符**（Python `len`）就拆。在 4000 字之前最后一个空行处切；一段就超过 4000 字的，在 4000 字处硬切。第一段沿用原标题和原 ID；后面的标题是"原标题 (2)""原标题 (3)"……，ID 是原 ID 加 `@2`、`@3`……。
   - 后缀用 `@`，不用需求 3.5 原文写的 `-2`，这样拆分单元和重名单元永远不会撞（用户 2026-11-10 的决定）。属于偏离需求原文，已记进"以后再做"。
   - 先按第 1、2 条定好每个章节的 ID，再拆分。因为第 1 条保证标题生成的 ID 里没有 `@`，拆分后的 ID 不用再查重名。
   - 4000 字的依据：2026-11-10 用 `Invoke-WebRequest` 取 `https://kiro.dev/docs/hooks.md` 约 9.2 KB、`specs.md` 约 8.7 KB，按 `##` 拆后多数章节在 4000 字以内；4000 字大约对应 1000–2000 个 token，一次读取不会撑满上下文。
4. **按哪几级标题拆**：`#`、`##`、`###` 开始新单元；`####` 及更深的留在上一级单元里。代码块（```` ``` ```` 或 `~~~` 围起来的部分）里的 `#` 行不算标题；以 `>` 开头的行不算标题（Kiro 的 `.md` 页面开头就是 `> ## Documentation Index`）。
5. **第一个标题之前的正文**：不为空时单独成一个单元，标题取文件名（不带扩展名），和需求 3.6 用同一条规则。
   - 这个单元的标题借自文件名，不是真标题，分 ID 时排最后：先按第 2 条给所有真标题分完 ID，再给它分；和真标题撞了（不分大小写）就从 `-2` 起找空号。它在清单里仍排第一，只是分 ID 的先后不同。例如 kiro.dev 的 `hooks.md`，`# Hooks` 是 `Hooks`，开头那段是 `hooks-2`（用户 2026-11-11 的决定）。
6. **引用的正则**：仍用 `\[ref:([a-z0-9-]+)/([^\]\s]+)\]`。单元 ID 部分 `[^\]\s]+` 本来就能匹配 `@`，所以不用改，`citation.md` 里写明这一点。
7. **待定问题 2（标到需求级还是每条验收标准）**：定为需求级。一条需求块里（从 `### 需求 N：` 或 `### Requirement N:` 到下一个 `### `；冒号全角半角都认，出处行认 `出处`、`Source`、`Sources`；外部审阅 2026-11-12）任何位置有一个有效的 `[ref:…]`，就不是幻影需求。验收标准末尾的行内引用可写可不写。`citation.md` 的幻影需求定义同步改成"需求块里没有有效引用"。
8. **校验值**：单元正文统一换行为 `\n` 后算 SHA-256。

## 5. MCP 工具（5 个）

服务名 `refcov`，Kiro 里显示为 `mcp_refcov_<工具名>`（实测）。

| 工具 | 输入 | 输出 | 需求 |
| --- | --- | --- | --- |
| `list_units` | `source?`：参考源 ID，不填列出全部 | 每个单元的 ID、标题、类型、是否必看、历史上是否看过 | 5.6、12.2 |
| `read_unit` | `source`、`unit` | 单元文字（适配器有图片时附图片），末尾一行 `refcov-call: c-<seq>`；单元不存在时返回错误和最接近的 3 个 ID | 4.1、4.6 |
| `check` | `path?`：目标路径，不填按全部参考源 | 是否达标、还差的单元（前 20 个和总数）、幻影需求和无效引用（严格模式） | 5.6、6.5、6.6、8.1 |
| `request_token` | 无 | 达标时返回凭证编号，末尾一行 `refcov-call: t-<seq>`；不达标时返回还差的单元 ID 和标题 | 7.1–7.3 |
| `report` | `format`：`text` 或 `json`，默认 `text` | 报告（第 3.5 节）。本会话一栏为"不可用"（`session_available: false`） | 12.1 |

- 没有登记、确认、改配置、写记录的工具（需求 14.3）。登记和确认只能用命令行，由用户运行。
- 每个工具的返回都带一句提示：直接读参考文件不算看过（和需求 9.9 同一句）。
- 返回文字的顺序：正文 → 提示 → `refcov-call:` 行。`refcov-call:` 永远是最后一行，钩子只认最后一行，单元正文里恰好有一行 `refcov-call:` 也不会认错。

## 6. 核心层入口（`refcov/api.py`）

接入层只调用这些函数（需求 13.2），参数里没有 Kiro 的字段名：

| 入口 | 输入 | 输出 |
| --- | --- | --- |
| `read(source, unit)` | 单元 | 内容、调用编号；追加 `read`。唯一追加 `read` 的函数（需求 4.8） |
| `attach_session(call, session)` | 调用编号、会话 | 追加 `session` |
| `check_write(path, session)` | 目标路径 | 放行 / 拦截 + 原因；拦截时追加 `block` |
| `record_write(path, session, tool, source_known)` | 写入后的路径 | 追加 `write`（不达标、无法判断、来源不明时）。如果任务 17 第一步实测 shell 写入会触发 PostFileSave，改成每次写入都追加（含达标的），见第 8 节 |
| `check_task(tasks_file, task_line, session)` | tasks.md 路径和任务行 | 放行 / 拦截 + 原因；找不到任务时放行并追加 `task_not_found` |
| `issue_token(session=None)` | 无 | 凭证或拒绝原因 |
| `report(session=None)` | 会话（可无） | 报告 JSON |
| `status_line(session)` | 会话 | 一行简短报告 |

命令行 `refcov`：

| 子命令 | 做什么 | AI 用 shell 跑 |
| --- | --- | --- |
| `add <路径或网址> --id <参考源ID>` | 登记或重新登记 | **拦**：AI 可以用同一个参考源 ID 登记一个很小的文件，把参考源变成一个单元，读一下就是 100% |
| `report [--json] [--session <会话ID>]` | 报告 | 放行（只读；更新基准见第 3.6 节） |
| `check [路径]`、`check-spec <需求文档>` | 只读检查 | 放行 |
| `confirm [<文件>…]` | 第 3.6 节（任务 18，可选） | **拦** |

- 没有 `init`：配置由用户从 `integrations/kiro/refcov.example.toml` 手动复制，状态目录第一次写入时自动建（第 2 节）。这样核心层的命令行也不用知道接入层的路径。
- 只能由用户跑的子命令记在核心层的 `USER_ONLY = ("add", "confirm")` 里。规则：会往日志里追加记录、会写配置文件、会建立或清空日志的子命令都要放进这个元组。现在没有清空或重建日志的子命令；以后加了也要放进去。
- 接入层的保护检查不能 import 核心层（需求 14.5），所以 `hook.py` 里抄一份同名元组，`tests/test_user_only.py` 检查两份一致。
- 命令行没有会写读取记录的子命令（需求 14.3）。`add` 会写 `register` 记录，按需求 14.4 拦（用户 2026-11-11 的决定），不再偏离需求原文。

## 7. 判断规则（`refcov/coverage.py`）

全是纯函数，输入是清单、日志里的记录、配置、需求文档解析结果，不读文件，所以属性测试可以直接喂数据。

1. **有效读取**：`read` 记录里校验值和清单一致的单元集合。按会话的版本只取能对上该会话的记录（第 3.2 节）。
2. **必看集合**（需求 5.1）：基础集合 − 放宽项 + 被需求引用的单元。基础集合：严格模式取适配器声明为严格必看的类型；轻量模式取关键类型。被引用的单元：所有 `requirements` 文档里有效引用指向的单元。
3. **按路径判断**（需求 8.1、8.2）：必看集合限定在命中的 `scope` 参考源内，再并上全部被引用的单元（需求 6.5：引用了没看过的单元一律不达标，不论在哪个参考源）。
4. **出处检查**（需求 6.6、6.7）：严格模式下有幻影需求、无效引用，或有需求文档一条需求都没解析出来（第 3.4 节，偏离需求原文），就不达标；目标是规格文件时跳过这一步。文字出处算"未转换"。按路径判断时，命中的 `scope` 里有不存在的参考源就按全部参考源（第 3.4 节）。
5. **达标** = 按路径的必看集合 ⊆ 有效读取，且第 4 步通过。不分会话（需求 5.7）。
6. **任务**（需求 9.6）：任务行和子项里的 `[ref:…]`，加上 `_需求：…_`（英文 `_Requirements: …_` 也认）里列出的需求编号对应需求块里的全部 `[ref:…]`。要求这些单元都有效读取，且第 4 步通过。找任务时去掉行首的 `- [ ]`、`- [~]`、`- [x]`、`*` 和首尾空白再比较，也比较去掉编号后的标题。**偏离设计原文（补充，外部审计 2026-11-12，用户定）**：任务行前面可以有空格或制表符（制表符按 4 格算），按缩进深度分层；子任务只算它自己这一行和它自己的子项，父任务算它自己的，再并上全部子任务的（宁可多要求）。顶格的非任务行照旧结束所有任务。状态标记认方括号里的任意单个字符（例如 `[-]`、`[X]`；需求 9.6 原文只列三种，偏离需求原文）。先在全部任务里按完整标题找，找不到再按去掉编号的标题找。同一个编号有几块需求时，几块的引用都算。Kiro 对嵌套子任务传的 `task_name` 是那一行去掉缩进和状态标记后的全文（2026-11-12 在 IDE 里实测）。**偏离设计原文（补充，任务 16，用户 2026-11-12 定）**：需求块只从 tasks.md 同一文件夹里的 `requirements.md` 找，而且它必须命中配置的 `requirements`；找不到可用的需求文档时，任务列的需求编号全算"找不到"。任务列了需求文档里没有的编号，和无效引用同样处理（需求 6.4、6.6）：严格模式不达标，原因写"任务列了需求 N，需求文档里没有"；轻量模式只提示。tasks.md 不在仓库里、文件名不是 `tasks.md`、tasks.md 或需求文档读不了，都按出错处理（钩子放行并记 errors.log），不算找不到任务。RefCov 只读 tasks.md，不改它。

## 8. Kiro 钩子

配置放在 `integrations/kiro/hooks/`，用户确认后复制到 `.kiro/hooks/`（Kiro 要求写这个目录每次确认）。命令都是 `python integrations/kiro/hook.py <事件>`。匹配条件写成锚定的正则，只认精确工具名（需求 9.5）。

| 钩子文件 | 事件 | 匹配条件 | 调用 | 需求 |
| --- | --- | --- | --- | --- |
| `refcov-pre-write.json` | PreToolUse | `^(fs_write\|str_replace\|fs_append)$` | 先做需求 14.1、14.2 的保护；再 `check_write` | 9.1、11.2、14.1、14.2 |
| `refcov-pre-shell.json` | PreToolUse | `^(execute_pwsh\|control_pwsh_process\|execute_bash)$` | 只做需求 14.4 的文本匹配，不调用核心层 | 14.4、14.5 |
| `refcov-post-write.json` | PostToolUse | `^(fs_write\|str_replace\|fs_append)$` | `record_write(source_known=True)` | 10.1 |
| `refcov-post-mcp.json` | PostToolUse | `^mcp_refcov_` | 从 `tool_response` 的最后一行取 `refcov-call:`，`attach_session` | 4.5、7.1 |
| `refcov-file-save.json` | PostFileSave | 无 | `record_write(source_known=False)`；留不留看任务 17 第一步，见表下 | 10.3 |
| `refcov-pretask.json` | PreTaskExec | 无 | `check_task(spec_name, task_name)` | 9.6、9.7 |
| `refcov-prompt.json` | UserPromptSubmit | 无 | `status_line(session_id)` 写 stdout | 9.8、9.9 |

（共 7 个钩子文件、5 种事件；`refcov-file-save.json` 可能删掉，见下。）

`refcov-file-save.json` 留不留，由任务 17 第一步的实测决定：AI 用 shell 写文件（例如 `Set-Content`）时 PostFileSave 触不触发。

- 不触发：这个钩子看到的每次保存，PostToolUse 都已经处理过（2026-11-10 的样本里用户手动保存没触发它，只测了一次），没有新信息。删掉这个钩子文件和 `hook.py` 里的分支。需求 10.3 是"收到保存事件时"才适用的条件句，不注册这个钩子不违反它。
- 触发：它是唯一能发现 shell 写入的地方，留下。去重不在钩子里做：`refcov-post-write.json` 每次写入都追加 `write`（含达标的），`refcov-file-save.json` 每次也追加一条；生成报告时，一条保存记录前后 10 秒内同一路径没有写文件工具的 `write` 记录，才算"来源不明"。这样和两个钩子进程谁先写日志无关（两者几乎同时触发，`hooks.jsonl` 20:34:54 的三条）。

shell 工具名：`execute_pwsh` 在 `docs/验证结果.md` 第 2 项里实测过。`control_pwsh_process` 只在 agent 的工具列表里见过，钩子能不能按这个名字匹配上没测过，第 10 节第 7 步做关卡前先实测。`execute_bash` 是其他系统上的 shell 工具名（AWS Labs 的记录里有），加上它，评委在 Mac 上试时保护也生效；本机测不到。

`hook.py` 的顺序（需求 11.1、11.3、14.5）：

1. 按字节读 stdin，UTF-8 解码，stdout、stderr 改成 UTF-8。按自己的文件位置算出仓库根目录（第 2 节），不依赖当前目录。
2. 事件是 PreToolUse 时做保护检查，命中就退出码 2，这一步的任何异常也退出码 2，这一步不 import 核心层：
   - 写文件：`tool_input.path` 在 `.refcov/` 下或是 `refcov.toml`。
   - shell，出现就拦：`tool_input.command` 里出现 `.refcov`、`refcov.toml` 或 `.kiro/hooks`（正反斜杠都算）。`command` 为 `null`（`control_pwsh_process` 的 `stop`，`docs/验证结果.md` 第 7 项）当空字符串。`.kiro/hooks` 是用户 2026-11-12 定的，比需求 11.4 多保护一处（**偏离需求原文**）：挪走、删掉、查看钩子目录都由用户做，钩子文件由用户提交，AI 看这个目录用读文件的工具。任务 18 里钩子校验值那一块因此不做。
   - shell，只在被执行时拦：用 Python 运行钩子脚本，正则 `(^|[\s;&|(])python3?(\.exe)?(\s+-(?!m\b|c\b)\S+)*\s+["']?(\S*[/\\])?hook\.py\b`；运行 MCP 服务，正则 `-m\s+refcov_mcp\b`。钩子脚本那条比第一版收紧了（任务 14）：第一版的 `[^;&|\n]*hook\.py` 会把 `python -m pytest tests/test_hook.py` 也拦住；现在 `python` 后面紧跟 `-m`、`-c` 不算，文件名也必须正好是 `hook.py`。只是在命令里提到 `integrations/kiro` 或 `refcov_mcp` 不拦，所以 `git add integrations/kiro/hook.py`、`git diff integrations/kiro/…`、`pytest tests/test_refcov_mcp.py` 都能跑。
   - shell，只能用户跑的子命令：正则 `(^|[\s;&|(])(refcov(\.exe)?|python3?(\.exe)?\s+-m\s+refcov)\s+(add|confirm)\b`（`add`、`confirm` 来自 `USER_ONLY`）。
   - 以上都不分大小写。
3. import 核心层，调用入口。任何异常都写 `.refcov/errors.log`（`json.dumps(..., ensure_ascii=True)`）并退出码 0。
4. 拦截时原因写 stderr、退出码 2；同一会话同一目标第 2 次起加"停下来，向用户说明情况"（需求 11.2）。`enforce = false` 时第 3 步一律放行，第 2 步照常（需求 17.1）。

注意：

- 第 2 步的文本匹配也会拦住 AI 用 shell **读**状态目录（例如 `Get-Content .refcov/log.jsonl`）、`git add .refcov/sources.json`，以及提交信息里写到这些名字的 `git commit`。AI 看记录要用 MCP 的 `report`；清单要提交时用 `git add -A` 或由用户提交，README 写明。
- 用管道把样例喂给 `hook.py` 自测，也会被"运行钩子脚本"那条拦住。钩子脚本的自测写成 pytest 测试（命令文本是 `pytest …`，不匹配），测试里用临时目录当仓库根目录。
- 文本匹配挡不住改了写法的命令（例如拼接字符串、用 `py` 启动），这是需求 11.4 写明的局限。
- 逃生办法：保护检查出异常时一律拦（需求 14.5），这一步要是写错一行，每次写文件和每条 shell 命令都会被拦，Kiro 自己改不回来。用户把 `.kiro/hooks/refcov-pre-*.json` 移出 `.kiro/hooks/` 就能立即停用（2026-11-10 实测移走钩子文件立即生效）。README 写明这一步。

## 9. 属性测试（需求 16）

Hypothesis 直接生成第 7 节纯函数的输入，不经过文件。

生成数据：

- **参考源和单元**：1–4 个参考源，每个 0–20 个单元。单元类型从 `section`、`shot`、`crs`、`extent`、`fields`、`validity`、`sample` 里抽。标题用含中文、空格、方括号、`@`、emoji 的文本，并故意生成重名标题和本身以"-2"结尾的标题；ID 用第 4 节的函数生成。
- **适配器声明**：每种类型随机定"严格必看"；"关键类型"只从严格必看的类型里抽（满足需求 2.4）。
- **读取记录**：从单元里随机抽，可重复；一部分校验值故意写错（过期）；随机挂会话。
- **需求文档**：随机条数的需求块，每块引用 0–3 个单元，混入不存在的单元（无效引用）、没有引用的块（幻影需求）、文字出处。
- **配置**：两种模式；放宽项从参考源、类型、单元里各抽子集；`scope` 随机。
- **AI 的文字**：任意文本，用来测性质 4。

| 性质 | 测法 |
| --- | --- |
| 16.1 | 任意输入，两种覆盖率都在 [0, 1] |
| 16.2 | 把某条读取记录再追加 1–5 次，覆盖率不变 |
| 16.3 | 选一个被引用的单元，删掉它的有效读取，不论放宽项怎么设都不达标 |
| 16.4 | 同一输入配不同的 AI 文字（自述、写入正文、`tool_input` 里的其他字段），结论相同 |
| 16.5 | 同一输入下，轻量必看集合 ⊆ 严格必看集合 |
| 16.6 | 同一输入下，严格达标 ⇒ 轻量达标。第 7 节第 4 步在轻量模式下不判失败，在严格模式下可能判失败，方向一致，不影响这条 |

另加三条和单元 ID 有关的（`testing.md` 要求）：

- 生成的 ID 不含空白、方括号；标题生成的 ID 不含 `@`。
- 同一标题序列生成两次，ID 相同；同一参考源里所有 ID（含拆分出的 `@N`）互不重复。
- 拆分后把所有段的正文按顺序拼回去，等于原正文。

反例按 `testing.md` 固定成回归测试并记进 DEVLOG。`max_examples` 用默认值，持续集成里在 Linux 上再跑一遍（需求 13.5）。

## 10. 先做哪条通路（外部审阅 D1）

先通一条最细的路，关卡放在后面。每一步做完都能用。

| 步 | 做什么 | 用到的模块 | 完成标志 |
| --- | --- | --- | --- |
| 1 | `refcov add` 登记一份 Markdown，拆单元，写清单；`.gitignore` 检查（需求 1.3） | store、sources、markdown | 登记 `https://kiro.dev/docs/hooks.md`，清单里单元和标题对得上，拆两次 ID 相同；`test_gitignore.py` 通过 |
| 2 | MCP 的 `list_units`、`read_unit`，写 `read` 记录（带哈希链） | store、api、refcov_mcp | 在 Kiro 里读 3 个单元，日志里 3 条，链完整 |
| 3 | `refcov-post-mcp.json` 钩子补记会话 | integrations/kiro | 两个会话各读一次，日志里会话分得开 |
| 4 | `refcov report` 文字和 JSON，`refcov-prompt.json` 一行报告 | api、coverage（只算覆盖率） | 发消息时上下文里出现"本会话 x/y，历史 a/y" |
| 5 | 用它管自己：登记比赛规则页和 Kiro 钩子文档，后面写钩子代码前先经 MCP 读完 | — | DEVLOG 开始记"RefCov 拦了自己几次"所需的数据 |
| 6 | `citations`、`check-spec`，必看集合和达标；属性测试 16.1–16.6 | citations、coverage | 属性测试通过 |
| 7 | 关卡：实测 `control_pwsh_process`；保护检查；写文件、任务开工、写入后记录、拦截次数提示；`refcov confirm` 和文件校验值（可选，放在最后） | integrations/kiro、api | 没读完时写 `integrations/kiro/**` 被拦，读完后放行；用户点引用了没读单元的任务的 Start task 被拦；AI 跑 `refcov add` 被拦 |
| 8 | 凭证和 `check`、`request_token` | api、refcov_mcp | 凭证在配置修改后显示失效 |

持续集成（GitHub Actions 在 Linux 上跑 `pytest`）在第 1 步就建好，换行、大小写这类只在 Linux 上暴露的问题早发现。

目标：第 1–4 步在 2026-11-14 前跑通（审阅 D1 说"两天内"；用户 11-12 要先写两个应用和演示页的需求，所以推到 11-14，和 `tasks.md` 一致）。第 7 步之后，开发本项目的写入就会被自己的关卡管住。

## 11. 已知取舍

- 一个日志文件放所有记录：格式最少；代价是报告要扫全文件。记录量是每次读取一行，比赛期间预计几千行，直接扫可以接受。
- `refcov add` 只能由用户在终端跑。2026-11-10 曾决定放行，理由是"重新登记只会让旧记录失效"；这只在登记同一份内容时成立，用同一个 ID 登记一个很小的文件就能把覆盖率做到 100%，所以 2026-11-11 改为拦（外部审阅一.2）。
- 经 MCP 的 `report` 没有本会话数，本会话数只在 UserPromptSubmit 那一行和命令行 `--session` 里有。
- PostFileSave 在用户手动保存时这次实测没触发（DEVLOG 2026-11-10，只测了一次）。要不要注册这个钩子，看任务 17 第一步的实测（第 8 节）。

---

## 附：spec-auditor 审阅报告（2026-11-10，第一版设计，原文）

审了 `.kiro/specs/refcov-skeleton/design.md`，对照 `.kiro/specs/refcov-skeleton/requirements.md`。检查项 1 发现 0 处；检查项 2 发现 2 处没有任何对应，另有 2 处只在内容上对应；检查项 3 发现 7 处，其中 6 处是设计和需求冲突，1 处是设计文档内部不一致；检查项 4 发现 3 处，都是按草案判断。

### 1. 引用的需求编号是否存在

无。

设计里出现的编号都在需求文档里，包括表格"需求"列和正文的"需求 N.M"。区间引用也核对过：2.1–2.6、3.1–3.6、5.1–5.7、6.1–6.4、6.5–6.7、7.1–7.6、8.1–8.5、9.5–9.10、10.1–10.3、12.1–12.4、14.1–14.6、16.1–16.6、17.1–17.3。已删除的 4.2、9.2–9.4、15.3 没有被引用，9.5–9.10 这个区间也绕开了 9.2–9.4。第 10 节的"外部审阅 D1"是审阅节号，不是需求编号，没算进来。

### 2. 需求里没有对应设计的验收标准

完全没有对应：
- 1.3：`.gitignore` 不得忽略 `.kiro` 目录及其内容，并要有一项自动检查。设计只在第 2 节写了 `cache/` 被忽略，没提 `.kiro`，也没提这项自动检查。
- 17.4：用掉的额度由用户手动抄；实验只做严格模式下 `enforce` 开、关两组；实验放在单独的规格里。设计里没有对应内容。

没有编号引用，只在内容上对应：
- 4.8：不根据 AI 的文字自述增加读取记录。设计第 9 节性质 16.4 的测法里有"自述"，但没有地方写这条规则本身。
- 13.3：核心层计算部分只用标准库。第 1 节写了"只有 `refcov_mcp` 依赖第三方包"，但没标 13.3。

### 3. 设计和需求说法冲突（人工判断）

1. **AI 用 shell 跑 `refcov add`。** 设计第 11 节第 2 条说 AI 能这样做，而且"不拦"；第 3.2 节说 `register` 记录写进同一个日志。需求 14 的引言说保护"一律生效"，需求 14.4 要求拦住出现"其他会写记录的 RefCov 入口"的 shell 命令。第 8 节第 2 步的匹配词（`.refcov`、`refcov.toml`、`integrations/kiro`、`refcov_mcp`）都匹配不上 `refcov add`。
2. **`refcov init` 写配置文件。** 设计第 6 节的 `init` 会创建 `refcov.toml`。需求 14.2 说配置只能由用户手动修改，需求 14.4 要求拦住出现配置文件名的 shell 命令。命令文本 `refcov init` 里没有 `refcov.toml`，所以第 8 节第 2 步拦不住它。
3. **经 MCP 拿到的报告没有本会话数。** 设计第 5 节 `report` 工具说"只给历史数，不给本会话数"，第 11 节第 3 条也这样写。需求 12.1 要求命令行和 MCP 两种方式都给报告；需求 12.2 要求每个参考源的覆盖率"各给本会话和历史两个数"。
4. **按会话的数字。** 设计第 3.5 节最后一条说放在 `--by-session` 里，"不放进默认报告"。需求 17.3 写的是"THE 报告 SHALL 按会话给出每组需要的数字"，没说可以另开选项。
5. **记录缺时间和会话 ID。** 需求 12.2 末尾要求"各类记录……每条带时间和会话 ID"。设计第 3.5 节的 JSON 例子里，`blocks` 和 `protected` 没有 `time`，`writes` 既没有 `time` 也没有 `session`。例子可能是省略写法，但文中没说明。
6. **默认豁免路径。** 需求 8.3 写的是豁免 `DEVLOG.md`。设计第 3.4 节写的是 `docs/DEVLOG.md`，而且配置路径从仓库根目录开始匹配，所以其他位置的 `DEVLOG.md` 不再豁免。
7. **钩子数量（设计内部不一致）。** 开头的 EN summary 写"6 Kiro hooks"，第 8 节写"共 7 个钩子文件、5 种事件"，表格里也列了 7 个。按 language.md 的规矩，英文要和中文一致。

### 4. `[ref:…]` 示例和单元 ID 规则是否符合 citation.md（按草案判断）

1. **什么算幻影需求。** citation.md 说"没有 `出处：` 行、或 `出处：` 行里一个有效引用都没有的需求，算幻影需求"。设计第 4 节第 5 条改成"需求块里任何位置有一个有效的 `[ref:…]`，就不是幻影需求"。照设计的写法，只在验收标准里写了行内引用、没有 `出处：` 行的需求不算幻影需求；照 citation.md 算。另外，设计说"定下 citation.md 的待定问题"，但 citation.md 的待定问题 2 还没划掉。
2. **ID 生成比草案多几条规则。** 设计第 4 节第 1 条另加了：连续空白合成一个 `-`；去掉首尾的 `-`；结果为空时用 `section`。citation.md 和需求 2.5 只写了"空白和方括号换成短横线"。例如标题 `a  b`，按草案字面得到 `a--b`，按设计得到 `a-b`。两边不矛盾，但写法不一样。
3. **拆分后撞 ID 怎么办。** 需求 3.5 要求超长拆分得到的 ID（原 ID 加 `-2`）撞上已有 ID 时继续加后缀。设计第 4 节第 4 条没写这一步。按第 1 条的规则，标题"退出码 2"会生成 `退出码-2`，正好和超长拆分出的 `退出码-2` 重复。

和 citation.md 一致的部分：
- 例子里的参考源 ID `kiro-hooks` 符合 `[a-z0-9-]+`。
- 单元 ID `退出码`、`退出码-2`、`Hooks` 都符合 `[^\]\s]+`。
- 例子里 `退出码 (2)` 对应 ID `退出码-2`，符合 citation.md 的拆分写法。
- tasks.md 里用 `_需求：…_` 写需求编号的做法也一致。

### 没法检查的项

- 引用的参考源和单元是否真实存在、有没有有效读取记录、哪些是幽灵单元和被忽略单元：没有登记清单和读取记录，无数据，未检查。
- 设计开头写的需求提交 `d04e8fa` 和当前需求文档是否一致：我只读文件，没查 git 历史，未检查。
- shell 工具名：`execute_pwsh` 在 `docs/验证结果.md` 的实测表里出现过；`control_pwsh_process` 在 `docs/` 和 `experiments/` 里都没有实测记录，未核实。
- 4000 字上限的依据（hooks.md 约 9.2 KB、specs.md 约 8.7 KB）：没有抓取原文，未核实。

## 附：报告的处理结果（第二版设计）

| 报告条目 | 处理 | 改在哪 |
| --- | --- | --- |
| 2·1.3 | 加 `tests/test_gitignore.py`；只认 `.gitignore` 来源的命中为失败，`.git/info/exclude` 的不算 | 第 2 节文件位置；第 10 节第 1 步 |
| 2·17.4 | 写明不在本设计范围；需求层面记进"以后再做" | 第 1 节 |
| 2·4.8、13.3 | 补编号；4.8 写成"只有 `api.read` 追加读取记录" | 第 1、2、6 节 |
| 3·1 | 用户决定 `refcov add` 放行；偏离需求 14.4 原文，记进"以后再做" | 第 6 节命令行表；第 11 节 |
| 3·2 | `init`、`confirm` 列为只能用户跑，shell 里一律拦；两处元组用测试保持一致 | 第 6 节；第 8 节第 2 步 |
| 3·3 | 需求本身做不到；MCP 报告本会话一栏标"不可用"；记进"以后再做" | 第 3.5、5 节 |
| 3·4 | `by_session` 放进默认报告 | 第 3.5 节 |
| 3·5 | 例子补上 `time`、`session`；日志每行都带 `session` | 第 3.2、3.5 节 |
| 3·6 | 默认豁免改成 `DEVLOG.md`、`**/DEVLOG.md`、`docs/decisions/**`；需求措辞记进"以后再做" | 第 3.4 节 |
| 3·7 | 英文摘要改成"7 Kiro hook files on 5 events" | 开头 |
| 4·1 | `citation.md` 的幻影需求定义改成"需求块里没有有效引用"，划掉待定问题 2 | 第 4 节第 7 条；`citation.md` |
| 4·2 | `citation.md` 补上合并空白、去首尾、空时用 `section` | `citation.md` |
| 4·3 | 用户决定：拆分后缀用 `@2`，重名后缀用 `-2`；标题里的 `@` 也换成 `-`，两种不会撞 | 第 4 节第 1–3 条；`citation.md` |
| 未核实·`control_pwsh_process` | 第 7 步做关卡前实测 | 第 8 节；第 10 节第 7 步 |
| 未核实·4000 字依据 | 数字来自 agent 2026-11-10 用 `Invoke-WebRequest` 取的响应大小，写明来源 | 第 4 节第 3 条 |

用户另加的一项：`docs/decisions/` 的文件列校验值，没确认或改过的标红"待用户确认"，用户用 `refcov confirm` 确认（第 3.6 节）。
