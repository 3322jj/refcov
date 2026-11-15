# 设计文档：图层覆盖率应用 `apps/layer-coverage`（初稿，等审阅）

依据：`requirements.md` 第二稿（2026-11-15）。核心层不动（第 9 节）；要动就停下，等检查点 3。

## 1. 总览

应用把纽约建筑轮廓数据（NYC Open Data `5zhs-2jue`）的 Bayside 子集（6018 条）变成 RefCov 能登记的单元：每个字段一个单元，另有一个坐标系单元和一个范围单元。字典说明和数据统计写在同一个字段单元里。全部用 Python 标准库。不做地图、图表、字段筛选和数据清洗（需求 6.2）。

| 文件 | 作用 | 允许的依赖 |
|---|---|---|
| `apps/layer-coverage/fetch.py` | 分页下载子集到仓库外的一个文件；`--check` 只核对计数，不写文件 | 标准库 |
| `apps/layer-coverage/build.py` | 读本地 GeoJSON 和字典网址，算统计，写 `bayside.fields.md` | 标准库；导入 `stats.py`、`adapter.py` |
| `apps/layer-coverage/stats.py` | 纯函数：非空数、不同取值数、前 5 个、值为 0 的条数 | 标准库 |
| `apps/layer-coverage/adapter.py` | 适配器 `layer`：把清单拆成单元，读单元，列事实。导入时不做耗时的事 | 标准库，`refcov.sources`（`Unit`、`KindDecl`） |
| `apps/layer-coverage/cli.py` | `fields`、`show`：只读清单，不写读取记录 | 标准库 |
| `apps/layer-coverage/bayside.fields.md` | 生成的清单。进仓库，不含原始数据 | — |
| `apps/layer-coverage/README.md` | 英文说明：机制和局限 | — |

## 2. 数据

- 接口：`https://data.cityofnewyork.us/resource/5zhs-2jue`（SODA）。
- 子集：`within_box(the_geom, 40.770, -73.785, 40.755, -73.765)`，6018 条（接口 `count(*)` 核对过）。
- 查询：
  - 条数：`$select=count(*)`
  - 分组计数：`$select=feature_code,count(*)&$group=feature_code`
  - 下载：`.json` 端点，`$order=:id`，`$limit=50000`，`$offset` 翻页，直到返回空页。
- 行的处理：`the_geom` 是几何，其余键是属性。所有行的键取并集，缺的键补 null。本地抽取文件（第 0 步）里 15 个属性的值全是字符串或 null。输出是 FeatureCollection，带 CRS84 的 `crs` 成员。
- 字典：`https://raw.githubusercontent.com/CityOfNewYork/nyc-geo-metadata/main/Metadata/Metadata_BuildingFootprints.md`。`build.py` 直接读这个网址，算 sha256，写进清单。
- 数据不进仓库。`fetch.py` 拒绝把输出写进仓库目录。

## 2.1 字段名对应（需求 2）

字典的 Attribute 表（单元 `nyc-bldg-dict/3.-Attribute-Information` 和 `@2`，2026-11-15 读过）、形状文件的列名、接口的小写键，对应如下：

| 数据键（接口，小写） | 字典名 | 形状文件名 | 字典类型 | 备注 |
|---|---|---|---|---|
| objectid | OBJECTID | OBJECTID | number | |
| base_bbl | BASE_BBL | BASE_BBL | text | |
| bin | BIN | BIN | number | |
| construction_year | CONSTRUCTION_YEAR | CNSTRCT_YR | number | |
| doitt_id | DOITT_ID | DOITT_ID | number | |
| feature_code | FEATURE_CODE | FEAT_CODE | number | 编码表在字典里 |
| geom_source | GEOM_SOURCE | GEOM_SOURCE | text | |
| ground_elevation | GROUND_ELEVATION | GROUNDELEV | number | 字典：英尺 |
| height_roof | HEIGHT_ROOF | HEIGHTROOF | number | 字典：英尺 |
| last_edited_date | LAST_EDITED_DATE | LSTMODDATE | date | |
| last_status_type | LAST_STATUS_TYPE | LSTSTATTYPE | text | |
| mappluto_bbl | MAPPLUTO_BBL | MPLUTO_BBL | text | |
| name | NAME | NAME | text | 子集里全部为空 |
| shape_area | Area（别名 Shape__Area、SHAPE_AREA、shape_area） | varies | number | 字典：Do not use |
| shape_length | Length（别名 Shape__Length、SHAPE_LENGTH、shape_length） | varies | number | 字典：Do not use |

