"""
Database management module that provides functionality for interacting with MySQL database.

Base is SQLAlchemy's declarative base class used to define the base class for all ORM models.
All classes inheriting from Base will be mapped to database tables and table structures will be created automatically.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    DECIMAL,
)
from sqlalchemy.exc import SQLAlchemyError  # Import SQLAlchemy base exception class
from enums import BotStatus
import enum
from datetime import timedelta

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "mysql+aiomysql://root:root@db/says_dev?charset=utf8mb4"
engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True will print executed SQL statements
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create declarative base class that all model classes will inherit from
Base = declarative_base()


# Model definitions
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
    friend_score_cap = Column(Integer, default=5000)
    friend_score_floor = Column(Integer, default=0)
    romance_score_cap = Column(Integer, default=5000)
    friend_score_peak = Column(Integer, default=0)
    friend_score_trough = Column(Integer, default=0)
    romance_score_peak = Column(Integer, default=0)
    friend_score_pos_k = Column(Integer, default=1000)
    friend_score_neg_k = Column(Integer, default=100)
    romance_score_k = Column(Integer, default=1000)
    last_chat_time = Column(DateTime)
    relationship_type = Column(String(20), default="friend")
    relationship_level = Column(String(20), default="neutral")
    friend_level = Column(String(20), default="neutral")
    romance_level = Column(String(20))
    friend_buffer_status = Column(String(20), default="none")
    romance_buffer_status = Column(String(20), default="none")
    relationship_style = Column(Text)
    friend_config = Column(JSON)
    romance_config = Column(JSON)
    override_config = Column(JSON)
    is_polite = Column(Integer, default=0)
    is_crushing = Column(Integer, default=0)
    emotions_config = Column(JSON)
    context = Column(JSON)
    context_metadata = Column(JSON)
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
    message_time = Column(DateTime)
    status = Column(String(20), default="sent")
    message_metadata = Column(JSON)

    # Explicitly declare columns to be mapped
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
            "message_time",
            "status",
            "message_metadata",
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
            "message_time": (self.message_time.isoformat() if self.message_time else None),
            "status": self.status,
            "message_metadata": self.message_metadata,
        }


class Emotion(Base):
    """Emotion model, corresponding to the emotions table in the database

    Inherits from Base indicating it's an ORM model that maps to a database table
    """

    __tablename__ = "emotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=datetime.now(timezone.utc)
    )  # MySQL will automatically update this through triggers
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    emotion_type = Column(String(50), nullable=False)  # Emotion type, such as anger, happy
    emotion_score = Column(Integer, default=0)  # Emotion score, range 1-12
    original_emotion_score = Column(Integer, default=0)  # Original emotion score before decay
    emotion_level = Column(Integer, default=0)  # Emotion level
    friend_score_delta = Column(Integer, default=0)  # Impact on friend score
    original_friend_score_delta = Column(Integer, default=0)  # Original impact on friend score
    romance_score_delta = Column(Integer, default=0)  # Impact on romance score
    original_romance_score_delta = Column(Integer, default=0)  # Original impact on romance score
    decay_ratio = Column(DECIMAL(3, 2), default=0.8)  # Decay ratio for emotion over time
    start_time = Column(DateTime)  # Emotion start time
    end_time = Column(DateTime)  # Emotion end time (actual end time)
    original_end_time = Column(DateTime)  # Original planned end time
    is_ended = Column(Integer, default=0)  # Whether the emotion has ended
    update_time = Column(DateTime)  # Emotion update time


class MySQLManager:
    def __init__(self):
        self.session_maker = async_session
        self._init_task = asyncio.create_task(self._initialize())

    def _convert_enum_to_str(self, value: Optional[enum.Enum]) -> Optional[str]:
        """Convert enum value to string."""
        return value.value.lower() if value is not None else None

    def _convert_str_to_enum(self, enum_class: type, value: Optional[str]) -> Optional[enum.Enum]:
        """Convert string to enum value."""
        if value is None:
            return None
        try:
            return enum_class.__members__[value.upper()]
        except KeyError:
            logger.warning(f"Invalid enum value: {value} for enum class: {enum_class}")
            return None

    async def _initialize(self):
        """Initialize database connection with retry mechanism."""
        max_retries = 100
        retry_count = 0
        base_delay = 1  # Initial delay 1 second
        max_delay = 30  # Maximum delay 30 seconds

        while True:
            try:
                logger.info("Attempting to connect to database...")
                async with self.session_maker() as session:
                    # Test connection
                    await session.execute(text("SELECT 1"))
                    logger.info("Database connection test successful")

                    # Check table schema
                    try:
                        # Check if bots table has all necessary columns
                        await session.execute(text("SELECT friend_score FROM bots LIMIT 1"))
                        logger.info("Database schema validation successful")
                    except SQLAlchemyError as schema_error:
                        logger.warning(f"Database schema validation failed: {str(schema_error)}")
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

                # Calculate delay for next retry (exponential backoff)
                delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
                logger.warning(
                    f"Database connection attempt {retry_count} failed. Retrying in {delay} seconds... Error: {str(e)}"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                error_msg = f"Unexpected error during database initialization: {str(e)}"
                logger.critical(error_msg)
                raise Exception(error_msg) from e

    async def get_user_by_id(self, user_id: int):
        """Get user information."""
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_bot_by_id(self, bot_id: int):
        """Get bot information by id."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_by_id: {str(e)}")
            raise Exception(f"Failed to get bot by id: {str(e)}") from e

    async def get_bot_by_entity_id(self, entity_id: str):
        """Get bot information by entity_id."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.entity_id == entity_id))
                bot = result.scalar_one_or_none()
                if bot:
                    # Convert enum value
                    bot.status = self._convert_str_to_enum(BotStatus, bot.status)
                return bot
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_by_entity_id: {str(e)}")
            raise Exception(f"Failed to get bot by entity_id: {str(e)}") from e

    async def get_bot_data(self, bot_id: int, related_user_id: Optional[int] = None) -> Optional[dict]:
        """Get all relevant data for a bot."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()

                if bot and (bot.user_id is None or bot.user_id == related_user_id):
                    # Build relationship dictionary
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

    async def update_bot_data(self, bot_id: int, bot_data: dict) -> None:
        """Update bot information based on a dictionary of changes."""
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

    async def get_emotions_data(self, bot_id: int) -> Dict[str, Dict[str, Any]]:
        """Get the current active emotions for a bot

        Retrieves emotions that have not ended (is_ended=FALSE).
        If there are multiple active emotions of the same type, selects the one with the most recent start_time.

        Args:
            bot_id: Bot ID

        Returns:
            Dict[str, Dict[str, Any]]: Mapping from emotion type to emotion details
        """
        try:
            async with self.session_maker() as session:
                now = datetime.now(timezone.utc)

                # Query for valid emotions that have not ended
                query = """
                SELECT e.* 
                FROM emotions e
                INNER JOIN (
                    SELECT emotion_type, MAX(start_time) as latest_start_time
                    FROM emotions
                    WHERE bot_id = :bot_id 
                        AND start_time IS NOT NULL 
                        AND is_ended = FALSE
                    GROUP BY emotion_type
                ) latest ON e.emotion_type = latest.emotion_type AND e.start_time = latest.latest_start_time
                WHERE e.bot_id = :bot_id
                """

                result = await session.execute(text(query), {"bot_id": bot_id, "now": now})
                emotions = result.fetchall()

                # Check for duplicate emotions with the same type and start_time
                emotion_counts = {}
                for emotion in emotions:
                    emotion_type = emotion.emotion_type
                    if emotion_type in emotion_counts:
                        emotion_counts[emotion_type] += 1
                    else:
                        emotion_counts[emotion_type] = 1

                # Log warning for duplicate emotions
                for emotion_type, count in emotion_counts.items():
                    if count > 1:
                        logger.warning(
                            f"Multiple active emotions found for bot {bot_id}, type {emotion_type}. "
                            f"Using the one with most recent start_time."
                        )

                # Build the return result
                emotions_dict = {}
                for emotion in emotions:
                    emotions_dict[emotion.emotion_type] = {
                        "emotion_score": emotion.emotion_score,
                        "original_emotion_score": emotion.original_emotion_score,
                        "emotion_level": emotion.emotion_level,
                        "friend_score_delta": emotion.friend_score_delta,
                        "original_friend_score_delta": emotion.original_friend_score_delta,
                        "romance_score_delta": emotion.romance_score_delta,
                        "original_romance_score_delta": emotion.original_romance_score_delta,
                        "decay_ratio": (float(emotion.decay_ratio) if emotion.decay_ratio else 0.8),
                        "start_time": (emotion.start_time.isoformat() if emotion.start_time else None),
                        "end_time": (emotion.end_time.isoformat() if emotion.end_time else None),
                        "original_end_time": (
                            emotion.original_end_time.isoformat() if emotion.original_end_time else None
                        ),
                        "is_ended": bool(emotion.is_ended),
                        "update_time": (emotion.update_time.isoformat() if emotion.update_time else None),
                    }

                return emotions_dict

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_current_bot_emotions: {str(e)}")
            raise Exception(f"Failed to get current bot emotions: {str(e)}") from e

    async def update_emotions_data(self, bot_id: int, emotions: Dict[str, Dict[str, Any]]) -> bool:
        """Batch update a bot's emotion data

        If there exists an emotion with the same emotion_type and same start_time,
        update that emotion, otherwise create a new emotion record.

        Args:
            bot_id: Bot ID
            emotions: Emotion data in format {emotion_type: {emotion_details}}

        Returns:
            bool: Whether the update was successful
        """
        try:
            async with self.session_maker() as session:
                for emotion_type, emotion_data in emotions.items():
                    # Parse time fields
                    start_time = None
                    if "start_time" in emotion_data and emotion_data["start_time"]:
                        if isinstance(emotion_data["start_time"], str):
                            start_time = datetime.fromisoformat(
                                emotion_data["start_time"].replace("Z", "+00:00")
                            )
                        else:
                            start_time = emotion_data["start_time"]
                    else:
                        start_time = datetime.now(timezone.utc)

                    end_time = None
                    if "end_time" in emotion_data and emotion_data["end_time"]:
                        if isinstance(emotion_data["end_time"], str):
                            end_time = datetime.fromisoformat(emotion_data["end_time"].replace("Z", "+00:00"))
                        else:
                            end_time = emotion_data["end_time"]
                    else:
                        # Default end time is start time plus one hour
                        end_time = start_time + timedelta(hours=1)

                    original_end_time = None
                    if "original_end_time" in emotion_data and emotion_data["original_end_time"]:
                        if isinstance(emotion_data["original_end_time"], str):
                            original_end_time = datetime.fromisoformat(
                                emotion_data["original_end_time"].replace("Z", "+00:00")
                            )
                        else:
                            original_end_time = emotion_data["original_end_time"]
                    else:
                        # Default original end time is same as end time
                        original_end_time = end_time

                    update_time = None
                    if "update_time" in emotion_data and emotion_data["update_time"]:
                        if isinstance(emotion_data["update_time"], str):
                            update_time = datetime.fromisoformat(
                                emotion_data["update_time"].replace("Z", "+00:00")
                            )
                        else:
                            update_time = emotion_data["update_time"]
                    else:
                        update_time = datetime.now(timezone.utc)

                    # Get original values from data or use current values
                    original_emotion_score = emotion_data.get(
                        "original_emotion_score", emotion_data.get("emotion_score", 0)
                    )

                    original_friend_score_delta = emotion_data.get(
                        "original_friend_score_delta",
                        emotion_data.get("friend_score_delta", 0),
                    )

                    original_romance_score_delta = emotion_data.get(
                        "original_romance_score_delta",
                        emotion_data.get("romance_score_delta", 0),
                    )

                    decay_ratio = emotion_data.get("decay_ratio", 0.8)
                    is_ended = emotion_data.get("is_ended", False)

                    # Find if there's an emotion with the same type and start time
                    if start_time:
                        # Query for emotions with the same type and start time
                        query = """
                        SELECT * FROM emotions 
                        WHERE bot_id = :bot_id 
                        AND emotion_type = :emotion_type 
                        AND start_time = :start_time
                        """

                        result = await session.execute(
                            text(query),
                            {
                                "bot_id": bot_id,
                                "emotion_type": emotion_type,
                                "start_time": start_time,
                            },
                        )
                        existing_emotion = result.fetchone()

                        if existing_emotion:
                            # Update existing emotion
                            update_query = """
                            UPDATE emotions 
                            SET emotion_score = :emotion_score,
                                emotion_level = :emotion_level,
                                original_emotion_score = :original_emotion_score,
                                friend_score_delta = :friend_score_delta,
                                original_friend_score_delta = :original_friend_score_delta,
                                romance_score_delta = :romance_score_delta,
                                original_romance_score_delta = :original_romance_score_delta,
                                decay_ratio = :decay_ratio,
                                end_time = :end_time,
                                original_end_time = :original_end_time,
                                is_ended = :is_ended,
                                update_time = :update_time
                            WHERE id = :id
                            """

                            await session.execute(
                                text(update_query),
                                {
                                    "id": existing_emotion.id,
                                    "emotion_score": emotion_data.get(
                                        "emotion_score", existing_emotion.emotion_score
                                    ),
                                    "emotion_level": emotion_data.get(
                                        "emotion_level", existing_emotion.emotion_level
                                    ),
                                    "original_emotion_score": original_emotion_score,
                                    "friend_score_delta": emotion_data.get("friend_score_delta", 0),
                                    "original_friend_score_delta": original_friend_score_delta,
                                    "romance_score_delta": emotion_data.get("romance_score_delta", 0),
                                    "original_romance_score_delta": original_romance_score_delta,
                                    "decay_ratio": decay_ratio,
                                    "end_time": end_time,
                                    "original_end_time": original_end_time,
                                    "is_ended": is_ended,
                                    "update_time": update_time,
                                },
                            )
                            logger.debug(f"Updated existing emotion: {emotion_type} for bot {bot_id}")
                        else:
                            # Create new emotion
                            insert_query = """
                            INSERT INTO emotions 
                            (bot_id, emotion_type, emotion_score, original_emotion_score, emotion_level, 
                             friend_score_delta, original_friend_score_delta, 
                             romance_score_delta, original_romance_score_delta, 
                             decay_ratio, start_time, end_time, original_end_time, is_ended, update_time)
                            VALUES
                            (:bot_id, :emotion_type, :emotion_score, :original_emotion_score, :emotion_level, 
                             :friend_score_delta, :original_friend_score_delta, 
                             :romance_score_delta, :original_romance_score_delta, 
                             :decay_ratio, :start_time, :end_time, :original_end_time, :is_ended, :update_time)
                            """

                            await session.execute(
                                text(insert_query),
                                {
                                    "bot_id": bot_id,
                                    "emotion_type": emotion_type,
                                    "emotion_score": emotion_data.get("emotion_score", 0),
                                    "original_emotion_score": original_emotion_score,
                                    "emotion_level": emotion_data.get("emotion_level", 0),
                                    "friend_score_delta": emotion_data.get("friend_score_delta", 0),
                                    "original_friend_score_delta": original_friend_score_delta,
                                    "romance_score_delta": emotion_data.get("romance_score_delta", 0),
                                    "original_romance_score_delta": original_romance_score_delta,
                                    "decay_ratio": decay_ratio,
                                    "start_time": start_time,
                                    "end_time": end_time,
                                    "original_end_time": original_end_time,
                                    "is_ended": is_ended,
                                    "update_time": update_time,
                                },
                            )
                            logger.debug(f"Created new emotion: {emotion_type} for bot {bot_id}")

                await session.commit()
                return True

        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_emotions: {str(e)}")
            await session.rollback()
            raise Exception(f"Failed to update bot emotions: {str(e)}") from e

    async def get_messages_by_bot(self, from_entity: str, to_entity: str, limit: int = 10):
        """Get session history messages."""
        async with self.session_maker() as session:
            query = (
                select(MessageHistory)
                .where(
                    ((MessageHistory.from_entity == from_entity) & (MessageHistory.to_entity == to_entity))
                    | ((MessageHistory.from_entity == to_entity) & (MessageHistory.to_entity == from_entity))
                )
                .order_by(MessageHistory.created_at.desc())
                .limit(limit)
            )

            result = await session.execute(query)
            messages = result.scalars().all()
            return [msg.to_dict() for msg in messages]

    async def save_message(self, message: dict):
        """Save message to the database."""
        try:
            async with self.session_maker() as session:
                # Handle timestamp
                timestamp = message.get("timestamp")
                if isinstance(timestamp, str):
                    try:
                        # Convert ISO format to datetime object
                        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        logger.warning("Invalid timestamp format, using current time instead.")
                        timestamp = datetime.now(timezone.utc)
                elif timestamp is None:
                    timestamp = datetime.now(timezone.utc)

                message_data = {
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "from_entity": message["from_entity"],
                    "to_entity": message["to_entity"],
                    "message_id": message.get("message_id", ""),
                    "content": message.get("content", ""),
                    "message_type": message.get("message_type"),
                    "message_service": message.get("message_service"),
                    "message_time": timestamp,
                    "status": message.get("status", "sent"),
                    "message_metadata": message.get("message_metadata", {}),
                }

                # Create new message instance
                new_message = MessageHistory(**message_data)
                session.add(new_message)
                await session.commit()
                return new_message
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            if "session" in locals():
                await session.rollback()
            raise
