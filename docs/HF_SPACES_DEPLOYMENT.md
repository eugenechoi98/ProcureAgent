# Hugging Face Spaces Deployment

## Status

Batch C.1：本地发布包准备完成。

Batch C.2：用户网页端创建 Space，尚未执行。

Batch C.3：上传发布包并验证公网链接，尚未执行。

当前没有创建 Hugging Face Space，没有登录 Hugging Face，没有上传代码，
没有上传模型，也没有部署公网链接。

Engineering Closure 已补齐 LangChain 离线 benchmark、Docker Compose 配置、GitHub Actions CI 和本地 Release Readiness。这些工作不改变上述在线状态，也没有进入 Batch C.2 或 C.3。

## Local Package

本地发布目录：

```text
spaces/procureguard_demo/
```

该目录是 CPU-only Gradio Space 最小包，只包含 Unified Portfolio Demo 运行
所需文件、Model Lab 轻量 artifacts、fixture 和最小 Python runtime 模块。

发布包不包含：

- LayoutLMv3、Qwen 或 LoRA 模型权重；
- checkpoint、adapter、safetensors、bin、pt、pth、ckpt；
- Notebook；
- Phase 1 / Phase 3 训练脚本；
- GPU requirements；
- 本地 SQLite 数据库；
- `.venv`、`.venv-phase3`、`artifacts` 或缓存目录。

## Build Locally

```powershell
.\.venv\Scripts\python.exe scripts\demo\build_hf_space_package.py
```

该命令只在本地复制 allowlist 文件并输出 JSON 摘要，不访问网络，不下载模型，
不上传任何内容。

## Smoke Check

```powershell
.\.venv\Scripts\python.exe scripts\demo\run_hf_space_package_smoke.py
```

该命令从 `spaces/procureguard_demo/` 独立 import 并构建 Gradio App，不启动
长期服务，不打开浏览器，不联网，不需要 GPU，不需要 API Key，不加载模型。

## Windows Local Demo Start

如需本地打开完整仓库内的 Demo，可先设置本机代理绕过和关闭 Gradio analytics：

```powershell
$env:NO_PROXY="127.0.0.1,localhost"
$env:no_proxy="127.0.0.1,localhost"
$env:GRADIO_ANALYTICS_ENABLED="False"
.\.venv\Scripts\python.exe -m demo.app
```

`localhost 502` 属于本地 Gradio 自检 / 网络策略提示，不是业务链失败。

## Public Space Steps Not Yet Done

后续 Batch C.2 才由用户在 Hugging Face 网页端创建 Space。

后续 Batch C.3 才上传 `spaces/procureguard_demo/` 内容并验证公网链接。

不要把当前 C.1 本地发布包准备写成 Space 已上线、线上模型推理已启用或生产可用。
