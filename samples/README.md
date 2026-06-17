# Samples

此目录只保存轻量 synthetic 样例，用于 clean-clone smoke。它不包含真实企业发票、真实 PO/GRN、模型权重或受限制数据集。

## 内容

- `invoices/clean_invoice.json`：synthetic 结构化发票字段。
- `procurement_context/mock_po_grn.json`：与项目 seed 数据一致的 mock PO/GRN 摘要。
- `expected_outputs/clean_invoice_summary.json`：稳定预期字段，不固定随机 trace ID。
- `manual_audit/`：Phase 4C 标准通过、金额不一致和缺 GRN 请求，以及稳定预期摘要。

## 运行

```powershell
.\.venv\Scripts\python.exe scripts\samples\run_sample_audit.py
```

脚本使用内存 SQLite，调用现有 Phase 2 规则主链并向 stdout 输出 AuditReport JSON。它不运行 OCR/LayoutLMv3，不加载 LoRA，不访问网络，也不写项目数据库。

样例中的 `extraction_model=synthetic-manual-input-v1` 表示字段由样例直接提供，不是图片模型预测。

## Manual Audit MVP

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case all
```

该脚本直接调用产品化 service，三条请求都明确使用 `manual_input` 和 `explicit_mock_context`。输出包含 AuditReport、source labels、fallback status 和付款权限边界。

Phase 4D 支持可选 review 和导出：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case amount_mismatch --export json --output-dir samples\manual_audit\generated
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case missing_grn --review "Need PO owner confirmation" --export markdown --output-dir samples\manual_audit\generated
```

`generated/` 不提交 Git；预期导出结构见 `expected_export_json.json` 和 `expected_export_markdown.md`。
