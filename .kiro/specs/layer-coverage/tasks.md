# 实施计划：图层覆盖率应用 `apps/layer-coverage`

EN summary: Implementation tasks for the layer-coverage app, following design.md (2026-11-15 draft, awaiting review). Order: the statistics functions with property tests; the adapter with its import guard and stdlib check; the build script that writes the manifest; the fetch script with count checks; the read-only CLI and English README; a real-data run that writes only the in-repo manifest; the standard-answer script outside the repo; then a stop at checkpoint 2, before any demo run. Each task is its own commit, the full test suite must pass before the next task starts, and a task's ledger row goes into the next commit.

依据：`requirements.md`（第二稿）、`design.md`（2026-11-15 初稿）。`_需求：…_` 写需求编号，"设计 N"指 `design.md` 第 N 节。

规矩：

- 每个任务单独提交。全套测试过了才进下一个任务。
- 改文件和跑测试分开发出，提交和推送也分开发出。
- 每个提交说明的最后一行是 `Kiro-Model: claude-haiku-5.5`。
- 施工账的行在下一次提交里补，那一行写上这件活的提交号。
- 仓库里不放原始数据（6018 条的 GeoJSON）和标准答案。
- 不改核心层。要改就停下，等检查点 3。
- 提交说明里不写保护检查按命令文本匹配的那些子命令名。
- DEVLOG 每件活做完就补记，写英文 `EN:` 行。

- [ ] 1. 统计纯函数和性质测试（`apps/layer-coverage/stats.py`，设计 5）
  - `FieldStats`、`stats_of(values)`：非空数、文字形式、不同取值数、前 5 个、零的条数、类型集合
  - `tests/test_layer_stats.py`：P1 守恒、P2 顺序、P3 排列不变、P4 null 不变、P5 零；另有几个固定例子（`"0.0"`、`""`、`true`、只有 null 的输入）
  - _需求：2_

- [ ] 2. 适配器（`apps/layer-coverage/adapter.py`，设计 4）
  - `name = "layer"`，`kinds` 三种，`split` / `read` / `facts`；单元 ID 通过 `validate_unit_id`
  - 导入守卫（设计 4 最后一条）：顶层只放 import、常量、`KindDecl(...)` 赋值、函数和类定义
  - `tests/test_layer_adapter.py`：拆分的 ID、kind、标题；缺 kind、ID 重复、kind 未知、空段都抛 `ValueError`；`read` 返回正文；不存在的 ID 抛 `KeyError`；`facts` 的数字与统计相同
  - `tests/test_layer_adapter_import.py`：替换 `subprocess`、`urllib`、`socket`、文件哈希，导入必须成功，用时不超过 0.5 秒；`ast` 静态检查顶层语句
  - `tests/test_layer_stdlib.py`：`apps/layer-coverage/*.py` 只 import 标准库；只有 `adapter.py` 可以 import `refcov.sources`；禁止 geopandas、pyproj、shapely、fiona、numpy
  - _需求：2、3、5、6.3_

- [ ] 3. 清单生成（`apps/layer-coverage/build.py`，设计 2.1、3、7）
  - 读 GeoJSON（CRS 检查、几何类型检查）；读字典网址并算 sha256；解析 Attribute 表（`<br>` 别名）；按 2.1 节对应数据键，对不上就退出码 1
  - 渲染清单：`crs`、`extent`（含"数据来源"行，GLOBALID 写在这里）、15 个字段节；原子写入 `--out`；输出确定
  - `tests/test_layer_build.py`：假 GeoJSON 和假字典表；两次生成的字节相同；对不上、CRS 不对都退出码 1；字典有而数据没有的字段写进范围节
  - _需求：2、3_

- [ ] 4. 下载（`apps/layer-coverage/fetch.py`，设计 6）
  - `--out` 和 `--check`；分页（`$order=:id`，`$limit=50000`）；超时 60 秒；网络错误和 5xx 重试 3 次
  - 核对总条数和每个 `feature_code` 的条数；不一致不写文件；`--out` 在仓库里时退出码 2
  - `tests/test_layer_fetch.py`：注入假的 `fetch_json`，覆盖翻页、两种核对失败、仓库内拒绝、重试成功和重试用尽
  - _需求：1.2、6.3_

- [ ] 5. 命令行和英文说明（`apps/layer-coverage/cli.py`、`README.md`，设计 8）
  - `fields` 和 `show <ID>`：只读清单，不 import `refcov`，不写记录
  - `tests/test_layer_cli.py`：`fields` 列出全部单元，`show` 打印正文，找不到的 ID 退出码 1，运行前后清单的 sha256 和目录内容都不变
  - `README.md` 用英文写：做什么，怎么复现清单，关卡怎么拦、出处怎么查，局限（只有 Bayside 子集；不算面积；适配器副本要放在工作区相对路径里）。不写"抓到了多少"（需求 7.2）
  - _需求：6.1、7.1、7.2_

- [ ] 6. 实跑，只写仓库里的清单（设计 2、7）
  - `fetch.py --check` 连接实时接口，核对 6018 条和分组计数（2100 为 4301，5110 为 1715，5100 为 1，1001 为 1）；不写文件
  - `build.py --geojson <本地抽取文件>` 生成 `apps/layer-coverage/bayside.fields.md`。本地抽取文件是 `D:\agent\kiro\refcov-trial\A-template\bayside_buildings.geojson`，只读
  - 用 `adapter.py` 拆清单，得 17 个单元；`cli.py fields` 列出全部；核对 `name` 字段非空为 0
  - 提交清单。提交前跑全套测试
  - _需求：1、2、3_

- [ ] 7. 仓库外的判分脚本（设计 10.1、10.4）
  - 写到 `D:\agent\kiro\refcov-trial-grader\layer_grade.py`（仓库外，设计第 12 节第 7 条）
  - 用 pyproj 把几何投影到 EPSG:2263，逐个多边形算面积，换算成平方米；输出两个标准值（口径 A 4303 个、口径 B 4301 个）和第 10.4 节的三个错误参照值
  - 数值不进仓库，不写进 DEVLOG 或任何提交说明
  - _需求：8.2、8.3_

- [ ] 8. 停在检查点 2
  - 把设计第 10 节的模板步骤、两组运行、提示词（含 answer.md 那一句）、记录方式交用户审
  - 不运行任何演示，不起 kiro-cli。等用户批准后再运行
  - _需求：8.4–8.6_
