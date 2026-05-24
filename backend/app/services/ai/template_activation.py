"""Template activation validation services."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai import ai_personality_placeholder as personality_placeholder_crud
from app.services.ai.utils.template import find_missing_required_placeholder_keys


async def get_missing_required_prompt_variables_for_template(
    db: AsyncSession,
    *,
    personality_id: int | None,
    prompt_variables: object,
) -> list[str]:
    """Return missing required prompt variable keys for one template personality."""
    if personality_id is None:
        return []
    placeholders = await personality_placeholder_crud.get_placeholders_by_personality(
        db,
        personality_id=personality_id,
    )
    return find_missing_required_placeholder_keys(
        prompt_variables if isinstance(prompt_variables, dict) else None,
        placeholders,
    )
