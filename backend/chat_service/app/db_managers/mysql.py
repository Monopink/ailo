from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, JSON, ForeignKey
from datetime import datetime, timezone
import enum
import asyncio
import logging
from typing import Optional
from sqlalchemy.exc import SQLAlchemyError  # 导入 SQLAlchemy 异常基类

# 配置日志记录器
logger = logging.getLogger(__name__)

# 数据库配置
DATABASE_URL = "mysql+aiomysql://root:root@db/says_dev?charset=utf8mb4"
engine = create_async_engine(DATABASE_URL, echo=True) # echo=True 会打印出执行的SQL语句
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# 枚举类型定义
class UserStatus(enum.Enum):
    active = "active"
    inactive = "inactive"
    banned = "banned"

class UserRole(enum.Enum):
    user = "user"
    admin = "admin"
    moderator = "moderator"

class BotStatus(enum.Enum):
    active = "active"
    inactive = "inactive"

class RelationType(enum.Enum):
    stranger = "stranger"
    friend = "friend"
    confidant = "confidant"
    lover = "lover"

# 模型定义
class User(Base):
    __tablename__ = 'user'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    last_login = Column(DateTime)
    status = Column(Enum(UserStatus), default=UserStatus.active)
    role = Column(Enum(UserRole), default=UserRole.user)
    language = Column(String(10), default='zh')
    area = Column(String(100), default='China')
    phone = Column(String(20))

class Bot(Base):
    __tablename__ = 'bot'
    
    id = Column(Integer, primary_key=True)
    model = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    status = Column(Enum(BotStatus), default=BotStatus.active)
    gender = Column(String(10), nullable=False)
    birth_date = Column(DateTime)
    time_zone = Column(String(10), default='+8:00')
    city_name = Column(String(100))
    user_id = Column(Integer, ForeignKey('user.id', ondelete='SET NULL'))
    relationship_score = Column(Integer, default=0)
    relationship_type = Column(Enum(RelationType), default=RelationType.stranger)
    context = Column(JSON)
    important_context = Column(JSON)
    memory = Column(Text)
    stranger_style = Column(Text)
    friend_style = Column(Text)
    confidant_style = Column(Text)
    lover_style = Column(Text)

class MessageHistory(Base):
    __tablename__ = 'message_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_id = Column(String(36), nullable=False)
    to_id = Column(String(36), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default='chat')
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    status = Column(Enum('sent', 'delivered', 'read', 'failed'), default='sent')
    meta_data = Column(JSON)
    message_service = Column(String(36))

    # 显式声明要映射的列
    __mapper_args__ = {
        'include_properties': [
            'id', 'from_id', 'to_id', 'content', 'message_type',
            'created_at', 'status', 'meta_data', 'message_service'
        ]
    }

    def to_dict(self):
        return {
            'id': self.id,
            'from_id': self.from_id,
            'to_id': self.to_id,
            'content': self.content,
            'message_type': self.message_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status,
            'meta_data': self.meta_data,
            'message_service': self.message_service
        }

class DatabaseManager:
    def __init__(self):
        self.session_maker = async_session
        self._init_task = asyncio.create_task(self._initialize())
        
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
                logger.warning(f"Database connection attempt {retry_count} failed. Retrying in {delay} seconds... Error: {str(e)}")
                await asyncio.sleep(delay)
            except Exception as e:
                error_msg = f"Unexpected error during database initialization: {str(e)}"
                logger.critical(error_msg)
                raise Exception(error_msg) from e

    async def get_bot_context(self, bot_id: int, user_id: int) -> Optional[dict]:
        """获取bot上下文"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Bot).where(Bot.id == bot_id)
                )
                bot = result.scalar_one_or_none()
                if bot and (bot.user_id is None or bot.user_id == user_id):
                    return {
                        'context': bot.context or {},
                        'important_context': bot.important_context or {},
                        'memory': bot.memory,
                        'relationship_score': bot.relationship_score,
                        'relationship_type': bot.relationship_type.value if bot.relationship_type else None
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_context: {str(e)}")
            raise Exception(f"Failed to get bot context: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error in get_bot_context: {str(e)}")
            raise

    async def update_bot_context(self, bot_id: int, context_data: dict) -> bool:
        """更新bot上下文"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Bot).where(Bot.id == bot_id)
                )
                bot = result.scalar_one_or_none()
                if bot:
                    valid_fields = {'context', 'important_context', 'memory', 
                                  'relationship_score', 'relationship_type'}
                    update_data = {k: v for k, v in context_data.items() 
                                 if k in valid_fields}
                    
                    for key, value in update_data.items():
                        setattr(bot, key, value)
                    
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_context: {str(e)}")
            await session.rollback()
            raise Exception(f"Failed to update bot context: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error in update_bot_context: {str(e)}")
            if 'session' in locals():
                await session.rollback()
            raise

    async def get_bot_by_id(self, bot_id: int):
        async with self.session_maker() as session:
            result = await session.execute(select(Bot).where(Bot.id == bot_id))
            return result.scalar_one_or_none()

    async def save_message(self, message: dict):
        """保存消息到数据库"""
        try:
            async with self.session_maker() as session:
                # 只包含数据库表中实际存在的字段
                message_data = {
                    'from_id': message['from_id'],
                    'to_id': message['to_id'],
                    'content': message.get('content', ''),
                    'message_type': message.get('message_type', 'chat'),
                    'message_service': message.get('message_service'),
                    'meta_data': message.get('meta_data'),
                    'status': message.get('status', 'sent')
                }
                new_message = MessageHistory(**message_data)
                session.add(new_message)
                await session.commit()
                return new_message
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            if 'session' in locals():
                await session.rollback()
            raise

    async def get_user_by_id(self, user_id: int):
        """获取用户信息"""
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_messages_by_session(self, from_id: str, to_id: str, limit: int = 10):
        """获取会话历史消息"""
        async with self.session_maker() as session:
            query = select(MessageHistory).where(
                ((MessageHistory.from_id == from_id) & (MessageHistory.to_id == to_id)) |
                ((MessageHistory.from_id == to_id) & (MessageHistory.to_id == from_id))
            ).order_by(MessageHistory.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            messages = result.scalars().all()
            return [msg.to_dict() for msg in messages]

    async def get_active_bots(self):
        """获取所有活跃的机器人"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(Bot).where(Bot.status == BotStatus.active)
            )
            return result.scalars().all()

    async def update_bot_status(self, bot_id: int, status: BotStatus):
        """更新机器人状态"""
        async with self.session_maker() as session:
            try:
                result = await session.execute(
                    select(Bot).where(Bot.id == bot_id)
                )
                bot = result.scalar_one_or_none()
                if bot:
                    bot.status = status
                    await session.commit()
                    return True
                return False
            except Exception as e:
                logger.error(f"Error updating bot status: {str(e)}")
                return False

    async def get_bot_settings(self, bot_id: int):
        """获取机器人设置"""
        async with self.session_maker() as session:
            result = await session.execute(select(Bot).where(Bot.id == bot_id))
            bot = result.scalar_one_or_none()
            if bot:
                return {
                    'id': bot.id,
                    'model': bot.model,
                    'status': bot.status.value,
                    'gender': bot.gender,
                    'time_zone': bot.time_zone,
                    'city_name': bot.city_name,
                    'relationship_score': bot.relationship_score,
                    'relationship_type': bot.relationship_type.value,
                    'stranger_style': bot.stranger_style,
                    'friend_style': bot.friend_style,
                    'confidant_style': bot.confidant_style,
                    'lover_style': bot.lover_style
                }
            return None

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

# 创建全局数据库管理器实例
db_manager = DatabaseManager()