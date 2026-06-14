# Phase 3I LoRA 后续路线评估

## 1. Executive Summary

推荐路线：**路线 D 继续作为正式默认路径，同时把路线 B 作为唯一优先实验，并在 B 中吸收路线 C 的 evidence citation 约束。**

当前不启动第三轮自由文本 LoRA。两轮结果说明，训练 loss 收敛不等于受控解释能力达标。第二轮只修改事实约束 prompt 和六段式 gold answer，但 fine-tuned 仍未通过任何 hard gate：

| metric | Phase 3E fine-tuned | Phase 3G fine-tuned | hard gate |
| --- | ---: | ---: | ---: |
| format_compliance | 0.1500 | 0.0000 | >= 0.9000 |
| factual_consistency | 0.8000 | 0.9000 | >= 0.9500 |
| action_consistency | 0.8500 | 0.4500 | >= 0.9000 |
| anomaly_coverage | 0.7333 | 0.4250 | >= 0.9000 |
| hallucination_rate | 0.2000 | 0.1500 | <= 0.0500 |

Phase 3H 的 Template / Guard / Fallback 架构仍然合理。它把模型限制在解释层之后，保证模型失败不会改变 `risk_level`、`recommended_action` 或 `anomaly_types`。当前 Guard 能拦截已知格式的未知单号、金额、供应商、政策角色和决策变化，但不能证明自然语言的语义等价，也不能可靠识别隐含推断、同义改写和未建模实体。

## 2. What Failed In Phase 3E / 3G

### Phase 3E

- 微调明显学会了建议动作和部分异常覆盖，但 format 只有 0.15。
- 20 条测试中有 4 条 hallucination，包括补全未知金额、GRN 和供应商关系。
- 首轮 gold answer 只有三段，200 条答案都没有显式负约束。
- 失败主要说明模型学会了任务意图，却没有学会事实边界。

### Phase 3G

- 第二轮保持模型、split、seed、训练参数和 evaluator 不变，只修改 prompt 与 gold answer。
- 200 条 gold answer 全部改成六段式，并显式写缺失字段和禁止补全。
- 训练 loss 从 1.4592 降到 0.1458，validation loss 降到 0.139261，但五项 hard gate 全部失败。
- 仍出现 `PO-77450099`、`GRN-unknown` 和“审批人”等无依据内容。
- action consistency 和 anomaly coverage 比首轮明显下降，format compliance 变为 0。

这不是单一的“训练不充分”。更准确的结论是：小数据、模板化目标、自由文本任务、0.5B 模型容量和当前评测可观测性共同造成失败。

## 3. Failure Taxonomy

### 3.1 数据层

| 问题 | 可见证据 | 影响指标 | 第三轮只改数据能否解决 |
| --- | --- | --- | --- |
| 数据量小 | 仅 200 条，train 160 条 | 全部指标，尤其泛化稳定性 | 只能缓解，不能保证 |
| synthetic 且同质 | 6 个供应商、4 个币种、固定单号模式、固定生成器 | factual、hallucination | 不能单独解决 |
| 输出高度模板化 | 200 条均为同一六段结构 | format；也可能鼓励表面记忆 | 可改善契约学习，但已有第二轮反证 |
| 多异常覆盖不足 | 175 条单异常，只有 25 条双/三异常 | anomaly_coverage | 可明显改善 |
| 缺少真正 hard negative | 66 条含缺失字段负约束，但没有成对的“错误补全 -> 拒绝”训练目标 | factual、hallucination | 可改善 |
| 动作分布不完整 | 168 条 `request_human_approval`、32 条 `reject`，没有 `auto_approve` | action_consistency | 可改善，但本任务本身是异常解释 |
| split 生成机制同源 | train/validation/test 使用同一模板、词表和编号规律 | 指标可信度与泛化判断 | 需要独立挑战集 |

第三轮若只扩充同类 synthetic 模板，收益有限。真正有价值的数据改造应加入成对 hard negatives、未知字段反例、格式扰动、多异常长尾和独立人工挑战集。

### 3.2 Prompt / Gold Answer 层

