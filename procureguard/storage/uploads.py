"""上传文件安全保存和哈希计算。"""

from dataclasses import dataclass
from pathlib import Path
import hashlib

from fastapi import UploadFile

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class SavedUpload:
    """已保存上传文件的信息。"""

    file_path: Path
    file_hash: str
    size_bytes: int


class UploadValidationError(ValueError):
    """上传文件校验错误。"""


async def save_invoice_upload(
    upload_dir: Path,
    invoice_id: str,
    file: UploadFile,
) -> SavedUpload:
    """保存发票文件，拒绝空文件和不支持的扩展名。"""

    original_name = file.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UploadValidationError(
            "Unsupported file extension. Allowed: .pdf, .png, .jpg, .jpeg."
        )

    content = await file.read()
    if not content:
        raise UploadValidationError("Uploaded file is empty.")

    target_dir = upload_dir / invoice_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / f"{invoice_id}{extension}").resolve()
    upload_root = upload_dir.resolve()
    if upload_root not in target_path.parents:
        raise UploadValidationError("Invalid upload path.")

    try:
        target_path.write_bytes(content)
    except OSError as exc:
        raise UploadValidationError(f"Failed to save uploaded file: {exc}") from exc

    return SavedUpload(
        file_path=target_path,
        file_hash=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )
