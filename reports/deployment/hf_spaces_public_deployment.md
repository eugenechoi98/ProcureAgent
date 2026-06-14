# Hugging Face Spaces 公网部署

## 公网 Demo 展示最终收口结果

- Hub：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App：https://eugene-98-procureguard-ai-demo.hf.space
- 远端 commit：`c1a6bccec34f2fca53a5890372854dc0ee9d2179`
- Runtime：`RUNNING`，硬件为 `cpu-basic`
- 中文页签：发票审核、模型实验、系统架构
- 远端文件：70 个，禁入文件：0 个

发票审核页增加“如何看本页”和 5 个中文案例摘要；模型实验页将 LoRA Guard 拦截亮点前移，并把完整指标、长表和 JSON 默认折叠；系统架构页强化受控 Agent 定位。三页签结构保持不变。

案例图片不含真实个人或企业数据，不是 SROIE 样本或 LayoutLMv3 单图推理结果，也不用于证明数据集级 F1。公网 HTTP、Gradio config 和 `run_audit` API smoke 已通过。

公网 `run_audit` API 继续通过：`vendor_name_mismatch + experimental_guard_fail` 返回中风险、转人工审批，并显示 Guard 未通过后回退确定性模板。

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
