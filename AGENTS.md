# AGENTS.md

## 目标
本文件用于说明当前项目的本地运行、文件处理、代码规范和文档维护规则。  
开始当前项目任务时，优先读取本文件，并按这里的规则执行。

## 多对话协作分工
本项目复杂度较高，默认拆成 6 个长期对话并行推进，避免单个对话上下文过长、职责混乱。

1. 审查与总控对话：只做架构理解、任务拆分、阶段审查、代码审查、风险检查和下一步排序。本对话属于这一类。
2. Phase 1 模型抽取对话：负责 LayoutLMv3、PaddleOCR、SROIE/CORD 数据预处理、训练 Notebook、字段级 F1 和错误分析。
3. Phase 2 后端基础对话：负责 FastAPI、SQLite schema、Pydantic 模型、上传/查询接口、mock 数据和基础测试。
4. Phase 2 Agent 与规则对话：负责三单匹配、重复检测、Policy RAG、工具函数、Agent function calling、Risk Engine 和 Audit Trace。
5. Phase 3 LoRA 对话：负责异常说明训练数据、Qwen2.5-0.5B LoRA SFT、base vs fine-tuned 对比和解释质量评测。
6. 工程交付对话：负责 Docker Compose、GitHub Actions CI、README、部署说明、Demo 材料和最终开源整理。

协作规则：
- 每个开发对话只改自己模块内的文件；跨模块接口必须先在审查与总控对话确认。
- 审查与总控对话不直接大规模写业务代码，优先负责发现问题、定接口、定顺序、验收结果。
- 新对话开始时先读取 `AGENTS.md` 和总架构文件，再读取该模块已有代码和文档。
- 每个阶段完成后，由对应开发对话更新实现与测试，再回到审查与总控对话做审查和下一步决策。

## 新对话交接模板
每次开启新对话时，第一句按下面模板说明，保证新对话先理解整体架构和自己的模块边界。

通用模板：
```text
这是 ProcureGuard AI 项目的【模块名】开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责【模块边界】，不要修改其他模块。
如果发现跨模块接口问题，先暂停并说明，需要回到审查与总控对话确认。
现在请开始【本轮具体任务】。
```

工程共享契约对话：
```text
这是 ProcureGuard AI 项目的工程共享契约开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责 Pydantic 模型、SQLite schema、状态流、5 个工具接口、Policy RAG mock 数据和最小测试，不要实现模型训练、Agent 主链或 Docker。
如果发现跨模块接口问题，先暂停并说明，需要回到审查与总控对话确认。
现在请开始搭建 procureguard 项目骨架，并实现共享契约层。
```

Phase 1 模型抽取对话：
```text
这是 ProcureGuard AI 项目的 Phase 1 模型抽取开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责 LayoutLMv3、PaddleOCR、SROIE/CORD 数据预处理、OCR baseline、训练 Notebook、F1 评测和错误分析，不要修改后端 API、Agent 或部署文件。
如果需要新增字段或改变模型输出 schema，先暂停并说明，需要回到审查与总控对话确认。
现在请开始搭建 Phase 1 的目录、脚本和 Notebook 骨架。
```

Phase 2 后端基础对话：
```text
这是 ProcureGuard AI 项目的 Phase 2 后端基础开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责 FastAPI、SQLite 连接、上传/查询接口、mock 数据和基础测试，不要实现模型训练、LoRA 或部署。
如果需要修改共享模型、数据库 schema 或工具接口，先暂停并说明，需要回到审查与总控对话确认。
现在请开始实现后端基础服务。
```

Phase 2 Agent 与规则对话：
```text
这是 ProcureGuard AI 项目的 Phase 2 Agent 与规则开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责三单匹配、重复检测、Policy RAG、5 个工具函数、Agent function calling、Risk Engine 和 Audit Trace，不要修改模型训练、后端基础路由或部署。
如果需要修改共享模型、数据库 schema 或工具接口，先暂停并说明，需要回到审查与总控对话确认。
现在请开始实现 Agent 与规则闭环。
```

Phase 3 LoRA 对话：
```text
这是 ProcureGuard AI 项目的 Phase 3 LoRA 异常说明开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责异常说明训练数据、Qwen2.5-0.5B LoRA SFT、base vs fine-tuned 对比和解释质量评测，不要修改后端 API、Agent 主链或部署。
如果需要修改 AuditReport 字段或异常输入格式，先暂停并说明，需要回到审查与总控对话确认。
现在请开始搭建 LoRA 数据与 Notebook 骨架。
```

工程交付对话：
```text
这是 ProcureGuard AI 项目的工程交付开发对话。
请先读取 AGENTS.md、CONTEXT.md、DECISIONS.md、TIMELINE.md 和 ProcureAgent_AI_Engineering_Design.md。
本对话只负责 Docker Compose、GitHub Actions CI、README、部署说明、Demo 材料和最终开源整理，不要修改核心业务逻辑。
如果部署或 CI 暴露出跨模块接口问题，先暂停并说明，需要回到审查与总控对话确认。
现在请开始整理工程交付文件。
```

