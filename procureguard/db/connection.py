"""SQLite 连接和 schema 初始化。"""

from pathlib import Path
import sqlite3

DEFAULT_DB_PATH = Path("procureguard/data/procureguard.sqlite3")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """创建启用外键和行字典访问的 SQLite 连接。"""

    path = Path(db_path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """执行共享 schema，准备基础表结构。"""

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()