不生成字段单元的两项：
- SHAPE（几何）不是属性。它进坐标系单元。
- GLOBALID 字典里有，子集数据里没有。写进范围单元的"数据来源"行。

对应规则：数据键与字典名、或字典别名（字典的别名列用 `<br>` 分开）按大小写不敏感比对。有数据键对不上时，`build.py` 报错退出，不静默丢字段。

## 3. 清单格式

文件是 `apps/layer-coverage/bayside.fields.md`。

- 开头是一行标题和"由 build.py 生成，手改会被覆盖"。开头不是单元。
- 每个单元一节：`## <单元 ID>`，节的第一行是 `kind: crs`、`kind: extent` 或 `kind: field`，其余是正文。
- 顺序：`crs`，`extent`，然后 15 个字段按字典顺序。

字段节的格式（占位符用尖括号）：

```
## feature_code
kind: field
字典名：FEATURE_CODE；形状文件名：FEAT_CODE；字典类型：number。
字典说明：<字典 Description 原文，<br> 换成换行>
字典注意：<字典 Notes 原文；空则写"（无）">
数据：非空 <n> 条；不同取值 <m> 个；值为 0 的条数 <k>。
数据里的类型：<str 等>
取值分布（前 5 个，按条数从多到少，同数按文字排序）：
- <值>：<条数>
```

- `crs` 节：几何类型计数，坐标系（CRS84，经度在前），字典里 SHAPE 行和 Area 行的原文。节里不写换算指令，换算是答题的事。
- `extent` 节，标题"范围和数据来源"：子集的经度和纬度最小、最大值；`within_box` 的写法；GeoJSON 文件的 sha256 和条数；字典网址和它的 sha256；字典里有、数据里没有的字段（GLOBALID）。

## 4. 适配器 `adapter.py`（需求 2、3、5）

- `name = "layer"`。
- `kinds`：`field: KindDecl(strict=True, key=False)`，`crs: KindDecl(strict=True, key=True)`，`extent: KindDecl(strict=True, key=True)`。坐标系和范围最容易出错，所以轻量模式也必看。满足需求 2.4（关键类型也是严格必看）。
- `split(data, name)`：按行首的 `## ` 切段。`## ` 后面的文字是单元 ID，必须通过 `validate_unit_id`。每段第一行必须是 `kind:` 加三种之一。ID 重复、kind 不认识、缺 kind 行，都抛 `ValueError`。标题前的文字不是单元。`title`：字段为"`<ID>`（字典名 X）"，坐标系为"坐标系"，范围为"范围和数据来源"。
- `read(data, name, unit_id)`：返回 `[正文]`，不含图片。单元不存在时抛 `KeyError`。
- `facts(data, name, unit_id)`：每个单元都有 `id` 和 `kind`。字段另有 `non_null`、`distinct`、`zeros`，从"数据："那一行解析。范围另有经纬度的最小、最大值和 `rows`。
- 导入守卫：模块顶层只放 import、常量、两处 `KindDecl(...)` 赋值、函数和类定义。导入时不读文件、不开子进程、不联网、不算哈希。测试见第 11 节。

## 5. 统计（`stats.py`，需求 2）

输入：一个属性在全部行里的值列表，缺键按 null 算。输出 `FieldStats(rows, non_null, distinct, top, zeros, types)`。

