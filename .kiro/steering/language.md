---
inclusion: always
---

# 双语规矩

EN summary: Project documents are written in Chinese with English added in fixed places: an English README at the repo root; one `EN:` line under each requirement title and each user story; an English summary at the top of each steering file; one `EN:` line under each DEVLOG bullet. When the Chinese text changes, update its English line in the same edit.

比赛要求提交材料用英文或附英文翻译，评委会翻 `.kiro` 目录。英文只加在下面几处，其余照常用中文。

## 加在哪

1. **README**：根目录 `README.md` 用英文写。内容变了（状态、目录、局限）要同步改。
2. **需求文档**（`.kiro/specs/*/requirements.md`）：
   - 每条需求的标题下一行写 `EN: <英文标题>`。
   - 用户故事下一行写 `EN: As a ..., I want ..., so that ...`。
   - 验收标准、术语、出处行不加英文。

   ```markdown
   ### 需求 1：参考源登记和本地缓存
   EN: Source registration and local cache

   **用户故事：** 作为用户，我想……，以便……
   EN: As a user, I want ..., so that ...
   ```

3. **引导文档**（`.kiro/steering/*.md`）：front matter 之后、一级标题之后，写一段 `EN summary:`，3–5 句，说清这份文档规定了什么。
4. **DEVLOG**：每条要点下一行 `EN:`，规则见 `devlog.md`。

## 规矩

- 改中文时在同一次修改里改对应的英文，不留到以后补。
- 英文要能单独看懂：写事实、数字、文件名，不逐字硬译。
- 英文和中文意思不一致时，以中文为准，并当场改英文。
- `EN:` 行不是 `### ` 标题，不影响 `citation.md` 里按 `### 需求 N：` 切分需求。