- Phase 3F 明确改善了数据契约：六段齐全、缺失值显式、禁止补全规则清楚。
- 但自由文本 SFT 仍要求模型同时完成字段复制、集合覆盖、格式序列化、中文表达和事实约束，任务耦合过多。
- gold answer 是自然语言模板，模型可以用语义近似但格式不精确的文本获得低 loss。
- evaluator 要求动作和风险值按英文枚举原样出现；模型若翻译或改写，语义可能接近但仍判失败。这对正式机器契约是合理要求，但说明任务应改成 schema-first，而不是继续依赖自然语言服从。
- 当前 evaluator 的 `REQUIRED_SECTIONS` 只检查三段，而 Phase 3F gold answer 定义六段。gold 本身仍能通过测试，但训练契约、Phase 3H 模板契约和评测契约没有完全统一。

结论：不建议继续把自然语言 SFT 作为主攻方向。建议改为 structured explanation schema，再由确定性 renderer 输出自然语言。

### 3.3 模型能力层

- Qwen2.5-0.5B 可以学习常见表面模式，但当前证据不足以支持它稳定执行多字段复制、集合完整性和禁止推断。
- 4-bit QLoRA 可能增加边缘格式不稳定，但现有实验没有全精度或非量化对照，不能把失败归因于量化。
- 换 1.5B/3B/7B 可能提高指令遵循和格式稳定性，也会增加 GPU、推理、部署和评测成本。
- 当前作品集已经有两轮真实训练、失败分析和 Guard/Fallback 证据。继续堆训练成本的边际价值低于完成结构化、可审计的解释契约。

结论：0.5B 不适合承担默认自由文本解释器；当前阶段也不推荐直接换大模型。

### 3.4 评测层

hard gate 不应降低。采购审核解释中，未知单号、错误动作和漏报异常都可能误导人工审核，0.95 factual、0.90 action/coverage/format 和 0.05 hallucination 上限并不过严。

当前 evaluator 风险：

- 第二轮本地没有 prediction、evaluation 和 manifest，仅有用户确认的汇总报告与 3 个 hallucination 例子。
- 因此无法逐样本复算 `format_compliance=0`，也无法区分是章节标点、截断、动作枚举、关键事实缺失还是整体格式漂移。
- format 是五个条件的全合取，任一条件失败整条记 0，适合做 gate，但不适合单独定位根因。
- 正则只能发现已建模格式；隐含虚构、同义政策角色和未匹配的金额/供应商表达可能漏检。
- `hallucination_rate` 按“样本是否至少有一次违规”计数，适合风险门禁，但应同时报告 violation count 和类型分布。

需要新增 evaluator debug report，但应先恢复第二轮逐样本 predictions。建议输出每个 format component、截断状态、生成 token 数、违规类型、原始输出和 gold diff。不能为了过 gate 降低门槛。

### 3.5 任务定义层

根本问题是把“受控解释”定义成了自由文本生成。系统已经有 Canonical Audit Facts、确定性风险和建议动作，模型不需要重新决定或重新组织这些关键字段。让模型先自由生成，再用正则证明它没有改事实，验证成本高于直接生成结构化增量。

更合适的任务是：

```text
Canonical Audit Facts
-> schema-constrained explanation plan
-> evidence-id validation
-> deterministic natural-language renderer
```

模型只允许生成 `explanation_bullets` 等低风险语言字段；决策字段只能复制并由程序做相等校验。

## 4. Candidate Route Comparison

| 路线 | 收益 | 主要风险 | 工作量 | 推荐 |
| --- | --- | --- | --- | --- |
| A 第三轮自然语言 LoRA | 可验证 hard negatives 是否改善 0.5B | 仍是自由文本；第二轮 artifacts 不完整；可能继续无效训练 | 中 | 否，暂缓 |
| B Structured Output First | 将格式、复制字段、集合覆盖变成可校验 schema；renderer 可复现 | JSON 仍可能填错值；需要 schema validator 和新 evaluator | 中 | **是，优先实验** |
| C Retrieval-Grounded Explanation | 每条说明绑定 evidence id，来源清楚 | 仅有 citation 不代表句子忠实；需句子到证据的校验 | 中高 | 是，作为 B 的第二层 |
| D Template 默认 + shadow research | 当前最稳、零模型依赖、作品集可信 | 语言灵活性有限 | 低 | **是，正式默认** |
| E 更大模型/强解码 | 可能提高指令和格式服从 | 成本高；仍需 Guard；不能修复任务定义 | 高 | 当前否 |

## 5. Recommended Route

推荐路线：**D 作为正式架构不变，下一阶段只执行 B；B 通过后再加入 C。**

原因：

