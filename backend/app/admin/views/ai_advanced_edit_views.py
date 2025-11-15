"""
Custom views for advanced editing in AI models.
Provides specialized editing interfaces for prompt_variables and position_mapping_params.
"""

import json

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView
from starlette.exceptions import HTTPException

from core.database import SessionLocal
from crud.ai import ai_personality_placeholder as personality_crud
from utils.logging import get_logger
from services.ai.utils.position_mapping import get_algorithm_param_specs

logger = get_logger(__name__)


class CharacterAdvancedEditView(CustomView):
    """Edit character with per-dimension position mapping configuration."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the advanced editing page."""
        character_id = request.path_params.get("id")

        if not character_id:
            raise HTTPException(status_code=400, detail="Character ID is required")

        try:
            character_id = int(character_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid character ID")

        try:
            async with SessionLocal() as db:
                # Get character with eager loading
                from sqlalchemy.orm import selectinload
                from sqlalchemy import select
                from models.ai.character import AICharacter
                from models.ai.style import AIStyleDimension, AIDimension
                from crud.ai.character_dimension import get_by_character

                result = await db.execute(
                    select(AICharacter)
                    .where(AICharacter.id == character_id)
                    .options(
                        selectinload(AICharacter.personality),
                        selectinload(AICharacter.style),
                        selectinload(AICharacter.relationship),
                    )
                )
                character = result.scalar_one_or_none()

                if not character:
                    raise HTTPException(status_code=404, detail="Character not found")

                # Get placeholders for the personality
                placeholders = await personality_crud.get_placeholders_by_personality(
                    db, personality_id=character.personality_id
                )

                # Get JSON Schema from personality
                json_schema = character.personality.json_schema or {}
                score_props = json_schema.get("properties", {}).get("score", {}).get("properties", {})

                # Extract schema dimensions
                schema_dims = {}
                for dim_name, dim_schema in score_props.items():
                    schema_dims[dim_name] = {
                        "min": dim_schema.get("minimum", 0),
                        "max": dim_schema.get("maximum", 1000),
                    }

                # Get style dimensions
                style_dimensions_result = await db.execute(
                    select(AIDimension, AIStyleDimension.initial_position)
                    .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
                    .where(AIStyleDimension.style_id == character.style_id)
                    .order_by(AIDimension.name)
                )
                style_dimensions = [
                    type(
                        "_Tmp",
                        (),
                        {
                            "id": dim.id,
                            "name": dim.name,
                            "display_name": dim.display_name,
                            "initial_position": init_pos,
                        },
                    )
                    for dim, init_pos in style_dimensions_result.all()
                ]

                # Check schema vs style dimension mismatch
                schema_dim_names = set(schema_dims.keys())
                style_dim_names = {d.name for d in style_dimensions}
                schema_mismatch = schema_dim_names != style_dim_names

                # Get character dimensions
                character_dimensions = await get_by_character(db, character_id)

                # Build dimension map
                char_dim_map = {d["dimension_id"]: d for d in character_dimensions}

                # Check for mismatches
                warnings = []
                dimension_data = []

                if schema_mismatch:
                    warnings.append(
                        {
                            "level": "error",
                            "message": f"JSON Schema dimensions mismatch with Style dimensions. Schema: {sorted(schema_dim_names)}, Style: {sorted(style_dim_names)}",
                        }
                    )

                for style_dim in style_dimensions:
                    char_dim = char_dim_map.get(style_dim.id)
                    schema_info = schema_dims.get(style_dim.name, {"min": 0, "max": 1000})

                    if not char_dim:
                        warnings.append(
                            {
                                "level": "warning",
                                "message": f"Missing character dimension: {style_dim.display_name}",
                            }
                        )

                    dimension_data.append(
                        {
                            "dimension_id": style_dim.id,
                            "dimension_name": style_dim.name,
                            "display_name": style_dim.display_name,
                            # JSON Schema info
                            "schema_min": schema_info["min"],
                            "schema_max": schema_info["max"],
                            "schema_exists": style_dim.name in schema_dims,
                            # Style dimension info
                            "initial_position": style_dim.initial_position,
                            # Character dimension info
                            "score": char_dim["score"] if char_dim else None,
                            "position": char_dim["position"] if char_dim else None,
                            "current_relationship": (
                                char_dim.get("current_relationship") if char_dim else None
                            ),
                            "position_mapping_algorithm": (
                                char_dim["position_mapping_algorithm"] if char_dim else None
                            ),
                            "position_mapping_params": char_dim["position_mapping_params"] if char_dim else None,
                        }
                    )

                # Check for extra dimensions
                style_dim_ids = {d.id for d in style_dimensions}
                for char_dim in character_dimensions:
                    if char_dim["dimension_id"] not in style_dim_ids:
                        warnings.append(
                            {
                                "level": "warning",
                                "message": f"Extra character dimension: {char_dim['dimension_name']}",
                            }
                        )

                # Extract character data
                character_data = {
                    "id": character.id,
                    "qiao_id": character.qiao_id,
                    "personality_display_name": (
                        character.personality.display_name if character.personality else "N/A"
                    ),
                    "style_display_name": (character.style.display_name if character.style else "N/A"),
                    "prompt_variables": character.prompt_variables or {},
                    "relationship_display_name": (
                        character.relationship.display_name if character.relationship else None
                    ),
                    "typing_speed_wpm": character.typing_speed_wpm,
                }

            # Prepare status indicators
            schema_status = "error" if schema_mismatch else "success"
            schema_errors = [w["message"] for w in warnings if w.get("level") == "error"]

            style_status = "success"  # Style is always OK if loaded
            style_errors = []

            character_status = "success"
            character_warnings = [w["message"] for w in warnings if w.get("level") == "warning"]
            if character_warnings:
                character_status = "warning"

            context = {
                "request": request,
                "character": character_data,
                "dimensions": dimension_data,
                "warnings": warnings,
                "placeholders": placeholders,
                "schema_mismatch": schema_mismatch,
                "schema_status": schema_status,
                "schema_errors": schema_errors,
                "style_status": style_status,
                "style_errors": style_errors,
                "character_status": character_status,
                "character_warnings": character_warnings,
                "algorithm_param_specs": get_algorithm_param_specs(),
            }

            return templates.TemplateResponse("custom_views/ai_character_advanced_edit.html", context)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "ai_character_advanced_edit_error", character_id=character_id, error=str(e), exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Failed to load character edit page: {str(e)}")


class CharacterTemplateAdvancedEditView(CustomView):
    """Edit character template with per-dimension position mapping configuration."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the advanced editing page."""
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
            from models.ai.template import AICharacterTemplate
            from models.ai.style import AIStyleDimension, AIDimension

            result = await db.execute(
                select(AICharacterTemplate)
                .where(AICharacterTemplate.id == template_id)
                .options(
                    selectinload(AICharacterTemplate.personality),
                    selectinload(AICharacterTemplate.style),
                )
            )
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Get placeholders for the personality
            placeholders = await personality_crud.get_placeholders_by_personality(
                db, personality_id=template.personality_id
            )

            # Get style dimensions
            style_dimensions_result = await db.execute(
                select(AIDimension, AIStyleDimension.initial_position)
                .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
                .where(AIStyleDimension.style_id == template.style_id)
                .order_by(AIDimension.name)
            )
            style_dimensions = [
                type(
                    "_Tmp",
                    (),
                    {
                        "id": dim.id,
                        "name": dim.name,
                        "display_name": dim.display_name,
                        "initial_position": init_pos,
                    },
                )
                for dim, init_pos in style_dimensions_result.all()
            ]

            # Parse prompt_variables robustly (could be JSON string)
            pv = template.prompt_variables
            if isinstance(pv, str):
                try:
                    pv = json.loads(pv)
                except Exception:
                    pv = {}
            elif pv is None:
                pv = {}
            elif not isinstance(pv, dict):
                pv = {}

            # Parse position_mapping_config robustly (could be JSON string)
            position_mapping_config = template.position_mapping_config
            if isinstance(position_mapping_config, str):
                try:
                    position_mapping_config = json.loads(position_mapping_config)
                except Exception:
                    position_mapping_config = {}
            elif position_mapping_config is None:
                position_mapping_config = {}
            elif not isinstance(position_mapping_config, dict):
                position_mapping_config = {}

            # Build dimension config list
            dimension_configs = []
            for dim in style_dimensions:
                dim_config = position_mapping_config.get(dim.name, {})
                dimension_configs.append(
                    {
                        "dimension_name": dim.name,
                        "display_name": dim.display_name,
                        "algorithm": dim_config.get("algorithm", 1),
                        "params": dim_config.get("params", {}),
                    }
                )

            # Extract data while session is active
            template_data = {
                "id": template.id,
                "personality_display_name": (
                    template.personality.display_name if template.personality else "N/A"
                ),
                "prompt_variables": pv,
                "typing_speed_wpm": template.typing_speed_wpm,
            }

        context = {
            "request": request,
            "template": template_data,
            "dimension_configs": dimension_configs,
            "placeholders": placeholders,
            "algorithm_param_specs": get_algorithm_param_specs(),
        }

        return templates.TemplateResponse("custom_views/ai_character_template_advanced_edit.html", context)


# Create view instances
character_advanced_edit_view = CharacterAdvancedEditView(
    label="Edit Character",
    name="character_advanced_edit",
    path="/ai_character/advanced-edit/{id:int}",
    add_to_menu=False,
)

character_template_advanced_edit_view = CharacterTemplateAdvancedEditView(
    label="Edit Character Template",
    name="character_template_advanced_edit",
    path="/ai_character_template/advanced-edit/{id:int}",
    add_to_menu=False,
)


class PersonalityAdvancedEditView(CustomView):
    """Edit personality JSON schema and placeholders in one page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the advanced editing page."""
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

        return templates.TemplateResponse("custom_views/ai_personality_advanced_edit.html", context)


personality_advanced_edit_view = PersonalityAdvancedEditView(
    label="Advanced Edit",
    name="personality_advanced_edit",
    path="/ai_personality/advanced-edit/{id:int}",
    add_to_menu=False,
)


class StyleAdvancedEditView(CustomView):
    """Edit style with dimensions and mappings in one page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the style advanced editing page."""
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
                AIStyleDimension,
                AIDimensionRelationshipMapping,
                AIRelationship,
                AIDimension,
            )

            # Get style
            result = await db.execute(select(AIStyle).where(AIStyle.id == style_id))
            style = result.scalar_one_or_none()

            if not style:
                raise HTTPException(status_code=404, detail="Style not found")

            # Get dimensions for this style
            dimensions_result = await db.execute(
                select(AIDimension, AIStyleDimension.initial_position)
                .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
                .where(AIStyleDimension.style_id == style_id)
                .order_by(AIDimension.name)
            )
            dimensions = [
                type(
                    "_Tmp",
                    (),
                    {
                        "id": dim.id,
                        "name": dim.name,
                        "display_name": dim.display_name,
                        "description": dim.description,
                        "initial_position": init_pos,
                    },
                )
                for dim, init_pos in dimensions_result.all()
            ]

            # Get mappings for this style with dimension names via JOIN
            mappings_result = await db.execute(
                select(
                    AIDimensionRelationshipMapping.id,
                    AIDimensionRelationshipMapping.dimension_id,
                    AIDimension.display_name.label("dimension_display_name"),
                    AIDimensionRelationshipMapping.start_position,
                    AIDimensionRelationshipMapping.end_position,
                    AIDimensionRelationshipMapping.relationship_id,
                    AIDimensionRelationshipMapping.priority,
                    AIDimensionRelationshipMapping.limit_count,
                )
                .join(AIDimension, AIDimensionRelationshipMapping.dimension_id == AIDimension.id)
                .join(
                    AIStyleDimension,
                    AIStyleDimension.dimension_id == AIDimensionRelationshipMapping.dimension_id,
                )
                .where(AIStyleDimension.style_id == style_id)
                .order_by(AIDimensionRelationshipMapping.start_position)
            )
            mappings = mappings_result.all()

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
                    "description": getattr(d, "description", None),
                    "initial_position": d.initial_position,
                }
                for d in dimensions
            ]

            mappings_data = [
                {
                    "id": i.id,
                    "dimension_id": i.dimension_id,
                    "dimension_display_name": i.dimension_display_name,
                    "start_position": i.start_position,
                    "end_position": i.end_position,
                    "relationship_id": i.relationship_id,
                    "priority": i.priority,
                    "limit_count": i.limit_count,
                }
                for i in mappings
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
            "mappings": mappings_data,
            "relationships": relationships_data,
        }

        return templates.TemplateResponse("custom_views/ai_style_advanced_edit.html", context)


style_advanced_edit_view = StyleAdvancedEditView(
    label="Advanced Edit",
    name="style_advanced_edit",
    path="/ai_style/advanced-edit/{id:int}",
    add_to_menu=False,
)
