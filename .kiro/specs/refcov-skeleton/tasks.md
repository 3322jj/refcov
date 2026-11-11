# 实施计划：RefCov 骨架

EN summary: Implementation tasks for the skeleton, following design.md section 10. Tasks 1–7 build the thinnest path (register a Markdown source, split it, read units via MCP, record reads with a hash chain, attach session IDs from a PostToolUse hook, report) and should run end to end by 2026-11-14; Linux CI is set up in task 2. Task 8 puts RefCov in charge of its own development. Gates come after that: the task-start gate (task 16) is required, while `refcov confirm` with file checksums (task 18) and tokens (task 19) are optional; there is no `refcov init`.

依据：`requirements.md`（冻结于 `d04e8fa`）、`design.md`（第二版，`c23e09f`；2026-11-11 按 `docs/设计第二版审阅.md` 改了对应句子）。每个任务的 `_需求：…_` 写需求编号，"设计 N"指 `design.md` 第 N 节。骨架能读参考源之后，任务子项再补 `[ref:…]`。

2026-11-11 任务编号调整：原任务 18（任务开工关卡）改成必做，编号改为 16；原任务 16（`init`、`confirm`、校验值）砍掉 `init`、改成可选，编号改为 18。任务 17 不变。DEVLOG 里这一天之前的记录按旧编号。

## 最细通路（设计 10 第 1–4 步，目标 2026-11-14 前跑通）

- [ ] 1. 项目结构、环境和状态目录
  - 建 `pyproject.toml`（Python ≥ 3.11；运行依赖只有 `mcp`，开发依赖 `pytest`、`hypothesis`；命令行入口 `refcov`）、`refcov/`、`refcov_mcp/`、`integrations/kiro/`、`tests/`
  - 环境：用 PATH 上的 `python`（钩子命令用的就是它），在里面 `pip install -e .`；README 写明这一步，再写一行"把 `integrations/kiro/refcov.example.toml` 复制成仓库根目录的 `refcov.toml`"（设计 2）
  - `integrations/kiro/refcov.example.toml`：按设计 3.4 的例子写
  - 仓库根目录由调用方传入，核心层不按当前目录找状态目录（设计 2）
  - `.gitignore` 加 `.refcov/errors.log`、`.refcov/log.lock`、`.refcov/report-last.json`；新建 `.gitattributes`，写 `*.jsonl -text`
  - `refcov/store.py`：状态目录路径，第一次写入时自动建；读 `refcov.toml`（`tomllib`，不存在时用设计 3.4 的默认值）；读写 `.refcov/sources.json`；路径匹配先转小写再用 `fnmatchcase`（设计 3.4）
  - 追加日志：`log.lock` 文件锁、`seq`、`time`、`session`、`prev` 哈希链（按不含换行符的 UTF-8 内容算，换行固定 `\n`）；2 秒拿不到锁就报错；校验哈希链，返回"完整"或"第 N 行起断开"
  - 测试：两个进程同时各追加 100 行，链仍完整、`seq` 不重复；手工改一行后校验报出断开的行号
  - _需求：1.1、1.2、4.3、4.4、13.3_

- [ ] 2. `.gitignore` 检查和持续集成
  - `tests/test_gitignore.py`：对 `.kiro` 下所有文件和构造路径跑 `git check-ignore -v --no-index`，命中规则来自 `.gitignore` 就失败，来自 `.git/info/exclude` 的不算（设计 2）
  - 持续集成：GitHub Actions 在 Linux 上跑 `pytest`（从任务 12 提前到这里，换行和大小写的问题早发现）
  - _需求：1.3、13.5_

- [ ] 3. 单元 ID 和文档适配器
  - `refcov/sources.py`：适配器接口（拆成单元、读一个单元、可核对的事实，共 3 个函数）；ID 生成（设计 4 第 1–3 条：空白、`[`、`]`、`@` 换成 `-`，重名 `-2`，拆分 `@2`）
  - `refcov/adapters/markdown.py`：按 `#` 到 `###` 拆；跳过代码块和 `>` 开头的行；第一个标题前的正文和无标题文档按文件名成一个单元；超过 4000 字符按空行切；单元正文换行统一后算 SHA-256。数一下不含注释和空行的行数，超过 50 行左右就在设计里写原因
  - 属性测试：ID 不含空白和方括号、标题生成的 ID 不含 `@`；同一标题序列两次结果相同、ID 互不重复；拆分后拼回等于原文（设计 9）
  - _需求：2.1、2.2、2.3、2.4、2.5、3.1、3.2、3.3、3.5、3.6_

