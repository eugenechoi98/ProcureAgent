# Phase 3 Explanation Evaluation Rubric

本评测只检查模型是否忠实解释输入事实，不评价或重算 Phase 2 的业务结论。

## 指标

### format_compliance

一条输出必须同时满足：

- 包含 `异常类型：`、`关键事实：`、`审核结论：` 三段。
- 覆盖输入中的全部异常类型。
- 包含该异常的关键单号、金额、数量或供应商事实。
- 原样包含输入的 `risk_level` 和 `recommended_action`。

汇总值为完全合规样本数除以总样本数。

### factual_consistency

检查输出中的发票号、采购订单号、收货单号、币种、金额、数量和供应商是否都能在 `input_facts`、`mismatches` 或 `evidence` 中找到。发现任一未知事实，该样本记为不一致。

### action_consistency

输出必须只包含输入的 `recommended_action`。模型不得把 `reject` 改成审批，也不得在正确动作之外追加互相矛盾的备选动作。

### anomaly_coverage

对每条样本计算“已提及异常数 / 输入异常总数”，再对所有样本取平均。该指标重点约束 `multi_issue_combination`。

### hallucination_rate

只要输出出现任一未知单号、金额、币种、政策条款或审批角色，该样本就记为 hallucination。汇总值为 hallucination 样本数除以总样本数，越低越好。

## 输入输出格式

评测数据使用 `data/phase3/generated/test.jsonl`。模型推理结果为 JSONL：

```json
{"sample_id": "phase3-amount_discrepancy-024", "explanation": "..."}
```

base 与 fine-tuned 必须使用同一 test split、同一生成参数和同一评测脚本。本轮尚未执行模型推理，因此不记录或伪造任何对比数字。

## 运行方式

```powershell
.\.venv\Scripts\python.exe scripts\phase3\evaluate_explanations.py `
  --dataset data\phase3\generated\test.jsonl `
  --base-predictions artifacts\phase3\predictions\base.jsonl `
  --fine-tuned-predictions artifacts\phase3\predictions\fine_tuned.jsonl `
  --output-dir artifacts\phase3\evaluation
```