- `non_null`：不是 null 的值的个数。
- 文字形式：字符串原样；布尔和数字用 `json.dumps`。
- `distinct`：非空值里文字形式不同的个数。
- `top`：最多 5 对 `(文字, 条数)`，按条数从多到少，同数按文字的码位顺序。
- `zeros`：数字等于 0，或字符串去掉空白后能读成 0（`"0"`、`"0.0"`、`"-0"`）。布尔不算，空字符串不算。
- `types`：非空值的 Python 类型名集合。子集数据里是 `str`。

性质测试（Hypothesis，`tests/test_layer_stats.py`）：

- P1 守恒：各文字的条数相加等于 `non_null`；`top` 里的条数等于真实条数；`len(top) == min(5, distinct)`。
- P2 顺序：`top` 是按（条数降序、文字升序）排好的前 5 个。
- P3 排列不变：打乱输入，结果不变。
- P4 null 不变：加入 null 只改 `rows`，其余不变。
- P5 零：`zeros` 等于按"能读成 0"判断的个数。生成的值包括 `0`、`0.0`、`"0"`、`"0.0"`、`"1"`、`""` 和 null。

## 6. 下载（`fetch.py`，需求 1.2、6.3）

- 用法：`python apps/layer-coverage/fetch.py --out <文件>`。`--check` 只查计数，不写文件。
- 翻页：每页 50000 条，`$order=:id`。遇到空页，或不满一页，就停。每次请求超时 60 秒。网络错误和 5xx 重试 3 次，间隔 2、4、8 秒。
- 核对：下载的总条数等于 `count(*)`；每个 `feature_code` 的条数等于分组查询的结果。不一致就退出码 1，不写文件。
- 写入：先写临时文件，再用 `os.replace` 换到 `--out`。`--out` 在仓库目录里时退出码 2，什么也不写。
- 输出：条数、分组条数、输出文件的 sha256。
- 测试注入假的 `fetch_json(url)`，不联网。

## 7. 清单生成（`build.py`，需求 2、3）

- 用法：`python apps/layer-coverage/build.py --geojson <文件> [--dictionary-url <网址>] [--out apps/layer-coverage/bayside.fields.md]`。
- 步骤：
  1. 读 GeoJSON。`crs` 不是 CRS84，或有非 MultiPolygon 的几何，退出码 1。
  2. 用标准库 urllib 读字典网址，算 sha256。
  3. 解析字典的 Attribute 表：5 列的行，`<br>` 分开的别名。
  4. 按第 2.1 节对应数据键和字典名。对不上就退出码 1，并列出名字。
  5. 用 `stats.py` 算每个字段的统计，渲染各节。
  6. 原子写入 `--out`。
- 输出是确定的：不写时间，字段按字典顺序。同样的输入两次写出的字节相同（测试）。
- 字典的文字照抄，只把 `<br>` 换成换行。

## 8. 命令行（`cli.py`，需求 6.1）

- `python apps/layer-coverage/cli.py fields`：每个单元一行，格式为"ID 制表符 标题"。
- `python apps/layer-coverage/cli.py show <ID>`：打印该单元的正文。ID 不存在时退出码 1。
- 只读 `apps/layer-coverage/bayside.fields.md`。不 import `refcov`，不写任何记录（测试）。

## 9. 核心层和接入（需求 6.3，检查点 3）

不改核心层。用到的接口：

- `[adapters] layer = "apps/layer-coverage/adapter.py"`：适配器加载器，`refcov/adapters/loader.py`。
- `[sources.layer] files = ["apps/layer-coverage/bayside.fields.md"]`：`refcov/store.py` 的 `[sources]` 子表。
- `KindDecl(strict, key)`：`refcov/sources.py`。

