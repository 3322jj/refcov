---
inclusion: always
---

# DEVLOG 记录规则

EN summary: `docs/DEVLOG.md` is the development log that the submission write-up and blog draw from; add at least one entry per day, right after each piece of work. Record which Kiro features were used and how, problems found (including doc-vs-behavior mismatches), spec-flow vs. ad-hoc differences, property-test findings, and every time RefCov blocked its own development. Each bullet gets an indented `EN:` line. Record only what happened, never delete unflattering entries, and put new ideas in the "以后再做" (later) section instead of building them.

开发日记在 `docs/DEVLOG.md`，交作品时的"怎么用 Kiro"说明和博客都从这里取材料。每天至少一条，做完一件事就补记，不要攒到最后。

## 每天记什么

1. **用了哪个 Kiro 功能**：规格、钩子、引导文档、MCP、属性测试、powers、自定义 agent、子 agent、多会话等。写具体用法，不只写名字。
2. **遇到什么问题**：包括文档和实测不一致的地方，接着前面的编号往下记。
3. **规格流程和随口对话的差别**：同类事情两种做法各差在哪，例如漏掉了什么、返工了几次。
4. **属性测试抓到什么**：哪条性质、反例、改了哪里。没抓到就写没抓到。
5. **RefCov 拦了自己几次**：骨架能用之后，记每次被拦：哪天、读了几分之几、差点漏掉什么。

## 格式

- 标题：`## 日期（时段：一句话主题）`。
- 每条要点后面附一句英文，用 `EN:` 开头，单独一行缩进写在该条下面：

  ```markdown
  - 用 PreTaskExec 钩子拦住了没读完材料的任务开工。
    EN: A PreTaskExec hook blocked a task from starting until its cited units had been read.
  ```

- 英文要能单独看懂，写事实和数字，不写形容词堆砌。

## 规矩

- 只记真实发生的事。没做就写没做，没测就写没测，推测要标"推测"。
- 不为了好看造记录，也不删掉不好看的记录。
- 新点子记进"以后再做"一节，不动手做（见 `product.md` 范围冻结）。
- 写 DEVLOG 时不要写出钩子拦截用的标记词，避免把写日志这一步也拦掉。
