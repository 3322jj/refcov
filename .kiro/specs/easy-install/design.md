# 设计文档：易用性改造第一层，安装简化（第一稿，2026-11-17）

依据：`requirements.md` 第一稿；`docs/易用性改造方案.md` 第 2 节；`docs/简化上手设计.md`（上一版，已实现）。读过的代码：`integrations/kiro/setup.py`、`integrations/kiro/hook.py`、`refcov/cli.py`、`refcov/store.py`、`refcov/api.py`（`plan_sync` 只读）、`tests/test_protect.py`、`tests/test_core_names.py`、`tests/test_setup_kiro.py`。Kiro 文档单元 `kiro-hooks/Hook-file-schema`、`kiro-hooks/File-naming-and-location`、`kiro-permissions/Defining-rules`，以及 `dec-design-review/1-shell-里拦-init，放行-add`，都经 MCP 的 `read_unit` 读过。

状态：第一稿，检查点 3。第 2 节的几处决定等 Claude 审，审过以前不写代码。第 1、4、5、6 节里"读代码得出"的结论还没有实测，第 10 节列出要实测的项。

## 1. 现状和要改的地方

| 项 | 现在（读代码得出） | 这一层要做的 |
|---|---|---|
| 安装 | 要克隆仓库，`pip install -e`（README Setup 第 1 步） | 用 `uv tool install git+…` 装，不留克隆 |
| 包的内容 | `pyproject.toml` 的 `packages.find` 只含 `refcov*`、`refcov_mcp*`，`integrations/kiro/` 不在包里 | 接入层和 5 个模板进包 |
| 写 Kiro 配置 | `integrations/kiro/setup.py` 只用标准库、不导入 `refcov`；写进去的钩子命令指向克隆里的钩子脚本，所以克隆不能挪 | 新的 `refcov init`；钩子命令改用包里的模块 |
| 钩子模板 | 模板命令是 `python integrations/kiro/hook.py <事件>`（相对路径）；setup 把前缀换成绝对路径和 `--root` | 前缀换成 `"<解释器>" -P -m integrations.kiro.hook --root "<仓库根>"`（第 2.4 节） |
| 检查 | 没有 `doctor`；`report` 和 `check` 不检查 Kiro 配置 | 新的只读 `refcov doctor` |
| 保护 | `USER_ONLY = ("add", "confirm", "sync")`，`refcov/cli.py` 和钩子脚本各一份，测试比对两份 | 加 `init`；加三条新规则（第 6 节） |
| 模板示例 | 注释里 `files = ["videos/*.mp4"]` | 第 4.4 节 |

保留不变：MCP 配置和钩子写解释器的绝对路径（避免 Windows 上找不到 `python`）；只补装不覆盖；`--force` 只动 MCP 的 `refcov` 项和 5 个钩子；配置文件 `refcov.toml` 永不覆盖。

## 2. 等 Claude 审的决定

### 2.1 `setup.py`：保留，调用 `init`（建议）
- 办法：`integrations/kiro/setup.py` 缩成几行。它把克隆根放进 `sys.path`（只为导入包），然后调用 `integrations.kiro.init` 的 `run`。输出和 `init` 一样。
- 不选删掉：README 第 2 步和演示页第 7 段（已上线）都写着运行它。删了，两处都要改，改已上线的页面要用户同意。
- 不选保留旧代码：两份写法会分叉。现在 `USER_ONLY` 和模板改写逻辑已经在两个文件里各有一份，就是这样来的。
- 它会写配置和钩子，所以和 `init` 一样受保护（需求 6.3）。旧的做法（只用克隆、不装包）从此写不出可用的钩子，这是有意的（需求 4.3）。

### 2.2 钩子命令：模块形式，加 `-P`（建议）
- 形式：`"<解释器>" -P -m integrations.kiro.hook --root "<仓库根>" <事件>`。MCP 项同理，`args` 为 `["-P", "-m", "refcov_mcp", "--root", "<仓库根>"]`。
- 为什么加 `-P`：`python -m` 把当前目录放在 `sys.path` 最前面。已实测：在临时目录里运行 `python -m site`，第一项是那个目录；加 `-P` 后第一项是标准库的 zip。钩子和 MCP 服务在用户仓库里运行，不加 `-P` 时，用户仓库里的同名包会先被导入。`-P` 从 Python 3.11 起有，项目要求 3.11 以上。
- 替代：加一个控制台入口（如 `refcov-kiro-hook`）。要改 `[project.scripts]`，可执行文件的路径要在虚拟环境的 Scripts 目录里算。模块形式和现在 MCP 那一项的写法一样，少一个要维护的入口。选模块形式。
- 老的 MCP 配置（不带 `-P`）不算问题。doctor 不检查 `-P`。

### 2.3 包的位置：留在 `integrations/`（建议）
- 做法：`integrations/` 和 `integrations/kiro/` 各加一个空的 `__init__.py`；`pyproject.toml` 的 `include` 加 `integrations*`；`package-data` 加 `integrations.kiro` 的 `hooks/*.json`。
- 替代：改名为 `refcov_kiro/`。名字更清楚，但仓库自己的 `.kiro/hooks/*.json`（用户的文件，只能由用户改）写的是 `python integrations/kiro/hook.py`，测试里约 47 处把这个路径当字符串用。改名要留转发壳，或者让用户改钩子。本步不做，记进"以后再做"。
- 风险：顶层名 `integrations` 比较泛。装在 uv 的工具虚拟环境里时只有 `refcov` 和它的依赖，目前没有冲突。

### 2.4 钩子模板：不改（建议）
- `integrations/kiro/hooks/*.json` 保持 `python integrations/kiro/hook.py <事件>`；`init` 只换前缀。
- 理由：`test_hook.py`、`test_pretask.py`、`test_protect.py` 直接比对模板的命令字符串（共 5 处断言），不改就不动它们。
- 替代：模板改成模块形式。`init` 就不用改写，但要改那 5 处断言。

## 3. 打包（需求 1）
- `pyproject.toml`：

```toml
[tool.setuptools.packages.find]
include = ["refcov*", "refcov_mcp*", "integrations*"]

[tool.setuptools.package-data]
"integrations.kiro" = ["hooks/*.json"]
```

- 依赖不变（`mcp>=1.28,<2`）。接入层的 `init` 只用标准库；核心层的 doctor 部分用 `tomllib`（标准库，3.11 起有）。
- 不进包：`apps/`、`site/`、`tests/`、`docs/`、`.kiro/`、`.github/`。`integrations/kiro/refcov.example.toml` 不在 `package-data` 里，只是给人看的示例。
- 检查方法见第 7.2 节：导出仓库内容后打包，用 `python -m zipfile -l` 看里面的文件。

## 4. `refcov init`（需求 2、3、4、7）

### 4.1 入口和层次
- `refcov/cli.py` 加子命令 `init`（带 `--force`）。它只分派：延迟导入 `integrations.kiro.init`，调用 `run(repo, force)`。核心模块不导入接入层。
- `tests/test_core_names.py` 扫描 `refcov/` 和 `refcov_mcp/` 的源码和注释，`.kiro` 之类的字样不许出现。帮助文字里不写 `.kiro`。

### 4.2 写什么

| 文件 | 行为 |
|---|---|
| `.kiro/settings/mcp.json` | 不存在则新建。存在且合法，只添加（`--force` 时替换）`mcpServers.refcov`，其他项不动；内容不变，但缩进可能统一成两格。不合法则不改，打印要粘贴的内容。`command` 是 `sys.executable`，`args` 是 `["-P", "-m", "refcov_mcp", "--root", <仓库根>]`，`disabled` 为假。 |
| `.kiro/hooks/refcov-*.json`（5 个） | 从包里的模板复制，只替换 `action.command` 的前缀 `python integrations/kiro/hook.py` 为 `"<sys.executable>" -P -m integrations.kiro.hook --root "<仓库根>"`，事件名留在后面。同名不覆盖；`--force` 只覆盖这 5 个。 |
| 配置文件 `refcov.toml` | 不存在则写模板（第 4.4 节）。存在则不动，`--force` 也不动。 |

- 仓库根是当前目录，要有 `.git`（和现在的命令一样）。不碰 `.refcov/`。
- 写钩子之前（需求 2.3）：在仓库根目录里运行子进程 `sys.executable -P -B -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('integrations.kiro.hook') else 1)"`。`-P` 不把当前目录放进路径，所以只能找到安装的包；`-B` 不写字节码。这和钩子实际运行的条件一样。找不到就一个钩子都不写。
- 路径里有空格时，整个命令用双引号括起来。路径里有双引号时直接报错，不转义。

### 4.3 输出
- 每个文件一行：写了；跳过（已存在，附原因）；没改（不合法，附要粘贴的内容）。
- 最后一行写下一步：在配置文件的 `[sources]` 里写要读的材料；运行同步命令；在 Kiro 里确认 `refcov` MCP 已连上（`refcov doctor` 能查 MCP 配置）。方案第 2 节说"重连"可能不需要，要实测，所以这里不写死。

### 4.4 模板的注释（需求 7）
注释改成下面的内容，示例保持注释状态：

