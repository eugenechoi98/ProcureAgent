# Phase 1 GPU Notebook Runbook

## ModelScope 最少步骤

### 1. 启动 GPU Notebook

在 ModelScope Notebook 页面选择可用 GPU 并启动实例。GPU 型号以页面实际资源为准。

### 2. clone 仓库

```bash
cd /mnt/workspace
git clone YOUR_GIT_REPOSITORY_URL ProcureAgent
```

已有仓库时跳过 clone。

### 3. 准备本地模型

将已经下载好的 `microsoft/layoutlmv3-base` 上传或解压到：

```text
/mnt/workspace/models/layoutlmv3-base
```

目录必须包含模型配置、processor 配置和：

```text
model.safetensors
```

训练 Notebook 显式使用 `local_files_only=True` 和 `use_safetensors=True`，不会重新
访问 Hugging Face，也不会回退到 `pytorch_model.bin`。缺少 Safetensors 时 bootstrap
会在训练前停止。

如果云端镜像可以访问，也可以先在可联网环境下载，再复制整个目录：

```python
from huggingface_hub import snapshot_download

snapshot_download(
    "microsoft/layoutlmv3-base",
    local_dir="/mnt/workspace/models/layoutlmv3-base",
)
```

只补权重文件也可以使用：

```bash
huggingface-cli download microsoft/layoutlmv3-base model.safetensors \
  --local-dir /mnt/workspace/models/layoutlmv3-base
```

### 4. 上传 processed JSONL

上传 `sroie_task3_processed.tar.gz`，解压后确认存在：

```text
/mnt/workspace/ProcureAgent/data/phase1/sroie_task3/processed/train.jsonl
/mnt/workspace/ProcureAgent/data/phase1/sroie_task3/processed/validation.jsonl
```

### 5. 准备 ModelScope 图片

通过 ModelScope 镜像获取 SROIE 图片并解压到：

```text
/mnt/workspace/SROIE/unpacked/sroie/imgs
```

不需要手工修改 JSONL 中的 Windows 路径，也不要手工处理 `(1)`、`(2)`、`(3)`。

### 6. 更新仓库

```bash
cd /mnt/workspace/ProcureAgent
git pull
```

### 7. 打开 Notebook

打开：

```text
notebooks/phase1_layoutlmv3_training.ipynb
```

### 8. 运行统一 bootstrap

运行 Notebook 第一个代码单元。它等价于使用当前 Kernel 执行：

```python
import sys
import subprocess

subprocess.run(
    [
        sys.executable,
        "scripts/phase1/bootstrap_gpu_notebook.py",
        "--project-root", "/mnt/workspace/ProcureAgent",
        "--processed-dir", "/mnt/workspace/ProcureAgent/data/phase1/sroie_task3/processed",
        "--image-root", "/mnt/workspace/SROIE/unpacked/sroie/imgs",
        "--model-dir", "/mnt/workspace/models/layoutlmv3-base",
        "--runtime", "modelscope",
    ],
    cwd="/mnt/workspace/ProcureAgent",
    check=True,
)
```

bootstrap 会：

- 使用 `sys.executable` 检查和安装依赖。
- 显式使用 `https://pypi.org/simple`，不使用异常的默认镜像。
- 将项目安装到当前 Kernel。
- 备份并修复 train/validation JSONL 图片路径。
- 安全匹配文件名末尾的 `(1)`、`(2)`、`(3)`。
- 检查本地模型、样本数量、图片、BIO 标签和 baseline。
- 输出 `reports/phase1/gpu_notebook_bootstrap.json`。

如果 PyPI 也无法访问，bootstrap 会停止并给出 wheelhouse 离线安装命令，不会继续训练。

### 9. 确认 guard

必须看到：

```text
training_guard_passed=true
```

也可以使用当前 Notebook Kernel 单独执行只读验证：

```python
subprocess.run(
    [
        sys.executable,
        "scripts/phase1/verify_gpu_notebook_env.py",
        "--project-root", "/mnt/workspace/ProcureAgent",
        "--processed-dir", "/mnt/workspace/ProcureAgent/data/phase1/sroie_task3/processed",
        "--image-root", "/mnt/workspace/SROIE/unpacked/sroie/imgs",
        "--model-dir", "/mnt/workspace/models/layoutlmv3-base",
        "--runtime", "modelscope",
    ],
    cwd="/mnt/workspace/ProcureAgent",
    check=True,
)
```

guard 为 false 时不要运行训练单元格。

### 10. Hydrate 当前 Kernel

bootstrap 子进程不能修改当前 Notebook Kernel 的 Python 变量。继续运行第二个代码单元：

```python
from procureguard.extraction.gpu_notebook_context import build_gpu_notebook_context

context = build_gpu_notebook_context(
    project_root="/mnt/workspace/ProcureAgent",
    processed_dir="/mnt/workspace/ProcureAgent/data/phase1/sroie_task3/processed",
    model_dir="/mnt/workspace/models/layoutlmv3-base",
    baseline_report_path=(
        "/mnt/workspace/ProcureAgent/"
        "reports/phase1/baseline_sroie_task3_validation.json"
    ),
)
globals().update(context)
```

