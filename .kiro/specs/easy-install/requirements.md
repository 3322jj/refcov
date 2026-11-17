# 需求文档：易用性改造第一层，安装简化（第一稿，2026-11-17）

EN summary: Requirements for the first layer of the usability plan. RefCov installs as a package without a source clone; `refcov init` writes the Kiro MCP entry and five hooks with absolute paths and never overwrites valid configuration; a read-only `refcov doctor` reports each configuration problem with a fix; `init` is user-only under the protection checks; the template example that pointed at videos is corrected; and acceptance is tested in a temporary directory and a clean virtual environment. The second layer (natural-language source management) is outside this document.

状态：**第二稿，2026-11-17。** 依据 `docs/易用性改造方案.md` 第 2 节（用户 2026-11-17 指示做第一层）。第 3 节的第二层不在本文档。设计写在 `design.md`。第一稿经 Claude 检查点 3 审过，方向同意；第二稿按审阅意见改，改完直接实现。第二稿改动的条目：2.6、3.3、3.6、5.2、5.10、6.2 至 6.8、8.1 至 8.6，以及"已定和还没定的"。

文字出处（未登记，待转换）：`docs/易用性改造方案.md`（没有登记为参考源，所以没有单元 ID；登记以后改成 `[ref:…]`）、`docs/简化上手设计.md`（上一版设计，已实现）、用户在聊天里的指示（2026-11-17，还没有存成 `docs/decisions/` 下的文件，等用户过目以后再转换）、`.kiro/steering/tech.md`（钩子脚本、Windows 编码和持续集成的规定）。Kiro 文档的单元和 2026-11-10 的决定已登记，出处写成 `[ref:…]`。

## 简介

现在装 RefCov 要克隆仓库、留着克隆目录、运行安装脚本、手改配置。这一层把安装改成两步：装包，然后在仓库根目录运行 `refcov init`。`refcov doctor` 只读地检查装得对不对，并给每个问题写出修法（方案第 1、2 节）。

## 术语

- **解释器的绝对路径**：运行 `init` 的那个 Python 的完整路径（`sys.executable`）。写进配置的命令都用它，不用 PATH 上的 `python`。
- **钩子**：`.kiro/hooks/` 下的 5 个 JSON 文件，Kiro 在对应事件时运行它们。
- **只能由用户运行**（USER_ONLY）：AI 在 shell 里运行会被保护检查拦下的子命令。`init` 加入这一组。
- **只读**：命令运行前后，仓库里每个文件的存在与否和内容都不变。不建 `.refcov/`，不写日志，不拿锁。
- **模板**：`integrations/kiro/hooks/` 下的 5 个 JSON 文件。它们随包安装，`init` 复制它们。

## 第一部分：安装

### 需求 1：随包安装，不留克隆
EN: Install as a package, without keeping a clone

**用户故事：** 作为想用 RefCov 的开发者，我想用一条命令装好，不用留着仓库克隆，以便装完就能在任何项目里用。
EN: As a developer who wants to use RefCov, I want to install it with one command and keep no clone, so that I can use it in any project once it is installed.

#### 验收标准

1. THE 安装包 SHALL 包含接入层的钩子脚本（`integrations/kiro/hook.py`）和 `integrations/kiro/hooks/` 下的 5 个模板。装好以后，这些文件从安装包里找到，不依赖克隆目录。
2. THE 安装包 SHALL NOT 包含 `apps/`、`site/`、`tests/`、`docs/` 和 `.kiro/`。应用的依赖（ffmpeg、geopandas）不进安装包。
3. THE 安装包的运行时依赖 SHALL 只有 `mcp` 及它的依赖。核心层和接入层只用标准库。
4. WHEN 在没有克隆的 Windows 机器上运行 `uv tool install git+https://github.com/3322jj/refcov@phase2-haiku`（合并到 main 以后用 `main`），THE 安装 SHALL 完成，`refcov --version` SHALL 可用。这一条由用户在推送以后验收（需求 8.4）。

出处：文字出处 `docs/易用性改造方案.md` 第 2 节（未登记，待转换）；`.kiro/steering/tech.md`（核心层只用标准库，只有 MCP 模块依赖 `mcp`）

## 第二部分：init