```
# 登记只收 Markdown，视频不能直接登记。要先用镜头应用生成清单：
# 在 RefCov 仓库的 apps/shot-coverage 里运行 detect，生成 <视频>.shots.md（默认放在视频旁边）。
# 声明适配器和登记清单的写法见 apps/shot-coverage/README.md。
# [adapters]
# shot = "apps/shot-coverage/adapter.py"
#
# [sources.shot]
# files = ["videos/*.shots.md"]
```

- 实际限制（写进第 9 节）：适配器的路径要在用户仓库里（`refcov.example.toml` 的注释写明）。镜头应用不在安装包里，要用它的人要自己拿到它的代码，还要装 ffmpeg。注释不假装这些已经解决。

### 4.5 `setup.py`（需求 4）
缩成：把克隆根放进 `sys.path`，导入 `integrations.kiro.init`，调用 `run`，结束时打印一行"可以改用 init 命令"。`--force` 原样传下去。

## 5. `refcov doctor`（需求 5）

### 5.1 结构和只读
- 核心部分：`refcov/api.py` 新增 `doctor_core(store)`，只读。检查配置文件能否解析和配置问题（复用报告里的配置问题）、已登记参考源（manifest 里的 ID 和单元数）、待同步（复用 `plan_sync`，它的文档字符串写明只读，实现时用测试确认）。
- 接入层部分：`integrations/kiro/doctor.py` 的 `run(repo)`，检查 MCP 配置和 5 个钩子，并报告权限文件。`refcov/cli.py` 先跑核心部分，再跑接入层部分，按节打印。
- `Store(root)` 构造时不建目录（`ensure_state_dir()` 才建），所以 doctor 可以用它。不要调用 `ensure_state_dir`，不拿 `log.lock`，不调用写入的方法。
- 探测解释器用子进程，带 `-P -B`，只做查找，不运行钩子或 MCP 服务。注意 `find_spec` 对带点的名字会先导入父包（`integrations`），所以它会运行安装包里的 `integrations/__init__.py`。这个文件是空的，不写东西。

### 5.2 检查项

| 节 | 检查 | 是问题的情况 | 修法 |
|---|---|---|---|
| MCP 配置 | 文件存在、合法 JSON、有 `mcpServers.refcov` | 任一不满足 | 在仓库根目录运行 `init`；不合法时先改好 JSON，或删掉它再运行 |
| MCP 配置 | `command` 是存在的绝对路径 | 相对路径，或文件不存在 | `init --force`（用当前安装的解释器重写） |
| MCP 配置 | `--root` 等于当前仓库根 | 不等 | `init --force` |
| MCP 配置 | 解释器能找到 `refcov_mcp`（子进程探测） | 找不到 | 用装了 RefCov 的解释器运行 `init --force` |
| 钩子 | 5 个文件都在，每个是合法 JSON | 缺一个，或不合法 | `init`（缺的会补，已有的不覆盖） |
| 钩子 | 命令的解释器是存在的绝对路径 | 相对路径（例如只写 `python`），或文件不存在 | `init --force` |
| 钩子 | 解释器能找到 `integrations.kiro.hook`（同一个探测） | 找不到 | 同 MCP 那一条 |
| 钩子 | 命令里有 `--root`，且等于当前仓库根 | 没有，或不等 | `init --force` |
| 钩子 | 文件名和事件名对应（`refcov-pre-write.json` 对应 `pre-write`） | 不对应 | `init --force` |
| 配置文件 | 存在；能用 `tomllib` 解析 | 不存在；语法错（报出行号） | 不存在则 `init` 写模板；语法错则改掉 |
| 配置文件 | 配置问题 | 有 | 按提示改（由用户改） |
| 参考源 | 每个源的 ID 和单元数；有没有登记 | 没有登记（只是提示） | 在 `[sources]` 写文件，再运行同步命令 |
| 待同步 | 匹配到但没登记的文件；内容变了但没同步的文件 | 有 | 运行同步命令 |
| Kiro 权限 | `~/.kiro/settings/permissions.yaml` 在不在 | 从不算问题 | 第二层才用 |

- 表里的"`init`"指 `refcov init`，"同步命令"指 `refcov sync`。
- 本仓库自己的钩子是相对路径、没有 `--root`，doctor 会报它们有问题。这是事实。钩子是用户的文件，这一步不改它。
- 退出码：0 没有问题；1 有问题；2 不能检查（不在仓库根目录，或没有 `.git`）。提示不影响退出码。

