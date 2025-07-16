"""
Emotion model for bot_message_service.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, DECIMAL
from ..base import Base


class Emotions(Base):
    """Emotion model, corresponding to the emotions table in the database

    Inherits from Base indicating it's an ORM model that maps to a database table
    """

    __tablename__ = "emotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=datetime.now(timezone.utc)
    )  # MySQL will automatically update this through triggers
    bot_id = Column(Integer, nullable=False, index=True)
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
