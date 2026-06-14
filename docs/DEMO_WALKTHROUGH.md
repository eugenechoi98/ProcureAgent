# ProcureGuard AI Demo Walkthrough

## 打开 Demo

访问 [Hugging Face Space](https://huggingface.co/spaces/eugene-98/procureguard-ai-demo)。
该 Demo 运行在 `cpu-basic`，不需要登录、API Key、GPU 或模型下载。

当前公网版本不支持上传任意发票并现场运行 LayoutLMv3。页面展示真实离线
checkpoint 证据链，以及轻量 CPU 审核逻辑和已验证审核结果。

## 3–5 分钟面试演示脚本

### 1. 一句话定位

“这是一个受控采购发票审核 Agent，不是让大模型直接决定风险的
autonomous LLM 系统。”

### 2. 案例 A：标准发票审核通过

1. 打开“发票审核”，保持默认案例 A。
2. 指出左到右三张图：真实 SROIE validation 图片、OCR bbox、
   LayoutLMv3 离线 checkpoint prediction。
3. 指出字段表来自 H0 证据包中的真实离线预测，不是网页现场推理。
4. 说明预测字段进入 Phase 2 审核链，完成三单匹配、Policy RAG 和风险规则检查。
5. 说明 PO/GRN 是 mock 采购上下文，因为 SROIE 不包含企业采购系统数据。
6. 指出最终低风险和自动通过由确定性规则生成，不由 LayoutLMv3 或 LoRA 决定。

### 3. 案例 B：日期版式挑战

1. 切换到案例 B，指出日期文本包含前缀和时间等版式噪音。
2. 展示日期 span 清理与标准日期重建。
3. 明确这是单样本可追溯证据，用来解释修复做了什么。
4. 数据集级 Date F1 `0.1423 -> 0.8764` 在“模型实验”页展示，
   不能靠这一张图证明整体提升。

### 4. 案例 C：LoRA 幻觉与回退

1. 切换到案例 C，说明本案例没有发票图片，输入是 synthetic evaluation fixture。
2. 展开技术明细，展示首轮真实离线 LoRA 原始输出。
3. 指出模型补出了输入中不存在的 `GRN-20260149`。
4. 展示真实 Guard 结果：`REJECT`，命中
   `unknown_identifier:GRN-20260149`。
5. 指出正式解释自动 fallback 到确定性模板。
6. 强调 LoRA 当前只保留为 `shadow / experimental / Phase 3I`
   候选，不是默认正式解释器。

### 5. 模型实验

1. 展示 OCR + Regex baseline Macro F1：`0.4387`。
2. 展示修复后 LayoutLMv3 Macro F1：`0.8067`。
3. 展示 Date F1：`0.1423 -> 0.8764`。
4. 说明这些指标来自 `local_validation_split_seed_42` 的
   `offline_checkpoint_inference`，`official_test=false`。
5. 展示第二轮 LoRA 未通过 hard gate，以及 Guard / fallback 为什么成为正式架构。

### 6. 系统架构

最后总结三层职责：

- 模型层负责字段抽取和受控解释实验。
- Agent 工具负责查询 PO、GRN、重复记录、政策和人工审核流转证据。
- 确定性规则负责风险等级与建议动作，Guard / fallback 保证解释不能篡改事实。

原 5 个合成案例保留在发票审核页的默认折叠区，只用于补充展示缺少
PO/GRN、供应商不一致和重复发票等流程分支，不是主证据链。

## 面试官追问回答

### Q1：这个网页能不能上传任意发票现场识别？

当前公网 Demo 不支持任意图片在线推理。它展示的是真实离线 checkpoint
证据链，以及轻量 CPU 审核规则链和已验证结果。在线上传与实时 LayoutLMv3
属于后续 live inference feasibility，不是当前已上线能力。

### Q2：右边字段是不是预设的？

A/B 的字段来自 H0 证据包中的真实离线 LayoutLMv3 checkpoint prediction，
不是网页现场推理，也不是手写成模型输出。PO/GRN 是 mock 采购上下文，
用于让字段进入三单匹配和风险审核。页面和 manifest 已分别标记模型字段、
mock 上下文与审核事实。

### Q3：为什么不把 LoRA 直接上线？

两轮 QLoRA 训练后，第二轮仍未通过 hard gate，并出现
`unknown_identifier`、unsupported approver 等幻觉风险。因此正式输出默认
使用确定性模板；LoRA 只保留为 `shadow / experimental / Phase 3I` 候选，
必须经过 Guard 才可能用于受控润色。

### Q4：这是 Agent 还是规则系统？

这是受控采购审核 Agent。模型负责字段抽取和受控解释，五个 Agent 工具负责
证据查询，风险等级和建议动作由确定性规则生成。采购审核要求结果可复现、
可审计，所以系统不会让 LLM 自由决定付款风险或随意规划固定业务依赖。

### Q5：mock PO/GRN 会不会让项目不真实？

不会。SROIE 是发票字段数据集，只提供 company、address、date、total，
不包含企业采购系统中的 PO/GRN。项目把真实发票字段抽取结果接入明确标注的
mock 采购上下文，用来演示三单匹配、Policy RAG 和风险规则链。关键是没有把
mock 数据冒充图片抽取结果或真实企业数据。

## 当前运行边界

- 公网 Demo 已通过 HTTP、Gradio config 和浏览器检查。
- 不执行任意图片在线推理。
- 在线 LayoutLMv3、网页实时真实 LoRA 和 GPU Space 未启用。
- 不上传模型权重，不使用外部模型 API、API Key 或 secrets。
- 该作品集 Demo 不是生产服务，也不代表 official test 或生产指标。
