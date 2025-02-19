import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, JSON, ForeignKey
from sqlalchemy.exc import SQLAlchemyError  # 导入 SQLAlchemy 异常基类
from enums import (
    UserStatus,
    UserRole,
    BotStatus,
    RelationshipType,
    MessageType,
    MessageStatus,
)
import enum

# 配置日志记录器
logger = logging.getLogger(__name__)

# 数据库配置
DATABASE_URL = "mysql+aiomysql://root:root@db/says_dev?charset=utf8mb4"
engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True 会打印出执行的SQL语句
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


# 模型定义
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    entity_id = Column(String(36), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    last_login = Column(DateTime)
    status = Column(String(20), default="active")
    role = Column(String(20), default="user")
    language = Column(String(10), default="zh")
    area = Column(String(100), default="China")
    phone = Column(String(20))


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    entity_id = Column(String(36), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    user_entity_id = Column(String(36))
    model = Column(String(50), nullable=False)
    status = Column(String(20), default="active")
    gender = Column(String(10), nullable=False)
    birthday = Column(DateTime)
    timezone = Column(String(10), default="Asia/Shanghai")
    city_name = Column(String(100))
    relationship_score = Column(Integer, default=0)
    relationship_type = Column(String(20), default="stranger")
    context = Column(JSON)
    info = Column(Text)
    memory = Column(Text)
    styles = Column(JSON)


class MessageHistory(Base):
    __tablename__ = "message_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    message_id = Column(String(36))
    from_entity = Column(String(36), nullable=False)
    to_entity = Column(String(36), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="chat")
    message_service = Column(String(36), nullable=False)
    timestamp = Column(DateTime)
    status = Column(String(20), default="sent")
    meta_data = Column(JSON)

    # 显式声明要映射的列
    __mapper_args__ = {
        "include_properties": [
            "id",
            "created_at",
            "updated_at",
            "message_id",
            "from_entity",
            "to_entity",
            "content",
            "message_type",
            "message_service",
            "timestamp",
            "status",
            "meta_data",
        ]
    }

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_id": self.message_id,
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "content": self.content,
            "message_type": self.message_type,
            "message_service": self.message_service,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "status": self.status,
            "meta_data": self.meta_data,
        }


class MySQLManager:
    def __init__(self):
        self.session_maker = async_session
        self._init_task = asyncio.create_task(self._initialize())

    def _convert_enum_to_str(self, value: Optional[enum.Enum]) -> Optional[str]:
        """将枚举值转换为字符串"""
        return value.value.lower() if value is not None else None

    def _convert_str_to_enum(
        self, enum_class: type, value: Optional[str]
    ) -> Optional[enum.Enum]:
        """将字符串转换为枚举值"""
        if value is None:
            return None
        try:
            return enum_class.__members__[value.upper()]
        except KeyError:
            logger.warning(f"Invalid enum value: {value} for enum class: {enum_class}")
            return None

    async def _initialize(self):
        """初始化数据库连接，包含重试机制"""
        max_retries = 100
        retry_count = 0
        base_delay = 1  # 初始延迟1秒
        max_delay = 30  # 最大延迟30秒

        while True:
            try:
                async with self.session_maker() as session:
                    await session.execute(text("SELECT 1"))
                logger.info("Database connection initialized successfully")
                break
            except SQLAlchemyError as e:
                retry_count += 1
                if retry_count > max_retries:
                    error_msg = f"Database initialization failed after {max_retries} attempts: {str(e)}"
                    logger.critical(error_msg)
                    raise Exception(error_msg) from e

                # 计算下一次重试的延迟时间（指数退避）
                delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
                logger.warning(
                    f"Database connection attempt {retry_count} failed. Retrying in {delay} seconds... Error: {str(e)}"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                error_msg = f"Unexpected error during database initialization: {str(e)}"
                logger.critical(error_msg)
                raise Exception(error_msg) from e

    async def get_bot_data(
        self, bot_id: int, related_user_id: Optional[int] = None
    ) -> Optional[dict]:
        """获取bot的所有相关数据"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()

                if bot and (
                    bot.related_user_id is None
                    or bot.related_user_id == related_user_id
                ):
                    return {
                        "context": bot.context,
                        "info": bot.info,
                        "memory": bot.memory,
                        "relationship_score": bot.relationship_score,
                        "relationship_type": (bot.relationship_type),
                        "styles": bot.styles or {},
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_data: {str(e)}")
            raise Exception(f"Failed to get bot data: {str(e)}") from e

    async def update_bot_context(self, bot_id: int, context: dict) -> bool:
        """更新bot的context字段"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()
                if bot:
                    bot.context = context
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_context: {str(e)}")
            await session.rollback()
            raise Exception(f"Failed to update bot context: {str(e)}") from e

    async def update_bot_memory(self, bot_id: int, memory: str) -> bool:
        """更新bot的memory字段"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()
                if bot:
                    bot.memory = memory
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_memory: {str(e)}")
            await session.rollback()
            raise Exception(f"Failed to update bot memory: {str(e)}") from e

    async def get_bot_by_id(self, bot_id: int):
        """获取bot信息"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_by_id: {str(e)}")
            raise Exception(f"Failed to get bot by id: {str(e)}") from e

    async def get_bot_by_entity_id(self, entity_id: str):
        """通过 entity_id 获取 bot 信息"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Bot).where(Bot.entity_id == entity_id)
                )
                bot = result.scalar_one_or_none()
                if bot:
                    # 转换枚举值
                    bot.status = self._convert_str_to_enum(BotStatus, bot.status)
                    bot.relationship_type = self._convert_str_to_enum(
                        RelationshipType, bot.relationship_type
                    )
                return bot
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_by_entity_id: {str(e)}")
            raise Exception(f"Failed to get bot by entity_id: {str(e)}") from e

    async def save_message(self, message: dict):
        """保存消息到数据库"""
        try:
            async with self.session_maker() as session:
                # 处理时间戳
                timestamp = message.get("timestamp")
                if isinstance(timestamp, str):
                    try:
                        # 将 ISO 格式转换为 datetime 对象
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    except ValueError:
                        logger.warning(
                            "Invalid timestamp format, using current time instead."
                        )
                        timestamp = datetime.now(timezone.utc)
                elif timestamp is None:
                    timestamp = datetime.now(timezone.utc)

                message_data = {
                    "from_entity": message["from_entity"],
                    "to_entity": message["to_entity"],
                    "message_id": message.get("message_id", ""),
                    "content": message.get("content", ""),
                    "message_type": message.get("message_type"),
                    "message_service": message.get("message_service"),
                    "timestamp": timestamp,
                    "status": message.get("status", "sent"),
                    "meta_data": message.get("meta_data", {}),
                }

                # 创建新消息实例
                new_message = MessageHistory(**message_data)
                session.add(new_message)
                await session.commit()
                return new_message
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            if "session" in locals():
                await session.rollback()
            raise

    async def get_user_by_id(self, user_id: int):
        """获取用户信息"""
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_messages_by_bot(
        self, from_entity: str, to_entity: str, limit: int = 10
    ):
        """获取会话历史消息"""
        async with self.session_maker() as session:
            query = (
                select(MessageHistory)
                .where(
                    (
                        (MessageHistory.from_entity == from_entity)
                        & (MessageHistory.to_entity == to_entity)
                    )
                    | (
                        (MessageHistory.from_entity == to_entity)
                        & (MessageHistory.to_entity == from_entity)
                    )
                )
                .order_by(MessageHistory.created_at.desc())
                .limit(limit)
            )

            result = await session.execute(query)
            messages = result.scalars().all()
            return [msg.to_dict() for msg in messages]

    async def update_bot_status(self, bot_id: int, status: BotStatus):
        """更新bot状态"""
        async with self.session_maker() as session:
            try:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()
                if bot:
                    # 转换为小写字符串存储
                    bot.status = self._convert_enum_to_str(status)
                    await session.commit()
                    return True
                return False
            except Exception as e:
                logger.error(f"Error updating bot status: {str(e)}")
                return False

    async def update_bot(self, bot_id: int, bot_data: dict) -> None:
        """更新bot信息"""
        async with self.session_maker() as session:
            try:
                stmt = select(Bot).where(Bot.id == bot_id)
                result = await session.execute(stmt)
                bot = result.scalar_one_or_none()

                if bot:
                    for key, value in bot_data.items():
                        setattr(bot, key, value)
                    await session.commit()
                else:
                    logger.error(f"Bot not found with id: {bot_id}")
                    raise ValueError(f"Bot not found with id: {bot_id}")

            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating bot: {str(e)}")
                raise

    async def get_active_bots(self):
        """获取所有活跃的bot"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(Bot).where(Bot.status == BotStatus.ACTIVE)
            )
            return result.scalars().all()
