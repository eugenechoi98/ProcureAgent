# Hugging Face Spaces 公网部署

## 模型实验页展示优化结果

- Hub：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App：https://eugene-98-procureguard-ai-demo.hf.space
- 远端 commit：`5f541c99a11c59eaaa2b7dee579be946de544573`
- Runtime：`RUNNING`，硬件为 `cpu-basic`
- 中文页签：发票审核、模型实验、系统架构
- 远端文件：62 个，禁入文件：0 个

模型实验页现在先展示三项核心指标，再展示 LayoutLMv3 和 LoRA 实验；原始 JSON 证据统一收进默认折叠区。公开页面不再单独展示“缺失 artifacts”区域或重复的实时推理免责声明，manifest 中的原始边界证据保持不变。

公网 `run_audit` API 继续通过：`normal_invoice + template` 返回风险等级、建议动作、事实哈希和完整审核报告 JSON。

## 边界

公网应用不会加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。模型实验页只展示真实离线 artifacts，不代表在线模型推理、生产服务或 official test。

自动化浏览器已确认公网首屏，切换模型实验页时连接超时，因此继续保持：

```text
manual_browser_check_required=true
online_deployment_verified=false
```