## 6. 保护（需求 6）
- `USER_ONLY = ("add", "confirm", "sync", "init")`，`refcov/cli.py` 和钩子脚本两处一致。`tests/test_protect.py::test_user_only_matches_core` 的期望同步改。
- `SHELL_RULES` 增加三条。每条都要求前面有命令，只写一个路径不拦：
  - `-m\s+integrations\.kiro\.hook\b`：原因"命令在运行钩子脚本"，和现有的 `hook.py` 规则并列；
  - `python3?(\.exe)?(\s+-\S+)*\s+["']?\S*integrations[\\/]kiro[\\/]setup\.py\b`：原因"命令在运行 Kiro 安装脚本"；
  - `-m\s+integrations\.kiro\.(setup|init)\b`：原因同上。
- 必须放行的样例（测试里要有）：`refcov doctor`；`python -m refcov check …`；`git add integrations/kiro/hook.py`；`git add integrations/kiro/setup.py`；`git add integrations/kiro/hooks/refcov-pre-shell.json`。
- 出错的规则不变：`pre-write`、`pre-shell` 出错就拦（需求 14.5）。但解释器找不到模块时，钩子在 Python 启动阶段就失败，退出码是 1，既不拦也不报给 Kiro。这是 `init`（需求 2.3）和 `doctor` 要防的情况。
- `hook.py` 的 `sys.path` 处理要改。现在 `ROOT`（`--root` 给的用户仓库）会被放进 `sys.path` 最前面，在 `main()` 和几个分支里都有。改成：`ROOT` 仍由 `--root` 决定（状态目录和配置在哪）；`sys.path` 只放代码自己的上级目录 `Path(__file__).resolve().parents[2]`，且只在它不在 `sys.path` 里时放。装了包时它已在里面，不放；克隆里运行时要放。
- 改 `hook.py` 会立即改变本仓库正在用的保护，因为代码每次运行都重新读。所以先在测试里跑通，再提交。

## 7. 测试和验收（需求 8）

### 7.1 测试（pytest；性质写在 docstring；Hypothesis 生成输入）
- `tests/test_init_kiro.py`（新）：
  - 性质 I1：`init` 连续运行两次，第二次之后写过的文件逐字节不变。输入：随机的已有 MCP 配置，合法的、不合法的、缺字段的都有。
  - 性质 I2：配置文件的内容在任何参数下都不变，`--force` 也不变。输入：随机的已有内容。
  - 性质 I3：合法 MCP 配置里的其他服务器，`init` 之后仍然在。输入：随机的服务器表。
  - 固定例子：不在仓库根目录时不写文件；不碰 `.refcov/`；前缀替换只换前缀，不以模板前缀开头的命令原样保留。

- `tests/test_doctor.py`（新）：
  - 性质 D1：doctor 只读。输入：随机的仓库状态（缺文件、坏 JSON、有或没有 `.refcov/`）。运行前后文件树和字节相同，且没有新建 `.refcov/`。
  - 第 7.2 节第 7 条的五种问题各一个固定例子，每个都报出来，并有修法。
  - 干净的 `init` 以后，doctor 退出码为 0。
- `tests/test_setup_kiro.py`（改）：`setup.py` 的结果和 `init` 一样；`--force` 范围一样；没装包时不写钩子。
- `tests/test_protect.py`（改）：`USER_ONLY` 的期望；第 6 节的三条新规则和放行样例。
- `tests/test_packaging.py`（新）：用 `tomllib` 读 `pyproject.toml`，检查 `include` 含 `integrations*`，`package-data` 含 `hooks/*.json`，模板的 5 个文件都在。不在测试里打 wheel（慢，也可能要网络），打包放到 7.2 节的人工验收。
- `tests/test_core_names.py`：现有测试，新的核心代码要通过。

### 7.2 干净环境的验收（实现后、推送前，在临时目录里做）
本机没有 `uv`（2026-11-17 确认），所以用 `venv` 和 `pip`：
1. 导出已提交的内容：`git archive --format=zip -o <临时>\rc.zip HEAD`，解压到 `<临时>\src`。只有已提交的内容会进来。
2. 建虚拟环境：`D:\pyth\python.exe -m venv <临时>\venv`（本机是 3.12.10，满足 3.11 以上）。
3. 安装：`<临时>\venv\Scripts\python.exe -m pip install <临时>\src`。不用 `pip install -e`。
4. 证明不是从克隆导入：在 `<临时>\proj`（一个 `git init` 过的空目录）里运行 `<临时>\venv\Scripts\python.exe -P -c "import refcov, integrations.kiro.hook as h; print(refcov.__file__, h.__file__)"`。两个路径都必须在 `<临时>\venv\Lib\site-packages` 下。
5. 在 `<临时>\proj` 里运行 `<临时>\venv\Scripts\refcov.exe init`，再运行 `refcov.exe doctor`。doctor 应退出码 0（只有"没有登记资料"的提示也是 0）。
6. 再运行一次 `init`，比对写过的文件的哈希，应完全相同。
7. 逐个人为破坏，每次运行 doctor，确认对应的问题被报出来并有修法：删一个钩子文件；把一个钩子的 `--root` 改成别的目录；把 `command` 的解释器改成不存在的路径；配置文件里写一个语法错；加一个匹配到 `[sources]` 的文件，但不运行同步。
8. 推送以后（用户做）：在没有克隆的 Windows 机器上运行 `uv tool install git+https://github.com/3322jj/refcov`，再运行 `refcov init` 和 `refcov doctor`。用户要先装 `uv`。

