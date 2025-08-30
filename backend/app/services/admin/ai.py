"""
Admin AI management service.

This module provides administrative functions for managing AI templates,
characters, and configurations through the admin panel.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

# Using AI CRUD layer for admin operations
from crud.ai import (
    ai_personality,
    ai_personality_placeholder,
    ai_style,
    ai_relationship,
    ai_relationship_index,
    ai_character,
    ai_info_template,
    ai_profile_template,
)
from utils.logging import get_logger

logger = get_logger(__name__)


# AI Personality Template Management
async def get_personality_templates(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """Get list of AI personality templates."""
    try:
        personalities = await ai_personality.get_multi(db, skip=skip, limit=limit)

        result = []
        for personality in personalities:
            # Get placeholders for this personality
            placeholders = await ai_personality_placeholder.get_by_personality_id(
                db, personality_id=personality.id
            )

            result.append(
                {
                    "id": personality.id,
                    "name": personality.name,
                    "prompt": personality.prompt,
                    "json_schema": personality.json_schema,
                    "placeholders": [
                        {
                            "key": p.placeholder_key,
                            "value": p.default_value,
                            "description": p.description,
                        }
                        for p in placeholders
                    ],
                    "created_at": personality.created_at,
                    "updated_at": personality.updated_at,
                }
            )

        return result

    except Exception as e:
        logger.error("get_personality_templates_error", error=str(e))
        return []


async def create_personality_template(
    db: AsyncSession, template_data: Dict[str, Any], admin_id: int
) -> Optional[Dict[str, Any]]:
    """Create new AI personality template."""
    try:
        # Create personality
        personality = await ai_personality.create(
            db,
            obj_in={
                "name": template_data["name"],
                "prompt": template_data["prompt"],
                "json_schema": template_data.get("json_schema"),
            },
        )

        # Create placeholders
        placeholders_data = template_data.get("placeholders", [])
        for placeholder_data in placeholders_data:
            await ai_personality_placeholder.create(
                db,
                obj_in={
                    "personality_id": personality.id,
                    "placeholder_key": placeholder_data["key"],
                    "placeholder_type": placeholder_data.get("type", 1),
                    "default_value": placeholder_data.get("value"),
                    "description": placeholder_data.get("description"),
                },
            )

        logger.info(
            "personality_template_created",
            personality_id=personality.id,
            name=personality.name,
            admin_id=admin_id,
        )

        return await get_personality_template(db, personality.id)

    except Exception as e:
        logger.error("create_personality_template_error", error=str(e), admin_id=admin_id)
        return None


async def get_personality_template(db: AsyncSession, personality_id: int) -> Optional[Dict[str, Any]]:
    """Get single personality template with details."""
    try:
        personality = await ai_personality.get(db, id=personality_id)
        if not personality:
            return None

        placeholders = await ai_personality_placeholder.get_by_personality_id(
            db, personality_id=personality_id
        )

        return {
            "id": personality.id,
            "name": personality.name,
            "prompt": personality.prompt,
            "json_schema": personality.json_schema,
            "usage_count": personality.usage_count,
            "status": personality.status,
            "placeholders": [
                {"key": p.placeholder_key, "value": p.default_value, "description": p.description}
                for p in placeholders
            ],
            "created_at": personality.created_at,
            "updated_at": personality.updated_at,
        }

    except Exception as e:
        logger.error("get_personality_template_error", error=str(e), personality_id=personality_id)
        return None


# AI Style Template Management
async def get_style_templates(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Get list of AI style templates."""
    try:
        styles = await ai_style.get_multi(db, skip=skip, limit=limit)

        result = []
        for style in styles:
            # Get relationship mappings for this style
            mappings = await ai_relationship_index.get_by_style_id(db, style_id=style.id)

            result.append(
                {
                    "id": style.id,
                    "name": style.name,
                    "score_count": style.score_count,
                    "score_name": style.score_name,
                    "usage_count": style.usage_count,
                    "status": style.status,
                    "relationship_mappings": [
                        {
                            "relationship_id": m.relationship_id,
                            "score_order": m.score_order,
                            "score_start": m.score_start,
                            "score_end": m.score_end,
                        }
                        for m in mappings
                    ],
                    "created_at": style.created_at,
                    "updated_at": style.updated_at,
                }
            )

        return result

    except Exception as e:
        logger.error("get_style_templates_error", error=str(e))
        return []


