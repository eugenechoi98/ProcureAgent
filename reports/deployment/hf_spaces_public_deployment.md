# Hugging Face Spaces 公网部署

## 中文化结果

- Hub：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App：https://eugene-98-procureguard-ai-demo.hf.space
- 远端 commit：`49423f166a8a0b92063178c121d8130990c14757`
- Runtime：`RUNNING`，硬件为 `cpu-basic`
- 中文页签：发票审核、模型实验、系统架构
- 远端文件：62 个，禁入文件：0 个

发票审核页已增加中文“如何使用”说明，业务字段标签已中文化。模型实验页已增加离线 artifacts 说明和中文实验标题。系统架构页已改为中文链路和中文治理边界。

公网 `run_audit` API 继续通过：`normal_invoice + template` 返回风险等级、建议动作、事实哈希和完整审核报告 JSON。

## 边界

公网应用不会加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。模型实验页只展示真实离线 artifacts，不代表在线模型推理、生产服务或 official test。

自动化视觉浏览器在当前环境仍加载超时，因此继续保持：

```text
manual_browser_check_required=true
online_deployment_verified=false
```
