"""Custom views for advanced editing in AI models.
Provides specialized editing interfaces for prompt_variables and position_mapping_params.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.crud.ai import ai_personality_placeholder as personality_crud
from app.crud.ai.instance_dimension import get_by_instance
from app.models.ai.instance import AIInstance
from app.models.ai.memory import AIInstanceMemory, AITemplateMemory
from app.models.ai.personality import AIPersonality
from app.models.ai.style import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIRelationship,
    AIStyle,
    AIStyleDimension,
)
from app.models.ai.template import AITemplate
from app.models.llm import LLMConfig
from app.services.ai.queries.instance_queries import get_style_dimensions
from app.services.ai.utils.position_mapping import get_algorithm_param_specs
from app.type_defs import DimensionSpec, JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


class InstanceAdvancedEditView(CustomView):
    """Edit instance with per-dimension position mapping configuration."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the advanced editing page."""
        try:
            instance_id = int(request.path_params["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid instance ID") from exc

        session_factory = get_sessionmaker()
        async with session_factory() as db:
            instance = await self._load_instance(db, instance_id)
            placeholders = await personality_crud.get_placeholders_by_personality(
                db, personality_id=instance.personality_id
            )

            # Load instance memories
            memories_stmt = (
                select(AIInstanceMemory)
                .where(AIInstanceMemory.instance_id == instance_id)
                .order_by(AIInstanceMemory.importance.desc(), AIInstanceMemory.created_at.desc())
            )
            memories_result = await db.execute(memories_stmt)
            memories = memories_result.scalars().all()
            memories_data = [
                {
                    "id": str(m.id),
                    "memory_type": m.memory_type,
                    "content": m.content,
                    "importance": m.importance,
                    "status": m.status,
                    "refreshed_at": m.refreshed_at.isoformat() if m.refreshed_at else None,
                    "expires_at": m.expires_at.isoformat() if m.expires_at else None,
                    "source_message_id": (
                        str(m.source_message_id) if m.source_message_id is not None else None
                    ),
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memories
            ]

            schema_dims = self._load_schema_dimensions(instance)
            style_dimensions = await get_style_dimensions(db, instance.style_id)
            dimension_view = self._build_dimension_view(
                schema_dims=schema_dims,
                style_dimensions=style_dimensions,
                raw_dimensions=await get_by_instance(db, instance.id),
            )

            instance_data = self._build_instance_summary(instance)

        context = {
            "request": request,
            "instance": instance_data,
            "dimensions": dimension_view.dimensions,
            "warnings": dimension_view.warnings,
            "placeholders": placeholders,
            "memories": memories_data,
            "schema_mismatch": dimension_view.schema_mismatch,
            "schema_status": dimension_view.schema_status,
            "schema_errors": dimension_view.schema_errors,
            "style_status": "success",
            "style_errors": [],
            "instance_status": dimension_view.instance_status,
            "instance_warnings": dimension_view.instance_warnings,
            "algorithm_param_specs": get_algorithm_param_specs(),
        }

        return templates.TemplateResponse("custom_views/ai_instance_advanced_edit.html", context)

    async def _load_instance(self, db: AsyncSession, instance_id: int) -> AIInstance:
        result = await db.execute(
            select(AIInstance)
            .where(AIInstance.id == instance_id)
            .options(
                selectinload(AIInstance.personality),
                selectinload(AIInstance.style),
                selectinload(AIInstance.relationship),
                selectinload(AIInstance.llm_config).selectinload(LLMConfig.provider),
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        return instance

    @staticmethod
    def _load_schema_dimensions(instance: AIInstance) -> dict[str, dict[str, int]]:
        personality = instance.personality
        schema = personality.json_schema if personality and personality.json_schema else {}
        score_props = schema.get("properties", {}).get("score", {}).get("properties", {})
        compiled: dict[str, dict[str, int]] = {}
        for dim_name, dim_schema in score_props.items():
            if not isinstance(dim_name, str) or not dim_name:
                continue
            if not isinstance(dim_schema, dict):
                continue
            min_raw = dim_schema.get("minimum")
            max_raw = dim_schema.get("maximum")
            if isinstance(min_raw, bool) or not isinstance(min_raw, int | float):
                continue
            if isinstance(max_raw, bool) or not isinstance(max_raw, int | float):
                continue
            min_value = int(min_raw)
            max_value = int(max_raw)
            if min_value >= max_value:
                continue
            compiled[dim_name] = {
                "min": min_value,
                "max": max_value,
            }
        return compiled

    @dataclass
    class _DimensionView:
        dimensions: list[JSONDict]
        warnings: list[dict[str, str]]
        schema_mismatch: bool
        schema_status: str
        schema_errors: list[str]
        instance_status: str
        instance_warnings: list[str]

    def _build_dimension_view(
        self,
        *,
        schema_dims: dict[str, dict[str, int]],
        style_dimensions: Iterable[DimensionSpec],
        raw_dimensions: list[JSONDict],
    ) -> "_DimensionView":
        schema_dim_names = set(schema_dims.keys())
        style_dim_names = {dim["name"] for dim in style_dimensions}
        schema_mismatch = schema_dim_names != style_dim_names

        raw_map = {row["dimension_id"]: row for row in raw_dimensions}
        warnings: list[dict[str, str]] = []
        if schema_mismatch:
            warnings.append(
                {
                    "level": "error",
                    "message": (
                        "JSON Schema dimensions mismatch with Style dimensions. "
                        f"Schema: {sorted(schema_dim_names)}, Style: {sorted(style_dim_names)}"
                    ),
                }
            )

        dimensions_payload: list[JSONDict] = []
        for style_dim in style_dimensions:
            dim_id = style_dim["id"]
            dim_name = style_dim["name"]
            char_dim = raw_map.get(dim_id)
            schema_info = schema_dims.get(dim_name, {"min": 0, "max": 1000})

            if char_dim is None:
                warnings.append(
                    {
                        "level": "warning",
                        "message": f"Missing instance dimension: {style_dim['display_name']}",
                    }
                )

            dimensions_payload.append(
                {
                    "dimension_id": dim_id,
                    "dimension_name": dim_name,
                    "display_name": style_dim["display_name"],
                    "schema_min": schema_info["min"],
                    "schema_max": schema_info["max"],
                    "schema_exists": dim_name in schema_dims,
                    "initial_position": style_dim["initial_position"],
                    "score": char_dim["score"] if char_dim else None,
                    "position": char_dim["position"] if char_dim else None,
                    "current_relationship": (
                        char_dim.get("current_relationship") if char_dim else None
                    ),
                    "position_mapping_algorithm": (
                        char_dim["position_mapping_algorithm"] if char_dim else None
                    ),
                    "position_mapping_params": (
                        char_dim["position_mapping_params"] if char_dim else None
                    ),
                }
            )

        style_dim_ids = {dim["id"] for dim in style_dimensions}
        for char_dim in raw_dimensions:
            if char_dim["dimension_id"] not in style_dim_ids:
                warnings.append(
                    {
                        "level": "warning",
                        "message": f"Extra instance dimension: {char_dim['dimension_name']}",
                    }
                )

        schema_errors = [msg["message"] for msg in warnings if msg["level"] == "error"]
        instance_warnings = [msg["message"] for msg in warnings if msg["level"] == "warning"]

        return self._DimensionView(
            dimensions=dimensions_payload,
            warnings=warnings,
            schema_mismatch=schema_mismatch,
            schema_status="error" if schema_errors else "success",
            schema_errors=schema_errors,
            instance_status="warning" if instance_warnings else "success",
            instance_warnings=instance_warnings,
        )

    @staticmethod
    def _build_instance_summary(instance: AIInstance) -> JSONDict:
        llm_summary: JSONDict | None = None
        if instance.llm_config:
            provider_name = (
                instance.llm_config.provider.display_name if instance.llm_config.provider else None
            )
            llm_summary = {
                "id": instance.llm_config.id,
                "name": instance.llm_config.name,
                "provider": provider_name,
            }

        return {
            "id": str(instance.id),
            "qiao_id": instance.qiao_id,
            "persona_id": str(instance.persona_id) if instance.persona_id is not None else None,
            "personality_display_name": (
                instance.personality.display_name if instance.personality else "N/A"
            ),
            "style_display_name": instance.style.display_name if instance.style else "N/A",
            "prompt_variables": instance.prompt_variables or {},
            "relationship_display_name": (
                instance.relationship.display_name if instance.relationship else None
            ),
            "typing_speed_wpm": instance.typing_speed_wpm,
            "timezone": instance.timezone,
            "llm_config_id": instance.llm_config_id,
            "llm_config": llm_summary,
        }


class TemplateAdvancedEditView(CustomView):
    """Edit template with per-dimension position mapping configuration."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render the advanced editing page."""
        try:
            template_id = int(request.path_params["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid template ID") from exc

        session_factory = get_sessionmaker()
        async with session_factory() as db:
            template = await self._load_template(db, template_id)
            placeholders = await personality_crud.get_placeholders_by_personality(
                db, personality_id=template.personality_id
            )

            # Load template memories
            memories_stmt = (
                select(AITemplateMemory)
                .where(AITemplateMemory.template_id == template_id)
                .order_by(AITemplateMemory.display_order, AITemplateMemory.created_at)
            )
            memories_result = await db.execute(memories_stmt)
            memories = memories_result.scalars().all()
            memories_data = [
                {
                    "id": str(m.id),
                    "memory_type": m.memory_type,
                    "content": m.content,
                    "importance": m.importance,
                    "display_order": m.display_order,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memories
            ]

            style_dimensions = await get_style_dimensions(db, template.style_id)
            prompt_variables = self._coerce_json_dict(template.prompt_variables)
            position_mapping = self._coerce_json_dict(template.position_mapping_config)
            dimension_configs = self._build_dimension_configs(style_dimensions, position_mapping)
            template_data = self._build_template_summary(template, prompt_variables)

        context = {
            "request": request,
            "template": template_data,
            "dimension_configs": dimension_configs,
            "placeholders": placeholders,
            "memories": memories_data,
            "algorithm_param_specs": get_algorithm_param_specs(),
        }

        return templates.TemplateResponse("custom_views/ai_template_advanced_edit.html", context)

    async def _load_template(self, db: AsyncSession, template_id: int) -> AITemplate:
        result = await db.execute(
            select(AITemplate)
            .where(AITemplate.id == template_id)
            .options(
                selectinload(AITemplate.personality),
                selectinload(AITemplate.style),
                selectinload(AITemplate.llm_config).selectinload(LLMConfig.provider),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template

    @staticmethod
    def _coerce_json_dict(value: object) -> JSONDict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _build_dimension_configs(
        style_dimensions: Iterable[DimensionSpec],
        position_mapping_config: JSONDict,
    ) -> list[JSONDict]:
        configs: list[JSONDict] = []
        for dim in style_dimensions:
            dim_name = dim["name"]
            raw_config = position_mapping_config.get(dim_name, {})
            config_dict = raw_config if isinstance(raw_config, dict) else {}
            algorithm = config_dict.get("algorithm", 1)
            params = config_dict.get("params", {})
            configs.append(
                {
                    "dimension_name": dim_name,
                    "display_name": dim["display_name"],
                    "algorithm": algorithm if isinstance(algorithm, int) else 1,
                    "params": params if isinstance(params, dict) else {},
                }
            )
        return configs

    @staticmethod
    def _build_template_summary(template: AITemplate, prompt_variables: JSONDict) -> JSONDict:
        personality_name = template.personality.display_name if template.personality else "N/A"
        llm_summary = None
        if template.llm_config:
            provider = (
                template.llm_config.provider.display_name if template.llm_config.provider else None
            )
            llm_summary = {
                "id": template.llm_config.id,
                "name": template.llm_config.name,
                "provider": provider,
            }
        return {
            "id": template.id,
            "personality_display_name": personality_name,
            "prompt_variables": prompt_variables,
            "typing_speed_wpm": template.typing_speed_wpm,
            "llm_config_id": template.llm_config_id,
            "llm_config": llm_summary,
        }


# Create view instances
instance_advanced_edit_view = InstanceAdvancedEditView(
    label="Edit Instance",
    name="instance_advanced_edit",
    path="/ai_instance/advanced-edit/{id:int}",
    add_to_menu=False,
)

template_advanced_edit_view = TemplateAdvancedEditView(
    label="Edit AI Template",
    name="ai_template_advanced_edit",
    path="/ai_template/advanced-edit/{id:int}",
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid personality ID") from exc

        session_factory = get_sessionmaker()
        async with session_factory() as db:
            # Get personality
            result = await db.execute(
                select(AIPersonality).where(AIPersonality.id == personality_id)
            )
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
                "display_name": personality.display_name,
                "status": personality.status,
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid style ID") from exc

        session_factory = get_sessionmaker()
        async with session_factory() as db:
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
            dimensions_rows = dimensions_result.all()
            dimensions_data = [
                {
                    "id": dim.id,
                    "name": dim.name,
                    "display_name": dim.display_name,
                    "description": dim.description,
                    "initial_position": init_pos,
                }
                for dim, init_pos in dimensions_rows
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
            mapping_rows = mappings_result.all()

            # Get all active relationships for dropdown
            relationships_result = await db.execute(
                select(AIRelationship)
                .where(AIRelationship.status == 1)
                .order_by(AIRelationship.display_name)
            )
            relationships = relationships_result.scalars().all()

            # Convert to dicts for JSON serialization
            mappings_data = [
                {
                    "id": mapping_id,
                    "dimension_id": dimension_id,
                    "dimension_display_name": dimension_display_name,
                    "start_position": start_position,
                    "end_position": end_position,
                    "relationship_id": relationship_id,
                    "priority": priority,
                    "limit_count": limit_count,
                }
                for (
                    mapping_id,
                    dimension_id,
                    dimension_display_name,
                    start_position,
                    end_position,
                    relationship_id,
                    priority,
                    limit_count,
                ) in mapping_rows
            ]

            relationships_data = [
                {
                    "id": r.id,
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
