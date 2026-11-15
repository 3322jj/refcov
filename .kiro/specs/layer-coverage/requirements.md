# 需求文档：图层覆盖率应用 `apps/layer-coverage`（初稿，2026-11-15，等审阅）

EN summary: Draft requirements for the layer-coverage app, which proves citation tracing and the gate on GIS data. The NYC building-footprint data dictionary is registered as a reference source, the data itself stays out of the repository, and a layer adapter turns each field into one unit that merges what the data file shows with what the dictionary says. Kiro spec requirements cite those units; phantom requirements and invalid references are listed. This round adds no page, and the public claims describe only the mechanism. Status: draft for checkpoint 1, 2026-11-15, following the second version of docs/应用定位和陷阱试验.md.

状态：**初稿，2026-11-15，等用户审阅（检查点 1）。** 依据 `docs/应用定位和陷阱试验.md` 第 5 节和附录（第二版）。核心层不在本文档范围内；要动核心层的部分按冲刺计划第 3 节，单独停一次。

## 简介

图层覆盖率给 GIS 数据算"拦和出处"：纽约建筑轮廓的官方数据字典登记成参考源，AI 读完字段单元以后才能写设计和代码；Kiro 规格里的每条需求都要标出处，没有出处的列成幻影需求，引用了没读过的字段的需求不达标。它在整体讲法里负责"拦和出处"（`docs/应用定位和陷阱试验.md` 第 5 节）。

不做：地图、图表、字段筛选界面、数据清洗，也不做"理解数据含义"的模型。页面和视觉语言（定位文档第 7 节）是有余力的部分，按冲刺计划第 5 节的砍单顺序放在最后。

**这份文档写的是需求，不是设计**：字段的具体处理和适配器接口在设计阶段定。

## 术语

- **数据字典**：纽约市 OTI 发布的官方 Markdown 说明（参考源 `nyc-bldg-dict`），写字段的含义、单位和编码表。
- **数据文件**：NYC Open Data `5zhs-2jue` 的下载数据，不进仓库。演示只用 Bayside 子集（6018 条）。
- **字段单元**：数据文件里的一个字段，合并"数据文件里看到的"和"数据字典里写的"。本应用的单元类型是 `field`。
- **坐标系单元、范围单元**：描述数据的水平坐标系，以及数据和演示子集覆盖的范围。
- **出处**：需求块里的 `出处：[ref:…]` 行，写法见 `.kiro/steering/citation.md`。

## 第一部分：应用本身

### 需求 1：登记数据字典，数据不进仓库
EN: Registering the data dictionary, with the data kept out of the repository

**用户故事：** 作为用户，我想让 AI 读到纽约建筑轮廓的官方数据字典，并且数据本身不进仓库，以便演示可以公开，而不违反数据的使用条款。
EN: As a user, I want the AI to read the official NYC building-footprint data dictionary while the data itself stays out of the repository, so that the demo can be public without breaking the data's terms.

#### 验收标准

1. THE 应用 SHALL 把数据字典登记为参考源 `nyc-bldg-dict`，来源是字典的原文 Markdown 网址（不是 GitHub 网页）。登记由用户在终端运行 `refcov add`，应用不代劳。
2. THE 仓库 SHALL NOT 放数据文件。仓库里只放下载脚本，脚本和 README 都写明来源：NYC Open Data，数据集编号 `5zhs-2jue`。
3. THE 演示 SHALL 只用 Bayside 子集（6018 条）。全市的 1,082,972 条 SHALL NOT 进仓库。
4. THE README SHALL 写明：数据和字典的使用条款全文还没有读完；对外使用之前要读完并照做。

出处：[ref:nyc-bldg-dict/Building-Footprints] [ref:app-positioning/附录：纽约建筑轮廓数据] [ref:app-positioning/5.-图层覆盖率-`apps/layer-coverage`：拦和出处]

### 需求 2：每个字段一个单元
EN: One unit per field

**用户故事：** 作为用户，我想让每个数据字段都是一个可读的单元，以便 AI 写需求时能引用到具体字段，并且知道字段在数据里是什么样子、在字典里是什么意思。
EN: As a user, I want each data field to be a readable unit, so that the AI can cite a specific field when it writes requirements, and knows both what the field looks like in the data and what the dictionary says it means.