async def create_style_template(
    db: AsyncSession, template_data: Dict[str, Any], admin_id: int
) -> Optional[Dict[str, Any]]:
    """Create new AI style template."""
    try:
        # TODO: Create style using proper Pydantic schemas
        # For now, return a placeholder response
        logger.info(
            "style_template_creation_requested",
            name=template_data.get("name"),
            admin_id=admin_id,
        )

        return {
            "message": "Style template creation not yet implemented",
            "admin_id": admin_id,
        }

    except Exception as e:
        logger.error("create_style_template_error", error=str(e), admin_id=admin_id)
        return None


async def get_style_template(db: AsyncSession, style_id: int) -> Optional[Dict[str, Any]]:
    """Get single style template with details."""
    try:
        style = await ai_style.get(db, id=style_id)
        if not style:
            return None

        mappings = await ai_relationship_index.get_by_style_id(db, style_id=style_id)

        return {
            "id": style.id,
            "name": style.name,
            "score_count": style.score_count,
            "score_name": style.score_name,
            "usage_count": style.usage_count,
            "status": style.status,
            "relationship_mappings": [
                {
                    "relationship_id": m.relationship_id,
                    "score_order": m.score_order,
                    "score_start": m.score_start,
                    "score_end": m.score_end,
                }
                for m in mappings
            ],
            "created_at": style.created_at,
            "updated_at": style.updated_at,
        }

    except Exception as e:
        logger.error("get_style_template_error", error=str(e), style_id=style_id)
        return None


# AI Relationship Management
async def get_relationship_types(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get list of AI relationship types."""
    try:
        relationships = await ai_relationship.get_multi(db)

        return [
            {
                "id": rel.id,
                "name": rel.name,
                "prompt_fragment": rel.prompt_fragment,
                "usage_count": rel.usage_count,
                "status": rel.status,
                "created_at": rel.created_at,
                "updated_at": rel.updated_at,
            }
            for rel in relationships
        ]

    except Exception as e:
        logger.error("get_relationship_types_error", error=str(e))
        return []


async def create_relationship_type(
    db: AsyncSession, relationship_data: Dict[str, Any], admin_id: int
) -> Optional[Dict[str, Any]]:
    """Create new AI relationship type."""
    try:
        # TODO: Create relationship using proper Pydantic schema
        logger.info(
            "relationship_type_creation_requested",
            name=relationship_data.get("name"),
            admin_id=admin_id,
        )

        return {
            "message": "Relationship type creation not yet implemented",
            "admin_id": admin_id,
        }

    except Exception as e:
        logger.error("create_relationship_type_error", error=str(e), admin_id=admin_id)
        return None


# AI Character Management
async def get_ai_characters(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Get list of AI characters."""
    try:
        # TODO: Implement status filtering in CRUD layer
        characters = await ai_character.get_multi(db, skip=skip, limit=limit)

        result = []
        for character in characters:
            # Build character info from available fields
            char_info = {
                "qiao_id": character.qiao_id,
                "username": character.username,
                "user_type": character.user_type,
                "status": character.status,
                "profile": character.profile,
                "category": character.category,
                "created_at": character.created_at.isoformat() if character.created_at else None,
                "updated_at": character.updated_at.isoformat() if character.updated_at else None,
            }
            if char_info:
                result.append(char_info)

        return result

    except Exception as e:
        logger.error("get_ai_characters_error", error=str(e))
        return []
