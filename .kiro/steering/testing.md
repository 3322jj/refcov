---
inclusion: fileMatch
fileMatchPattern: "tests/**"
---

# 测试约定

EN summary: Tests use pytest; core calculations get Hypothesis property tests, at least one `@given` test per property listed in requirement 16. Each test's docstring names the property it checks. Counterexamples found by property tests become regression tests and are logged in DEVLOG. Properties are never weakened to make tests pass; ask the user first.

- 测试框架 pytest，属性测试用 Hypothesis（开发依赖，核心层运行时不依赖它）。
- 核心层计算部分（单元模型、读取记录、覆盖率、出处检查、凭证）的每条性质至少一个 `@given` 测试。
- 测试函数的文档字符串写明它验证的是哪条性质，例如 `"""性质 16.2：重复读同一单元，覆盖率不变。"""`。
- 属性测试抓到的反例，固定成一个普通的回归测试（`@example` 或单独用例），并记进 `docs/DEVLOG.md`：哪条性质、反例是什么、改了哪里。
- 不为了测试通过而改测试里的性质。性质不成立时先和用户确认是代码错还是需求错。

## 必须覆盖的性质（需求 16）

出自 `.kiro/specs/refcov-skeleton/requirements.md` 需求 16（第四稿编号是需求 17）。

1. 覆盖率和必看覆盖率始终在 0% 到 100% 之间。
2. 同一单元读多次只算一次：重复追加同一单元的读取记录，覆盖率不变。
3. 需求引用了没有有效读取记录的单元，一定判定不达标。
4. 关卡结论只由读取记录和配置决定：输入里任意改动 AI 的文字（例如自述、写入正文），结论不变。
5. 同样的单元和配置下，轻量模式的必看集合一定是严格模式必看集合的子集。
6. 同样的记录下，严格模式达标，则轻量模式一定达标。

## 生成数据时注意

- 单元标题要包含中文、空格、方括号和其他特殊字符，Windows 下的编码问题要能被测到。
- 单元 ID 由标题生成（需求 2.5），要包含中文；同时验证生成的 ID 里没有空白和方括号，含空白或方括号的 ID 会被拒绝。
- 读取记录要覆盖"校验值已过期"的情况（需求 1.4），过期记录不算看过。
- 放宽项、关键类型、可选类型（例如样本行）都要随机生成，性质 5、6 才有意义。
