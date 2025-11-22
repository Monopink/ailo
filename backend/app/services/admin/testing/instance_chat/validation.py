"""
AI Instance Chat Test Validation Service

Handles prerequisite validation for AI instance testing, ensuring all required
configurations and relationships are properly established before test execution.
"""

import json
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from services.llm.config import get_active_configs
from utils.logging import get_logger
from services.ai.queries import get_instance_context
from services.ai.types import InstanceContext
from enums import ContactType, UserType, ProfileOwnerType
from models.ai.instance import AIInstance
from models.contact import Contact
from models.user import User
from crud.profile import profile as profile_crud
from schemas.profile import ProfileCreate

logger = get_logger(__name__)


class ValidationError(Exception):
    """Exception raised when validation fails"""

    def __init__(
        self, message: str, error_code: str = "VALIDATION_ERROR", suggestions: Optional[list] = None
    ):
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or []
        super().__init__(message)


class ValidationService:
    """Stateless service for AI instance test prerequisite validation"""

    async def validate_instance_test_prerequisites(
        self, db: AsyncSession, instance_id: int
    ) -> Dict[str, Any]:
        """
        Validate all prerequisites for AI instance testing.

        Args:
            db: Database session
            instance_id: AI instance ID

        Returns:
            Dictionary containing validation results and test data

        Raises:
            ValidationError: If any validation fails
        """
        try:
            # Step 1: Load and validate instance context
            instance_context = await self._validate_instance(db, instance_id)
            await self._ensure_instance_contact_policy(db, instance_context["instance_qiao_id"])

            # Step 2: Extract profile info from context
            instance_profile = self._extract_instance_profile(instance_context)

            # Step 3: Validate AI style and personality configuration
            style_info, personality_info = self._validate_ai_configuration(instance_context)

            # Step 4: Current relationship snapshot comes from context
            current_relationship = instance_context.get("current_relationship")

            # Step 5: Validate relationship scores exist
            relationship_scores = await self._validate_relationship_scores(
                db, instance_context, style_info
            )

            # Step 6: Validate LLM configurations available
            llm_configs = await self._validate_llm_configs(db)

            # Step 7: Validate prompt variables completeness
            await self._validate_prompt_variables(instance_context, personality_info)

            logger.info(
                "ai_instance_test_validation_success",
                instance_id=instance_id,
                instance_qiao_id=instance_context["instance_qiao_id"],
            )

            return {
                "valid": True,
                "instance": instance_context,
                "instance_profile": instance_profile,
                "style": style_info,
                "personality": personality_info,
                "current_relationship": current_relationship,
                "relationship_scores": relationship_scores,
                "llm_configs": llm_configs,
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error("ai_instance_test_validation_error", instance_id=instance_id, error=str(e))
            raise ValidationError(
                f"Validation failed due to system error: {str(e)}", error_code="SYSTEM_ERROR"
            )

    async def _validate_instance(self, db: AsyncSession, instance_id: int) -> InstanceContext:
        """Validate AI instance exists and is active, returning context."""
        context = await get_instance_context(db, instance_id=instance_id)

        if not context:
            stmt = select(AIInstance).where(AIInstance.id == instance_id)
            result = await db.execute(stmt)
            instance_record = result.scalar_one_or_none()

            if instance_record:
                await self._ensure_instance_profile_exists(db, instance_record)
                context = await get_instance_context(db, instance_id=instance_id)

        if not context:
            stmt = select(AIInstance).where(AIInstance.id == instance_id)
            result = await db.execute(stmt)
            instance_record = result.scalar_one_or_none()

            if instance_record:
                raise ValidationError(
                    f"AI instance with ID {instance_id} exists but context could not be loaded",
                    error_code="INSTANCE_CONTEXT_MISSING",
                    suggestions=[
                        "Check if instance profile and style/personality are configured correctly",
                        "Ensure AIInstance.qiao_id matches Profile.owner_qiao_id",
                    ],
                )
            raise ValidationError(
                f"AI instance with ID {instance_id} not found in database",
                error_code="INSTANCE_NOT_FOUND",
                suggestions=[
                    "Check if the instance ID is correct",
                    "Verify the instance exists in AI Instances list",
                ],
            )

        if context["status"] != 1:
            raise ValidationError(
                f"AI instance '{context['instance_qiao_id']}' is not active (status: {context['status']})",
                error_code="INSTANCE_INACTIVE",
                suggestions=[
                    "Activate the instance in AI Instances management",
                    "Check instance status settings",
                ],
            )

        return context

    def _extract_instance_profile(self, context: InstanceContext) -> Dict[str, Any]:
        """Extract profile data from context and ensure it exists."""
        profile = context.get("profile") or {}

        return {
            "nickname": profile.get("nickname"),
            "bio": profile.get("bio"),
            "gender": profile.get("gender"),
            "avatar_url": profile.get("avatar_url"),
            "avatar_prompt": profile.get("avatar_prompt"),
            "region": profile.get("region"),
        }

    def _validate_ai_configuration(
        self, context: InstanceContext
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Validate AI style and personality configuration from context."""
        style = context["style"]
        personality = context["personality"]

        if personality.get("status") != 1:
            raise ValidationError(
                f"AI personality '{personality.get('name')}' is not active",
                error_code="PERSONALITY_INACTIVE",
                suggestions=["Activate the personality", "Check personality status"],
            )

        style_info = {
            "id": style.get("id"),
            "name": style.get("name"),
            "display_name": style.get("display_name"),
        }

        personality_info = {
            "id": personality.get("id"),
            "name": personality.get("name"),
            "display_name": personality.get("display_name"),
            "prompt": personality.get("prompt"),
            "json_schema": personality.get("json_schema"),
        }

        return style_info, personality_info

    async def _validate_relationship_scores(
        self, db: AsyncSession, instance_context: InstanceContext, style_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate relationship scores exist for this instance.
        Auto-initialize if missing to match main flow behavior.
        """
        from services.ai.relationship_scoring import get_relationship_scores

        # Use auto_initialize=True to match main flow behavior
        scores = await get_relationship_scores(
            db, instance_context["instance_qiao_id"], auto_initialize=True
        )

        if not scores:
            # If still no scores after auto-initialization, this is a critical error
            raise ValidationError(
                f"Failed to initialize relationship scores for instance '{instance_context['instance_qiao_id']}' "
                f"(ID: {instance_context['instance_id']}, Style: {style_info['display_name']})",
                error_code="RELATIONSHIP_SCORES_INIT_FAILED",
                suggestions=[
                    f"Verify style '{style_info['name']}' has dimensions configured in ai_style_dimensions",
                    "Check database logs for initialization errors",
                    "Ensure ai_style_dimensions table has initial_position values",
                ],
            )

        # Convert to expected format
        return [
            {
                "dimension_name": score["dimension_name"],
                "score": score["score"],
                "position": score["position"],
                "relationship_display_name": score.get("relationship_display_name"),
            }
            for score in scores
        ]

    async def _validate_llm_configs(self, db: AsyncSession) -> list[Dict[str, Any]]:
        """Validate LLM configurations are available"""
        configs = await get_active_configs(db)

        if not configs:
            raise ValidationError(
                "No LLM configurations available",
                error_code="LLM_CONFIGS_MISSING",
                suggestions=[
                    "Configure at least one LLM provider and config",
                    "Check LLM Configurations management",
                    "Verify LLM provider API keys are set",
                ],
            )

        # configs is a list of (LLMConfig, LLMProvider) tuples
        return [
            {
                "name": config.name,
                "model_name": config.model_name or provider.default_model,
                "provider_name": provider.name,
            }
            for config, provider in configs
        ]

    async def _validate_prompt_variables(
        self, instance_context: InstanceContext, personality_info: Dict[str, Any]
    ) -> None:
        """
        Validate prompt variables format (if present).

        Note: Missing or empty prompt_variables is acceptable - the system will handle
        missing placeholders by replacing them with empty strings during prompt rendering.
        """
        prompt_variables = instance_context.get("prompt_variables")

        # If no variables configured, that's fine - system will handle empty placeholders
        if not prompt_variables or prompt_variables == "{}":
            logger.debug(
                "prompt_variables_empty",
                instance_qiao_id=instance_context["instance_qiao_id"],
                message="No prompt variables configured, placeholders will be replaced with empty strings",
            )
            return

        # Only validate JSON format if variables are provided
        try:
            if isinstance(prompt_variables, str):
                json.loads(prompt_variables)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValidationError(
                f"Invalid JSON format in prompt_variables: {str(e)}",
                error_code="PROMPT_VARIABLES_INVALID_JSON",
                suggestions=[
                    "Fix JSON format in prompt_variables field",
                    'Ensure it\'s a valid JSON object like {"key": "value"}',
                ],
            )

    async def _ensure_instance_profile_exists(self, db: AsyncSession, instance: AIInstance) -> None:
        """Ensure AI instance has a profile record (create empty profile if needed)."""
        existing = await profile_crud.get_by_owner_qiao_id(
            db, owner_qiao_id=instance.qiao_id, owner_type=ProfileOwnerType.AI
        )
        if existing:
            return

        await profile_crud.create_with_owner(
            db,
            obj_in=ProfileCreate(),
            owner_id=instance.id,
            owner_qiao_id=instance.qiao_id,
            owner_type=ProfileOwnerType.AI,
            commit=False,
        )
        await db.flush()
        logger.warning(
            "ai_persona_auto_created",
            instance_id=instance.id,
            instance_qiao_id=instance.qiao_id,
        )

    async def _ensure_instance_contact_policy(self, db: AsyncSession, instance_qiao_id: str) -> None:
        """Ensure instance has no non-virtual contacts before allowing test."""
        stmt = (
            select(User.user_type)
            .join(Contact, Contact.user_id == User.id)
            .where(
                and_(
                    Contact.contact_qiao_id == instance_qiao_id,
                    Contact.contact_type == ContactType.AI,
                    Contact.is_deleted == 0,
                )
            )
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if any(user_type != UserType.VIRTUAL for user_type in rows):
            raise ValidationError(
                "AI 角色存在真实用户联系人，无法进入测试模式",
                error_code="NON_VIRTUAL_CONTACT_EXISTS",
                suggestions=[
                    "删除所有非 virtual 联系人后再重试",
                    "或在测试结束后再重新创建真实用户联系人",
                ],
            )


# Global instance for dependency injection
validation_service = ValidationService()
