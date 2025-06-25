from .mysql import (
    MySQLManager,
    User,
    Bot,
    MessageHistory,
)
from ..core.config import settings

# 创建数据库管理器实例，并传入数据库连接URL
# Create a database manager instance and pass in the database connection URL
db_manager = MySQLManager(database_url=settings.database_url)

__all__ = [
    "db_manager",
    "MySQLManager",
    "User",
    "Bot",
    "MessageHistory",
]