该单元会在当前 Kernel 内恢复真实 `LABEL2ID`、`ID2LABEL`、`SroieSample`、
本地 processor、Torch、device 和全部训练参数。

### 11. 运行 preflight

第三个代码单元必须输出：

```text
missing_names = []
```

只有 bootstrap guard 和 runtime preflight 都通过，才继续创建 Dataset。

### 12. 顺序运行训练

继续按顺序运行剩余单元格。不要手工新增变量、依赖安装、路径重写、loader 或标签定义。

## Kernel 与 Terminal

ModelScope Terminal 和 Notebook Kernel 可能是两个 Python 环境。

训练只认 Notebook Kernel。bootstrap 负责外部环境和数据验证，hydrate 负责当前
Kernel 的 Python 对象：

```text
sys.executable
Python version
torch version
transformers version
CUDA available
GPU name
```

Notebook 第一格还会设置：

```python
os.environ["TOKENIZERS_PARALLELISM"] = "false"
```

用于减少 DataLoader/fork 场景中的 tokenizer 并行 warning。

Terminal 的 `python` 只用于文件操作参考，不能证明 Notebook 已安装依赖。

当前实际验证目标环境是：

```text
Python 3.12
torch 2.10.0+cu128
NVIDIA A10
```

实际运行时仍以 Notebook 首个单元打印的结果为准。

## seqeval 安装说明

`seqeval` 最新版本仍为 `1.2.2`，它依赖 distribution 名 `scikit-learn`。
GPU requirements 显式声明现代 `scikit-learn`，并从 PyPI 安装，避免使用旧的
`sklearn` 占位包或异常镜像导致 `setup.py egg_info` 失败。

## Transformers Warning

云端曾出现 `device argument deprecated` FutureWarning。当前训练流程没有自行传递
已废弃的 `device` 参数，因此本轮不做大范围依赖改造；记录 warning，后续随
Transformers/processor API 升级单独处理。

## OOM

出现 CUDA out of memory 时：

1. 将 `BATCH_SIZE` 从 `2` 改为 `1`。
2. 保留 `GRAD_ACCUMULATION_STEPS=4`，必要时再提高。
3. 重启 Kernel 释放显存，然后重新运行 bootstrap。

## 输出位置

最佳 checkpoint：

```text
checkpoints/phase1/layoutlmv3_best/
```

训练报告：

```text
reports/phase1/gpu_training/
```

错误分析：

```text
reports/phase1/layoutlmv3_validation_errors.md
```

训练完成后手动下载 checkpoint 和 reports，模型权重不要提交 Git。

## First GPU Fine-tuning Run

首次 NVIDIA A10 完整运行已完成：

```text
evaluation_split=local_validation_split_seed_42
official_test=false
best_epoch=5
token_f1=0.8647
field_macro_f1=0.6231
```

日期字段的 OCR token 覆盖完整，但旧字段重建会把 `DATE:`、时间和其他文本拼入结果。
统一日期 span 清洗后，金标 BIO 重建错误从 122 降至 25；剩余 25 条与 alignment miss
对应。下一步先用现有 checkpoint 重跑 validation inference，不直接修改训练参数。

## Colab 备用路径

将 Notebook 第一格改为：

```python
RUNTIME = "colab"
```

并按实际挂载位置调整 `PROJECT_ROOT`、`PROCESSED_DIR`、`IMAGE_ROOT`、`MODEL_DIR`。
其余 bootstrap、训练和评测代码保持一致。

## Phase 1G: Existing Checkpoint Validation

不运行训练单元格。保留现有：

```text
checkpoints/phase1/layoutlmv3_best/model.safetensors
data/phase1/sroie_task3/processed/validation.jsonl
```

更新仓库：

```bash
cd /mnt/workspace/ProcureAgent
git pull
```

打开训练 Notebook，只运行第 14 节 `Phase 1G Existing Checkpoint Inference`。
该独立单元使用当前 Kernel 的 `sys.executable`，并通过 `--image-root` 在内存中解析
跨平台图片路径，不改写 processed JSONL，也不需要运行前面的训练单元。
第 14 节会从 Kernel 当前目录、父目录和直接子目录定位仓库，并在启动推理前检查
脚本、checkpoint、validation JSONL、图片目录和 baseline 报告。
图片目录按以下顺序自动解析：显式参数、`PROCUREGUARD_PHASE1G_IMAGE_ROOT` 或
`SROIE_IMAGE_ROOT` 环境变量、ModelScope workspace 的
`SROIE/unpacked/sroie/imgs`、仓库内 Task 3/SROIE 候选。解析只发生在内存中，
不会改写 validation JSONL。

脚本对同一批模型 token predictions 同时执行旧版和新版日期重建，不训练、不调参。
结果保存到：

```text
reports/phase1/checkpoint_inference/date_reconstruction_inference.json
reports/phase1/checkpoint_inference/date_reconstruction_inference.md
reports/phase1/checkpoint_inference/date_reconstruction_predictions.jsonl
```

只需回传上述三个小文件，不需要下载 checkpoint。
