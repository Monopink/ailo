import uuid
from typing import cast

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.instance import AIInstance
from app.models.ai.memory import AIInstanceMemory, AITemplateMemory
from app.models.ai.personality import AIPersonality
from app.models.ai.style import AIStyle
from app.models.ai.template import AITemplate, AIType
from app.models.user import User
from app.services.ai.memory import copy_template_memories_to_instance
from app.services.ai.memory.operations import process_memory_operations
from app.type_defs import InstanceContext


async def _get_reference(
    session: AsyncSession,
) -> tuple[User | None, AIStyle | None, AIPersonality | None]:
    user = (await session.execute(select(User).limit(1))).scalar_one_or_none()
    style = (await session.execute(select(AIStyle).limit(1))).scalar_one_or_none()
    personality = (await session.execute(select(AIPersonality).limit(1))).scalar_one_or_none()
    return user, style, personality


@pytest.mark.asyncio
async def test_memory_operations_lifecycle(
    db_session: AsyncSession,
) -> None:
    """Ensure add/update/refresh/remove behave correctly on ai_instance_memories."""
    user, style, personality = await _get_reference(db_session)
    if not all([user, style, personality]):
        pytest.skip("Required seed data missing for memory operations test")

    assert user is not None
    assert style is not None
    assert personality is not None

    instance = AIInstance(
        qiao_id=f"test_{uuid.uuid4().hex[:24]}",  # 5+24=29 chars, fits in varchar(32)
        user_id=user.id,
        user_qiao_id=user.qiao_id,
        style_id=style.id,
        personality_id=personality.id,
        creation_metadata={},
        status=1,
        prompt_variables={},
        request_params={},
        typing_speed_wpm=200,
        timezone="Asia/Shanghai",
        created_by=2,
    )
    db_session.add(instance)
    await db_session.flush()

    context = cast(
        InstanceContext,
        {
            "instance_id": instance.id,
            "instance_qiao_id": instance.qiao_id,
            "user_id": user.id,
            "user_qiao_id": user.qiao_id,
            "status": instance.status,
            "created_by": instance.created_by,
            "prompt_variables": instance.prompt_variables,
            "request_params": instance.request_params,
            "typing_speed_wpm": instance.typing_speed_wpm,
            "timezone": instance.timezone,
            "relationship_counts": {"total": 0},
            "style": {"id": style.id, "display_name": style.display_name},
            "personality": {
                "id": personality.id,
                "display_name": personality.display_name,
                "prompt": personality.prompt,
            },
            "profile": {
                "nickname": user.username or user.qiao_id,
                "bio": None,
                "gender": None,
                "avatar_url": None,
                "avatar_prompt": None,
                "region": None,
            },
            "dimensions": [],
        },
    )

    # Add core/recent memories
    await process_memory_operations(
        db_session,
        context,
        {
            "remove": [],
            "update": [],
            "refresh": [],
            "add": [
                {"memory_type": "core", "content": "用户喜欢跑步", "importance": 9},
                {"memory_type": "recent", "content": "用户昨天熬夜", "importance": 3},
            ],
        },
    )

    memories = (
        (
            await db_session.execute(
                select(AIInstanceMemory).where(AIInstanceMemory.instance_id == instance.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(memories) == 2

    core = next(m for m in memories if m.memory_type == "core")
    recent = next(m for m in memories if m.memory_type == "recent")

    # Update/refresh
    await process_memory_operations(
        db_session,
        context,
        {
            "remove": [],
            "update": [
                {
                    "old_content": "用户喜欢跑步",
                    "new_content": "用户喜欢夜跑",
                    "new_importance": 8,
                }
            ],
            "refresh": ["用户昨天熬夜"],
            "add": [],
        },
    )
    await db_session.refresh(core)
    await db_session.refresh(recent)
    assert core.content == "用户喜欢夜跑"
    assert core.importance == 8
    assert recent.refreshed_at is not None

    # Remove core entry
    await process_memory_operations(
        db_session,
        context,
        {
            "remove": ["用户喜欢夜跑"],
            "update": [],
            "refresh": [],
            "add": [],
        },
    )
    await db_session.refresh(core)
    assert core.status == 2

    # Clean up test data
    await db_session.execute(
        delete(AIInstanceMemory).where(AIInstanceMemory.instance_id == instance.id)
    )
    await db_session.execute(delete(AIInstance).where(AIInstance.id == instance.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_copy_template_memories_to_instance(
    db_session: AsyncSession,
) -> None:
    """Ensure template memories are copied into ai_instance_memories during instantiation."""
    user, style, personality = await _get_reference(db_session)
    ai_type = (await db_session.execute(select(AIType).limit(1))).scalar_one_or_none()
    if not all([user, style, personality, ai_type]):
        pytest.skip("Required seed data missing for template memory copy test")

    assert user is not None
    assert style is not None
    assert personality is not None
    assert ai_type is not None

    template = AITemplate(
        type_id=ai_type.id,
        style_id=style.id,
        personality_id=personality.id,
        prompt_variables={},
        request_params={},
        llm_config_id=None,
        timezone="Asia/Shanghai",
        typing_speed_wpm=180,
        display_name="Template Memory Test",
    )
    db_session.add(template)
    await db_session.flush()

    template_memories = [
        AITemplateMemory(
            template_id=template.id,
            display_order=1,
            memory_type="core",
            content="用户最近在练习吉他",
            importance=8,
        ),
        AITemplateMemory(
            template_id=template.id,
            display_order=2,
            memory_type="recent",
            content="用户计划周末远足",
            importance=4,
        ),
    ]
    db_session.add_all(template_memories)
    await db_session.flush()

    instance = AIInstance(
        qiao_id=f"tmpl_{uuid.uuid4().hex[:27]}",  # 5+27=32 chars, exact fit
        user_id=user.id,
        user_qiao_id=user.qiao_id,
        style_id=style.id,
        personality_id=personality.id,
        creation_metadata={},
        status=1,
        prompt_variables={},
        request_params={},
        typing_speed_wpm=template.typing_speed_wpm,
        timezone="Asia/Shanghai",
        created_by=2,
    )
    db_session.add(instance)
    await db_session.flush()

    copied = await copy_template_memories_to_instance(
        db_session, template_id=template.id, instance=instance
    )
    assert copied == len(template_memories)

    instance_memories = (
        (
            await db_session.execute(
                select(AIInstanceMemory).where(AIInstanceMemory.instance_id == instance.id)
            )
        )
        .scalars()
        .all()
    )
    assert {m.content for m in instance_memories} == {m.content for m in template_memories}
    assert all(m.status == 1 for m in instance_memories)

    await db_session.execute(
        delete(AIInstanceMemory).where(AIInstanceMemory.instance_id == instance.id)
    )
    await db_session.execute(
        delete(AITemplateMemory).where(AITemplateMemory.template_id == template.id)
    )
    await db_session.execute(delete(AIInstance).where(AIInstance.id == instance.id))
    await db_session.execute(delete(AITemplate).where(AITemplate.id == template.id))
    await db_session.commit()
