# Engineering Delivery

## Docker Compose

仓库提供 CPU-only `api` 与 `demo` 两个服务：

```powershell
docker compose up --build
```

- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- Unified Gradio Demo: `http://127.0.0.1:7860`

默认镜像只安装 `.[demo]`，不安装 LangChain、Phase 1 或 Phase 3 训练依赖，不包含模型权重、adapter、checkpoint、API Key 或 secrets。SQLite 与上传目录写入 Compose named volume。

停止服务：

```powershell
docker compose down
```

## Verification Status

Dockerfile、Compose 结构、服务命令、端口、health check、依赖边界和 `.dockerignore` 已通过仓库静态测试。

当前 Windows 主机没有安装 Docker CLI，因此本轮状态是：

```text
configuration_ready=true
runtime_not_verified=true
```

这不是容器运行 PASS。安装 Docker Desktop 后应执行 `docker compose config`、build、up 和 health check，再记录真实 runtime 结果。

## GitHub Actions CI

`.github/workflows/ci.yml` 使用 Ubuntu CPU runner，安装 `.[demo,langchain,test]`，执行 `pip check`、Model Lab、Unified Demo、HF 本地包、LangChain、Docker 静态配置、Release Readiness 和全量 pytest。Workflow 不读取 secrets，不加载模型，也不要求 GPU。

## Release Readiness

```powershell
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py
```

该脚本默认只打印 JSON，仅在显式传入 `--output` 时写文件。`ready=true` 表示本地发布材料完整，不表示 HF Space 已创建、已上传或公网部署已验证。
