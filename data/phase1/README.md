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

## CORD 后续用途

CORD 是补充数据集，用于后续扩展更多票据字段和版式，不混入 SROIE 四字段 benchmark。本阶段不下载 CORD、不伪造 CORD 指标。
