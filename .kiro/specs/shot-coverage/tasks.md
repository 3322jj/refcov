# 实施计划：镜头覆盖率应用 `apps/shot-coverage`

EN summary: Implementation tasks for the shot-coverage app, following design.md section 10 item 5 (approved 2026-11-14). The core-layer changes C1–C4 and C6 are already done. Order: list format and pure functions with property tests and the import guard; the adapter's read with the video check and keyframe extraction; the detect command with the 360-pixel scaling calibration on EP01; end-to-end tests; a read-only count command; the strip page; the English README with the stated limitations. Each task is its own commit and the full test suite must pass before the next one. After the README, stop: the video comparison trial design (checkpoint 2) is handed over for review before anything is run.

依据：`requirements.md`（第二稿）、`design.md`（2026-11-14 批准，补了第 3.1.1、6、11 节）。每个任务的 `_需求：…_` 写需求编号，"设计 N"指 `design.md` 第 N 节。核心层的 C1–C4、C6 已做完（见 `requirements.md` 第二部分），本计划不再动核心层；要动就先停下等审阅。

规矩：每个任务单独提交，全套测试过了才进下一个；写文件和跑它分开发出；仓库里不放 EP01 的任何帧和视频，测试只用合成视频或假字节；提交说明里不写那个只能用户跑的子命令的完整形式（保护检查按命令文本匹配）。出处暂用文字写法，转换以后再做。

- [x] 1. 清单格式、纯函数和导入守卫（`apps/shot-coverage/adapter.py` 的第一部分）
  - 单元 ID：`shot_id(start_tenths)`，格式 `shot-<分>-<秒>-<十分之一秒>`（设计 2）
  - `build_shots(cuts, duration, min_shot)`：四舍五入到 0.1 秒、去重、去掉 0 和终点上的点、并入过短的镜头；不用 ffmpeg（设计 4 第 4 步）
  - `format_list(...)` 写清单，`parse_list(text)` 严格校验后读回；`split(data, name)` 返回 `Unit`，单元 `text` 是校验值的输入（设计 2、3.1）
  - `name = "shot"`、`kinds = {"shot": KindDecl(strict=True, key=False)}`
  - 导入守卫（设计 3.1.1）：顶层不做任何耗时的事
  - 属性测试（`tests/test_shot_list.py`）：`build_shots` 首尾相接、覆盖全片、每个镜头不短于 `min_shot`、切点是输入的子集；清单往返后 ID 满足骨架需求 2.5、单元数等于镜头数、同一份清单拆两次结果相同；视频 SHA-256、任一起止时间、阈值、最短镜头时长变一个，对应单元的校验值就变，不变的单元校验值不变；有空隙、重叠、ID 对不上起点、`shots` 数不对、缺键的清单 `split` 抛 `ValueError`
  - `tests/test_shot_adapter_import.py`：替身守卫加 `ast` 静态检查
  - _需求：1.2–1.6、3.1、7.5、10_

- [x] 2. 适配器的 `read`：视频核对和关键帧（设计 3.2）
  - 找仓库根目录：从适配器文件往上找第一个含 `.git` 的目录
  - 视频核对：存在的普通文件；大小和 `mtime_ns` 一致就通过；不一致重算 SHA-256，一致放行、不一致拒绝；通过的 `(路径, 大小, mtime_ns)` 记在进程内
  - 取关键帧：`ffmpeg -nostdin`、`stdin=DEVNULL`、超时 60 秒、中点一帧、宽度不超过 960 的 JPEG；失败带 stderr 前 300 个字符
  - `read` 返回 `[文字, Image]`，文字只写事实加局限一句；`facts` 返回索引、起止、时长、视频校验值
  - 测试（`tests/test_shot_read.py`）：假视频字节（不用 ffmpeg）的核对分支（一致放行、内容变而大小和修改时间变、只改修改时间、文件不存在）；合成视频（`lavfi`）上读取返回能解码的 JPEG、宽度不超过 960；取帧失败时经核心层 `api.read` 不写记录
  - _需求：2.1–2.6、3.2–3.4_

