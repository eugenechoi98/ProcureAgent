# LoRA Explanation Lab

本目录展示 Phase 3 两轮 QLoRA 真实离线实验结果。

固定口径：

- Model: `Qwen/Qwen2.5-0.5B-Instruct`
- Runtime: ModelScope A10 离线实验
- 当前 Web Demo 不实时加载 Qwen 或 LoRA。
- 第二轮 adapter 未通过上线 hard gate，不接 API，不作为默认用户输出。

重要缺失项已经显式记录：

- 第一轮 committed report 没有训练 loss 曲线。
- 第二轮本地 checkpoint、adapter、predictions 或真实 runtime artifacts 副本不存在。

这些缺失项不能用推测、重训或伪造数据补齐。