- [ ] 4. 登记参考源和 `refcov add`
  - `sources.register(origin, source_id)`：抓取（本地文件或网址）、存进 `.refcov/cache/`、拆单元、写清单和 `register` 记录；重新登记时校验值变了就重拆
  - 不是 Markdown 时登记失败并报"不支持该格式"；抓取失败报原因；两种情况都不改清单
  - 命令行 `refcov add <路径或网址> --id <参考源ID>`（只能由用户跑，任务 14 拦 AI 在 shell 里跑）
  - 完成标志（自动测试）：登记仓库里的一份本地 Markdown 样例（放在 `tests/` 下），清单里的单元和标题对得上；同一内容登记两次，ID 相同
  - 手动检查：登记 `https://kiro.dev/docs/hooks.md`。这台机器外网时断时续，失败不算任务失败，结果记进 DEVLOG
  - _需求：1.1、1.4、1.5、2.6、3.4_

- [ ] 5. MCP 服务：`list_units`、`read_unit`
  - `refcov/api.py`：`read(source, unit)`，唯一追加 `read` 记录的函数，记 `text_units`、`images`，返回内容和调用编号；拿不到日志锁时报错、不返回内容
  - `refcov_mcp/server.py`：官方 SDK，stdio；启动参数 `--root <仓库根目录>`；两个工具按设计 5 的输入输出；返回顺序是正文 → "直接读文件不算看过"的提示 → `refcov-call: c-<seq>`，`refcov-call:` 永远是最后一行；单元不存在时返回最接近的 3 个 ID
  - 更新 `docs/mcp.example.json`，指向正式服务，写出 `--root` 参数；用户手动改 `.kiro/settings/mcp.json`
  - 完成标志：在 Kiro 里读 3 个单元，日志里 3 条 `read`，哈希链完整
  - _需求：4.1、4.6、4.7、4.8、13.2、13.4_

- [ ] 6. 会话补记钩子
  - `integrations/kiro/hook.py`：按设计 8 第 1、3 步写好编码处理、按自己的位置算仓库根目录并放进 `sys.path`、出错放行并写 `.refcov/errors.log`；先只接 PostToolUse 的 MCP 分支
  - `api.attach_session(call, session)`：只认 `tool_response` 最后一行的 `refcov-call:`，追加 `session` 记录
  - `integrations/kiro/hooks/refcov-post-mcp.json`（匹配 `^mcp_refcov_`），由用户确认后放进 `.kiro/hooks/`
  - 完成标志：两个会话各读一次，日志里两次读取分属两个会话；把钩子挪走再读一次，日志里有这次的 `read` 行、没有对应的 `session` 行；`.refcov/errors.log` 是空的
  - _需求：4.5、9.5、9.10、11.1、11.3_

- [ ] 7. 报告和一行简短报告
  - `refcov/coverage.py`：有效读取（校验值和清单一致）、覆盖率，按历史和按会话各算一次（这一步还不算必看集合，必看 = 全部单元）
  - `api.report(session)`：生成设计 3.5 的 JSON（这一步只填 `sources`、`missing`、`unknown_session_calls`、`by_session`、`chain`）；文字版由 JSON 生成；`api.status_line(session)`
  - 命令行 `refcov report [--json] [--session <会话ID>]`；MCP 工具 `report`（本会话一栏"不可用"）
  - `integrations/kiro/hooks/refcov-prompt.json`（UserPromptSubmit）
  - 完成标志（自动测试）：pytest 里用 subprocess 把一条 UserPromptSubmit 样例从 stdin 喂给 `hook.py`（临时目录当仓库根目录），stdout 里有"本会话 x/y，历史 a/y"和"直接读文件不算看过"的提示
  - 完成标志：任务 6 里挪走钩子后读的那一次，报告里"会话未知"计数是 1
  - 旁证：用户发消息时 AI 转述上下文里出现了这一行（只作旁证，不算完成标志）
  - _需求：5.4、5.5、5.7、9.8、9.9、12.1、12.2、12.3、12.4、17.3_

- [ ] 8. 检查点：最细通路跑通
  - 从登记到报告完整走一遍，结果记进 DEVLOG；有问题先问用户再往下做

## 用它管自己（设计 10 第 5 步）

- [ ] 9. 登记开发要读的材料
  - 由用户在终端登记：比赛规则页、`https://kiro.dev/docs/hooks.md`、`https://kiro.dev/docs/permissions.md`、`docs/decisions/` 下的文件
  - 比赛规则页是 HTML，文档适配器会拒绝（需求 3.4）：由用户把规则页正文存成本地 Markdown 文件，放在 `.refcov/` 下、`cache/` 旁边，再登记这个本地文件
  - 在 DEVLOG 开始记"RefCov 拦了自己几次"所需的数字：每天看了几分之几、写钩子代码前读了哪些单元
  - _需求：6.1_

## 出处检查和达标（设计 10 第 6 步）

- [ ] 10. 解析需求文档和 tasks.md
  - `refcov/citations.py`：按 `### 需求 N：` 切块；用 `citation.md` 的正则提取引用；识别 `出处：` 行里的文字出处（报"未转换"）；列出幻影需求、无效引用、被引用的单元
  - 解析 tasks.md：按设计 7 第 6 条找任务（去掉状态标记和首尾空白），收集任务和子项里的引用、`_需求：…_` 指向的需求块里的引用
  - 命令行 `refcov check-spec <需求文档>`
  - 测试：用 `tests/` 下一份固定的样例需求文档跑，结果和预期的未转换、幻影需求、无效引用条数一致。不直接用 `requirements.md`，它在任务 11 最后一步会变
  - _需求：6.1、6.2、6.3、6.4、9.6_

- [ ] 11. 必看集合和达标判断
  - `coverage.py`：必看集合 = 基础集合 − 放宽项 + 被引用单元（设计 7 第 2 条）；按路径和 `scope` 判断（第 3 条）；严格模式下的出处检查和规格文件例外（第 4 条）；达标（第 5 条）；被忽略单元、幽灵单元、本模式未要求的单元
  - 报告补齐：`ghost_units`、`not_required_units`、`ignored_units`、`phantom_requirements`、`invalid_refs`、`unconverted_requirements`、`relaxed`、`exempt`、`config_mtime`
  - MCP 工具 `check`；命令行 `refcov check [路径]`
  - 最后一步：把 `requirements.md` 的文字出处换成 `[ref:…]`（需求文档简介里已计划的事，不改需求内容）。出处里用到、任务 9 还没登记的文件由用户先登记；对不上单元的（例如原文在工作区外）保留文字出处。跑 `refcov check-spec` 和 `refcov report`，把幻影需求、被忽略单元、无效引用、未转换的结果记进 DEVLOG
  - _需求：5.1、5.2、5.3、5.6、6.1、6.5、6.6、6.7、8.1、8.2、8.3、8.4、8.5、15.1、15.2_

- [ ] 12. 属性测试（需求 16）
  - 按设计 9 写数据生成器；16.1–16.6 每条至少一个 `@given` 测试，文档字符串写明是哪条性质
  - 再加一个普通测试：`refcov/`、`refcov_mcp/` 里不出现 Kiro 的工具名、事件名、`.kiro` 路径，也不 import `hypothesis`
  - 抓到的反例固定成回归测试，记进 DEVLOG
  - _需求：13.1、13.4、16.1、16.2、16.3、16.4、16.5、16.6_

## 关卡（设计 10 第 7 步）

- [ ] 13. 实测 `control_pwsh_process` 的钩子匹配
  - 用试验钩子确认 PreToolUse 能按这个工具名匹配上，`tool_input` 里有没有 `command`；结果记进 `docs/验证结果.md` 和 DEVLOG
  - _需求：14.4_