### 需求 2：`refcov init` 写 Kiro 的配置和钩子
EN: `refcov init` writes the Kiro MCP entry and the five hooks

**用户故事：** 作为用户，我想在仓库根目录运行一条命令，就写好 MCP 配置、5 个钩子和配置模板，以便不用手改文件。
EN: As a user, I want one command in the repository root to write the MCP entry, the five hooks and the configuration template, so that I do not edit files by hand.

#### 验收标准

1. WHEN 用户在仓库根目录（当前目录有 `.git`）运行 `refcov init`，THE 命令 SHALL 写 `.kiro/settings/mcp.json` 里的 `mcpServers.refcov` 一项，并写 `.kiro/hooks/` 下的 5 个钩子文件：`refcov-post-mcp.json`、`refcov-prompt.json`、`refcov-pre-write.json`、`refcov-pre-shell.json`、`refcov-pretask.json`。
2. THE 命令写进去的命令 SHALL 用绝对路径。解释器用 `sys.executable`，仓库根用完整路径。钩子命令的形式是 `"<解释器>" -P -m integrations.kiro.hook --root "<仓库根>" <事件>`。MCP 项的 `command` 是解释器的绝对路径，`args` 是 `["-P", "-m", "refcov_mcp", "--root", "<仓库根>"]`。`-P` 的理由见设计第 2.2 节。
3. WHEN 要写钩子时，THE 命令 SHALL 先在仓库根目录里用子进程确认这个解释器能找到 `integrations.kiro.hook`（只做查找，不导入用户仓库里的任何东西）。找不到就一个钩子都不写，并说明要先用同一个解释器装好 RefCov。原因：找不到模块时，钩子的退出码是 1，既不拦也不报给 Kiro，保护会无声失效。
4. THE 命令 SHALL NOT 创建、修改或删除 `.refcov/` 下的任何文件。
5. IF 当前目录没有 `.git`，THE 命令 SHALL 不写任何文件，并说明要在仓库根目录运行。
6. IF 接入层导入不了（例如 RefCov 装在别的解释器里），THE 命令 SHALL 说明"接入层没装上，用同一个解释器重新安装 RefCov"，以退出码 2 结束，不写任何文件。`refcov/cli.py` SHALL 只导入 `integrations/commands.py`，由它去导入接入层（设计第 4.1 节）。

出处：文字出处 `docs/易用性改造方案.md` 第 2 节（未登记，待转换）；[ref:kiro-hooks/Hook-file-schema]（钩子文件的格式：`hooks` 数组里每一项的 `action.command`）；[ref:kiro-hooks/File-naming-and-location]（钩子放在仓库的 `.kiro/hooks/`）

### 需求 3：不覆盖已有的有效配置
EN: Existing valid configuration is never overwritten

**用户故事：** 作为用户，我想让 `init` 可以放心地再运行一次，以便它不会抹掉我已经改过的配置。
EN: As a user, I want `init` to be safe to run again, so that it does not erase configuration I have already changed.

#### 验收标准

1. IF `.kiro/settings/mcp.json` 是合法的 JSON 对象，THE 命令 SHALL 只添加 `mcpServers.refcov` 一项，其他服务器的配置不变。已有 `refcov` 项时 SHALL 不覆盖，`--force` 除外。
2. IF `.kiro/settings/mcp.json` 不是合法的 JSON 对象，THE 命令 SHALL 不改这个文件，并打印要手工加入的内容。
3. IF 同名钩子文件已存在，THE 命令 SHALL 不覆盖它，`--force` 除外。`--force` 的范围是：`mcpServers.refcov` 的 `command` 和 `args`；这 5 个钩子文件。
4. THE `refcov.toml` SHALL 只在不存在时写模板。它存在时，不论内容如何，`--force` 也不改它。
5. WHEN 不带 `--force` 运行第二次，THE 命令 SHALL 不改任何已存在的文件（逐字节相同）。
6. WHEN 用 `--force` 替换 `mcpServers.refcov` 时，THE 命令 SHALL 只换 `command` 和 `args`，该项的其他键（例如 `autoApprove`、`env`、`disabled`）保留。`init` 不改 `disabled`；`disabled` 为真时由 `doctor` 报问题（需求 5.2）。