## 称呼
- 每轮回复开头先称呼我 `eugene`

## 文件与编码
- 所有文件读写默认使用 UTF-8 编码
- 修改文件时不要改变原有编码
- 处理含中文内容时，不使用 sed/awk，优先使用 Python 或 Node.js
- PowerShell 读取中文文件时：
  - 先执行 `chcp 65001`
  - 读取文件使用 `Get-Content -Encoding UTF8`
- 代码注释统一使用中文

## 输出规则
- 每次最终回复都附上“面试知识点”
- 面试知识点要围绕本轮真实工程决策来写，不写空泛定义
- 面试知识点必须用最简单、最容易懂的表达
- 面试知识点默认只回答三件事：
  - 这轮做了什么
  - 这个东西是用来干什么的
  - 为什么这轮要这么做
- 不要写抽象术语堆砌，不要写像论文或架构评审那样的表达
- 默认用口语化短句，让非本项目的人也能一眼看懂
- 为方便网页版 GPT 接收交接内容，中间更新和最终回复都要节省上下文，只保留任务结论、关键改动、验证结果、风险和未完成项
- 默认不粘贴代码、完整 diff、长日志、完整文件清单或重复背景；只有用户明确要求时才展开
- 文件较多时按模块概括，测试输出只报告命令类别、通过数量和关键错误，不逐条罗列



## Python 环境
- 优先使用项目本地虚拟环境
- Windows 使用 `.venv\Scripts\python.exe`
- 不直接使用系统 `python`

## 文档读取顺序
1. `AGENTS.md`
2. `CONTEXT.md`
3. `DECISIONS.md`
4. `TIMELINE.md`
5. `VALIDATION_SPEED_POLICY.md`
6. `README.md`
7. `ARCHITECTURE.md`
8. `DEPLOYMENT.md`

## 文档维护规则

### CONTEXT.md
始终保持极简，只保留当前工作现场，内容包括：
- 当前目标
- 当前进度
- 下一步
- 注意事项
- 最后更新时间

规则：
- 内容过时直接覆盖
- 不保留历史版本
- 保持简短，便于新线程快速接手

### TIMELINE.md
用于按日期索引项目改动，便于快速定位问题来源。

规则：
- 每次阶段性变更后追加一条
- 每条一行，一句话即可
- 只写“做了什么”，不展开原因和过程

示例：
- 2026-04-17：调整菜单结构字段，前端改为分组展示
- 2026-04-15：从 OCR-first 改为视觉模型直出

### DECISIONS.md
用于记录关键设计决定。

适用场景：
- 技术路线改变
- 方案取舍
- 明确放弃某方案及原因

规则：
- 只写“为什么这样做”
- 不写长过程
- 一条决策尽量独立成段，便于后续查找

### README.md
用于面向使用者说明项目。

仅在以下情况更新：
- 功能有变化
- 项目说明需要补充
- 运行方式有明显变化

内容保持简洁，重点包括：
- 项目是做什么的
- 技术怎么组成
- 功能列表
- 待办事项

### ARCHITECTURE.md
用于记录项目结构。

仅在结构变化时更新，内容包括：
- 模块职责
- 调用关系
- 核心设计

### DEPLOYMENT.md
用于记录操作流程。

仅在以下内容变化时更新：
- 本地运行方式
- 测试方式
- Git 流程
- 部署流程

内容保持简短清晰，重点包括：
- 本地启动与测试方法
- 常用测试命令
- Git 基本流程（提交 / 分支 / 合并）
- 部署步骤
- 部署后验证方法
- 必要注意事项

### RESEARCH.md
用于记录外部参考结论。

规则：
- 仅在进行了 skills.sh、GitHub 或其他外部搜索后更新
- 记录结论，不记录冗长搜索过程
- 目标是避免重复搜索

---

## 代码习惯
- 调试问题时，先确认根因和影响范围，再修改，不做表面修复
- 涉及数据删除、数据库变更或高风险操作，必须先确认
- 需求不清晰时，先提问再实现，不自行扩大需求
- 避免重复执行任务或无意义多轮测试

---

## 代码规范
- 单个文件尽量控制在 500 行以内，过长时考虑拆分
- 函数尽量保持单一职责
- 文件顶部写简短中文注释，说明用途
- 关键函数写一行中文注释说明作用
- 不硬编码配置、路径或密钥，统一放入配置文件
- 所有错误必须有明确提示或日志，不能静默失败


## 验证原则
- 当前项目仍处于 0->1 早期阶段
- 默认采用 Early-stage Lightweight Review
- 发现明显 bug 直接修复并重跑相关验证
- 不在错误工作区上继续开发或验证

## Command Output

Protect context usage. **Any command with unknown or potentially large output must be byte-capped.**

Default pattern:

```bash
COMMAND 2>&1 | head -c 4000
```
