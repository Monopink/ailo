"""
AI Character Chat Test Validation Service

Handles prerequisite validation for AI character testing, ensuring all required
configurations and relationships are properly established before test execution.
"""

import json
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.ai.character import AICharacter
from models.ai.personality import AIPersonality
from models.ai.style import AIStyle
from models.profile import Profile
from services.llm.config import get_active_configs
from utils.logging import get_logger

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
            # Step 1: Validate AI character exists and is active
            character_info = await self._validate_character(db, character_id)

            # Step 2: Validate character profile exists
            character_profile = await self._validate_character_profile(db, character_info)

            # Step 3: Validate AI style and personality configuration
            style_info, personality_info = await self._validate_ai_configuration(db, character_info)

            # Step 4: Validate relationship scores exist
            relationship_scores = await self._validate_relationship_scores(db, character_info, style_info)

            # Step 5: Validate LLM configurations available
            llm_configs = await self._validate_llm_configs(db)

            # Step 6: Validate prompt variables completeness
            await self._validate_prompt_variables(character_info, personality_info)

            logger.info(
                "ai_character_test_validation_success",
                character_id=character_id,
                character_qiao_id=character_info["qiao_id"],
            )

            return {
                "valid": True,
                "character": character_info,
                "character_profile": character_profile,
                "style": style_info,
                "personality": personality_info,
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

    async def _validate_character(self, db: AsyncSession, character_id: int) -> Dict[str, Any]:
        """Validate AI character exists and is active"""
        stmt = select(AICharacter).where(AICharacter.id == character_id)
        result = await db.execute(stmt)
        character = result.scalar_one_or_none()

        if not character:
            raise ValidationError(
                f"AI character with ID {character_id} not found",
                error_code="CHARACTER_NOT_FOUND",
                suggestions=["Check if the character ID is correct", "Verify character exists in database"],
            )

        if character.status != 1:  # ACTIVE
            raise ValidationError(
                f"AI character '{character.qiao_id}' is not active (status: {character.status})",
                error_code="CHARACTER_INACTIVE",
                suggestions=[
                    "Activate the character in AI Characters management",
                    "Check character status settings",
                ],
            )

        return {
            "id": character.id,
            "qiao_id": character.qiao_id,
            "category": character.category,
            "style_id": character.style_id,
            "personality_id": character.personality_id,
            "memory": character.memory,
            "prompt_variables": character.prompt_variables,
            "score_offset_algorithm": character.score_offset_algorithm,
            "score_offset_params": character.score_offset_params,
        }

    async def _validate_character_profile(
        self, db: AsyncSession, character_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate character profile exists"""
        stmt = select(Profile).where(
            Profile.owner_qiao_id == character_info["qiao_id"], Profile.owner_type == 2  # AI character
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            raise ValidationError(
                f"Profile not found for AI character '{character_info['qiao_id']}'",
                error_code="CHARACTER_PROFILE_MISSING",
                suggestions=[
                    "Create a profile for this AI character",
                    "Check Profile management in admin panel",
                ],
            )

        return {
            "nickname": profile.nickname,
            "bio": profile.bio,
            "gender": profile.gender,
            "avatar_url": profile.avatar_url,
        }

    async def _validate_ai_configuration(
        self, db: AsyncSession, character_info: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Validate AI style and personality configuration"""
        # Validate AI style
        stmt = select(AIStyle).where(AIStyle.id == character_info["style_id"])
        result = await db.execute(stmt)
        style = result.scalar_one_or_none()

        if not style:
            raise ValidationError(
                f"AI style with ID {character_info['style_id']} not found",
                error_code="STYLE_NOT_FOUND",
                suggestions=["Check AI Styles management", "Verify style_id in character configuration"],
            )

        # Validate AI personality
        stmt = select(AIPersonality).where(AIPersonality.id == character_info["personality_id"])
        result = await db.execute(stmt)
        personality = result.scalar_one_or_none()

        if not personality:
            raise ValidationError(
                f"AI personality with ID {character_info['personality_id']} not found",
                error_code="PERSONALITY_NOT_FOUND",
                suggestions=[
                    "Check AI Personalities management",
                    "Verify personality_id in character configuration",
                ],
            )

        if personality.status != 1:  # ACTIVE
            raise ValidationError(
                f"AI personality '{personality.name}' is not active",
                error_code="PERSONALITY_INACTIVE",
                suggestions=["Activate the personality", "Check personality status"],
            )

        style_info = {
            "id": style.id,
            "name": style.name,
            "display_name": style.display_name,
        }

        personality_info = {
            "id": personality.id,
            "name": personality.name,
            "display_name": personality.display_name,
            "prompt": personality.prompt,
            "json_schema": personality.json_schema,
        }

        return style_info, personality_info

    async def _validate_relationship_scores(
        self, db: AsyncSession, character_info: Dict[str, Any], style_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate relationship scores exist for this character.
        Uses main logic from services.ai.relationship for score retrieval and initialization.
        """
        from services.ai.relationship import get_relationship_scores

        # Use main logic to get scores (with auto-initialization)
        scores = await get_relationship_scores(db, character_info["qiao_id"], auto_initialize=True)

        if not scores:
            # This should not happen after auto-initialization, but handle gracefully
            logger.warning(
                "no_scores_after_initialization",
                character_id=character_info["id"],
                character_qiao_id=character_info["qiao_id"],
            )
            return []

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
                "config_key": config.config_key,
                "model_name": config.model_name or provider.default_model,
                "provider_name": provider.name,
            }
            for config, provider in configs
        ]

    async def _validate_prompt_variables(
        self, character_info: Dict[str, Any], personality_info: Dict[str, Any]
    ) -> None:
        """Validate prompt variables are complete"""
        prompt_variables = character_info.get("prompt_variables")
        if not prompt_variables or prompt_variables == "{}":
            raise ValidationError(
                f"Prompt variables not configured for AI character '{character_info['qiao_id']}'",
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
