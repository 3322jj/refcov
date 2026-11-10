# DEVLOG

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
- 第一次提交 `a64d773` 用了 rockey <denghongsh@gmail.com>，并已建公开仓库 `3322jj/refcov` 推上去。这一步做早了：用户随后要求提交者改成 GitHub noreply 邮箱，并且提交前、建仓库前都要先给他确认。已把本仓库的 git 身份改成 3322jj 的 noreply 邮箱（只改本仓库，没改全局）。经用户明确同意，第一次提交改写为 `51281a2`（内容不变，只改作者），用 `--force-with-lease` 覆盖远端。旧提交 `a64d773` 可能还能在 GitHub 上按哈希访问一段时间。用户要求：以后不经他明确同意不得强制推送。
- 需求文档从 kirohe 搬到 `.kiro/specs/refcov-skeleton/requirements.md`，按用户对 7 个问题的回复改成第二稿。PreTaskExec 的实测结果也写进去了（需求 10.6、10.7）。
- 用到的 Kiro 功能：规格流程（需求阶段第二轮）。

## 2026-11-10（夜：需求第三稿）

- 按用户对第二稿的 10 条审阅意见改成第三稿。新增需求 15（保护状态目录和配置）、16（轻量模式）、17（属性测试）、18（对照实验数据）。写文件关卡改为"必须持有有效凭证"。
- 改的过程中发现几个新问题，写进了文末待确认问题，最要紧的是：MCP 服务能不能拿到会话 ID（未实测）；RefCov 自己会写记录的命令可能被 AI 在 shell 里调用来伪造"看过"。
- 用户审过第三稿并回复了 6 个问题，据此改成第四稿：保护状态目录和配置的检查出错时拦截；写记录的入口只有 MCP 工具和钩子脚本；申请凭证要报任务；`enforce: false` 开关；记送出的单元数和图片数。
- 用到的 Kiro 功能：规格流程（需求阶段第三轮）。
