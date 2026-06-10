"""LayoutLMv3 token classification Dataset。"""

from pathlib import Path
from typing import Any

from procureguard.extraction.alignment import LABEL2ID, align_sample_tokens
from procureguard.extraction.schemas import SroieSample


def create_layoutlmv3_processor(
    model_name: str | Path = "microsoft/layoutlmv3-base",
    *,
    local_files_only: bool = False,
) -> Any:
    """延迟创建 LayoutLMv3Processor，避免默认后端依赖 transformers。"""

    try:
        from transformers import LayoutLMv3Processor
    except ImportError as exc:
        raise ImportError(
            "Transformers is not installed. Install Phase 1 extraction dependencies: "
            'pip install -e ".[extraction]"'
        ) from exc
    return LayoutLMv3Processor.from_pretrained(
        str(model_name),
        apply_ocr=False,
        local_files_only=local_files_only,
    )


class SROIELayoutLMv3Dataset:
    """把 processed SROIE 样本转换成 LayoutLMv3 输入。"""

    def __init__(
        self,
        samples: list[SroieSample],
        processor: Any,
        label2id: dict[str, int] | None = None,
        max_length: int = 512,
        allow_missing_images: bool = True,
    ):
        self.samples = samples
        self.processor = processor
        self.label2id = label2id or LABEL2ID
        self.max_length = max_length
        self.allow_missing_images = allow_missing_images

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        sample = self.samples[index]
        image = self._load_image(sample.image_path)
        words = [token.text for token in sample.tokens]
        boxes = [list(token.bbox) for token in sample.tokens]
        bio_labels, _ = align_sample_tokens(sample)
        label_ids = [self.label2id[label] for label in bio_labels]
        encoding = self.processor(
            image,
            words,
            boxes=boxes,
            word_labels=label_ids,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {key: _squeeze_batch(value) for key, value in encoding.items()}

    def _load_image(self, image_path: str) -> Any:
        """加载真实图片；fixture 没有图片时创建白底 smoke 图。"""

        path = Path(image_path)
        try:
            from PIL import Image
        except ImportError as exc:
            if self.allow_missing_images and not path.exists():
                return "missing-image-placeholder"
            raise ImportError(
                "Pillow is required for LayoutLMv3 image loading. Install extraction extras."
            ) from exc
        if path.exists():
            return Image.open(path).convert("RGB")
        if not self.allow_missing_images:
            raise FileNotFoundError(f"SROIE image does not exist: {path}")
        return Image.new("RGB", (1000, 1000), color="white")


def _squeeze_batch(value: Any) -> Any:
    """兼容 torch tensor 和测试用 fake tensor。"""

    if hasattr(value, "squeeze"):
        return value.squeeze(0)
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


InvoiceLayoutDataset = SROIELayoutLMv3Dataset
