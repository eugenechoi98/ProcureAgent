# Phase 1 GPU Notebook Runbook

## ModelScope Notebook

1. 打开 ModelScope Notebook 页面，新建一个 Notebook 实例。
2. 在页面提供的资源中选择 GPU。可用型号以页面实际显示为准。
3. 打开终端并 clone 项目：

```bash
git clone YOUR_GIT_REPOSITORY_URL ProcureAgent
cd ProcureAgent
```

4. 安装 extraction 依赖：

```bash
python -m pip install -e ".[extraction]"
```

5. 打开：

```text
notebooks/phase1_layoutlmv3_training.ipynb
```

6. 保持：

```python
RUNTIME = "modelscope"
```

7. 从第 1 节开始顺序执行，不跳过 GPU guard、数据转换或单 batch smoke。

## Google Colab 备用方式

1. 新建启用 GPU 的 Colab Notebook。
2. clone 项目并进入根目录。
3. 打开或上传项目中的训练 Notebook。
4. 修改：

```python
RUNTIME = "colab"
```

5. 从头顺序执行。训练代码与 ModelScope 相同，环境差异只在初始化部分。

## 正常训练表现

每个 epoch 应输出：

```text
epoch
train_loss
validation_loss
token_f1
field_macro_f1
learning_rate
elapsed_time
```

正常情况下：

- train loss 能持续计算，不出现 `nan`。
- validation loss 能完成。
- token F1 和 field macro F1 能输出。
- 最佳 field macro F1 提升时，checkpoint 会更新。

不要只看 loss。loss 下降但 F1 不提升，说明模型可能没有学到正确字段边界。

## OOM 处理

如果出现 CUDA out of memory：

1. 先将 `BATCH_SIZE` 从 `2` 调为 `1`。
2. 保持 `GRAD_ACCUMULATION_STEPS=4`，必要时再提高。
3. 重启运行环境，释放上一次失败残留的显存。
4. 不要第一次训练就修改模型结构或进行复杂超参数搜索。

## 训练输出

报告目录：

```text
reports/phase1/gpu_training/
```

预期包含：

```text
layoutlmv3_training_report.json
layoutlmv3_training_log.csv
layoutlmv3_training_report.md
layoutlmv3_loss_curve.png
```

错误分析：

```text
reports/phase1/layoutlmv3_validation_errors.md
```

最佳 checkpoint：

```text
checkpoints/phase1/layoutlmv3_best/
```

## 保存 checkpoint 和 reports

Notebook 最后会生成 checkpoint zip。训练结束后：

1. 手动下载 checkpoint zip，或复制到云端持久化存储。
2. 下载 `reports/phase1/gpu_training/`。
3. 不要把模型权重提交到 Git。
4. 精简后的 Markdown、JSON、CSV 和 loss PNG 可以回传项目审查。

## 回传总控对话

回到审查与总控对话时提供：

- 运行环境与 GPU 名称。
- 每个 epoch 的训练日志。
- best epoch。
- baseline macro F1 `0.4387`。
- fine-tuned validation macro F1。
- baseline vs fine-tuned 对比表。
- loss 曲线。
- 错误分析。
- checkpoint 保存位置。

必须明确：

```text
evaluation_split = local_validation_split_seed_42
```

这不是 official test。
