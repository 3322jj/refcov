# 样例需求文档（任务 10 的出处检查测试用，内容是编的）

简介里的引用不属于任何需求，不算：[ref:demo/简介里的引用]

### 需求 1：出处行里一个有效引用
EN: One valid reference on the source line

#### 验收标准

1. THE 骨架 SHALL 正常。

出处：[ref:demo/Hooks]

### 需求 2：只有行内引用，没有出处行
EN: Inline reference only

#### 验收标准

1. THE 骨架 SHALL 用退出码 2 拦截。[ref:demo/退出码@2]

### 需求 3：没有出处
EN: No source at all

#### 验收标准

1. THE 骨架 SHALL 什么都不引用。

### 需求 4：单元不存在
EN: Unknown unit

出处：[ref:demo/没有这个单元]

### 需求 5：参考源不存在
EN: Unknown source

出处：[ref:nosuch/Hooks]

### 需求 6：一个有效、一个无效
EN: One valid and one invalid reference

出处：[ref:demo/Hooks] [ref:demo/exit]

### 需求 7：文字出处
EN: Text source only

出处：交接说明·核心功能 3；外部审阅 A6。

### 需求 8：特殊字符
EN: Special characters in unit IDs

出处：[ref:rules/15.-Entrant’s-Personal-Information][ref:rules/6.-Judges-&-Criteria@2] [ref:dec-a/分析-#4-附：默认豁免]。

### 需求 9：手打直引号
EN: Straight quote typed by hand

出处：[ref:rules/15.-Entrant's-Personal-Information]

### 需求 10：参考源 ID 写成大写
EN: Upper-case source ID

出处：[ref:Demo/Hooks]

### 其他说明（不是需求）

这一块不属于需求 10：[ref:demo/Hooks]

### 需求 11：无效引用加文字出处
EN: Invalid reference plus text

出处：[ref:demo/exit]；第二稿审阅第 9 条

### 需求 12：出处行之外的文字不算未转换
EN: Text outside the source line does not count

（已删除：某条验收标准。出处：外部审阅 C2。）
