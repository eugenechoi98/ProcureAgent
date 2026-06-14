# Hugging Face Spaces 公网部署

## 发票审核案例增强部署结果

- Hub：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App：https://eugene-98-procureguard-ai-demo.hf.space
- 远端 commit：`9691cf21d563ca92006d594f03608d4aade215f7`
- Runtime：`RUNNING`，硬件为 `cpu-basic`
- 中文页签：发票审核、模型实验、系统架构
- 远端文件：70 个，禁入文件：0 个

发票审核页新增 5 个合成发票图片案例，并按图片、字段抽取对比、三单匹配、审核证据、风险动作、审核解释六个区块展示。完整技术输出保持可核查，但默认折叠。

案例图片不含真实个人或企业数据，不是 SROIE 样本或 LayoutLMv3 单图推理结果，也不用于证明数据集级 F1。公网 HTTP、Gradio config 和 `run_audit` API smoke 已通过。

公网 `run_audit` API 继续通过：`normal_invoice + template` 返回低风险、自动通过、模板解释和完整审核报告 JSON。

## 人工浏览器验收

- 公网页面：PASS
- 中文化页面：PASS
- 发票审核页：PASS
- 模型实验页：PASS
- 系统架构页：PASS
- 前端错误：未发现
- 本地设备专项结果：桌面与 390px 窄屏通过
- 公网设备专项结果：未单独记录

## 边界

公网应用不会加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。模型实验页只展示真实离线 artifacts，不代表在线模型推理、生产服务或 official test。

用户已完成人工浏览器验收，当前状态：

```text
manual_browser_check_required=false
online_deployment_verified=true
production_ready=false
```
