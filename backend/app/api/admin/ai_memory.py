"""
Admin AI Memory API endpoints.
Handles CRUD operations for Template Memories and Instance Memories.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.type_aliases import JSONDict
from app.models.ai.instance import AIInstance
from app.models.ai.memory import AIInstanceMemory, AITemplateMemory
from app.models.ai.template import AITemplate
from app.utils.logging import get_logger

logger = get_logger(__name__)

memory_router = APIRouter()

# Type alias for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ============================================================================
# Pydantic Schemas
# ============================================================================


class TemplateMemoryCreateSchema(BaseModel):
    """Schema for creating a template memory."""

    template_id: int = Field(..., description="Template ID")
    memory_type: Literal["core", "recent"] = Field(..., description="Memory type")
    content: str = Field(..., min_length=1, description="Memory content")
    importance: int = Field(..., ge=1, le=10, description="Importance 1-10")
    display_order: int = Field(default=0, description="Display order")


class TemplateMemoryUpdateSchema(BaseModel):
    """Schema for updating a template memory."""

    memory_type: Literal["core", "recent"] | None = Field(None, description="Memory type")
    content: str | None = Field(None, min_length=1, description="Memory content")
    importance: int | None = Field(None, ge=1, le=10, description="Importance 1-10")
    display_order: int | None = Field(None, description="Display order")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        """Ensure content is not empty string."""
        if v is not None and v.strip() == "":
            raise ValueError("Content cannot be empty")
        return v


class InstanceMemoryCreateSchema(BaseModel):
    """Schema for creating an instance memory."""

    instance_id: int = Field(..., description="Instance ID")
    memory_type: Literal["core", "recent"] = Field(..., description="Memory type")
    content: str = Field(..., min_length=1, description="Memory content")
    importance: int = Field(..., ge=1, le=10, description="Importance 1-10")
    source_message_id: int | None = Field(None, description="Source message ID")


class InstanceMemoryUpdateSchema(BaseModel):
    """Schema for updating an instance memory."""

    memory_type: Literal["core", "recent"] | None = Field(None, description="Memory type")
    content: str | None = Field(None, min_length=1, description="Memory content")
    importance: int | None = Field(None, ge=1, le=10, description="Importance 1-10")
    status: Literal[1, 2] | None = Field(None, description="Status: 1=active, 2=archived")
    source_message_id: int | None = Field(None, description="Source message ID")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        """Ensure content is not empty string."""
        if v is not None and v.strip() == "":
            raise ValueError("Content cannot be empty")
        return v


# ============================================================================
# Template Memory Endpoints
# ============================================================================


@memory_router.post("/template-memory/create")
async def create_template_memory(data: TemplateMemoryCreateSchema, db: DbSession) -> JSONDict:
    """Create a new template memory."""
    # Verify template exists
    stmt = select(AITemplate).where(AITemplate.id == data.template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Create memory
    memory = AITemplateMemory(
        template_id=data.template_id,
        memory_type=data.memory_type,
        content=data.content,
        importance=data.importance,
        display_order=data.display_order,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    logger.info(
        "template_memory_created",
        template_id=data.template_id,
        memory_id=memory.id,
        memory_type=data.memory_type,
    )

    return {
        "success": True,
        "message": "Memory created successfully",
        "memory_id": memory.id,
    }


@memory_router.put("/template-memory/{memory_id}/update")
async def update_template_memory(
    memory_id: int, data: TemplateMemoryUpdateSchema, db: DbSession
) -> JSONDict:
    """Update an existing template memory."""
    stmt = select(AITemplateMemory).where(AITemplateMemory.id == memory_id)
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Update fields
    update_fields = data.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No data to update")

    for field, value in update_fields.items():
        setattr(memory, field, value)

    await db.commit()

    logger.info(
        "template_memory_updated",
        memory_id=memory_id,
        fields=list(update_fields.keys()),
    )

    return {"success": True, "message": "Memory updated successfully"}


@memory_router.delete("/template-memory/{memory_id}/delete")
async def delete_template_memory(memory_id: int, db: DbSession) -> JSONDict:
    """Delete a template memory."""
    stmt = select(AITemplateMemory).where(AITemplateMemory.id == memory_id)
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    template_id = memory.template_id
    await db.delete(memory)
    await db.commit()

    logger.info(
        "template_memory_deleted",
        memory_id=memory_id,
        template_id=template_id,
    )

    return {"success": True, "message": "Memory deleted successfully"}


# ============================================================================
# Instance Memory Endpoints
# ============================================================================


@memory_router.post("/instance-memory/create")
async def create_instance_memory(data: InstanceMemoryCreateSchema, db: DbSession) -> JSONDict:
    """Create a new instance memory."""
    # Verify instance exists and get user info
    stmt = select(AIInstance).where(AIInstance.id == data.instance_id)
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    # Create memory with auto-filled user info
    memory = AIInstanceMemory(
        instance_id=data.instance_id,
        instance_qiao_id=instance.qiao_id,
        user_id=instance.user_id,
        user_qiao_id=instance.user_qiao_id,
        memory_type=data.memory_type,
        content=data.content,
        importance=data.importance,
        source_message_id=data.source_message_id,
        status=1,  # Active by default
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    logger.info(
        "instance_memory_created",
        instance_id=data.instance_id,
        memory_id=memory.id,
        memory_type=data.memory_type,
    )

    return {
        "success": True,
        "message": "Memory created successfully",
        "memory_id": memory.id,
    }


@memory_router.put("/instance-memory/{memory_id}/update")
async def update_instance_memory(
    memory_id: int, data: InstanceMemoryUpdateSchema, db: DbSession
) -> JSONDict:
    """Update an existing instance memory."""
    stmt = select(AIInstanceMemory).where(AIInstanceMemory.id == memory_id)
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Update fields
    update_fields = data.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No data to update")

    for field, value in update_fields.items():
        setattr(memory, field, value)

    await db.commit()

    logger.info(
        "instance_memory_updated",
        memory_id=memory_id,
        fields=list(update_fields.keys()),
    )

    return {"success": True, "message": "Memory updated successfully"}


@memory_router.delete("/instance-memory/{memory_id}/delete")
async def delete_instance_memory(memory_id: int, db: DbSession) -> JSONDict:
    """Delete an instance memory."""
    stmt = select(AIInstanceMemory).where(AIInstanceMemory.id == memory_id)
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    instance_id = memory.instance_id
    await db.delete(memory)
    await db.commit()

    logger.info(
        "instance_memory_deleted",
        memory_id=memory_id,
        instance_id=instance_id,
    )

    return {"success": True, "message": "Memory deleted successfully"}
