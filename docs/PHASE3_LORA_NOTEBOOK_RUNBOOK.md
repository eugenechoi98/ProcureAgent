# Phase 3 LoRA Notebook Runbook

本手册只覆盖 Phase 3 异常说明训练。默认 FastAPI 环境不安装 Torch、Transformers、PEFT、TRL 或 Unsloth。

## 1. 本地验收

使用项目 `.venv` 生成数据和运行 CPU 测试：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\generate_anomaly_explanations.py --seed 42
.\.venv\Scripts\python.exe scripts\phase3\verify_lora_notebook_env.py
.\.venv\Scripts\python.exe scripts\phase3\bootstrap_lora_notebook.py
.\.venv\Scripts\python.exe scripts\phase3\base_inference_smoke.py
.\.venv\Scripts\python.exe scripts\phase3\prepare_qwen_model.py
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_dataset.py tests\test_phase3_evaluation.py tests\test_phase3_gpu_notebook.py
```

本地不要求 GPU，也不要把 Notebook 的 `RUN_TRAINING` 改为 `True`。`base_inference_smoke.py` 默认是 dry-run，只打印模型目录、输入、输出和生成参数计划。

## 2. 分工

- `scripts/phase3/prepare_qwen_model.py`：显式准备或验证本地 Qwen 模型目录；默认 dry-run，只有 `--download` 会下载。
- `scripts/phase3/verify_lora_notebook_env.py`：只读检查，不创建目录、不下载模型、不安装依赖。
- `scripts/phase3/bootstrap_lora_notebook.py`：创建 `artifacts/phase3/` 输出目录，写入 `logs/environment_guard.json`。
- `procureguard.phase3.gpu_notebook`：统一做路径解析、数据 SHA guard、依赖 guard、CUDA guard、模型目录 guard 和 base inference smoke。
- `procureguard.phase3.runtime`：在 Notebook Kernel 内恢复 train/validation/test 数据、system prompt、训练参数、LoRA 参数和生成参数。

## 3. 独立 GPU 环境与 Kernel

Linux CUDA Notebook 环境必须创建独立虚拟环境，不复用默认后端环境：

```bash
python -m venv .venv-phase3
source .venv-phase3/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements/phase3-lora.txt
python -m pip install ipykernel
python -m ipykernel install --user --name procureguard-phase3 --display-name "ProcureGuard Phase 3 (.venv-phase3)"
```

打开 Notebook 后必须选择 `ProcureGuard Phase 3 (.venv-phase3)` Kernel。首个配置单元会输出 `sys.executable`；在 ModelScope 上它必须指向：

```text
/mnt/workspace/ProcureAgent/.venv-phase3/bin/python
```

如果 Terminal 与 Notebook Kernel 不一致，Notebook 会停止；不要继续训练，也不要在 Notebook 里手工改路径。

Unsloth 是优先后端。由于其安装命令依赖 CUDA、Torch 和运行平台，请按当前 Unsloth 官方安装说明在该独立环境安装；如果 Unsloth guard 未通过，Notebook 自动选择普通 Transformers + PEFT + TRL 路径。

不要在默认 `.venv` 中安装 Phase 3 GPU 依赖，也不要修改 `pyproject.toml` 的默认 dependencies。

`python -m pip install -e .` 只安装 ProcureGuard 默认项目依赖，例如 `pydantic` 和 FastAPI 基础依赖；LoRA 重型依赖仍只来自 `requirements/phase3-lora.txt`。
`ipykernel` 保持显式安装，用于稳定注册 `ProcureGuard Phase 3 (.venv-phase3)` Kernel。

## 4. ModelScope 最少操作步骤

下面命令按顺序复制执行。模型下载不会由 verify、bootstrap、base smoke 或 Notebook 静默触发；只有 `prepare_qwen_model.py --download` 会显式下载。

```bash
cd /mnt/workspace/ProcureAgent
git pull

python -m venv .venv-phase3
source .venv-phase3/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements/phase3-lora.txt
python -m pip install ipykernel
python -m ipykernel install --user --name procureguard-phase3 --display-name "ProcureGuard Phase 3 (.venv-phase3)"

export HF_HOME=/mnt/workspace/.cache/huggingface
export PHASE3_MODEL_CACHE=/mnt/workspace/models/phase3
export PHASE3_MODEL_DIR=/mnt/workspace/models/phase3/Qwen2.5-0.5B-Instruct
export PHASE3_KERNEL_PYTHON=/mnt/workspace/ProcureAgent/.venv-phase3/bin/python
export PROCUREGUARD_PROJECT_ROOT=/mnt/workspace/ProcureAgent

# 情况一：模型目录已经存在，直接验证。
python scripts/phase3/prepare_qwen_model.py --verify-only --model-dir "$PHASE3_MODEL_DIR"

# 情况二：云端可以联网，显式下载。只有这条命令会下载模型。
# python scripts/phase3/prepare_qwen_model.py --download --model-dir "$PHASE3_MODEL_DIR"

# 情况三：云端网络不可用，把完整模型目录或压缩包上传/解压到 $PHASE3_MODEL_DIR 后，再运行 verify-only。
# python scripts/phase3/prepare_qwen_model.py --verify-only --model-dir "$PHASE3_MODEL_DIR"