- [x] 3. `detect` 命令和 360 行高校准（设计 4）
  - `apps/shot-coverage/cli.py` 的 `detect <视频> [--out] [--threshold] [--min-shot] [--video-path]`：找 ffmpeg 和 ffprobe、时长、SHA-256、大小、修改时间、场景检测、写清单（先写临时文件再改名）、打印下一步；`--video-path` 指定写进清单的视频路径（给对比试验的模板用，设计 11）
  - 镜头数少于 2 或多于 300 时提示
  - **校准**：用 EP01 隔离副本和仓库外的标准答案，比较"缩小到 360 行高"和"不缩小"两种做法抓到的硬切（43 处标准答案）、用时；结果记进 DEVLOG；缩小抓得不对就退回不缩小，并把 `detect_scale` 写进清单文件头
  - 测试（`tests/test_shot_detect.py`）：合成红绿蓝三段各 2 秒检测出 3 个镜头 `[0,2]`、`[2,4]`、`[4,6]`；缺 ffmpeg 时失败且不生成清单（把 `PATH` 清掉）；`--out`、`--video-path`、视频在仓库外时的默认输出位置
  - _需求：1.1、1.2、1.5、1.7、4.4–4.6_

- [x] 4. 端到端测试
  - `tests/test_shot_end_to_end.py`：合成视频 → `detect` → 在临时仓库的配置里声明 `[adapters]` → `register(..., adapter="shot")` → 经 stdio 的 MCP 服务读全部镜头（每次返回文字加一张图）→ 检查达标；读取记录里 `images` 之和等于镜头数
  - 视频被改后读取被拒绝且日志不变；清单被手改坏后登记被拒绝且什么都不写；重新检测、重新登记后旧读取记录失效
  - 未读完时写文件关卡拦、读完放行（用 `api.check_write`）
  - _需求：2、3、4、6.1_

- [x] 5. `count` 子命令（只读）
  - `cli.py count [--source ID]`：从读取记录数出读过几个镜头、几张图（只算有效读取），输出一行文字和 `--json`
  - 测试：读取若干镜头后数字对得上；同一镜头读两次只算一个镜头、图片张数照加
  - _需求：8.1、8.2_

- [x] 6. 镜头条页面 `page.py` 和 `cli.py page`
  - `render_strip`：一排格子，宽度按时长成比例，读过亮、没读灰、被引用带标记；标题行、局限一句；`title` 属性写镜头 ID 和起止；**没有脚本也显示最终状态**；内联回放脚本（按读取顺序点亮，播放、暂停、进度条），不联网
  - 数据只来自核心层（设计 5）
  - 测试（`tests/test_shot_page.py`）：格子数等于镜头数、读过的格子数对、被引用的带标记、不含 `<img>` 和 `http`、读取记录里失效的读取不亮
  - _需求：5.1–5.5、1.8_

- [x] 7. README（英文）和局限
  - `apps/shot-coverage/README.md`：最短步骤（装 ffmpeg、`detect`、配置里声明适配器、登记、MCP 配置、复制钩子）；局限（只切硬切、一镜头一张关键帧看不到随时间出现的字、核对只比较大小和修改时间、适配器文件是普通代码改 `kinds` 能缩小必看集合属于不防蓄意伪造、适配器文件会在核心层进程里运行）；不用 power 的说明
  - 测试：README 里写的命令名和参数在 `cli.py` 里都存在（防文档和实现脱节）
  - _需求：1.8–1.10、6.2_

- [x] 8. 停下：视频对比试验的设计交给用户审（冲刺计划第 3 节检查点 2）
  - `docs/视频对比试验设计.md`：新任务的提示词、两组的模板（A：只有视频；B：`VB-template`，设计 11）、判分方式、单次上限、临时目录设在运行文件夹里
  - 判定规则草稿事先写进 DEVLOG（不改旧的，另起一条）
  - **不跑任何被测试验**，等用户审
  - _需求：8.3_
