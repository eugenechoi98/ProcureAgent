# Phase 3 LoRA Notebook Runbook

本手册只覆盖 Phase 3 异常说明训练。默认 FastAPI 环境不安装 Torch、Transformers、PEFT、TRL 或 Unsloth。

## 1. 本地验收

使用项目 `.venv` 生成数据和运行 CPU 测试：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\generate_anomaly_explanations.py --seed 42
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_dataset.py tests\test_phase3_evaluation.py
```

本轮无需 GPU，也不要把 Notebook 的 `RUN_TRAINING` 改为 `True`。

## 2. 独立 GPU 环境

建议在 Linux CUDA Notebook 环境创建独立虚拟环境，不复用默认后端环境：

```bash
python -m venv .venv-phase3
source .venv-phase3/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/phase3-lora.txt
```

Unsloth 是优先后端。由于其安装命令依赖 CUDA、Torch 和运行平台，请按当前 Unsloth 官方安装说明在该独立环境安装；如果 Unsloth guard 未通过，Notebook 自动选择普通 Transformers + PEFT + TRL 路径。

不要在默认 `.venv` 中安装 Phase 3 GPU 依赖，也不要修改 `pyproject.toml` 的默认 dependencies。

## 3. 数据与模型准备

1. 确认 `data/phase3/generated/` 有固定的 160/20/20 JSONL。
2. 保持 `SEED = 42` 和 `MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"`。
3. 模型缓存可由环境变量 `HF_HOME` 指向本地大容量目录。
4. 首次 smoke 时保持 `RUN_TRAINING = False`，依次执行 Notebook 单元格。
5. guard 显示数据、fallback 依赖和 CUDA 均通过后，才将 `RUN_TRAINING = True`。

## 4. 训练参数与导出

Notebook 固定记录：

- LoRA `r=16`、`alpha=32`、`dropout=0.05`
- batch size 2、gradient accumulation 8
- epoch 3、learning rate `2e-4`
- max sequence length 1024、seed 42

本地产物统一写入：

```text
artifacts/phase3/adapters/
artifacts/phase3/logs/
artifacts/phase3/predictions/
artifacts/phase3/evaluation/
```

adapter、checkpoint、模型缓存、预测和评测运行产物均被 `.gitignore` 排除，不提交 Git。

## 5. Base Vs Fine-tuned

base 与 adapter 必须：

- 使用同一 `test.jsonl`。
- 使用同一 chat template 和 system prompt。
- 使用相同的 `max_new_tokens=256`、`do_sample=False`。
- 分别导出 `base.jsonl` 和 `fine_tuned.jsonl`。
- 只通过 `scripts/phase3/evaluate_explanations.py` 计算指标。

Notebook 只有在两份真实预测都存在时才生成对比报告。不得手填或伪造指标。

## 6. 失败处理

- 数据 guard 失败：重新运行生成脚本，并核对 dataset summary 的 SHA256。
- CUDA guard 失败：停止训练，只保留 CPU smoke；不要强制在 CPU 上跑 QLoRA。
- Unsloth 导入失败：确认平台安装方式；仍失败时使用 fallback。
- OOM：先降低 batch size 或 max sequence length，不改变 test split 和评测口径。
- 评测缺少预测：补齐全部 20 条 test 输出，评测脚本不会静默跳过。
