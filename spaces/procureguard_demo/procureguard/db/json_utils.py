"""SQLite JSON 字段读写辅助。"""

from __future__ import annotations

import json
from typing import Any


def dumps_json(value: Any) -> str:
    """把业务对象稳定转成 JSON 字符串。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads_json(value: str | None, default: Any = None) -> Any:
    """从 SQLite JSON 字段读取对象。"""

    if value is None:
        return default
    return json.loads(value)