#### 验收标准

1. THE 图层适配器 SHALL 为数据文件里的每个字段生成一个单元。单元 ID 由字段名生成，规则和骨架需求 2.5 相同：空白和方括号换成短横线，其余字符保留。
2. THE 单元内容 SHALL 合并两部分：数据文件里的（字段名、类型、非空数、不同取值数、取值最多的前几个及其数量）；字典里的（含义、单位、编码表，取自字典的 Attribute Information 表）。
3. WHEN 字典里没有同名字段，THE 单元 SHALL 明确写"字典里没有"，不得静默省略。字段名在接口和字典里不同的（附录的例子：`FEAT_CODE` 对 `feature_code`），单元 SHALL 同时写出两个名字。
4. THE 单元 SHALL 写明字典里"0 或空表示不详"的说法，以及数据里的实际情况（附录：实际只有空值，建成年份为 0 的记录数为 0）。
5. THE 适配器被导入时 SHALL 不做耗时的事（不调 ffmpeg 之类的外部程序，不算哈希，不读数据），和镜头应用的约定相同。

出处：[ref:nyc-bldg-dict/3.-Attribute-Information] [ref:nyc-bldg-dict/3.-Attribute-Information@2] [ref:app-positioning/附录：纽约建筑轮廓数据] [ref:app-positioning/5.-图层覆盖率-`apps/layer-coverage`：拦和出处] [ref:shot-design/3.1.1-导入-`adapter.py`-时不做任何耗时的事（用户-2026-11-14-审阅补）]

### 需求 3：坐标系和范围单元
EN: Coordinate-system and extent units

**用户故事：** 作为用户，我想让 AI 知道数据的坐标系和覆盖范围，以便它写需求和代码时不会把投影坐标当成经纬度用。
EN: As a user, I want the AI to know the data's coordinate system and extent, so that it does not treat projected coordinates as latitude and longitude when it writes requirements and code.

#### 验收标准

1. THE 图层适配器 SHALL 生成一个坐标系单元，写明水平坐标系（New York State Plane Coordinates, Long Island East Zone, NAD83, US foot，EPSG:2263），以及发布用的 Web Mercator（EPSG:3857）和各下载格式对应的坐标系。
2. THE 图层适配器 SHALL 生成一个范围单元，写明数据覆盖纽约市，以及演示子集的选取方式和条数（6018 条）。
3. THE 坐标系单元 SHALL 写明字典给的定位精度（水平约 ±2 英尺，按 ASPRS Class 1），以及字典写明的"不得使用"的字段（`SHAPE_AREA`、`SHAPE_LENGTH` 及其小写写法，由 Web Mercator 自动算出，不保面积和长度）。

出处：[ref:nyc-bldg-dict/2.-Data-Quality-and-Specifications] [ref:nyc-bldg-dict/3.-Attribute-Information@2] [ref:app-positioning/附录：纽约建筑轮廓数据]

### 需求 4：Kiro 规格里每条需求都要标出处
EN: Every requirement in a Kiro spec cites a unit

**用户故事：** 作为用户，我想让 Kiro 规格里的每条需求都能追到材料里的具体单元，以便看出哪些需求不是来自材料。
EN: As a user, I want every requirement in a Kiro spec to trace back to a specific unit of the material, so that I can see which requirements do not come from the material.

#### 验收标准

1. THE 需求文档 SHALL 在每条需求的验收标准之后写一行出处，格式为 `出处：[ref:<参考源ID>/<单元ID>]`，多个引用用空格隔开。
2. WHEN 一条需求块里没有任何有效引用，THE 检查程序 SHALL 把它列为幻影需求。
3. WHEN 引用的参考源或单元不存在，THE 检查程序 SHALL 把它列为无效引用。
4. WHILE 处于严格模式，有幻影需求或无效引用，THE 检查程序 SHALL 判定不达标；轻量模式下只在报告里列出。
5. THE 检查程序 SHALL 把引用了没读过的单元的需求判定为不达标。

