from sqlalchemy import select, insert, update, Column, String, DateTime, Text, Integer, Date, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

# 创建异步数据库引擎
DATABASE_URL = "mysql+aiomysql://user:password@db/says_dev"
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# 添加数据库模型定义
class MessageHistory(Base):
    __tablename__ = 'message_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user = Column('from', String(100), nullable=False)
    to_user = Column('to', String(100), nullable=False)
    content = Column(String(1000))
    content_overview = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.now)

class ScheduledMessage(Base):
    __tablename__ = 'scheduled_messages'
    
    id = Column(String(36), primary_key=True)
    from_user = Column(String(36), nullable=False)
    to_user = Column(String(36), nullable=False)
    content = Column(Text, nullable=False)
    send_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

class Bot(Base):
    __tablename__ = 'bot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)
    update_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    status = Column(String(50), default='active')
    gender = Column(String(50))
    birth_date = Column(Date)
    time_zone = Column(String(50))
    city_name = Column(String(100))
    user_id = Column(Integer, ForeignKey('user.id'))
    relationship_score = Column(Integer)
    relationship_type = Column(String(50))
    long_term_memory = Column(Text)
    short_term_memory = Column(Text)
    stranger_style = Column(Text)
    friend_style = Column(Text)
    confidant_style = Column(Text)
    lover_style = Column(Text)

class DatabaseManager:
    def __init__(self):
        self.session = None

    async def get_session(self) -> AsyncSession:
        if not self.session:
            self.session = async_session()
        return self.session

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def save_message(self, from_user: str, to_user: str, content: str) -> bool:
        try:
            session = await self.get_session()
            query = insert(MessageHistory).values(
                from_user=from_user,
                to_user=to_user,
                content=content,
                created_at=datetime.now()
            )
            await session.execute(query)
            await session.commit()
            return True
        except Exception as e:
            print(f"Error saving message: {e}")
            await session.rollback()
            return False

    async def get_chat_history(self, user_id: str, bot_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            session = await self.get_session()
            query = select(MessageHistory).where(
                ((MessageHistory.from_user == user_id) & (MessageHistory.to_user == bot_id)) |
                ((MessageHistory.from_user == bot_id) & (MessageHistory.to_user == user_id))
            ).order_by(MessageHistory.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            messages = result.scalars().all()
            
            return [
                {
                    "from_user": msg.from_user,
                    "to_user": msg.to_user,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    async def save_scheduled_message(self, from_user: str, to_user: str, 
                                   content: str, send_at: datetime) -> bool:
        try:
            session = await self.get_session()
            query = insert(ScheduledMessage).values(
                from_user=from_user,
                to_user=to_user,
                content=content,
                send_at=send_at,
                created_at=datetime.now()
            )
            await session.execute(query)
            await session.commit()
            return True
        except Exception as e:
            print(f"Error saving scheduled message: {e}")
            await session.rollback()
            return False

    async def get_bot_info(self, bot_id: str) -> Optional[Dict[str, Any]]:
        try:
            session = await self.get_session()
            query = select(Bot).where(Bot.id == int(bot_id))
            result = await session.execute(query)
            bot = result.scalar_one_or_none()
            
            if bot:
                return {
                    "id": str(bot.id),
                    "model": bot.model,
                    "status": bot.status,
                    "relationship_score": bot.relationship_score,
                    "relationship_type": bot.relationship_type,
                    "long_term_memory": bot.long_term_memory,
                    "short_term_memory": bot.short_term_memory,
                    "gender": bot.gender,
                    "time_zone": bot.time_zone,
                    "city_name": bot.city_name
                }
            return None
        except Exception as e:
            print(f"Error getting bot info: {e}")
            return None

# 数据库对象管理器实例
db_manager = DatabaseManager()