# Hugging Face Spaces Public Deployment

## Result

- Hub: https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App: https://eugene-98-procureguard-ai-demo.hf.space
- Visibility: public
- Remote commit: `d1d12ae4529b47c34b6b4bd50cd27d0303cfa6c2`
- Runtime: `RUNNING` on `cpu-basic`
- Remote files: 62, including the Hub-generated `.gitattributes`
- Forbidden remote files: none

The Hub page, App root, and Gradio config returned HTTP 200 without login. The
public `run_audit` API completed `normal_invoice + template` and returned a low
risk result, `auto_approve`, a facts hash, and a complete AuditReport.

## Scope

The public app contains Invoice Audit, Model Lab, and Architecture. Model Lab
shows real offline artifacts. It does not load LayoutLMv3, Qwen, or a real LoRA
adapter, does not use GPU, API keys, or secrets, and is not a production service.

Automated visual browser loading timed out in the current environment. Therefore
`manual_browser_check_required=true` and `online_deployment_verified=false` are
kept conservatively even though HTTP, configuration, and Gradio API checks passed.
