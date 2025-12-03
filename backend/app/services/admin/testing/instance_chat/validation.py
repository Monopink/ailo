"""
AI Instance Chat Test Validation Service

Handles prerequisite validation for AI instance testing, ensuring all required
configurations and relationships are properly established before test execution.
"""

import json
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.profile import profile as profile_crud
from app.enums import ContactType, ProfileOwnerType, UserType
from app.exceptions import AIDataAccessError
from app.models.ai.instance import AIInstance
from app.models.contact import Contact
from app.models.user import User
from app.schemas.profile import ProfileCreate
from app.services.ai.queries import get_instance_context
from app.services.ai.relationship_scoring import get_relationship_scores
from app.services.ai.types import InstanceContext
from app.services.llm.config import get_active_configs
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Exception raised when validation fails"""

    def __init__(
        self, message: str, error_code: str = "VALIDATION_ERROR", suggestions: list | None = None
    ):
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or []
        super().__init__(message)


class ValidationService:
    """Stateless service for AI instance test prerequisite validation"""

    async def validate_instance_test_prerequisites(
        self, db: AsyncSession, instance_id: int
    ) -> dict[str, Any]:
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
                f"系统校验失败：{e!s}",
                error_code="SYSTEM_ERROR",
                suggestions=["查看系统日志确认具体原因", "修复错误后重试"],
            )

    async def _validate_instance(self, db: AsyncSession, instance_id: int) -> InstanceContext:
        """Validate AI instance exists and is active, returning context."""
        try:
            context = await get_instance_context(db, instance_id=instance_id)
        except AIDataAccessError as exc:
            reason_hint = None
            if isinstance(getattr(exc, "details", None), dict):
                reason_hint = exc.details.get("reason") or exc.details.get("query")
            readable_reason = reason_hint or getattr(exc, "reason", None) or str(exc)
            raise ValidationError(
                f"无法加载实例上下文：{readable_reason}",
                error_code="INSTANCE_CONTEXT_QUERY_FAILED",
                suggestions=[
                    "确认该实例的 Profile、风格、人格配置是否完整",
                    "检查 ai_instances.qiao_id 与 profiles.owner_qiao_id 是否匹配",
                    "查看后台日志获取更详细的 SQL 错误",
                ],
            )

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
                    f"ID 为 {instance_id} 的 AI 实例存在，但无法加载运行上下文",
                    error_code="INSTANCE_CONTEXT_MISSING",
                    suggestions=[
                        "检查该实例是否已经正确配置头像、风格与性格",
                        "确保 AIInstance.qiao_id 与 profiles.owner_qiao_id 一致",
                    ],
                )
            raise ValidationError(
                f"数据库中未找到 ID 为 {instance_id} 的 AI 实例",
                error_code="INSTANCE_NOT_FOUND",
                suggestions=[
                    "确认实例 ID 是否填写正确",
                    "在 AI 实例列表中确认该实例是否存在",
                ],
            )

        if context["status"] != 1:
            raise ValidationError(
                f"AI 实例 {context['instance_qiao_id']} 未处于激活状态 (status={context['status']})",
                error_code="INSTANCE_INACTIVE",
                suggestions=[
                    "在 AI 实例管理中将该实例设为启用",
                    "检查实例状态配置是否正确",
                ],
            )

        return context

    def _extract_instance_profile(self, context: InstanceContext) -> dict[str, Any]:
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
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate AI style and personality configuration from context."""
        style = context["style"]
        personality = context["personality"]

        if personality.get("status") != 1:
            raise ValidationError(
                f"AI 人格 {personality.get('name')} 未启用",
                error_code="PERSONALITY_INACTIVE",
                suggestions=["在 AI 人格管理中启用该人格", "检查人格状态配置"],
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
        self, db: AsyncSession, instance_context: InstanceContext, style_info: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Validate relationship scores exist for this instance.
        Auto-initialize if missing to match main flow behavior.
        """

        # Use auto_initialize=True to match main flow behavior
        scores = await get_relationship_scores(
            db, instance_context["instance_qiao_id"], auto_initialize=True
        )

        if not scores:
            # If still no scores after auto-initialization, this is a critical error
            raise ValidationError(
                f"无法为实例 {instance_context['instance_qiao_id']} 初始化关系分数（Style: {style_info['display_name']}）",
                error_code="RELATIONSHIP_SCORES_INIT_FAILED",
                suggestions=[
                    f"确认风格 {style_info['name']} 已在 ai_style_dimensions 中配置维度",
                    "查看数据库日志是否有初始化错误",
                    "确保 ai_style_dimensions 表写入了 initial_position",
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

    async def _validate_llm_configs(self, db: AsyncSession) -> list[dict[str, Any]]:
        """Validate LLM configurations are available"""
        configs = await get_active_configs(db)

        if not configs:
            raise ValidationError(
                "暂无可用的 LLM 配置",
                error_code="LLM_CONFIGS_MISSING",
                suggestions=[
                    "至少配置并启用一个 LLM 服务商",
                    "在 LLM 配置管理中检查配置状态",
                    "确认 LLM 提供商的 API Key 已正确设置",
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
        self, instance_context: InstanceContext, personality_info: dict[str, Any]
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
                f"prompt_variables 字段不是合法的 JSON：{e!s}",
                error_code="PROMPT_VARIABLES_INVALID_JSON",
                suggestions=[
                    "请修复 prompt_variables 字段中的 JSON 字符串",
                    '示例格式：{"key": "value"}',
                ],
            )

    async def _ensure_instance_profile_exists(self, db: AsyncSession, instance: AIInstance) -> None:
        """Ensure AI instance has a profile record (create empty profile if needed)."""
        existing = await profile_crud.get_by_owner_qiao_id(
            db, owner_qiao_id=instance.qiao_id, owner_type=ProfileOwnerType.AI_INSTANCE
        )
        if existing:
            return

        await profile_crud.create_with_owner(
            db,
            obj_in=ProfileCreate(),
            owner_id=instance.id,
            owner_qiao_id=instance.qiao_id,
            owner_type=ProfileOwnerType.AI_INSTANCE,
            commit=False,
        )
        await db.flush()
        logger.warning(
            "ai_persona_auto_created",
            instance_id=instance.id,
            instance_qiao_id=instance.qiao_id,
        )

    async def _ensure_instance_contact_policy(
        self, db: AsyncSession, instance_qiao_id: str
    ) -> None:
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