限制：适配器路径必须是相对仓库根目录的路径，不接受绝对路径，且必须在工作区里（`loader.py` 第 48–52 行）。演示的模板在仓库外，所以模板里要放一份 `apps/layer-coverage/adapter.py` 的副本，并用 sha256 核对它和仓库里的文件一致。如果这个做法不被接受，只有两条路：允许仓库外的适配器路径（改核心层，检查点 3），或改用内置的 markdown 适配器。后者的字段单元没有 kind，严格模式的必看规则要重新定。

## 10. 演示（需求 8）

### 10.1 问题和判分

- 问题原文固定：`Bayside 子集里，排除车库后，建筑的总占地面积是多少平方米？`
- 标准答案只在仓库外的判分脚本里，即 `D:\agent\kiro\refcov-trial-grader\layer_grade.py`。脚本用 pyproj 把几何投影到 EPSG:2263，逐个多边形算面积（外环减内环），再换算成平方米（1 平方英尺 = 0.09290304 平方米）。数值不写进仓库。
- 接受两种口径（需求 8.3）：A 是排除 5110 后的全部要素（4303 个）；B 只取 2100（4301 个）。容差 ±3%。
- 判分由人对照答案看数字。脚本只打印两个标准值，以及第 10.4 节的错误参照值。
- EPSG:2263 用美国英尺。用 0.09290304（国际英尺）换算，两者相差约 0.0004%，远小于容差。

### 10.2 两组

- 组 A（完整）：setup 装的 5 个钩子全部保留。
- 组 G（只留关卡）：只在模板里删除 `.kiro/hooks/refcov-prompt.json`，也就是发消息时报一行的状态行提示。仓库里的钩子模板不动。其余 4 个保留：`refcov-pre-write.json`、`refcov-pre-shell.json`、`refcov-pretask.json`、`refcov-post-mcp.json`。
- 每组 4 次，共 8 次。每次新开会话，用同一个提示词，模型是 claude-haiku-5.5。开跑前记下 kiro-cli 的版本。
- 提示词（待批准，见第 12 节第 2 条）：

  ```
  Bayside 子集里，排除车库后，建筑的总占地面积是多少平方米？请把计算过程和答案写进 answer.md。
  ```

