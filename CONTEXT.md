# CONTEXT.md

## 当前目标
Phase 2 后端基础服务。

## 当前进度
- FastAPI 应用入口已完成。
- SQLite 接入、上传/查询、mock 处理链、人工审核基础闭环和接口测试已完成。
- 最小 smoke test 已打通：上传发票、查询轨迹、查询审核队列、提交 approved 决定。
- 全量测试通过：`22 passed`。

## 下一步
回到审查与总控对话验收，再决定是否进入 Agent 与规则模块。

## 注意事项
- 共享契约已冻结。
- 当前处理链是 mock，不代表真实审核逻辑。
- 本轮没有实现 OCR、LayoutLMv3、Agent 主链、完整 Risk Engine、LoRA、Docker 或 CI。

## 最后更新时间
2026-06-10