出处：文字出处 `docs/易用性改造方案.md` 第 2 节（未登记，待转换）；`docs/简化上手设计.md` 第 2.2 节（未登记，待转换）

### 需求 4：`setup.py` 作为兼容入口
EN: `setup.py` stays as a compatibility entry

**用户故事：** 作为已经在用旧步骤的人，我想让 `setup.py` 继续能运行，并且和 `refcov init` 做同样的事，以便旧步骤不会坏掉，也不会有第二套写法。
EN: As someone already following the old steps, I want `setup.py` to keep working and do the same as `refcov init`, so that old steps do not break and there is no second way to write.

#### 验收标准

1. THE `integrations/kiro/setup.py` SHALL 调用和 `refcov init` 同一段代码，产生同样的文件，`--force` 的范围也一样。
2. THE `setup.py` 写出的钩子和 MCP 配置 SHALL NOT 指向克隆目录。它们用安装好的包。
3. THE `setup.py` SHALL 要求先装好包：没装时不写钩子（需求 2.3 同样适用）。旧的做法（只用克隆、不装包）因此不再能写出可用的钩子，这是有意的。
4. THE `setup.py` SHALL 受需求 6 的保护：AI 用 Python 运行它会被拦。

出处：文字出处 `docs/简化上手设计.md` 第 0 节第 8 条（未登记，待转换）；`docs/易用性改造方案.md` 第 2 节（未登记，待转换）。"保留并调用 `init`"的办法在设计第 2.1 节，等 Claude 审。

## 第三部分：doctor

### 需求 5：`refcov doctor`，只读，逐项给出修法
EN: `refcov doctor` is read-only and gives a fix for each problem

**用户故事：** 作为用户，我想运行一条只读的检查，看出装得对不对、哪里要改，以便不用逐个文件去查。
EN: As a user, I want one read-only check that shows whether the installation is right and what to change, so that I do not inspect each file by hand.

#### 验收标准

1. THE `refcov doctor` SHALL 只读。运行前后，仓库里每个文件的存在与否和字节都相同；它不建 `.refcov/`，不拿锁，不写日志。
2. THE doctor SHALL 检查 MCP 配置：文件存在，是合法 JSON，有 `mcpServers.refcov`，`command` 是存在的绝对路径，`args` 里的 `--root` 指向当前仓库根，并且这个解释器能找到 `refcov_mcp`（设计第 5.2 节）。`disabled` 为真时报问题；修法是手工把它改成假，`init` 不改这一项。
3. THE doctor SHALL 检查 5 个钩子：5 个文件都在，每个是合法 JSON；命令的解释器是存在的绝对路径；这个解释器能找到 `integrations.kiro.hook`；`--root` 指向当前仓库根；文件名和事件名对应。没有 `--root` 的命令也要报告，因为它靠脚本自己的位置算根。
4. THE doctor SHALL 检查配置文件 `refcov.toml`：存在，能解析（语法错要报出行号），并报出配置问题（沿用报告里的配置问题）。
5. THE doctor SHALL 报告已登记的参考源（每个源的 ID 和单元数），和待同步的情况：匹配到但没登记的文件，内容变了但没同步的文件。
6. THE doctor SHALL 报告 Kiro 的权限设置，但只报告、不判断对错：用户级权限文件 `~/.kiro/settings/permissions.yaml` 在不在。这一项第二层才用。
7. THE doctor 的每个问题 SHALL 给出修法，修法是用户能照着做的一步（例如"在仓库根目录运行 `refcov init --force`"）。提示不算问题，不影响退出码。
8. THE doctor 的退出码 SHALL 是：0 没有问题；1 有问题；2 不能检查（例如不在仓库根目录）。
9. THE doctor SHALL NOT 列入 USER_ONLY。AI 可以运行它。
10. THE doctor SHALL 比较路径时用 `os.path.normcase(os.path.realpath(...))`：Windows 上不分大小写，路径里有中文和空格时结果一样。

出处：[ref:kiro-hooks/Hook-file-schema]；[ref:kiro-hooks/File-naming-and-location]；[ref:kiro-permissions/Defining-rules]（用户级权限文件的位置）；文字出处 `docs/易用性改造方案.md` 第 2 节（未登记，待转换）

