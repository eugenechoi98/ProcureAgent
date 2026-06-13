# CONTEXT.md

## 当前目标
Engineering Closure Sprint 已完成本地实现与验证，等待合并和集中验收。

## 当前进度
- LangChain Policy RAG 可选兼容层和 8 条真实离线 benchmark 已完成；SQLite FTS5 / BM25 仍是正式主链。
- Docker Compose 的 API 与 Unified Demo CPU-only 配置已完成；当前环境无 Docker CLI，runtime 未验证。
- GitHub Actions CPU-only CI 和 Portfolio Release Readiness 聚合检查已完成。
- HF Spaces 仍只存在本地发布包，Space 未创建、未上传、公网链接未验证。

## 下一步
完成开发分支回归、受控合并 `main`、合并后回归并 push `origin/main`；之后只等待 Batch C.2 网页操作。

## 注意事项
- 不加载或下载模型，不启动 GPU，不重新训练，不修改 Phase 1、Phase 2、Phase 3H 业务语义或数据库 schema。
- 本地 release readiness 不等于在线部署验证。
- Docker config ready；Docker runtime not verified in current environment。

## 最后更新时间
2026-06-13
