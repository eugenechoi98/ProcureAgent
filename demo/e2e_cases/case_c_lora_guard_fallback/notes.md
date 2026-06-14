# LoRA Guard / fallback 证据边界

- 输入事实是固定 synthetic evaluation fixture，不是真实采购交易。
- 原始文本来自第一轮真实离线 LoRA 评测 artifact。
- Guard 使用当前生产代码离线执行，结论为 REJECT。
- fallback 使用当前确定性模板；LoRA 不参与风险判断。
