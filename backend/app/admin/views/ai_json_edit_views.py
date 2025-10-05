"""
Custom views for editing JSON fields in AI models.
Provides specialized editing interfaces for prompt_variables and score_offset_params.
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView
from starlette.exceptions import HTTPException

from core.database import SessionLocal
from crud.ai import ai_personality_placeholder as personality_crud
from enums import ScoreOffsetAlgorithm
from utils.logging import get_logger

logger = get_logger(__name__)


class CharacterJSONEditView(CustomView):
    """Edit character JSON fields (prompt_variables and score_offset_params) in one page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the JSON editing page."""
        character_id = request.path_params.get("id")

        if not character_id:
            raise HTTPException(status_code=400, detail="Character ID is required")

        try:
            character_id = int(character_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid character ID")

        async with SessionLocal() as db:
            # Get character with eager loading
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            from models.ai.character import AICharacter

            result = await db.execute(
                select(AICharacter)
                .where(AICharacter.id == character_id)
                .options(selectinload(AICharacter.personality))
            )
            character = result.scalar_one_or_none()

            if not character:
                raise HTTPException(status_code=404, detail="Character not found")

            # Get placeholders for the personality
            placeholders = await personality_crud.get_placeholders_by_personality(
                db, personality_id=character.personality_id
            )

            # Extract data while session is active
            character_data = {
                "id": character.id,
                "qiao_id": character.qiao_id,
                "personality_display_name": (
                    character.personality.display_name if character.personality else "N/A"
                ),
                "score_offset_algorithm": character.score_offset_algorithm,
                "prompt_variables": character.prompt_variables or {},
                "score_offset_params": character.score_offset_params or {},
            }

        # Get algorithm info
        algorithm = ScoreOffsetAlgorithm(character_data["score_offset_algorithm"])

        context = {
            "request": request,
            "character": character_data,
            "placeholders": placeholders,
            "algorithm": algorithm,
            "current_variables": character_data["prompt_variables"],
            "current_params": character_data["score_offset_params"],
        }

        return templates.TemplateResponse("custom_views/character_json_edit.html", context)


class InfoTemplateJSONEditView(CustomView):
    """Edit info template JSON fields (prompt_variables)."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the JSON editing page."""
        template_id = request.path_params.get("id")

        if not template_id:
            raise HTTPException(status_code=400, detail="Template ID is required")

        try:
            template_id = int(template_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid template ID")

        async with SessionLocal() as db:
            # Get template with eager loading
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            from models.ai.template import AIInfoTemplate

            result = await db.execute(
                select(AIInfoTemplate)
                .where(AIInfoTemplate.id == template_id)
                .options(selectinload(AIInfoTemplate.personality))
            )
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Get placeholders for the personality
            placeholders = await personality_crud.get_placeholders_by_personality(
                db, personality_id=template.personality_id
            )

            # Extract data while session is active
            template_data = {
                "id": template.id,
                "personality_display_name": (
                    template.personality.display_name if template.personality else "N/A"
                ),
                "prompt_variables": template.prompt_variables or {},
            }

        context = {
            "request": request,
            "template": template_data,
            "placeholders": placeholders,
            "current_values": template_data["prompt_variables"],
        }

        return templates.TemplateResponse("custom_views/info_template_json_edit.html", context)


# Create view instances
character_json_edit_view = CharacterJSONEditView(
    label="Edit JSON Fields",
    name="character_json_edit",
    path="/ai-character/{id:int}/edit-json",
    add_to_menu=False,
)

info_template_json_edit_view = InfoTemplateJSONEditView(
    label="Edit JSON Fields",
    name="info_template_json_edit",
    path="/ai-info-template/{id:int}/edit-json",
    add_to_menu=False,
)


class PersonalityCompleteEditView(CustomView):
    """Edit personality JSON schema and placeholders in one page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the complete editing page."""
        personality_id = request.path_params.get("id")

        if not personality_id:
            raise HTTPException(status_code=400, detail="Personality ID is required")

        try:
            personality_id = int(personality_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid personality ID")

        async with SessionLocal() as db:
            # Get personality
            from sqlalchemy import select
            from models.ai.personality import AIPersonality

            result = await db.execute(select(AIPersonality).where(AIPersonality.id == personality_id))
            personality = result.scalar_one_or_none()

            if not personality:
                raise HTTPException(status_code=404, detail="Personality not found")

            # Get placeholders
            placeholders = await personality_crud.get_placeholders_by_personality(
                db, personality_id=personality_id
            )

            # Extract data while session is active
            personality_data = {
                "id": personality.id,
                "name": personality.name,
                "display_name": personality.display_name,
                "prompt": personality.prompt or "",
                "json_schema": personality.json_schema or {},
            }

            placeholders_data = [
                {
                    "id": p.id,
                    "placeholder_key": p.placeholder_key,
                    "display_name": p.display_name or "",
                    "description": p.description or "",
                    "is_required": bool(p.is_required),
                    "example_value": p.example_value or "",
                }
                for p in placeholders
            ]

        context = {
            "request": request,
            "personality": personality_data,
            "placeholders": placeholders_data,
        }

        return templates.TemplateResponse("custom_views/personality_complete_edit.html", context)


personality_complete_edit_view = PersonalityCompleteEditView(
    label="Edit Complete",
    name="personality_complete_edit",
    path="/ai-personality/{id:int}/edit-complete",
    add_to_menu=False,
)


class StyleCompleteEditView(CustomView):
    """Edit style with dimensions and indexes in one page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the style complete editing page."""
        style_id = request.path_params.get("id")

        if not style_id:
            raise HTTPException(status_code=400, detail="Style ID is required")

        try:
            style_id = int(style_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid style ID")

        async with SessionLocal() as db:
            from sqlalchemy import select
            from models.ai.style import (
                AIStyle,
                AIRelationshipDimension,
                AIRelationshipIndex,
                AIRelationship,
            )

            # Get style
            result = await db.execute(select(AIStyle).where(AIStyle.id == style_id))
            style = result.scalar_one_or_none()

            if not style:
                raise HTTPException(status_code=404, detail="Style not found")

            # Get dimensions for this style
            dimensions_result = await db.execute(
                select(AIRelationshipDimension)
                .where(AIRelationshipDimension.style_id == style_id)
                .order_by(AIRelationshipDimension.name)
            )
            dimensions = dimensions_result.scalars().all()

            # Get indexes for this style with dimension names via JOIN
            indexes_result = await db.execute(
                select(
                    AIRelationshipIndex.id,
                    AIRelationshipIndex.dimension_id,
                    AIRelationshipDimension.name.label("dimension_name"),
                    AIRelationshipIndex.start_position,
                    AIRelationshipIndex.end_position,
                    AIRelationshipIndex.relationship_id,
                    AIRelationshipIndex.priority,
                    AIRelationshipIndex.limit_count,
                )
                .join(
                    AIRelationshipDimension, AIRelationshipIndex.dimension_id == AIRelationshipDimension.id
                )
                .where(AIRelationshipIndex.style_id == style_id)
                .order_by(AIRelationshipIndex.start_position)
            )
            indexes = indexes_result.all()

            # Get all active relationships for dropdown
            relationships_result = await db.execute(
                select(AIRelationship).where(AIRelationship.status == 1).order_by(AIRelationship.name)
            )
            relationships = relationships_result.scalars().all()

            # Convert to dicts for JSON serialization
            dimensions_data = [
                {
                    "id": d.id,
                    "name": d.name,
                    "display_name": d.display_name,
                    "initial_position": d.initial_position,
                }
                for d in dimensions
            ]

            indexes_data = [
                {
                    "id": i.id,
                    "dimension_id": i.dimension_id,
                    "dimension_name": i.dimension_name,
                    "start_position": i.start_position,
                    "end_position": i.end_position,
                    "relationship_id": i.relationship_id,
                    "priority": i.priority,
                    "limit_count": i.limit_count,
                }
                for i in indexes
            ]

            relationships_data = [
                {
                    "id": r.id,
                    "name": r.name,
                    "display_name": r.display_name,
                }
                for r in relationships
            ]

        context = {
            "request": request,
            "style": style,
            "dimensions": dimensions_data,
            "indexes": indexes_data,
            "relationships": relationships_data,
        }

        return templates.TemplateResponse("custom_views/style_complete_edit.html", context)


style_complete_edit_view = StyleCompleteEditView(
    label="Edit Complete",
    name="style_complete_edit",
    path="/ai-style/{id:int}/edit-complete",
    add_to_menu=False,
)
