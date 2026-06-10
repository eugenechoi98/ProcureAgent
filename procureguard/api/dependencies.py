"""FastAPI 依赖和数据库初始化。"""

from collections.abc import Iterator
from pathlib import Path
import sqlite3

from fastapi import Request

from procureguard.config import Settings
from procureguard.db import (
    get_connection,
    initialize_database,
    seed_mock_data,
    seed_policy_documents,
)


def initialize_app_database(settings: Settings) -> None:
    """初始化 SQLite schema 和 mock 数据。"""

    conn = get_connection(settings.database_path)
    try:
        initialize_database(conn)
        seed_mock_data(conn)
        seed_policy_documents(conn)
    finally:
        conn.close()


def open_connection(database_path: str | Path) -> sqlite3.Connection:
    """打开一次请求使用的 SQLite 连接。"""

    return get_connection(database_path)


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """为每个请求提供独立连接，并在结束后关闭。"""

    conn = open_connection(request.app.state.settings.database_path)
    try:
        yield conn
    finally:
        conn.close()