- [ ] 14. 保护检查
  - `hook.py` 第 2 步：写文件路径在 `.refcov/` 下或是 `refcov.toml` 就拦；shell 命令文本按设计 8 第 2 步匹配（`.refcov`、`refcov.toml` 出现就拦；钩子脚本和 `refcov_mcp` 只在被执行时拦；`USER_ONLY` 里的子命令）；任何异常都退出码 2；不 import 核心层
  - shell 钩子匹配 `^(execute_pwsh|control_pwsh_process|execute_bash)$`
  - `USER_ONLY = ("add", "confirm")` 在核心层和 `hook.py` 各一份，`tests/test_user_only.py` 检查一致
  - 追加 `protect` 记录（核心层加载失败时只写 stderr）
  - `integrations/kiro/hooks/refcov-pre-write.json`、`refcov-pre-shell.json`
  - README 写明：逃生办法（把 `.kiro/hooks/refcov-pre-*.json` 移出 `.kiro/hooks/` 立即停用）；清单要提交时用 `git add -A` 或由用户提交
  - 测试：`refcov add x --id y`、`python -m refcov confirm x`、`Add-Content .refcov/log.jsonl x`、`python integrations/kiro/hook.py PreToolUse` 被拦；`refcov report`、`git add integrations/kiro/hook.py`、`pytest tests/test_refcov_mcp.py` 放行
  - _需求：14.1、14.2、14.3、14.4、14.5、14.6_

- [ ] 15. 写文件关卡和拦截次数提示
  - 开始前：用户先从 `integrations/kiro/refcov.example.toml` 手动建好 `refcov.toml`，里面有覆盖 `integrations/kiro/**` 的 `[[scope]]`（配置只有用户能改）
  - `api.check_write(path, session)`；拦截原因写清还差的单元、幻影需求、无效引用；同一会话同一目标第 2 次起加"停下来，向用户说明情况"；追加 `block`
  - `enforce = false` 时放行，保护检查照常；文字报告第一行写"关卡已关闭"
  - 完成标志：没读完时写 `integrations/kiro/**` 被拦，读完后放行
  - _需求：9.1、11.2、17.1、17.2_

- [ ] 16. 任务开工关卡
  - `api.check_task`；`refcov-pretask.json`；拦截时提醒任务会停在"进行中"；找不到任务时放行并追加 `task_not_found`
  - 完成标志：用户在 IDE 里点一个引用了没读单元的任务，被拦；读完后放行
  - _需求：9.6、9.7_

- [ ] 17. 写入后记录
  - 第一步，实测：AI 用 shell 写文件（例如 `Set-Content`）时 PostFileSave 触不触发。结果记进 `docs/验证结果.md` 和 DEVLOG，按设计 8 决定留不留 `refcov-file-save.json`：
    - 不触发：不做 `refcov-file-save.json` 和 `hook.py` 里的分支
    - 触发：`refcov-post-write.json` 每次写入都追加 `write`（含达标的），`refcov-file-save.json` 每次也追加；"来源不明"在生成报告时判断（同一路径前后 10 秒内没有写文件工具的 `write` 记录），不标红
  - `api.record_write`；`refcov-post-write.json`（PostToolUse）
  - 判断出错时记"无法判断"；不恢复、不删除任何文件
  - _需求：10.1、10.2、10.3_

- [ ]* 18. `refcov confirm` 和文件校验值（可选）
  - 没有 `refcov init`：配置由用户手动复制，状态目录第一次写入时自动建（任务 1）
  - `confirm [<文件>…]`：追加 `confirm` 记录；不带参数时只列出待确认的文件
  - 报告 `files`：`watch` 组和上一次在终端跑 `refcov report` 存下的 `report-last.json` 比，钩子和 MCP 生成的报告只比较、不更新基准；`confirm` 组和最后一次 `confirm` 比（设计 3.6）；一行简短报告里提示待确认的数量
  - 先定：AI 用 shell 跑 `refcov report` 也会更新基准，要不要拦（设计 3.6）
  - _需求：12.2_

## 凭证（设计 10 第 8 步）

- [ ]* 19. 凭证和 `request_token`（可选）
  - `api.issue_token`；失效判断（单元校验值、新登记、配置修改时间）；MCP 工具 `request_token`（`refcov-call: t-<seq>` 是最后一行）；报告 `tokens`
  - 完成标志：改一下 `refcov.toml` 后，报告里凭证显示失效
  - _需求：7.1、7.2、7.3、7.4、7.5、7.6_

## 收尾

- [ ] 20. 文档
  - README 的状态、目录和局限按实际情况更新；局限照需求 11.4 逐条写
  - `citation.md` 去掉"草案"字样（如果实现和设计 4 一致）
  - _需求：11.4_
