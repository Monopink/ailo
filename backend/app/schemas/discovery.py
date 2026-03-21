"""Discovery page schemas.

This module contains Pydantic schemas for discovery page operations.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import ExposureStrategy, SquareCategoryTheme


class SquareCategoryItem(BaseModel):
    """Square category item returned to clients."""

    category_key: str = Field(..., description="Category key (kebab-case)")
    title: str = Field(..., description="Category display title")
    description: str | None = Field(None, description="Category description")
    theme_key: SquareCategoryTheme = Field(..., description="Theme key")
    icon_ref: str = Field(..., description="Icon reference (tdesign:<icon-name>)")

    class Config:
        """Configuration for discovery schema population."""

        from_attributes = True


class SquareCategoryListResponse(BaseModel):
    """Square category list response."""

    items: list[SquareCategoryItem] = Field(..., description="Square categories")


class SquareContactResponse(BaseModel):
    """Square page contact response."""

    qiao_id: str = Field(..., description="Contact qiao_id")
    category_key: str = Field(..., description="Category key (kebab-case)")
    type_id: int = Field(..., description="AI type identifier backing this entry")
    nickname: str | None = Field(None, description="Persona nickname")
    gender: int | None = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: str | None = Field(
        None, description="Dynamically generated avatar CDN URL (not stored in database)"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Preset tags written into contacts.tags when the user adds this persona",
    )
    remark: str | None = Field(
        None,
        description="Preset remark written into contacts.remark when the user adds this persona",
    )
    bio: str | None = Field(None, description="Bio/description")
    region: str | None = Field(None, description="Region/location")

    class Config:
        """Configuration for discovery schema population."""

        from_attributes = True


class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total items count")
    has_more: bool = Field(..., description="Whether there are more items")


class SquareContactListResponse(BaseModel):
    """Square contact list response."""

    items: list[SquareContactResponse] = Field(..., description="Contact list")
    pagination: PaginationInfo = Field(..., description="Pagination information")
    refresh_available_at: datetime | None = Field(
        None, description="Next allowed refresh time in ISO 8601"
    )


class SquareEntryBase(BaseModel):
    """Base schema for Square exposure entries."""

    category_key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Square category key (kebab-case)",
    )
    type_id: int = Field(..., description="AI type exposed in this slot")
    exposure_strategy: ExposureStrategy = Field(
        ExposureStrategy.RANDOM, description="Exposure strategy (1=random)"
    )
    status: int = Field(1, ge=1, le=2, description="Status: 1=active, 2=inactive")


class SquareEntryCreate(SquareEntryBase):
    """Schema for creating Square exposure entries."""


class SquareEntryUpdate(BaseModel):
    """Schema for updating Square exposure entries."""

    category_key: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Square category key (kebab-case)",
    )
    type_id: int | None = Field(None, description="AI type exposed in this slot")
    exposure_strategy: ExposureStrategy | None = Field(
        None, description="Exposure strategy (1=random)"
    )
    status: int | None = Field(None, ge=1, le=2, description="Status: 1=active, 2=inactive")


class SquareEntry(SquareEntryBase):
    """Square exposure entry response."""

    id: int = Field(..., description="Entry ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Configuration for discovery query schema population."""

        from_attributes = True


class SquareEntryListResponse(BaseModel):
    """Paginated response for square entries."""

    items: list[SquareEntry] = Field(..., description="Square entries")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class StrangerProfileResponse(BaseModel):
    """Stranger profile response (public profile without contact relationship)."""

    qiao_id: str = Field(..., description="Profile qiao_id")
    nickname: str | None = Field(None, description="Nickname")
    gender: int | None = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: str | None = Field(
        None, description="Dynamically generated avatar CDN URL (not stored in database)"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Preset tags written into contacts.tags when the user adds this persona",
    )
    remark: str | None = Field(
        None,
        description="Preset remark written into contacts.remark when the user adds this persona",
    )
    bio: str | None = Field(None, description="Bio/description")
    region: str | None = Field(None, description="Region/location")
    category_key: str | None = Field(None, description="Source category key")
    category_title: str | None = Field(None, description="Source category title")

    class Config:
        """Configuration for discovery filters schema population."""

        from_attributes = True
