"""
AI Character Chat Test Validation Service

Handles prerequisite validation for AI character testing, ensuring all required
configurations and relationships are properly established before test execution.
"""

import json
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.llm.config import get_active_configs
from utils.logging import get_logger
from services.ai.queries import get_character_context
from services.ai.types import CharacterContext

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
    """Stateless service for AI character test prerequisite validation"""

    async def validate_character_test_prerequisites(
        self, db: AsyncSession, character_id: int
    ) -> Dict[str, Any]:
        """
        Validate all prerequisites for AI character testing.

        Args:
            db: Database session
            character_id: AI character ID

        Returns:
            Dictionary containing validation results and test data

        Raises:
            ValidationError: If any validation fails
        """
        try:
            # Step 1: Load and validate character context
            character_context = await self._validate_character(db, character_id)

            # Step 2: Extract profile info from context
            character_profile = self._extract_character_profile(character_context)

            # Step 3: Validate AI style and personality configuration
            style_info, personality_info = self._validate_ai_configuration(character_context)

            # Step 4: Current relationship snapshot comes from context
            current_relationship = character_context.get("current_relationship")

            # Step 5: Validate relationship scores exist
            relationship_scores = await self._validate_relationship_scores(db, character_context, style_info)

            # Step 6: Validate LLM configurations available
            llm_configs = await self._validate_llm_configs(db)

            # Step 7: Validate prompt variables completeness
            await self._validate_prompt_variables(character_context, personality_info)

            logger.info(
                "ai_character_test_validation_success",
                character_id=character_id,
                character_qiao_id=character_context["character_qiao_id"],
            )

            return {
                "valid": True,
                "character": character_context,
                "character_profile": character_profile,
                "style": style_info,
                "personality": personality_info,
                "current_relationship": current_relationship,
                "relationship_scores": relationship_scores,
                "llm_configs": llm_configs,
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error("ai_character_test_validation_error", character_id=character_id, error=str(e))
            raise ValidationError(
                f"Validation failed due to system error: {str(e)}", error_code="SYSTEM_ERROR"
            )

    async def _validate_character(self, db: AsyncSession, character_id: int) -> CharacterContext:
        """Validate AI character exists and is active, returning context."""
        context = await get_character_context(db, character_id=character_id)

        if not context:
            raise ValidationError(
                f"AI character with ID {character_id} not found",
                error_code="CHARACTER_NOT_FOUND",
                suggestions=[
                    "Check if the character ID is correct",
                    "Verify character exists in database",
                ],
            )

        if context["status"] != 1:
            raise ValidationError(
                f"AI character '{context['character_qiao_id']}' is not active (status: {context['status']})",
                error_code="CHARACTER_INACTIVE",
                suggestions=[
                    "Activate the character in AI Characters management",
                    "Check character status settings",
                ],
            )

        return context

    def _extract_character_profile(self, context: CharacterContext) -> Dict[str, Any]:
        """Extract profile data from context and ensure it exists."""
        profile = context.get("profile")

        if not profile or not profile.get("nickname"):
            raise ValidationError(
                f"Profile not found for AI character '{context['character_qiao_id']}'",
                error_code="CHARACTER_PROFILE_MISSING",
                suggestions=[
                    "Create a profile for this AI character",
                    "Check Profile management in admin panel",
                ],
            )

        return {
            "nickname": profile.get("nickname"),
            "bio": profile.get("bio"),
            "gender": profile.get("gender"),
            "avatar_url": profile.get("avatar_url"),
            "avatar_prompt": profile.get("avatar_prompt"),
            "region": profile.get("region"),
        }

    def _validate_ai_configuration(
        self, context: CharacterContext
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
        self, db: AsyncSession, character_context: CharacterContext, style_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate relationship scores exist for this character.
        Uses main logic from services.ai.relationship for score retrieval and initialization.
        """
        from services.ai.relationship_scoring import get_relationship_scores

        # Do not auto-initialize in validation. Missing scores is an error by design.
        scores = await get_relationship_scores(db, character_context["character_qiao_id"], auto_initialize=False)

        if not scores:
            raise ValidationError(
                f"Relationship scores missing for character '{character_context['character_qiao_id']}'",
                error_code="RELATIONSHIP_SCORES_MISSING",
                suggestions=[
                    "Ensure character is created via template so scores are initialized",
                    "Check ai_character_dimensions records for this character",
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
        self, character_context: CharacterContext, personality_info: Dict[str, Any]
    ) -> None:
        """Validate prompt variables are complete"""
        prompt_variables = character_context.get("prompt_variables")
        if not prompt_variables or prompt_variables == "{}":
            raise ValidationError(
                f"Prompt variables not configured for AI character '{character_context['character_qiao_id']}'",
                error_code="PROMPT_VARIABLES_MISSING",
                suggestions=[
                    "Configure prompt_variables in AI character settings",
                    "Add required placeholders like personality_traits, character_name, etc.",
                ],
            )

        # Check if personality prompt contains placeholders that need variables
        personality_prompt = personality_info.get("prompt", "")
        required_placeholders = []

        if "{{personality_traits}}" in personality_prompt:
            required_placeholders.append("personality_traits")
        if "{{character_name}}" in personality_prompt:
            required_placeholders.append("character_name")

        if required_placeholders:
            try:
                variables = (
                    json.loads(prompt_variables) if isinstance(prompt_variables, str) else prompt_variables
                )
                missing_vars = [var for var in required_placeholders if var not in variables]

                if missing_vars:
                    raise ValidationError(
                        f"Missing required prompt variables: {', '.join(missing_vars)}",
                        error_code="PROMPT_VARIABLES_INCOMPLETE",
                        suggestions=[
                            f"Add missing variables to prompt_variables: {missing_vars}",
                            "Check personality prompt for required placeholders",
                        ],
                    )
            except (json.JSONDecodeError, TypeError):
                raise ValidationError(
                    "Invalid JSON format in prompt_variables",
                    error_code="PROMPT_VARIABLES_INVALID_JSON",
                    suggestions=["Fix JSON format in prompt_variables field"],
                )


# Global instance for dependency injection
validation_service = ValidationService()