python scripts/phase3/verify_lora_notebook_env.py --require-cuda --model-dir "$PHASE3_MODEL_DIR"
python scripts/phase3/bootstrap_lora_notebook.py --require-cuda --model-dir "$PHASE3_MODEL_DIR"
python scripts/phase3/base_inference_smoke.py --model-dir "$PHASE3_MODEL_DIR"
python scripts/phase3/base_inference_smoke.py --model-dir "$PHASE3_MODEL_DIR" --run
```

如果任一步失败，停止连续手工补依赖、补变量或改路径，把完整报错带回 Phase 3 对话，优先固化脚本修复。

如果看到 `Missing ProcureGuard project dependency modules` 或 `No module named 'pydantic'`，说明当前 `.venv-phase3` 尚未安装项目默认依赖。保持现有虚拟环境，激活后补执行：

```bash
python -m pip install -e .
```

不要手工单独 `pip install pydantic`，也不要删除 `.venv-phase3`。

以上命令全部通过后，才打开 `notebooks/phase3_lora_explainer_training.ipynb`，选择 `ProcureGuard Phase 3 (.venv-phase3)` Kernel。Notebook 顺序固定为：

1. 配置单元：只允许有意识地修改 `RUN_TRAINING` 和 `RUN_FULL_EVAL`。
2. guard：输出当前 `sys.executable`、CUDA、依赖、数据 SHA、模型目录和输出目录状态。
3. runtime context：恢复 train/validation/test 数据和训练参数。
4. base inference：先按 `RUN_BASE_SMOKE=False` dry-run；需要再次 smoke 时只改这个布尔值。
5. `RUN_TRAINING=True` 后执行 LoRA 训练。
6. 训练完成后 `RUN_FULL_EVAL=True`，自动执行 base/fine-tuned inference、评测和 manifest 导出。

Notebook 的项目根目录由 `procureguard.phase3.paths.resolve_project_root` 统一解析。它会优先读取 `PROCUREGUARD_PROJECT_ROOT`，并兼容 Kernel cwd 为 `/mnt/workspace`、仓库位于 `/mnt/workspace/ProcureAgent` 的 ModelScope 场景。不要在 Notebook 中手工写死项目路径。

## 5. Qwen 模型准备

模型目录统一使用：

```text
/mnt/workspace/models/phase3/Qwen2.5-0.5B-Instruct
```

三种情况：

- 模型目录已经存在：运行 `python scripts/phase3/prepare_qwen_model.py --verify-only --model-dir "$PHASE3_MODEL_DIR"`。
- 云端可以联网：运行 `python scripts/phase3/prepare_qwen_model.py --download --model-dir "$PHASE3_MODEL_DIR"`。
- 云端网络不可用：在本地下载完整 `Qwen/Qwen2.5-0.5B-Instruct` 目录，上传目录或压缩包到 ModelScope，解压后让文件直接位于 `$PHASE3_MODEL_DIR` 下，再运行 `--verify-only`。

模型目录 guard 至少检查：

- `config.json`
- `tokenizer_config.json`
- tokenizer 文件：`tokenizer.json`、`tokenizer.model` 或 `vocab.json` 至少一个
- `model.safetensors` 或 `model.safetensors.index.json`
- 如果存在 safetensors index，索引中列出的权重分片必须全部存在

未配置 `PHASE3_MODEL_DIR` 时，base inference smoke 保持 dry-run。

## 6. 数据、训练参数与导出

确认 `data/phase3/generated/` 有固定的 160/20/20 JSONL，并保持 `SEED = 42` 和 `MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"`。

Notebook 固定记录：

- LoRA `r=16`、`alpha=32`、`dropout=0.05`
- batch size 2、gradient accumulation 8
- epoch 3、learning rate `2e-4`
- max sequence length 1024、seed 42

训练完成后必须导出：

```text
artifacts/phase3/logs/environment_guard.json
artifacts/phase3/logs/training_config.json
artifacts/phase3/logs/trainer_log_history.json
artifacts/phase3/predictions/base.jsonl
artifacts/phase3/predictions/fine_tuned.jsonl
artifacts/phase3/evaluation/evaluation.json
artifacts/phase3/evaluation/evaluation.md
artifacts/phase3/artifacts_manifest.json
artifacts/phase3/adapters/
```

输出目录由正式代码创建，不需要在 Notebook 中手工创建目录。adapter、checkpoint、模型缓存、预测和评测运行产物均被 `.gitignore` 排除，不提交 Git。

adapter 目录不要提交 Git；压缩包保存到仓库外本地 artifacts 目录。

## 7. Base Vs Fine-tuned

base 与 adapter 必须：

- 使用同一 `test.jsonl`。
- 使用同一 chat template 和 system prompt。
- 使用相同的 `max_new_tokens=256`、`do_sample=False`。
- 分别导出 `base.jsonl` 和 `fine_tuned.jsonl`。
- 只通过 `scripts/phase3/evaluate_explanations.py` 计算指标。

Notebook 只有在两份真实预测都存在时才生成对比报告。不得手填或伪造指标。

## 8. 失败处理

- 数据 guard 失败：重新运行生成脚本，并核对 dataset summary 的 SHA256。
- 模型 guard 失败：先运行 `prepare_qwen_model.py --verify-only`，根据输出补齐模型目录。
- CUDA guard 失败：停止训练，只保留 CPU smoke；不要强制在 CPU 上跑 QLoRA。
- Unsloth 导入失败：确认平台安装方式；仍失败时使用 fallback。
- OOM：先降低 batch size 或 max sequence length，不改变 test split 和评测口径。
- 评测缺少预测：补齐全部 20 条 test 输出，评测脚本不会静默跳过。