1. Demo 已经通过真实失败案例证明 Guard/Fallback 的价值，不需要再靠第三轮训练证明“做过 LoRA”。
2. Structured output 把最重要的风险从自然语言猜测变成字段级校验，更符合现有 Canonical Audit Facts。
3. evidence id 可以让每条解释追溯来源，但应建立在 schema 已稳定的基础上。
4. 该路线不让模型决定风险、动作或异常类型，与 Phase 3H 完全兼容。
5. 作品集能体现“发现模型边界后重定义任务”的工程判断，而不是为了指标继续试参。

建议 schema：

```json
{
  "anomaly_types": [],
  "missing_fields": [],
  "cited_evidence_ids": [],
  "risk_level_copy": "medium",
  "recommended_action_copy": "request_human_approval",
  "explanation_bullets": []
}
```

其中前五类字段必须与 Canonical Audit Facts 做确定性相等或子集校验；`explanation_bullets` 每条必须绑定至少一个允许的 evidence id。最终中文文本由确定性 renderer 生成。

## 6. Non-Recommended Routes

- 不推荐立即做第三轮自由文本 LoRA：没有先补齐第二轮逐样本诊断，继续训练无法确认改动是否击中根因。
- 不推荐直接换更大模型：它可能改善服从性，但不会自动解决证据绑定、输出契约和审计问题。
- 不推荐降低 hard gate：这会把已知风险包装成“通过”，与采购审核定位冲突。
- 不推荐仅靠 Guard 放行自由文本：当前 Guard 是规则检测器，不是语义证明器。

## 7. Required Experiments If Continuing

下一步如果执行，应先做：

1. 定义 `StructuredExplanation` schema、字段不变量和拒绝原因，不接 API、不改 Phase 2。
2. 新建 20 至 50 条独立 challenge set，覆盖未知 PO/GRN/金额、无依据审批人、同义改写、多异常漏项和冲突动作。
3. 先对 base model 做 JSON/schema constrained decoding，不训练，建立结构化 baseline。
4. 输出 evaluator debug report：逐字段 exact match、JSON validity、evidence citation precision/recall、unsupported claim rate。
5. 只有 baseline 明确暴露可由训练解决的单一问题时，才考虑一次 structured-output LoRA。

第三轮训练的 decision gate：

- 第二轮逐样本 artifacts 可复算，或明确记录无法恢复；
- structured baseline 已完成；
- 单一变量写清楚；
- challenge set 与训练模板不同源；
- hard gate 保持不变；
- 任何模型输出仍必须经过 Phase 3H fallback。

## 8. Impact On Phase 3H

Phase 3H 保留，不需要推翻：

- `template` 继续是默认正式输出。
- `shadow` 继续只记录模型输出，最终仍返回模板。
- `experimental` 只有 schema 校验、evidence 校验和 Guard 全部通过才允许使用。
- 高风险、provider 错误、空输出、解析失败和非法字段继续 fallback。
- Structured output validator 应放在 Controlled Rewrite 与现有 Output Guard 之间。
- 现有正则 Guard 作为 defense-in-depth 保留，不承担唯一语义验证责任。

当前 Guard 已覆盖本项目已观察到的 `GRN-20260149`、`PO-77450099`、`8100.24` 和“审批人”等模式。它不能覆盖隐含因果、委婉政策承诺、未建模实体格式、证据与句子之间的语义不一致。

## 9. Interview Explanation

两轮 LoRA 都是真实训练，但第二轮即使 loss 很低，事实、动作、异常覆盖和格式仍没有过门禁。这里没有继续调参，而是把问题重新拆开：规则层负责结论，模板负责正式输出，模型只做可选润色；下一步若继续，就先输出可校验 JSON，再由程序生成自然语言。这样既保留了模型实验价值，也不会让模型失败影响采购审核结论。

## 10. Next-Step Decision Gate

当前决策：

```text
正式路径：路线 D
优先研发实验：路线 B
第二阶段约束：路线 C
暂停：路线 A、路线 E
```

Phase 3I 完成后，由总控决定：

- 执行一个不训练的 structured-output baseline；或
- 在当前作品集阶段暂停 LoRA，保留已有两轮训练和失败治理证据。

## Evidence Availability

- 首轮真实 artifacts 在仓库外本地目录可见，包含 adapter、predictions、evaluation 和 manifest；本报告未修改这些文件。
- 第二轮 artifacts 在当前 workspace 不存在。仓库仅有用户确认的运行配置、loss、汇总指标和 3 个 hallucination 例子。
- Demo case C 使用首轮真实离线输出，并由当前 Guard 真实复核后 fallback。
- 本报告没有推断或编造缺失的第二轮逐样本输出。