出处：[ref:app-positioning/5.-图层覆盖率-`apps/layer-coverage`：拦和出处] [ref:dec-review-reply/二·2-幻影需求和无效引用影响达标；聊天要求怎么当出处]

### 需求 5：写设计和代码前，引用的字段要读过
EN: Gate: referenced fields must be read before design and code are written

**用户故事：** 作为用户，我想让 AI 在写设计和代码之前读过它要用的字段，以便它不会凭记忆写字段名和取值。
EN: As a user, I want the AI to have read the fields it relies on before it writes design and code, so that it does not write field names and values from memory.

#### 验收标准

1. THE 配置 SHALL 把 `apps/layer-coverage/**` 和 `.kiro/specs/layer-coverage/**` 指向参考源 `nyc-bldg-dict`、`app-positioning`、`shot-design` 和 5 份 `dec-*` 决定。配置只能由用户改，AI 不改。
2. WHEN AI 要写上述路径下的文件，THE 写文件关卡 SHALL 检查这些参考源的必看单元是否都有有效读取记录；缺的，拦截写入，并列出还差的单元。
3. THE 写文件关卡 SHALL 只按读取记录判断，不因为 AI 的自述放行（钩子写入时现算是否达标）。
4. THE 没有豁免的需求文档 SHALL 按路径判断是否达标，不达标时直接拦截。

出处：[ref:app-positioning/5.-图层覆盖率-`apps/layer-coverage`：拦和出处] [ref:dec-review-reply/二·5-钩子写入时现算是否达标] [ref:dec-analysis-answers/分析-#4-严格模式下写需求文档]

### 需求 6：应用只做字段、坐标系、范围和出处
EN: The layer app covers only fields, coordinates, extent and citations

**用户故事：** 作为用户，我想让图层应用只做字段单元、坐标系单元、范围单元和出处检查，以便它在截止前做得完，并且不超出冻结的范围。
EN: As a user, I want the layer app to cover only field units, coordinate and extent units and citation checks, so that it can be finished before the deadline and stays within the frozen scope.

#### 验收标准

1. THE 应用 SHALL 提供命令行：列出字段单元；显示一个字段的单元内容。两个命令都只读，不写读取记录。
2. THE 应用 SHALL NOT 做地图、图表、字段筛选界面或数据清洗。页面和视觉语言放在最后，按砍单顺序列为有余力。
3. THE 应用 SHALL 只在 `apps/layer-coverage` 里依赖 geopandas，和镜头应用只在它里面依赖 ffmpeg 一样。核心层和接入层 SHALL NOT import 它。

出处：[ref:app-positioning/7.-视觉语言] [ref:app-positioning/9.-风险和待验证]

### 需求 7：对外只讲机制，不讲"抓到了多少"
EN: Public claims describe the mechanism, not a count of catches

**用户故事：** 作为用户，我想让图层应用的对外说法只讲出处和关卡的机制，以便不把没有测过的数字讲出去。
EN: As a user, I want the layer app's public claims to describe the citation and gate mechanism only, so that no unmeasured number is published.

#### 验收标准

1. THE 应用的 README 和对外文字 SHALL 只讲机制：出处怎么检查，关卡怎么拦，引用了没读的单元会怎样。
2. THE 对外文字 SHALL NOT 讲"抓到了多少个幻影需求"或"模型编造了多少出处"，直到 B2 试验（不装 RefCov 时的需求出处）由 Claude 逐条判定，并记进 DEVLOG。
3. THE 对外文字 SHALL NOT 说"AI 不会编造出处"。RefCov 只查引用的单元存在、而且读过，不查这条需求是不是真的由它推出（`dec-review-reply` 二·2 的口径）。

出处：[ref:app-positioning/9.-风险和待验证] [ref:app-positioning/1.-结论] [ref:app-positioning/5.-图层覆盖率-`apps/layer-coverage`：拦和出处]

## 已定和还没定的

- 已定：只做字段、坐标系、范围和出处（需求 6）；不做页面（有余力）。
- 还没定，设计阶段定：字段取值分布列出几个（初值待定）；演示子集的选取字段；字段名对不上时的具体写法（需求 2.3 的例子只是附录里的）。
- 还没定，等用户：B2 的逐条判定结果，决定需求 7.2 什么时候能放宽。
