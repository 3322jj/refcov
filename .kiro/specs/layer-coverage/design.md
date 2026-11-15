# 设计文档：图层覆盖率应用 `apps/layer-coverage`（初稿，等审阅）

依据：`requirements.md` 第二稿（2026-11-15）。核心层不动（第 9 节）；要动就停下，等检查点 3。检查点 2 的审阅结论见第 12 节。

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

对应规则：数据键与字典名、或字典别名（字典的别名列用 `<br>` 分开）按大小写不敏感比对。对不上的数据键照样生成字段单元，写明"字典里没有"，不静默丢字段（需求 2.3）。

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

- `crs` 节：几何类型计数，坐标系（CRS84，经度在前），字典数据质量节的水平坐标系（EPSG:2263，NAD83，US foot）和定位精度（ASPRS Class 1，水平约 ±2 英尺）的原文；字典 SHAPE 行的原文，以及 Area、Length 两行的原文（这两行写着"不得使用"，需求 3.3）。节里不写换算指令，换算是答题的事。
- `extent` 节，标题"范围和数据来源"：子集的经度和纬度最小、最大值；`within_box` 的写法；GeoJSON 文件的 sha256 和条数；覆盖范围（字典数据质量节 Spatial Coverage 的原文，需求 3.2）；字典网址和它的 sha256；字典里有、数据里没有的字段（GLOBALID）。

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
  4. 按第 2.1 节对应数据键和字典名。对不上的键生成字段单元，写明"字典里没有"。字典缺了数据质量节的三行（水平坐标系、定位精度、覆盖范围）或 Attribute 表里的 SHAPE、Area、Length 行，退出码 1。
  5. 用 `stats.py` 算每个字段的统计，渲染各节。
  6. 原子写入 `--out`。
- 输出是确定的：不写时间，字段按字典顺序。同样的输入两次写出的字节相同（测试）。
- 字典的文字照抄，只把 `<br>` 换成换行。

## 8. 命令行（`cli.py`，需求 6.1）

- `python apps/layer-coverage/cli.py fields`：列出字段单元（kind 为 field 的单元），每个一行，格式为"ID 制表符 标题"。坐标系和范围不列，它们用 `show` 看。（需求 6.1 写的是"列出字段单元"，这里照它做。）
- `python apps/layer-coverage/cli.py show <ID>`：打印该单元的正文。ID 不存在时退出码 1。
- 默认只读 `apps/layer-coverage/bayside.fields.md`；`--manifest <文件>` 可以指定别的清单（测试用）。不 import `refcov`，不写任何记录（测试）。切法和适配器的 `split` 一致（测试核对）。

## 9. 核心层和接入（需求 6.3，检查点 3）

不改核心层。用到的接口：

- `[adapters] layer = "apps/layer-coverage/adapter.py"`：适配器加载器，`refcov/adapters/loader.py`。
- `[sources.layer] files = ["apps/layer-coverage/bayside.fields.md"]`：`refcov/store.py` 的 `[sources]` 子表。
- `KindDecl(strict, key)`：`refcov/sources.py`。

限制：适配器路径必须是相对仓库根目录的路径，不接受绝对路径，且必须在工作区里（`loader.py` 第 48–52 行）。演示的模板在仓库外，所以模板里要放一份 `apps/layer-coverage/adapter.py` 的副本，并用 sha256 核对它和仓库里的文件一致。如果这个做法不被接受，只有两条路：允许仓库外的适配器路径（改核心层，检查点 3），或改用内置的 markdown 适配器。后者的字段单元没有 kind，严格模式的必看规则要重新定。

## 10. 演示（需求 8）

检查点 2 的审阅结论已改入本节，见第 12 节。

### 10.1 问题、标准答案和判分

- 问题原文固定：`Bayside 子集里，排除车库后，建筑的总占地面积是多少平方米？`
- 标准答案由仓库外的判分脚本算出：`D:\agent\kiro\refcov-trial-grader\layer_grade.py`。这是审阅批准的仓库外文件，只此一个。脚本先核对 GeoJSON 的 sha256（`0fdf697f0f2e817eaeb4a842bd3cb61fc33f8748ae313971274e11fcfd7e83e7`，和清单范围节记录的一致），不一致就退出。
- 算法：几何用 pyproj 投影到 EPSG:2263，逐个多边形算面积（外环减内环），再换算成平方米，常数 0.09290304（审阅批准保留）。脚本注释写明：EPSG:2263 用的是美国测量英尺，与国际英尺的常数相差约 0.0004%，远小于容差。
- 两种口径都算对（需求 8.3）：口径 A 是排除 5110 后的全部要素；口径 B 只取 2100。每个标准值各有 ±3% 的容差。
- 判分由人对照答案看数字。脚本只打印两个标准值和三个错误参照值（10.6），不给判分结论。
- 数字只在判分脚本的输出里，不进仓库、DEVLOG、提交说明。
- "掉进陷阱"的定义：答案不在口径 A 和口径 B 的任何一个容差之内。

### 10.2 三组

- 组 A（装 RefCov，完整）：setup 装的 5 个钩子全部保留。发消息时的状态行提示和写文件关卡都在。
- 组 G（装 RefCov，只留关卡）：去掉 `.kiro/hooks/refcov-prompt.json`（发消息时报一行的状态行提示）。其余 4 个保留：`refcov-pre-write.json`、`refcov-pre-shell.json`、`refcov-pretask.json`、`refcov-post-mcp.json`。去掉只在每次运行的工作区副本里做，模板本身不动（10.5）。
- 组 N（不装 RefCov，对照）：没有 RefCov 的配置、钩子和 MCP。文件和提示词与 A、G 相同。理由（审阅提出）：
  - 计数题（A 线校准）里 Sonnet 3 次全对，但那题的答案在数据里直接数得出。
  - 前端指南试验里，Haiku 不装 RefCov 时 4 次都没开指南。
  - 面积题的 `shape_area` 就在数据里。Haiku 不装时会不会直接对它求和，还没测过。组 N 就是测这件事。
- 模型：三组都是 claude-haiku-5.5。开跑前记下 kiro-cli 的版本。
- 提示词（审阅批准）：

  ```
  Bayside 子集里，排除车库后，建筑的总占地面积是多少平方米？请把计算过程和答案写进 answer.md。
  ```

  第二句是审阅加的。没有它，任务可能不写文件，关卡就没有机会拦。
- 每次运行都新开会话，用同一个提示词。

### 10.3 运行顺序

1. 探路（由 Claude 用无界面 kiro-cli 跑，用户不跑）：组 N × 1，组 G × 1。
   - 组 N 看两件事：答案是否掉进陷阱；如果掉进去，用了什么（`shape_area` 求和、没排除车库，还是单位错）。
   - 组 G 看一件事：第一次写文件是否被拦。
2. 按探路结果定次数：
   - 组 N 掉进陷阱：N、A、G 各 4 次。
   - 组 N 做对了：探路的这一次照实记下，组 N 不再跑；A、G 各 4 次。
