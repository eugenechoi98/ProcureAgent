# Phase 1 Data Directory

本目录只放数据说明，不提交真实 SROIE/CORD 大型数据集。

## SROIE 放置位置

```text
data/
  phase1/
    sroie/
      raw/
        train/
          img/
          box/
        key/ 或 entities/
        test/
          img/
          box/
          key/
      processed/
    cord/
      raw/
      processed/
    synthetic/
```

其中：

- `img/` 放票据图片。
- `box/` 放 OCR 文本与 bbox 标注，文件名与图片 stem 一致。
- `key/` 或 `entities/` 放结构化 ground truth JSON，字段为 `company`、`address`、`date`、`total`。

## 转换命令

```powershell
.\.venv\Scripts\python.exe scripts/phase1/prepare_sroie.py `
  --input data/phase1/sroie/raw/train `
  --output data/phase1/sroie/processed/train.jsonl
```

真实数据不会提交到 Git。fixture smoke 数据放在 `tests/fixtures/sroie_minimal/`，只用于验证脚本能跑通。

## 数据检查

```powershell
.\.venv\Scripts\python.exe scripts/phase1/check_sroie_dataset.py `
  --input data/phase1/sroie/raw
```

如果真实数据还没放置，这个命令会非 0 退出，并打印期望目录结构。

## ModelScope 镜像适配

当前镜像目录：

```text
data/phase1/sroie/inbox/SROIE/unpacked/sroie
```

整理命令：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/organize_sroie_dataset.py `
  --input data/phase1/sroie/inbox/SROIE/unpacked/sroie `
  --output data/phase1/sroie/raw
```

脚本只复制文件，不删除或覆盖 inbox。同内容文件会跳过，内容冲突会报错。

该镜像的 `train_label.jsonl/test_label.jsonl` 是 crop OCR 标签，字段只有 `filename/text`，不是 `company/address/date/total` entity ground truth。要计算真实字段级 F1，还需要人工补充官方 SROIE Task 3 entity JSON，并放入标准目录的 `key/`。

## CORD 后续用途

CORD 是补充数据集，用于后续扩展更多票据字段和版式，不混入 SROIE 四字段 benchmark。本阶段不下载 CORD、不伪造 CORD 指标。
