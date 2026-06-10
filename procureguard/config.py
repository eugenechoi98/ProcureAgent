"""后端基础服务配置。"""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """集中管理本地数据库和上传目录。"""

    database_path: Path
    upload_dir: Path


def get_settings() -> Settings:
    """从环境变量读取配置，未设置时使用本地开发默认值。"""

    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "data/procureguard.db")),
        upload_dir=Path(os.getenv("UPLOAD_DIR", "uploads")),
    )
