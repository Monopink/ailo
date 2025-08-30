"""
AI Repository interface definitions.

These interfaces define the contracts for AI data access operations,
following the Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession


class AICharacterRepository(ABC):
    """Abstract interface for AI character data operations."""

    @abstractmethod
    async def get_by_qiao_id(self, db: AsyncSession, qiao_id: str) -> Optional[Dict[str, Any]]:
        """Get character by qiao_id."""
        pass

    @abstractmethod
    async def get_with_relations(
        self, db: AsyncSession, character_qiao_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get character with all related data."""
        pass


class AIPersonalityRepository(ABC):
    """Abstract interface for AI personality data operations."""

    @abstractmethod
    async def get_with_placeholders(
        self, db: AsyncSession, personality_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get personality with placeholders."""
        pass

    @abstractmethod
    async def get_available(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get available personalities."""
        pass


class AIStyleRepository(ABC):
    """Abstract interface for AI style data operations."""

    @abstractmethod
    async def get_with_relationships(self, db: AsyncSession, style_id: int) -> Optional[Dict[str, Any]]:
        """Get style with relationship mappings."""
        pass

    @abstractmethod
    async def get_relationship_mappings(self, db: AsyncSession, style_id: int) -> List[Dict[str, Any]]:
        """Get relationship mappings for a style."""
        pass


class AIRelationshipRepository(ABC):
    """Abstract interface for AI relationship scoring operations."""

    @abstractmethod
    async def get_user_scores(
        self, db: AsyncSession, user_qiao_id: str, character_qiao_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get relationship scores between user and character."""
        pass

    @abstractmethod
    async def update_scores_batch(
        self, db: AsyncSession, character_id: int, user_qiao_id: str, new_scores: Dict[str, int]
    ) -> bool:
        """Update relationship scores in batch."""
        pass

    @abstractmethod
    async def initialize_default_scores(
        self, db: AsyncSession, character_id: int, user_qiao_id: str, style_score_names: List[str]
    ) -> bool:
        """Initialize default relationship scores."""
        pass


class AITemplateRepository(ABC):
    """Abstract interface for AI template operations."""

    @abstractmethod
    async def get_profile_with_info(self, db: AsyncSession, template_id: int) -> Optional[Dict[str, Any]]:
        """Get profile template with associated info template."""
        pass

    @abstractmethod
    async def cleanup_single_use_templates(
        self, db: AsyncSession, profile_template_id: int, info_template_id: int
    ) -> None:
        """Clean up single-use templates after character creation."""
        pass


class AIContextRepository(ABC):
    """Abstract interface for AI context operations."""

    @abstractmethod
    async def get_conversation_history(
        self, db: AsyncSession, user_qiao_id: str, character_qiao_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get conversation history between user and character."""
        pass

    @abstractmethod
    async def archive_old_contexts(
        self, db: AsyncSession, character_qiao_id: str, max_age_days: int = 30
    ) -> int:
        """Archive old contexts and return count of archived contexts."""
        pass

    @abstractmethod
    async def update_status(self, db: AsyncSession, context_id: int, status: int) -> bool:
        """Update context reply status."""
        pass


class AIRequestLogRepository(ABC):
    """Abstract interface for AI request log operations."""

    @abstractmethod
    async def get_usage_stats(
        self, db: AsyncSession, character_id: Optional[int] = None, days: int = 7
    ) -> Dict[str, Any]:
        """Get usage statistics for AI requests."""
        pass

    @abstractmethod
    async def get_error_logs(
        self, db: AsyncSession, character_id: Optional[int] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent error logs."""
        pass

    @abstractmethod
    async def cleanup_old_logs(self, db: AsyncSession, days_to_keep: int = 90) -> int:
        """Clean up old request logs."""
        pass
