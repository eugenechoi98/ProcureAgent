"""LayoutLMv3 Dataset 骨架，供训练 Notebook 复用。"""

from pathlib import Path
from typing import Any

from PIL import Image


class InvoiceLayoutDataset:
    """把统一样本转换成 LayoutLMv3 token classification 输入。"""

    def __init__(self, data: list[dict[str, Any]], processor: Any, label2id: dict[str, int]):
        self.data = data
        self.processor = processor
        self.label2id = label2id

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.data[idx]
        image = Image.open(Path(item["image_path"])).convert("RGB")
        labels = [self.label2id[label] for label in item["labels"]]
        encoding = self.processor(
            image,
            item["words"],
            boxes=item["bboxes"],
            word_labels=labels,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        return {key: value.squeeze(0) for key, value in encoding.items()}