- 记录：每次保留 RefCov 的会话记录和 kiro-cli 的会话记录，放在 `D:\agent\kiro\refcov-trial\L-runs\` 下，按组和次编号。目录由用户定。
- 组 G 要看的三件事（需求 8.5）：第一次写文件是否被拦，拦之后的 MCP 读取，最后的计算和答案。从记录里按时间顺序列出，不靠 AI 的自述。

### 10.3 模板（用户准备）

1. 在仓库外新建 `D:\agent\kiro\refcov-trial\L-template\`。
2. 把 `apps/layer-coverage/adapter.py` 和 `bayside.fields.md` 复制到模板里相同的相对路径。
3. 写 `refcov.toml`：
   - `[adapters] layer = "apps/layer-coverage/adapter.py"`
   - `[sources.layer] files = ["apps/layer-coverage/bayside.fields.md"]`
   - `[[scope]]`：`paths = ["**"]`，`sources = ["nyc-bldg-dict", "layer"]`（`**` 的写法在第一次运行时核对）
4. 运行 `setup.py`，写 MCP 配置和 5 个钩子。
5. 用 `refcov add` 登记字典网址，`--id nyc-bldg-dict`。
6. 运行 `refcov sync`。
7. 运行 `python -m refcov check`。必看单元应为 24：字典 7 个，清单 17 个（坐标系 1、范围 1、字段 15）。核对后才进组 A。
8. 只有组 G 才删除 `refcov-prompt.json`。

以上命令都由用户执行。注册和配置只能由用户做（phase-2 规则）。

### 10.4 错误答案的参照值（判分脚本输出，不写进仓库）

- 把 `shape_area` 当面积求和。它是 Web Mercator 的自动值，面积比例约为 1/cos²(纬度)。纬度 40.76° 时约 1.74。这是计算值，实测后写进判分脚本。
- 不排除车库，6018 个要素全部求和。
- 单位错：把平方英尺数当作平方米，相差约 10.7639 倍。

### 10.5 运行次数

每组 4 次，合计 8 次。这是描述，不做统计结论。组的大小与前端指南试验相同。

## 11. 测试

- `tests/test_layer_stats.py`：第 5 节的 P1–P5。
- `tests/test_layer_adapter.py`：用小清单测 split 的 ID、kind 和各种错误（缺 kind、ID 重复、kind 未知、空段）；read 返回正文；不存在的 ID 抛 `KeyError`；facts 的数字与统计结果相同。
- `tests/test_layer_adapter_import.py`：替换 `subprocess`、`urllib`、`socket` 和文件哈希函数，让它们一调用就失败。用 `loader.load` 导入适配器必须成功，不能触发替身，用时不超过 0.5 秒。另有 `ast` 检查：顶层语句只能是 import、常量赋值、`KindDecl(...)` 赋值、函数和类定义，以及文档字符串。
- `tests/test_layer_build.py`：假的 GeoJSON（几个小多边形）和假的字典表（含 `<br>` 和别名行）。两次生成的清单字节相同；数据键对不上时退出码 1；CRS 不对时退出码 1；字典有而数据没有的字段写进范围节。
- `tests/test_layer_fetch.py`：注入假的 `fetch_json`。翻页（每页 2 条）后得到全部行；计数不一致或分组不一致，都不写文件；`--out` 在仓库里时拒绝；网络错误重试后成功，或重试用尽后失败。
- `tests/test_layer_cli.py`：`fields` 列出全部单元；`show` 打印正文；`show` 找不到的 ID 退出码 1；运行前后清单的 sha256 不变，也不创建新文件。
- `tests/test_layer_stdlib.py`：扫描 `apps/layer-coverage/*.py` 的 import。只允许标准库；只有 `adapter.py` 允许 `refcov.sources`；不许出现 geopandas、pyproj、shapely、fiona、numpy 等第三方包。

真实数据的核对不算测试，放在任务 6 里做。

## 12. 需要用户看的几点

1. 适配器副本（第 9 节）。模板里要放一份副本。如果不接受，就得改核心层，等检查点 3。
2. 提示词多了一句"请把计算过程和答案写进 answer.md"（第 10.2 节）。没有这句，任务可能不写文件，关卡就没有机会拦。
3. 字段单元全部严格必看（`strict=True`）。字段 15 个，加坐标系和范围，模板的必看数是 24。
4. 换算常数。EPSG:2263 用美国英尺，题目给的 0.09290304 是国际英尺的常数，两者差约 0.0004%，不影响判分。建议保留这个常数，并在判分脚本注释里写明。
5. GLOBALID 字典里有、子集数据里没有，不生成单元。
6. 完整重下不在本次实现里。实现只做 `--check`（只读计数），并用本地抽取文件生成清单。完整重下要在仓库外写一个约 4.5 MB 的文件，phase-2 规则要你同意。
7. 判分脚本写在 `D:\agent\kiro\refcov-trial-grader\`，在仓库外。这超出了 phase-2 的写入范围。需求 8.2 要求标准答案在仓库外，所以照做，并在这里告诉你。

## 13. 需求对照

| 需求 | 设计节 |
|---|---|
| 1 登记字典，数据不进仓库 | 第 2、6 节 |
| 2 每个字段一个单元 | 第 2.1、3、4、5 节 |
| 3 坐标系和范围单元 | 第 3、4 节（crs、extent） |
| 4 出处（规格里每条需求标出处） | 不属于本应用；由 `refcov check-spec` 检查 |
| 5 写设计和代码前读过引用的字段 | 第 2.1 节的字典单元已读（2026-11-15） |
| 6 只做字段、坐标系、范围和出处；只用标准库 | 第 1、8、11 节 |
| 7 对外只讲机制 | 任务 5 的 README |
| 8 演示 | 第 10 节 |