## 8. 要动的文件（允许清单，实现时逐个确认）

| 文件 | 改什么 |
|---|---|
| `pyproject.toml` | `include` 加 `integrations*`；`package-data` 加 `hooks/*.json` |
| `integrations/__init__.py`、`integrations/kiro/__init__.py`（新，空） | 让 setuptools 认出包 |
| `integrations/kiro/init.py`（新） | 写 MCP 配置、钩子和模板；探测解释器；只用标准库 |
| `integrations/kiro/doctor.py`（新） | 接入层部分的只读检查 |
| `integrations/kiro/setup.py` | 缩成调用 `init.run` 的几行 |
| `integrations/kiro/hook.py` | `USER_ONLY` 加 `init`；三条新规则；`sys.path` 的处理（第 6 节） |
| `refcov/cli.py` | 子命令 `init`、`doctor`（延迟导入接入层）；`USER_ONLY` 加 `init`；帮助文字不写 `.kiro` |
| `refcov/api.py` | `doctor_core(store)`（只读） |
| `tests/test_protect.py`、`tests/test_setup_kiro.py` | `USER_ONLY` 的期望、新规则的样例；`setup.py` 包装后的行为 |
| `tests/test_init_kiro.py`、`tests/test_doctor.py`、`tests/test_packaging.py`（新） | 第 7.1 节 |
| `README.md` 的 Setup 一节 | 改成装包、`init`、`doctor`；删去"留着克隆"的话；写局限（第 9 节）。最后做 |

不动：`.kiro/hooks/*.json` 和 `.kiro/settings/mcp.json`（用户的文件）；配置文件；`.refcov/`；`integrations/kiro/hooks/*.json`（模板，第 2.4 节）；`site/`（演示页，第 10 节）。

## 9. 局限（要写进 README）
- 保护是文本匹配，换写法能绕过（和现在一样）。
- RefCov 的写文件保护不拦写 `.kiro/hooks/` 和 `.kiro/settings/mcp.json`（第 6 节）。
- 安装后，钩子和 MCP 项里的解释器与仓库根都是绝对路径：挪动仓库、换 Python、卸载 RefCov 都会让它们失效。`doctor` 能查出来；修法是 `init --force`，卸载后要先重装。
- 钩子模块找不到时，钩子的退出码是 1，既不拦也不报给 Kiro。`init` 和 `doctor` 的探测是防这一点的。
- 镜头应用不在安装包里，需要 ffmpeg；它的适配器路径要在用户仓库里（第 4.4 节）。

## 10. 没测、实现后要测的
- Kiro 能否运行绝对路径（含空格）的钩子命令。简化上手设计第 4 节也记了这一条。
- `-P -m integrations.kiro.hook` 在 Kiro 的钩子里能否跑通。
- `uv tool install`（本机没有 uv）。
- Linux 上 `init` 和 `doctor` 的路径处理（CI 两个系统都跑）。
- 演示页第 7 段和 README 的装法要跟着改。改已上线的页面要用户同意，`.kiro/specs/demo-page/requirements.md` 的需求 7.3–7.4 也要改。本步不动。

## 11. 和已有决定的关系
- `docs/简化上手设计.md` 第 0 节第 8 条（setup 不做成子命令）被这一版改掉：现在 `init` 是子命令，`setup.py` 变成调用它的包装。上一版的其他决定（`[sources]`、同步、`--force` 的范围）不变。
- 2026-11-10 的决定（`dec-design-review/1-shell-里拦-init，放行-add`）说 shell 里的 init 命令要拦。当时的 init 指清空、重建日志的命令；现在的 init 写配置和钩子。理由不同，拦的结论相同。该条里登记命令放行的部分已被后来的决定替代（`docs/简化上手设计.md` 第 6 节）。
- 范围冻结：这一步按用户 2026-11-17 的指示做，DEVLOG 同日条目记为例外。
