# GIS 试验结果：拦住了、记下了，但没测出"读了才做对"

EN summary: Three rounds of GIS trials with claude-haiku-5.5 (kiro-cli 3.3.0) on 2026-11-15. (1) The layer-coverage demo question (Bayside footprint area excluding garages): without RefCov, 1 of 1 correct; with RefCov, 8 of 8 correct, every run read all 24 required units, and all 4 gate-only runs were blocked on the first write, read the units, then wrote — the numbers did not change after reading. (2) A second question without the word "garage", with all 27 official NYC metadata files in the workspace: both runs answered with all 6018 features, but both had opened the footprint dictionary; the dictionary itself calls FEATURE_CODE "Type of Building", so this is ambiguity, not skipping. (3) A published benchmark task (ScienceAgentBench #21 = GeoAnalystBench #9, deforestation within 5.5 km of roads): both runs correct, one of them never opened the expert-knowledge file; the public reference code computes the complement (the share NOT deforested). Conclusion: in these GIS tasks the model either needed nothing from the material or was pushed to read it by the task itself, so RefCov showed its gate and its record but no gain in correctness. The literature agrees that LLM failures in GIS are mostly about capability (planning long workflows, tool use), which reading material does not fix. The evidence for "reading changes the result" stays the front-end trial.

Claude 跑、Claude 写，2026-11-15 夜。运行器、判分和核实脚本都在仓库外 `D:\agent\kiro\refcov-trial-grader\`。标准答案的具体数值不写进仓库（第一版沿用设计第 10 节的规定；第三版是公开基准题，避免泄题）。

## 1. 一句话

在 GIS 题上，RefCov 的关卡和记录都按设计工作，但没有测出"读了才做对"：不装 RefCov 的 Haiku 要么自己去读了，要么材料里没有它不知道的东西。

## 2. 第一版：设计第 10 节的演示题

题目："Bayside 子集里，排除车库后，建筑的总占地面积是多少平方米？请把计算过程和答案写进 answer.md。"工作区：Bayside 6018 个要素的 GeoJSON、建筑轮廓字典的本地副本、字段清单 `bayside.fields.md`、一行 README。装 RefCov 的组必看 24 个单元（字典 7 个，清单 17 个）。

| 组 | 次数 | 答案 | 读取 | 关卡 | 用时（秒） | 额度 |
|---|---|---|---|---|---|---|
| N：不装 RefCov | 1 | 对 | 直接打开了字典和清单（没有记录） | — | 59 | 0.08 |
| A：完整（5 个钩子） | 4 | 4 次都对 | 4 次都是 24/24 | 1 次读到一半时写文件被拦，3 次没拦 | 84–100 | 0.12–0.15 |
| G：只留关卡（去掉状态行提示） | 4 + 探路 1 | 5 次都对 | 5 次都是 24/24 | **5 次都是先被拦、读完再写** | 91–94（探路 300） | 0.14–0.15 |

"对"指在设计第 10.1 节两种口径之一的 ±3% 以内。

- **"拦"的证据有了**：G 组每次的顺序都一样：先直接打开文件、算完、写 `answer.md` 被拦，再经 MCP 读完 24 个单元，最后写成。顺序来自 RefCov 日志和 kiro-cli 记录，不靠 AI 的自述。
- **答案没被关卡改变**：G 组读完后都重写了 `answer.md`，文字有改动，但数字和被拦那次相同。这道题写了"排除车库"，不查字典就不知道车库是哪个编码，所以不装 RefCov 的那次也去查了字典。
- **完整版比只留关卡省**：A 组一开始就被状态行提示引到 MCP 上读，读完再算、再写；G 组读两遍、写两遍。和前端试验一样，起主要作用的是状态行，关卡是兜底。
- **保护检查拦了 3 次只读命令**：模型想用 shell 读 `refcov.toml`、`.refcov` 下的读取记录、`.kiro/hooks`，都被拦下，模型没有换写法绕过。保护检查对只读命令也拦，这一点以后可以再看是否过严。
- **关卡管不到工作区外**：A-03 把计算脚本写到了系统临时目录（工作区外），关卡不检查那里。
- 代价：装 RefCov 的额度约为不装的 1.6–1.9 倍，用时约 1.5 倍。

## 3. 第二版：不提车库

为了让"不查也能交差"，题目改成"Bayside 子集里有多少栋建筑？它们的总占地面积是多少平方米？"，不提车库；`docs/metadata/` 放纽约官方 nyc-geo-metadata 仓库的全部 27 份字典（Apache-2.0），README 只指向文件夹。判定规则跑之前写在 `GIS-N2-RULE.txt`。不装 RefCov，2 次。

| 次 | 主答案 | 有没有打开建筑轮廓字典 |
|---|---|---|
| N2-01 | 6018 条、全部要素的面积；另列"只算 2100 是 4301 栋" | 打开了，在计算之前 |
| N2-02 | 6018 栋、全部要素的面积；写明"按字面'建筑'取全部要素" | 先在 27 份字典里搜编码，算完后又整份读了 |

按规则字面，两次都"掉进陷阱"。但两次都读了字典，6018 不是没读造成的：字典对 FEATURE_CODE 的原文是"Type of Building"，车库（5110）就列在这些类型里，"车库算不算建筑"字典没有定论。写规则时把"只有 2100 才算建筑"当成了字典的规定，这是 Claude 的错。装上 RefCov 它读到的是同一份字典，多半给同样的答案，所以这一版证明不了漏读，也证明不了 RefCov 的作用。

## 4. 第三版：公认的 GIS 基准题

用户要求不再自己出题。查到的 GIS 能力基准里，只有 ScienceAgentBench（ICLR 2025，102 题，其中 GIS 27 题）把"专家知识"当作官方的实验条件，而且 27 道 GIS 题里只有第 21 题既是 GIS 分析、又能按数字判分：计算巴西朗多尼亚州道路两侧 5.5 公里缓冲区内的毁林面积百分比。

- **来源**：题目、数据集说明、专家知识取自 ScienceAgentBench 的标注表（Hugging Face，CC-BY-4.0）；提示词照它的 `agent.py` 原文拼，不带专家知识，只在末尾加一句"把程序存成 pred_program.py 并运行"。官方数据包的下载链接已失效（GitHub issue #16，2026-11-05 起），数据改用 GeoAnalystBench（Transactions in GIS 2025，同一团队，Apache-2.0）第 9 题，是同一道题。
- **专家知识**放成工作区里的 `docs/domain_knowledge.md`，README 一句指向它。官方的专家知识只解释了 Buffer 和 Clip 两个概念，没提投影。
- **公开参考代码有误**（Claude 用数据核实，脚本 `sab21_verify.py`）：GeoAnalystBench 第 9 题的参考代码用 `overlay(how='difference')`，算的是缓冲区里**没被砍掉**的占比，和题目问的相反；用 UTM 23S 带、UTM 20S 带、南美等积投影三种投影各算一遍，"毁林占比"和"参考代码的输出"之和都正好是 1。它还把数据投影到 UTM 23S 带（中央经线西经 45°），朗多尼亚在西经 60–67°，毁林区面积因此被放大约 10%；不过求的是两个面积的比，这一项对结果的影响不到 0.5 个百分点。
- **判定规则**跑之前写在 `SAB21-RULE.txt`，并写明：专家知识不涉及投影，所以不论结果如何，都不能拿来说明 RefCov 让答案变对。

| 次 | 结果 | 方法 | 有没有打开专家知识 | 用时（秒） | 额度 |
|---|---|---|---|---|---|
| S-01 | 按题意正确 | 南美等积投影，按米做缓冲，合并后取交集 | **没打开**，4 次工具调用直接写程序 | 305 | 0.10 |
| S-02 | 按题意正确 | 同上 | 打开了 | 177 | 0.05 |

两次的结果和 Claude 用等积投影算的值相差不到 0.1 个百分点。如果按公开参考代码的输出判分，这两次都会被判错。S-01 有一次命令撞上 120 秒超时，之后重跑成功。

## 5. 为什么 GIS 上测不出来

RefCov 让答案变对，要三个条件同时成立：答案取决于材料里的信息；模型不会自己去读；读了它能用上。

| 题 | 缺哪一条 |
|---|---|
| 第一版 | 第二条：数据里看不懂的编码会逼模型去查字典 |
| 第二版 | 第一条：字典自己没说清 |
| 第三版 | 第一条：专家知识里没有模型不知道的东西 |
| 前端指南试验（对照） | 三条都满足：Haiku 不装 0/16，装上 14/16 |

文献也指向同一方向：大模型在 GIS 上的弱点主要是能力，不是信息。

- GISAgentBench（2026，349 题，取自 GIS Stack Exchange）：最好的模型做对 32.7%；错误原因排前面的是漏了必要步骤（28.3%）、步骤顺序错（18.4%）、反复返工（14.4%）、选错工具（13.4%），坐标系问题只占 2.8%。
- ScienceAgentBench：GIS 题主要败在 geopandas 等专业库用错或编造函数；给专家知识，最好的代理只从 32.4% 提到 34.3%，作者的说法是代理"用不好这些知识"。
- GeoBenchX：主要错在理解几何关系，以及依赖过时的知识。

另外，我们出的都是一到三步的短题，落在模型已经会的那一端。

## 6. 能说什么、不能说什么

可以说：

- 关卡在没有状态行提示时照样起作用：GIS 演示题上 5 次都是先被拦、读完 24 个单元再写，顺序有记录。
- 不装 RefCov 的模型也会读字典，但只有装了 RefCov 的组留下了"24 个读了 24 个"的记录。
- 状态行负责引导，关卡负责兜底：完整版比只留关卡少一轮返工。
- 在一道公认的 GIS 基准题上，Haiku 5.5 两次都算对。

不能说 / 要照实交代：

- 不能说 RefCov 提升了模型的 GIS 能力，或在 GIS 题上让答案变对。三轮都没有测出这一点。
- RefCov 补的是信息缺口（项目规范、模型知道却不用的新写法、团队约定），不补能力缺口（规划长流程、用好专业库）。
- 装 RefCov 的额度约为不装的 1.6–1.9 倍。
- 每组 1–5 次，是描述，不是统计结论。

## 7. 运行记录

都在 `D:\agent\kiro\refcov-trial\runs\` 下：

- `gis-20261115-212356`：第一版探路（N-01、G-01）
- `gis-20261115-213112`：第一版正式（A-01–04、G-01–04）
- `gis-20261115-214331`：第二版（N2-01、N2-02）
- `gis-20261115-223218`：第三版（S-01、S-02）

模板：`GIS-template`、`GIS-N-template`、`GIS-N2-template`、`SAB21-N-template`。脚本：`refcov-trial-grader\run_gis.py`（运行）、`analyze_gis.py`（时间线和读取）、`layer_grade.py`（第一版判分）、`sab21_verify.py`（核实参考代码）。ScienceAgentBench 的数据不进仓库，作者要求不要转存。

## 8. 以后可以做的

- 把参考代码的问题报告给 GeoAnalystBench 的作者（GitHub issue）。用户的账号、公开发言，由用户决定。
- 设计第 10.5 节的 `[[scope]]` 写的是 `sources = ["nyc-bldg-dict", "layer"]`，但经 `refcov sync` 登记的清单编号是自动生成的 `f-apps-layer-coverage-bayside-fields-md-631ad0`，模板里已按实际编号写；设计里这一处要改。
