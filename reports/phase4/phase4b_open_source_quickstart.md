# Phase 4B Open-source Quickstart Report

## 结果

Phase 4B：PASS。

仓库现已具备面向 clean clone 的 CPU-only Quickstart、真实可运行的 synthetic AuditReport smoke、MIT License、环境变量样例、隐私/数据边界、sample bundle 和分层测试入口。

## 关键交付

- README 前部新增 10 分钟 Quickstart，并服务面试官、开发者和试用者三类读者。
- `.env.example` 只列当前实际支持的 `DATABASE_PATH` 和 `UPLOAD_DIR`，没有伪造环境模式或日志配置。
- 新增 MIT License 和独立隐私/数据边界说明。
- 新增 synthetic invoice、mock procurement context、稳定预期摘要和 sample audit 脚本。
- 新增 smoke、phase1、phase2、phase3、full 的 CPU-only 分层测试说明。
- README 和核心部署文档中的本机绝对路径已改为相对链接或仓库外 artifacts 描述。

## Sample 结果

`scripts/samples/run_sample_audit.py` 使用内存 SQLite 和现有 Phase 2 确定性主链，输出：

- `risk_level=low`
- `recommended_action=auto_approve`
- `po_match=true`
- `goods_receipt_match=true`
- `explanation_source=template`

该流程没有加载 LayoutLMv3、LoRA 或网络服务，也没有写项目数据库。

## 开源边界

- HF Space 仍是 public portfolio demo，不是生产产品。
- 不建议上传真实敏感发票，系统不能作为付款或财务最终决策依据。
- 数据集和基础模型保留原始许可；MIT 只覆盖本仓库代码。
- 权重、checkpoint、adapter、缓存、原始训练 artifacts、大型数据压缩包和本地上传不提交 Git。

## 验证

- JSON 报告解析：5 个 JSON 文件通过。
- Markdown 链接：检查 25 个本地链接，无断链。
- `.env.example` secret scan：通过，只有 2 个当前生效变量，无 secret。
- LICENSE：存在。
- sample audit：通过。
- Phase 4B pytest：1 passed。
- `pip check`：无依赖冲突；API/文档/sample 测试 21 项通过；Demo readiness 通过；`git diff --check` 通过。
- 全量测试未运行；本轮只涉及交付文档、样例和单一 smoke，且工作区已有其他线程未提交 Phase 3 改动。

## 下一步

进入 Phase 4C User-facing MVP Input Flow。在线 LayoutLMv3 继续不作为 blocker。
