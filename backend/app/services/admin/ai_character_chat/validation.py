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
from models.ai.style import AIStyle, AIRelationship
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

            # Step 4: Get current relationship info if set
            current_relationship = await self._get_current_relationship(db, character_info)

            # Step 5: Validate relationship scores exist
            relationship_scores = await self._validate_relationship_scores(db, character_info, style_info)

            # Step 6: Validate LLM configurations available
            llm_configs = await self._validate_llm_configs(db)

            # Step 7: Validate prompt variables completeness
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
            "relationship_id": character.relationship_id,
            "memory": character.memory,
            "prompt_variables": character.prompt_variables,
            "user_id": character.user_id,
            "user_qiao_id": character.user_qiao_id,
        }

    async def _get_current_relationship(
        self, db: AsyncSession, character_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get current relationship info if character has relationship_id set"""
        relationship_id = character_info.get("relationship_id")
        if not relationship_id:
            return None

        stmt = select(AIRelationship).where(AIRelationship.id == relationship_id)
        result = await db.execute(stmt)
        relationship = result.scalar_one_or_none()

        if not relationship:
            logger.warning(
                "relationship_not_found",
                relationship_id=relationship_id,
                character_qiao_id=character_info["qiao_id"],
            )
            return None

        return {
            "id": relationship.id,
            "name": relationship.name,
            "display_name": relationship.display_name,
            "prompt_fragment": relationship.prompt_fragment,
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
            "avatar_prompt": profile.avatar_prompt,
            "region": profile.region,
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
        from services.ai.relationship_scoring import get_relationship_scores

        # Do not auto-initialize in validation. Missing scores is an error by design.
        scores = await get_relationship_scores(db, character_info["qiao_id"], auto_initialize=False)

        if not scores:
            raise ValidationError(
                f"Relationship scores missing for character '{character_info['qiao_id']}'",
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
