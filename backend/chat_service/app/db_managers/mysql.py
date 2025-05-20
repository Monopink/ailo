"""
数据库管理模块，提供与MySQL数据库交互的功能。

Base 是 SQLAlchemy 的声明式基类，用于定义所有 ORM 模型的基类。
所有继承自 Base 的类都会被映射到数据库表，并自动创建表结构。
"""

import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
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

# 创建声明式基类，所有模型类都继承自这个基类
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
    timezone = Column(String(50), default="Asia/Shanghai")
    city_name = Column(String(100))
    friend_score = Column(Integer, default=0)
    romance_score = Column(Integer, default=0)
    friend_score_upper_limit = Column(Integer, default=5000)
    friend_score_lower_limit = Column(Integer, default=0)
    romance_score_upper_limit = Column(Integer, default=5000)
    friend_score_pos_k = Column(Integer, default=1000)
    friend_score_neg_k = Column(Integer, default=100)
    romance_score_k = Column(Integer, default=1000)
    friend_score_anger_minus = Column(Integer, default=0)
    romance_score_anger_minus = Column(Integer, default=0)
    last_chat_time = Column(DateTime)
    relationship_type = Column(String(20), default="friend")
    relationship_level = Column(String(20), default="neutral")
    relationship_style = Column(Text)
    friend_config = Column(JSON)
    romance_config = Column(JSON)
    override_config = Column(JSON)
    is_polite = Column(Integer, default=0)  # 新增：是否礼貌
    is_crushing = Column(Integer, default=0)  # 新增：是否暗恋
    emotions_config = Column(JSON)
    context = Column(JSON)
    info = Column(Text)
    memory = Column(Text)


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


class Emotion(Base):
    """情绪模型，对应数据库中的 emotions 表

    继承自 Base 表示这是一个 ORM 模型，会映射到数据库表
    """

    __tablename__ = "emotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=datetime.now(timezone.utc)
    )  # MySQL 会通过触发器自动更新
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    emotion_type = Column(String(50), nullable=False)  # 情绪类型，如 anger, happy
    emotion_score = Column(Integer, default=0)  # 情绪分数，范围 1-12
    emotion_level = Column(Integer, default=0)  # 情绪等级
    start_time = Column(DateTime)  # 情绪开始时间
    end_time = Column(DateTime)  # 情绪结束时间
    update_time = Column(DateTime)  # 情绪更新时间


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
                logger.info("Attempting to connect to database...")
                async with self.session_maker() as session:
                    # 测试连接
                    await session.execute(text("SELECT 1"))
                    logger.info("Database connection test successful")

                    # 检查表结构
                    try:
                        # 检查 bots 表是否有所有必要的列
                        await session.execute(
                            text("SELECT friend_score FROM bots LIMIT 1")
                        )
                        logger.info("Database schema validation successful")
                    except SQLAlchemyError as schema_error:
                        logger.warning(
                            f"Database schema validation failed: {str(schema_error)}"
                        )
                        logger.warning(
                            "This might be expected if the database is newly created or being updated"
                        )

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

                if bot and (bot.user_id is None or bot.user_id == related_user_id):
                    # 构建relationship字典
                    relationship = {
                        "type": bot.relationship_type,
                        "level": bot.relationship_level,
                        "style": bot.relationship_style,
                    }

                    return {
                        "context": bot.context,
                        "info": bot.info,
                        "memory": bot.memory,
                        "friend_score": bot.friend_score,
                        "romance_score": bot.romance_score,
                        "relationship": relationship,
                        "friend_config": bot.friend_config,
                        "romance_config": bot.romance_config,
                        "override_config": bot.override_config,
                        "is_polite": bool(bot.is_polite),
                        "is_crushing": bool(bot.is_crushing),
                        "emotions_config": bot.emotions_config,
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

    async def get_bot_emotions(self, bot_id: int) -> List[Dict]:
        """获取bot的情绪数据"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Emotion).where(Emotion.bot_id == bot_id)
                )
                emotions = result.scalars().all()
                return [
                    {
                        "id": emotion.id,
                        "emotion_type": emotion.emotion_type,
                        "emotion_score": emotion.emotion_score,
                        "emotion_level": emotion.emotion_level,
                        "start_time": (
                            emotion.start_time.isoformat()
                            if emotion.start_time
                            else None
                        ),
                        "end_time": (
                            emotion.end_time.isoformat() if emotion.end_time else None
                        ),
                        "update_time": (
                            emotion.update_time.isoformat()
                            if emotion.update_time
                            else None
                        ),
                    }
                    for emotion in emotions
                ]
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_emotions: {str(e)}")
            raise Exception(f"Failed to get bot emotions: {str(e)}") from e

    async def update_bot_emotion(
        self, bot_id: int, emotion_type: str, emotion_score: int, emotion_level: int
    ) -> bool:
        """更新bot的情绪数据"""
        try:
            async with self.session_maker() as session:
                # 查找现有情绪
                result = await session.execute(
                    select(Emotion).where(
                        (Emotion.bot_id == bot_id)
                        & (Emotion.emotion_type == emotion_type)
                    )
                )
                emotion = result.scalar_one_or_none()

                now = datetime.now(timezone.utc)

                if emotion:
                    # 更新现有情绪
                    emotion.emotion_score = emotion_score
                    emotion.emotion_level = emotion_level
                    emotion.update_time = now
                    if emotion_score > 0:
                        # 如果分数大于0，设置开始时间和结束时间
                        if not emotion.start_time:
                            emotion.start_time = now
                        # 设置结束时间为当前时间加上一小时
                        emotion.end_time = now + timedelta(hours=1)
                    else:
                        # 如果分数为0，清除开始时间和结束时间
                        emotion.start_time = None
                        emotion.end_time = None
                else:
                    # 创建新情绪
                    new_emotion = Emotion(
                        bot_id=bot_id,
                        emotion_type=emotion_type,
                        emotion_score=emotion_score,
                        emotion_level=emotion_level,
                        update_time=now,
                    )
                    if emotion_score > 0:
                        new_emotion.start_time = now
                        new_emotion.end_time = now + timedelta(hours=1)

                    session.add(new_emotion)

                await session.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_emotion: {str(e)}")
            await session.rollback()
            raise Exception(f"Failed to update bot emotion: {str(e)}") from e

    async def update_bot_relationship(
        self,
        bot_id: int,
        relationship_type: Optional[str] = None,
        relationship_level: Optional[str] = None,
        relationship_style: Optional[str] = None,
    ) -> bool:
        """更新bot的关系信息

        Args:
            bot_id: Bot ID
            relationship_type: 关系类型
            relationship_level: 关系等级
            relationship_style: 关系风格

        Returns:
            bool: 更新是否成功
        """
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()
                if bot:
                    # 更新关系字段
                    if relationship_type:
                        bot.relationship_type = relationship_type
                    if relationship_level:
                        bot.relationship_level = relationship_level
                    if relationship_style:
                        bot.relationship_style = relationship_style

                    await session.commit()
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_relationship: {str(e)}")
            await session.rollback()
            raise Exception(f"Failed to update bot relationship: {str(e)}") from e
