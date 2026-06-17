# Privacy And Data Boundaries

## 当前定位

ProcureGuard AI 是研究型受控采购发票审核原型和 public portfolio demo，不是生产财务系统。它不能作为付款、合规、税务或财务最终决策依据。

## 本地数据存储

- FastAPI 默认把 SQLite 数据写到 `data/procureguard.db`。
- 上传文件默认写到 `uploads/`。
- 两个路径可通过 `.env.example` 中的 `DATABASE_PATH` 和 `UPLOAD_DIR` 修改。
- 当前没有产品级加密、认证、多租户隔离、保留期限、自动删除、删除 SLA、备份或灾难恢复策略。
- 删除本地数据前应先停止服务并自行确认路径；仓库不提供自动清理真实数据的承诺。

因此，请勿上传真实身份证明、银行信息、税号、供应商机密、合同价格或其他敏感发票数据。

`POST /api/mvp/manual-audit` 不接收文件，并在请求级内存 SQLite 中处理手动字段与显式 mock context；请求结束后该临时数据库被关闭。但当前仍没有认证、请求日志脱敏、速率限制或正式隐私策略，因此也不应通过该入口提交真实敏感数据。

Phase 4D 会在 API 进程内存中保留 Manual Audit 请求、结果和 reviewer note，直到服务重启。它没有加密、访问控制、删除 SLA 或持久审计保证，因此 reviewer note 同样不得包含真实敏感信息。

Phase 4F extraction spike 在本地读取指定图片，并把 OCR token、bbox、字段候选、环境摘要和可选可视化写到用户指定的 output directory。该目录没有自动加密、脱敏或删除机制，因此只能使用公开、synthetic 或明确获准的测试图片，不得使用真实敏感发票。输出也可能包含原始 OCR 文本和位置坐标。

## 公网 Demo

- Hugging Face Space 是公开作品集 Demo，不接受任意真实发票并在线运行 LayoutLMv3。
- A/B 案例使用公开 SROIE 图片和真实离线 checkpoint prediction；PO/GRN 是 mock 采购上下文，不是企业系统数据。
- C 案例使用真实离线 LoRA artifact，但输入事实是 synthetic evaluation fixture。
- 公网 Demo 不运行在线 LoRA，也不连接真实 ERP、采购或付款系统。

## 模型与决策边界

- `risk_level` 和 `recommended_action` 只由确定性规则生成。
- deterministic template 是正式默认解释路径。
- LoRA、Structured Output 和 Evidence Citation 仍是 shadow、experimental 或 offline research。
- 模型输出不能覆盖规则生成的风险等级、建议动作或异常类型。

## 开源数据边界

- 仓库代码使用根目录 [LICENSE](../LICENSE) 中的 MIT License。
- SROIE、Voxel51 `scanned_receipts`、CORD 和基础模型各自受原始发布方许可与使用条款约束，不因本仓库采用 MIT License 而改变。
- 模型权重、checkpoint、adapter、缓存、原始训练 artifacts 和受限制数据集不提交 Git。
- `samples/` 只允许轻量 synthetic 数据或明确可公开再分发的数据。

发布或部署前，使用者需要自行核对数据集、模型和企业数据适用的许可、隐私与合规要求。
