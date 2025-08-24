"""
AI relationship score CRUD operations.

This module contains CRUD operations for AI relationship scores.
"""

from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIRelationshipScore


class CRUDAIRelationshipScore(CRUDBase[AIRelationshipScore, dict, dict]):
    """CRUD operations for AIRelationshipScore model."""

    async def get_character_scores(
        self, db: AsyncSession, *, character_id: int
    ) -> List[AIRelationshipScore]:
        """Get all scores for a character."""
        result = await db.execute(
            select(self.model)
            .where(self.model.character_id == character_id)
            .order_by(self.model.score_order)
        )
        return result.scalars().all()

    async def get_score_by_order(
        self, db: AsyncSession, *, character_id: int, score_order: int
    ) -> Optional[AIRelationshipScore]:
        """Get specific score by order."""
        result = await db.execute(
            select(self.model).where(
                and_(self.model.character_id == character_id, self.model.score_order == score_order)
            )
        )
        return result.scalar_one_or_none()

    async def update_score(
        self, db: AsyncSession, *, character_id: int, score_order: int, new_score: int
    ) -> Optional[AIRelationshipScore]:
        """Update a specific score."""
        score_record = await self.get_score_by_order(db, character_id=character_id, score_order=score_order)
        if score_record:
            score_record.score = new_score
            # Calculate position (per mille)
            score_record.score_position = int(
                (new_score - score_record.score_start)
                * 1000
                / (score_record.score_end - score_record.score_start)
            )
            db.add(score_record)
            await db.commit()
            await db.refresh(score_record)
        return score_record


# Create instance
ai_relationship_score = CRUDAIRelationshipScore(AIRelationshipScore)
