"""
Admin APIs for discovery management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.discovery import square_entry
from app.schemas.discovery import (
    PaginationInfo,
    SquareEntry,
    SquareEntryCreate,
    SquareEntryListResponse,
    SquareEntryUpdate,
)
from app.services.discovery.validators import ensure_ai_type_has_active_persona

router = APIRouter()


@router.get("/entries", response_model=SquareEntryListResponse)
async def list_square_entries(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List square exposure entries with pagination."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    skip = (page - 1) * page_size

    items = await square_entry.get_multi(db, skip=skip, limit=page_size)
    total = await square_entry.count(db)
    has_more = (page * page_size) < total

    # Convert ORM models to Pydantic schemas
    items_response = [SquareEntry.model_validate(item) for item in items]

    pagination = PaginationInfo(page=page, page_size=page_size, total=total, has_more=has_more)
    return SquareEntryListResponse(items=items_response, pagination=pagination)


@router.post("/entries", response_model=SquareEntry)
async def create_square_entry(entry: SquareEntryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new discovery entry."""
    await ensure_ai_type_has_active_persona(db, entry.type_id)
    db_obj = await square_entry.create(db, obj_in=entry)
    return SquareEntry.model_validate(db_obj)


@router.patch("/entries/{entry_id}", response_model=SquareEntry)
async def update_square_entry(
    entry_id: int,
    updates: SquareEntryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing discovery entry."""
    db_obj = await square_entry.get(db, id=entry_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_data = updates.model_dump(exclude_unset=True)
    if "type_id" in update_data and update_data["type_id"] is not None:
        await ensure_ai_type_has_active_persona(db, update_data["type_id"])

    updated_obj = await square_entry.update(db, db_obj=db_obj, obj_in=update_data)
    return SquareEntry.model_validate(updated_obj)
