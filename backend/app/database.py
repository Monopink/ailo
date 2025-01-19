from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, JSON, ForeignKey
from datetime import datetime
import enum
import asyncio
import logging

# 配置日志记录器
logger = logging.getLogger(__name__)

# 数据库配置
DATABASE_URL = "mysql+aiomysql://root:root@db/says_dev"
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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