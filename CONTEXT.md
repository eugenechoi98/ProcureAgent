# CONTEXT.md

## 当前目标
完成 Phase 2 真实规则链与 FastAPI 的集成收口。

## 当前进度
- 共享契约已完成。
- FastAPI 后端基础 mock 闭环已完成。
- Agent 与规则模块已完成：三单匹配、重复检测、Policy RAG、5 个工具执行、Risk Engine 和 Audit Trace。
- 当前 API 上传入口仍走 `mock_processor`，尚未切换至真实规则链。
- 当前基线：待提交 Agent 与规则验收 commit。

## 下一步
新开 Phase 2 集成收口对话，将真实 `agent_processor` 接入 API，保留 mock 模式，并补充端到端测试。

## 注意事项
- 共享契约保持冻结。
- `mock_processor` 不删除。
- 不在总控对话直接实现业务代码。

## 最后更新时间
2026-06-10
