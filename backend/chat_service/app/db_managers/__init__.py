from .mysql import (
    MySQLManager,
    User,
    Bot,
    MessageHistory,
    UserStatus,
    UserRole,
    BotStatus,
    RelationType,
)

# 创建数据库管理器实例
db_manager = MySQLManager()

__all__ = [
    'db_manager',
    'MySQLManager',
    'User',
    'Bot',
    'MessageHistory',
    'UserStatus',
    'UserRole',
    'BotStatus',
    'RelationType',
]