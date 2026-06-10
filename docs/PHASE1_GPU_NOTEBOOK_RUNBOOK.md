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

目录至少应包含模型配置、processor 配置和模型权重。训练 Notebook 使用
`local_files_only=True`，不会重新访问 Hugging Face。

如果云端镜像可以访问，也可以先在可联网环境下载，再复制整个目录：

```python
from huggingface_hub import snapshot_download

snapshot_download(
    "microsoft/layoutlmv3-base",
    local_dir="/mnt/workspace/models/layoutlmv3-base",
)
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

### 10. 顺序运行训练

从 Notebook 第二节开始顺序执行。不要再手工新增依赖安装、路径重写、loader 或变量补丁。

## Kernel 与 Terminal

ModelScope Terminal 和 Notebook Kernel 可能是两个 Python 环境。

训练只认 Notebook Kernel：

```text
sys.executable
Python version
torch version
transformers version
CUDA available
GPU name
```

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

## Colab 备用路径

将 Notebook 第一格改为：

```python
RUNTIME = "colab"
```

并按实际挂载位置调整 `PROJECT_ROOT`、`PROCESSED_DIR`、`IMAGE_ROOT`、`MODEL_DIR`。
其余 bootstrap、训练和评测代码保持一致。
