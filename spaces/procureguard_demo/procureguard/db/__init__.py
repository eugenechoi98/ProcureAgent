"""数据库初始化和 mock 数据入口。"""

from procureguard.db.connection import get_connection, initialize_database
from procureguard.db.seed_mock_data import seed_mock_data
from procureguard.db.seed_policies import seed_policy_documents

__all__ = [
    "get_connection",
    "initialize_database",
    "seed_mock_data",
    "seed_policy_documents",
]