## 第四部分：保护和模板

### 需求 6：`init` 和 `setup.py` 只能由用户运行
EN: `init` and `setup.py` can be run only by the user

**用户故事：** 作为用户，我想让 AI 不能自己替我写 Kiro 的配置和钩子，以便这些写入只在我的终端里发生。
EN: As a user, I want the AI unable to write Kiro configuration and hooks on its own, so that these writes happen only in my terminal.

#### 验收标准

1. THE `init` SHALL 加进 USER_ONLY，和 `add`、`confirm`、`sync` 同样处理。`refcov/cli.py` 和 `integrations/kiro/hook.py` 两处都改，`tests/test_protect.py` 里的期望同步改为 `("add", "confirm", "sync", "init")`。
2. WHEN AI 在 shell 里运行 `refcov init`、`sync`、`add` 或 `confirm`，包括带完整路径、带引号、带 `.exe` 的写法（例如 `C:\…\refcov.exe sync` 和 `& "C:\…\refcov.exe" add x.md --id a`），保护检查 SHALL 拦下：退出码 2，原因写 stderr。
3. WHEN AI 用 Python 运行 `integrations/kiro/setup.py`（解释器名后面允许一个引号，例如 `"D:\pyth\python.exe" "…\setup.py"`），或用 `-m integrations.kiro.setup`、`-m integrations.kiro.init` 运行，保护检查 SHALL 拦下。只写一个路径（例如 `git add integrations/kiro/setup.py`）SHALL NOT 被拦。
4. WHEN 命令文本里有 `-m integrations.kiro.hook`，或用 Python 运行 `hook.py`（解释器名后面允许一个引号，例如 `"D:\pyth\python.exe" "…\hook.py" --root "D:\x" pre-shell`），保护检查 SHALL 拦下。
5. THE `doctor` SHALL NOT 被拦（需求 5.9），包括 `"C:\…\refcov.exe" doctor`。
6. THE 文档 SHALL 写明：这是文本匹配，换写法能绕过；RefCov 的写文件保护不拦写 `.kiro/hooks/` 和 `.kiro/settings/mcp.json`。写 `.kiro/hooks/` 时 Kiro 要求每次确认（骨架设计里有这一条），`tests/test_protect.py` 的 `test_ordinary_writes_are_allowed` 也是这个期望。
7. THE 钩子模板 `refcov-pre-shell.json` 的 `description` SHALL 列出 `add`、`confirm`、`sync`、`init` 和安装脚本；只改说明，不改 `command`。
8. THE 测试 SHALL 覆盖：上面第 2、3、4 条的完整路径写法都被拦；init 实际写出的 5 条钩子命令和 MCP 那一行（拼成命令行）在 shell 文本里都被拦；`refcov doctor`、`"C:\…\refcov.exe" doctor`、`git add integrations/kiro/setup.py` 放行。

出处：[ref:dec-design-review/1-shell-里拦-init，放行-add]（shell 里运行 `refcov init` 一律拦；该条里登记命令放行的部分已被后来的决定替代，见 `docs/简化上手设计.md` 第 6 节）；文字出处 `docs/易用性改造方案.md` 第 2 节（未登记，待转换）

### 需求 7：配置模板的示例修正
EN: Correct the template example that pointed at videos

**用户故事：** 作为用户，我想让生成的配置模板里的示例照着用不会出错，以便视频不会被当成 Markdown 登记而失败。
EN: As a user, I want the example in the generated template to be correct when I follow it, so that a video is never registered as Markdown and fails.

#### 验收标准

1. THE 模板 SHALL NOT 含 `*.mp4` 的示例。
2. THE 模板的注释 SHALL 写明：登记只收 Markdown，视频不能直接登记；要先用镜头应用的 `detect` 生成清单 `<视频>.shots.md`（默认放在视频旁边，视频在仓库外时放在仓库根目录），再登记清单。注释 SHALL 指向 `apps/shot-coverage/README.md`，那里写着声明适配器的方法。
3. THE 模板里的示例 SHALL 写成 `[sources.shot]` 下的 `files = ["videos/*.shots.md"]`，并且是注释状态（模板里的其他示例也是注释）。
4. THE 测试 SHALL 检查模板里没有 `*.mp4`，并且注释里有 `detect`。

