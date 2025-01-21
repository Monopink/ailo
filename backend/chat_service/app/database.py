from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, JSON, ForeignKey
from datetime import datetime, timezone, timedelta
import enum
import asyncio
import logging

# 配置日志记录器
logger = logging.getLogger(__name__)

# 数据库配置
DATABASE_URL = "mysql+aiomysql://root:root@db/says_dev?charset=utf8mb4"
engine = create_async_engine(DATABASE_URL, echo=True)
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
    sleep = "sleep"
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
    long_term_memory = Column(Text)
    short_term_memory = Column(Text)
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
    content_overview = Column(String(255))
    message_type = Column(String(50), default='text')
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    status = Column(Enum('sent', 'delivered', 'read', 'failed'), default='sent')
    meta_data = Column(JSON)

    def to_dict(self):
        return {
            'id': self.id,
            'from_id': self.from_id,
            'to_id': self.to_id,
            'content': self.content,
            'content_overview': self.content_overview,
            'message_type': self.message_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status': self.status,
            'meta_data': self.meta_data
        }

class Session(Base):
    __tablename__ = 'session'
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    bot_id = Column(Integer, ForeignKey('bot.id', ondelete='CASCADE'), nullable=False)
    started_at = Column(DateTime, default=datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    status = Column(String(20), default='active')
    context = Column(JSON)
    meta_data = Column(JSON)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'bot_id': self.bot_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'status': self.status,
            'context': self.context,
            'meta_data': self.meta_data
        }

# 数据库操作类
class DatabaseManager:
    def __init__(self):
        self.session_maker = async_session
        self._init_task = asyncio.create_task(self._initialize())
        
    async def _initialize(self):
        """初始化数据库连接"""
        try:
            async with self.session_maker() as session:
                await session.execute(text("SELECT 1"))
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {str(e)}")
            raise

    async def get_bot_by_id(self, bot_id: int):
        async with self.session_maker() as session:
            result = await session.execute(select(Bot).where(Bot.id == bot_id))
            return result.scalar_one_or_none()

    async def get_session(self, session_id: str):
        """获取会话"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Session).where(Session.id == session_id)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {str(e)}")
            return None

    async def create_session(self, session_id: str, user_id: int, bot_id: int):
        """创建新会话"""
        try:
            async with self.session_maker() as session:
                new_session = Session(
                    id=session_id,
                    user_id=user_id,
                    bot_id=bot_id,
                    context={},
                    meta_data={}
                )
                session.add(new_session)
                await session.commit()
                return new_session
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            return None

    async def update_session(self, session_id: str, update_data: dict):
        """更新会话"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Session).where(Session.id == session_id)
                )
                db_session = result.scalar_one_or_none()
                
                if db_session:
                    for key, value in update_data.items():
                        setattr(db_session, key, value)
                    await session.commit()
                    return db_session
                else:
                    # 如果会话不存在，尝试创建新会话
                    user_id = int(session_id.split('_')[1])
                    bot_id = int(session_id.split('_')[0])
                    return await self.create_session(session_id, user_id, bot_id)
                    
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {str(e)}")
            return None

    async def save_message(self, message: dict):
        """保存消息到数据库"""
        async with self.session_maker() as session:
            new_message = MessageHistory(
                from_id=message['from_id'],
                to_id=message['to_id'],
                content=message['content'],
                content_overview=message.get('content_overview'),
                message_type=message.get('message_type', 'text'),
                meta_data=message.get('meta_data')
            )
            session.add(new_message)
            await session.commit()
            return new_message

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

    async def update_session_context(self, session_id: str, context: dict):
        """更新会话上下文"""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Session).where(Session.id == session_id)
                )
                db_session = result.scalar_one_or_none()
                if db_session:
                    db_session.context = context
                    db_session.last_activity = datetime.now(timezone.utc)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating session context: {str(e)}")
            return False

    async def get_active_sessions(self, timeout_minutes: int = 30):
        """获取活跃会话"""
        timeout = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        async with self.session_maker() as session:
            result = await session.execute(
                select(Session).where(
                    (Session.status == 'active') &
                    (Session.last_activity >= timeout)
                )
            )
            return result.scalars().all()

    async def cleanup_inactive_sessions(self, timeout_minutes: int = 30):
        """清理不活跃的会话"""
        timeout = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        async with self.session_maker() as session:
            try:
                await session.execute(
                    text("""
                    UPDATE session 
                    SET status = 'inactive' 
                    WHERE status = 'active' 
                    AND last_activity < :timeout
                    """),
                    {"timeout": timeout}
                )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Error cleaning up inactive sessions: {str(e)}")
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