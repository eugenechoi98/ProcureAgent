# Hugging Face Spaces 公网部署

## 公网 Demo 展示最终收口结果

- Hub：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App：https://eugene-98-procureguard-ai-demo.hf.space
- 远端 commit：`1235f47642277cb9c03c45f2ea44f8632d990710`
- Runtime：`RUNNING`，硬件为 `cpu-basic`
- 中文页签：发票审核、模型实验、系统架构
- 远端文件：144 个，禁入文件：0 个

发票审核页以 3 个 H0 端到端证据链案例为主视图，原 5 个合成流程案例保留在默认收起的补充区；模型实验页增加返回案例 A/B 查看完整链路的提示；系统架构页明确离线证据包与 CPU 运行边界。三页签结构保持不变。

案例 A/B 使用 SROIE validation 图片并保留 CC BY 4.0 归属。人工复核仅发现企业地址、电话和订单信息，未发现可识别自然人客户姓名，本次不做遮罩。单图证据不用于证明数据集级 F1。公网 HTTP 和 Gradio config 已通过。

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