3. 正式跑的记录放在 `D:\agent\kiro\refcov-trial\runs\gis-<时间>\`，按组和次编号。

实际结果（2026-11-15，已跑完；记录在 `D:\agent\kiro\refcov-trial\runs\gis-20261115-*`，详见 main 上的 `docs/GIS试验结果.md`）：

- 探路：组 N 1 次做对，所以按上面第二条，组 N 不再跑。组 N 直接打开了字典和清单，没有 RefCov 的记录。组 G 探路 1 次：先被拦，读完必看单元，再写。
- 正式跑：组 A 4 次全对，都读完 24 个单元；写文件时 1 次读到一半被拦，其余 3 次没拦。组 G 4 次全对，都读完 24 个单元，每次都是先被拦、读完再写。组 G 的 5 次（探路 1 次加正式 4 次）里，读完以后重写的答案，数字和被拦那次相同。
- 组 A 有一次（A-03）把计算脚本写到了系统临时目录，那是工作区外，关卡不检查那里。10.4 第四件（经 shell 写文件绕过关卡）：GIS 试验结果里没有组 G 这样做的记录。
- 另外两轮 GIS 试验（第二版不提车库；公认基准 ScienceAgentBench #21）也没测出"读了才做对"。

### 10.4 组 G 要看的四件事（需求 8.5）

从记录里按时间顺序列出，不靠 AI 的自述：

1. 第一次写文件是否被拦。
2. 拦截之后的 MCP 读取：读了哪些必看单元。
3. 最后的计算和答案。
4. 有没有经 shell 写文件（例如命令行重定向，或 PowerShell 的写入命令）绕过关卡。有就照实记下。

写文件关卡只按写文件工具（`fs_write`、`str_replace`、`fs_append`）的 `path` 判断。shell 工具只做保护检查，不拦 shell 写出的文件。这一点在 `docs/验证结果.md` 第 8 项里实测过，拦不住。所以第四件要查。

### 10.5 模板和工作区

模板目录（审阅改名）：

- `D:\agent\kiro\refcov-trial\GIS-template\`：组 A、组 G 用，装 RefCov。
- `D:\agent\kiro\refcov-trial\GIS-N-template\`：组 N 用，不装 RefCov。
- `L-template` 已被网店约定漏读试验占用，不动它。

两个模板的工作区文件完全相同，以下四项：

1. `bayside_buildings.geojson`：从 `D:\agent\kiro\refcov-trial\A-template\` 复制，复制后核对 sha256 = `0fdf697f0f2e817eaeb4a842bd3cb61fc33f8748ae313971274e11fcfd7e83e7`。题目要从几何算面积，所以工作区必须有这个文件。
2. `docs/Metadata_BuildingFootprints.md`：字典的本地副本，从 `D:\agent\kiro\refcov-trial\A2-template\` 复制，sha256 = `f1f7934c8c19a69af41d7ee4dbaee69b190e005c7adba0adbed4c3b55d22baae`，和实时字典相同。
3. `apps/layer-coverage/adapter.py` 和 `apps/layer-coverage/bayside.fields.md`：从仓库复制，两份的 sha256 都要和仓库里的文件一致。
4. `README.md`，一行：`Data: bayside_buildings.geojson. Data dictionary: docs/Metadata_BuildingFootprints.md.`

GIS-template 的 RefCov 配置和钩子由 setup 写入，GIS-N-template 没有这些。

GIS-template 的 `refcov.toml`：

- `[adapters] layer = "apps/layer-coverage/adapter.py"`
- `[sources.layer] files = ["apps/layer-coverage/bayside.fields.md"]`
- `[[scope]]`：`paths = ["**"]`，`sources = ["nyc-bldg-dict", "f-apps-layer-coverage-bayside-fields-md-631ad0"]`。`**` 能匹配根目录的 `answer.md`：`refcov/store.py` 的 `path_matches` 用 `fnmatchcase`，`*` 能跨 `/`（审阅核对过，不用等首次运行）。清单经 `refcov sync` 登记后，参考源的编号是自动生成的，即 `f-apps-layer-coverage-bayside-fields-md-631ad0`，不是 `layer`；`[[scope]]` 里写的是这个编号，模板已按实际编号写。

每次运行前，从模板复制一份新工作区，读取记录从零开始，上一次运行的记录不带过来。组 G 的那份工作区删除 `.kiro/hooks/refcov-prompt.json`，模板本身不删。

setup.py 写进 MCP 配置和钩子的是模板目录的绝对路径（`--root`）。每次复制工作区后，运行器要把这些路径换成副本自己的路径，否则钩子和 MCP 读的还是模板。

分工：

1. Claude：复制文件，核对 sha256，写 `refcov.toml`。
2. 用户在模板目录的终端里运行：`setup.py`（写 MCP 配置和 5 个钩子，用法见 README 的 Setup 一节）；`refcov add docs/Metadata_BuildingFootprints.md --id nyc-bldg-dict`（用本地副本登记字典，不用网址，各组看到的字典字节相同）；`refcov sync`；`python -m refcov check`。
3. `python -m refcov check` 的必看单元应为 24：字典 7 个，清单 17 个（坐标系 1、范围 1、字段 15）。不是 24 就停下来查，不进入探路。

### 10.6 错误答案的参照值（判分脚本输出，不写进仓库）

- 用 `shape_area` 求和（排除车库）：它是 Web Mercator 的自动值，面积比例约为 1/cos²(纬度)。纬度 40.76° 时约 1.74。
- 不排除车库，6018 个要素全部求和。
- 单位错：把平方英尺数当作平方米，相差约 10.76 倍。

### 10.7 次数

每组 4 次（组 N 视探路而定，见 10.3）。这是描述，不做统计结论。组的大小与前端指南试验相同。

## 11. 测试

- `tests/test_layer_stats.py`：第 5 节的 P1–P5。
- `tests/test_layer_adapter.py`：用小清单测 split 的 ID、kind 和各种错误（缺 kind、ID 重复、kind 未知、空段）；read 返回正文；不存在的 ID 抛 `KeyError`；facts 的数字与统计结果相同。
- `tests/test_layer_adapter_import.py`：替换 `subprocess`、`urllib`、`socket` 和文件哈希函数，让它们一调用就失败。用 `loader.load` 导入适配器必须成功，不能触发替身，用时不超过 0.5 秒。另有 `ast` 检查：顶层语句只能是 import、常量赋值、`KindDecl(...)` 赋值、函数和类定义，以及文档字符串。
- `tests/test_layer_build.py`：假的 GeoJSON（几个小多边形）和假的字典表（含 `<br>` 和别名行）。两次生成的清单字节相同；数据键对不上时退出码 1；CRS 不对时退出码 1；字典有而数据没有的字段写进范围节。
- `tests/test_layer_fetch.py`：注入假的 `fetch_json`。翻页（每页 2 条）后得到全部行；计数不一致或分组不一致，都不写文件；`--out` 在仓库里时拒绝；网络错误重试后成功，或重试用尽后失败。
- `tests/test_layer_cli.py`：`fields` 列出全部单元；`show` 打印正文；`show` 找不到的 ID 退出码 1；运行前后清单的 sha256 不变，也不创建新文件。
- `tests/test_layer_stdlib.py`：扫描 `apps/layer-coverage/*.py` 的 import。只允许标准库；只有 `adapter.py` 允许 `refcov.sources`；不许出现 geopandas、pyproj、shapely、fiona、numpy 等第三方包。

真实数据的核对不算测试，放在任务 6 里做。

## 12. 检查点 2 的审阅结论（2026-11-15）

应用本身通过：850 个测试复跑全过；清单抽查 crs、extent、feature_code、shape_area 和字典一致；四处需求补齐（1.4、2.3、3.1/3.3、3.2）都对。

八条批复：

1. 判分脚本：批准，只此一个仓库外文件。读 A-template 的 geojson，先核 sha256，不一致就退出；打印两个标准值和三个错误参照值。数字不进仓库、DEVLOG、提交说明。
2. 提示词加一句"请把计算过程和答案写进 answer.md。"：批准。
3. 模板放 `adapter.py` 副本并核 sha256：批准，不改核心层。
4. 换算常数 0.09290304：保留。脚本注释写明 EPSG:2263 是美国测量英尺，相差约 0.0004%。
5. 次数先探路再定（10.3）。`**` 不用等首次运行核对（10.5）。
6. 完整重下：不做。A-template 的 geojson 和清单记录的 sha256 一致，实时计数也一致。
7. `.refcov/log.jsonl`：继续跟踪，它是"Haiku 写之前读过"的证据。照旧按路径暂存，不带它；由用户或 Claude 在检查点单独提交。
8. decisions 文件：不做。需求第二稿已含这三处改动，check-spec 幻影 0。

设计改动（审阅发现，已写入第 10 节）：

- a. 模板目录重名。`L-template` 已被网店约定漏读试验占用，改用 `GIS-template`（装 RefCov）和 `GIS-N-template`（不装）。运行记录放 `runs\gis-<时间>\`（10.3、10.5）。
- b. 模板缺数据。工作区要有 `bayside_buildings.geojson`，从 A-template 复制并核 sha256（10.5）。
- c. 各组工作区文件相同（四项），字典用本地副本登记（10.5）。
- d. 加组 N：不装 RefCov 的对照组（10.2）。
- e. 写文件关卡只按写文件工具的 path 判断，shell 写的文件不经关卡。组 G 要查第四件（10.4）。

执行顺序：

1. 本轮（agent）：改设计第 10、12 节和 tasks.md；写判分脚本（任务 7）；全量测试、提交、推送、记施工账；然后停。
2. 模板（Claude 搭）：建 GIS-template 和 GIS-N-template，核对四项文件和 sha256，写 `refcov.toml`。用户在终端跑 setup.py、`refcov add`（本地字典副本）、`refcov sync`、`python -m refcov check`（必看 24）。
3. 探路（Claude 用无界面 kiro-cli）：组 N × 1，组 G × 1。
4. 按探路结果定次数（10.3），正式跑。

试跑都由 Claude 跑。用户不跑，省用户的额度。

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