出处：文字出处 `docs/易用性改造方案.md` 第 2 节（未登记，待转换）；`apps/shot-coverage/README.md`（生成清单和登记的写法，未登记，待转换）；`apps/shot-coverage/cli.py` 第 65–68 行（默认输出位置）

### 需求 8：验收，以及怎么测
EN: Acceptance, and how to test it

**用户故事：** 作为维护者，我想有一套可以重复跑的验收步骤，以便确认安装真的能用，而不只是测试通过。
EN: As a maintainer, I want repeatable acceptance steps that show the installation works, not only that the tests pass.

#### 验收标准

1. THE 验收 SHALL 包含一个默认跳过的测试（设 `REFCOV_CLEAN_INSTALL=1` 才跑，只在临时目录里做）：从提交的内容（`git archive HEAD`）打 wheel，用 `uv tool install` 装到临时的 `UV_TOOL_DIR` 和 `UV_TOOL_BIN_DIR`（找不到 uv 时退回 venv 加 pip）；证明 `refcov` 和钩子模块都从临时安装里导入，不从克隆导入；在临时项目里 `init` 和 `doctor` 都成功。
2. THE 验收 SHALL 包含：`init` 第二次运行以后，写过的文件逐字节不变；已有合法配置时不覆盖（需求 3）。
3. THE 验收 SHALL 包含：`doctor` 能发现这些人为制造的问题：缺一个钩子文件，钩子的 `--root` 指向别的目录，解释器路径不存在，配置文件有语法错，有待同步的文件。每个问题都有修法。
4. THE 用户验收 SHALL 在推送以后、在没有克隆的 Windows 机器上做，并满足三点：(a) 合并到 main 以前，地址用 `git+https://github.com/3322jj/refcov@phase2-haiku`，合并以后用 `main`；(b) 装完找不到 `refcov` 时，运行 `uv tool update-shell`，再开一个新终端（README 也写这一步）；(c) 不能只看 `doctor` 的退出码 0：在 Kiro 里打开那个项目，发一条消息能看到状态行；再让 Kiro 写 `.refcov/` 下的文件，应当被拦。只有这样才证明钩子在 Kiro 里真的跑起来了（设计第 10 节前两项）。
5. THE 测试 SHALL 检查 wheel 的内容：有 `integrations/__init__.py`、`integrations/kiro/hook.py` 和 5 个模板，没有 `apps/`、`site/`、`tests/`、`docs/`；并且 init 写出的 `refcov-pre-write.json` 里的命令原样用 shell 跑一次，喂一个写 `.refcov/x` 的输入，退出码 SHALL 是 2。
6. THE 测试命令和测试的性质 SHALL 写在设计第 7 节。

出处：文字出处 `docs/易用性改造方案.md` 第 2 节（验收，未登记，待转换）；`.kiro/steering/tech.md`（CI 在 Linux 和 Windows 上跑测试）

## 已定和还没定的

- 已定（用户 2026-11-17 指示）：做第一层，安装简化。第二层（自然语言管理资料）不在本文档。第 0 步的实测由用户在 Kiro 里做，不改仓库。
- 已定（Claude 审过第一稿，2026-11-17；见 `design.md` 第 2 节）：
  - `setup.py` 保留，并调用 `init`（需求 4）；
  - 钩子命令用模块形式，并加 `-P`，不加控制台入口（需求 2.2）；
  - 包的位置留在 `integrations/`，不改名为 `refcov_kiro/`（设计第 2.3 节）。
- 等用户决定：
  - 登记 `docs/易用性改造方案.md` 为参考源：用户 2026-11-17 决定先不登记，出处保持文字（严格模式下未转换不拦）；
  - 演示页第 7 段（已上线）的装法，等第一层验收完再和另外两处多余空白一起安排（需求 4，以及演示页需求 7.3–7.4）。本轮不改页面；
  - 聊天指示起草成 `docs/decisions/` 下的文件，给用户过目后再存（用户 2026-11-17 同意起草）。
- 范围冻结：这一步是用户 2026-11-17 指示的任务，按例外办理，DEVLOG 同日条目记下。
