# LangChain Policy RAG 对比实验

## 定位

现有 SQLite FTS5 / BM25 Policy RAG 继续作为正式主链。LangChain 仅作为可选兼容层和离线 benchmark，不接入 API 默认路径。

## 实现边界

- 使用 `procureguard.db.seed_policies.MOCK_POLICIES` 的 10 条本地政策。
- 使用 `langchain-core==1.4.7` 的 `Document` 和 `BaseRetriever` 接口。
- 使用确定性词法评分和显式 alias map，不使用 embedding 或语义模型。
- 不联网、不调用 LLM、不需要 API Key、不读写业务数据库。
- `semantic_like_paraphrase` 只验证声明过的词法别名，不表示真实语义检索。

## 实测结果

8 条 fixture 覆盖精确关键词、policy ID、金额阈值、审批要求、类同义改写、多词查询、缺失政策和歧义查询。

| 实现 | Top-1 accuracy | Mean recall@3 |
| --- | ---: | ---: |
| SQLite FTS5 / BM25 | 0.750 | 0.750 |
| LangChain offline compatibility retriever | 1.000 | 1.000 |

完整逐案例命中、分数、来源与本地延迟见：

- `reports/langchain/langchain_policy_rag_comparison.json`
- `reports/langchain/langchain_policy_rag_comparison.md`

这些指标只属于当前本地 mock 政策 fixture，不是线上、生产或 official test 指标。本地延迟只用于证明脚本真实执行，不用于性能承诺。

重新生成报告：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark\run_langchain_policy_rag_comparison.py
```
