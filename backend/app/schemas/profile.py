"""
Profile schemas for request/response validation
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ProfileBase(BaseModel):
    """Base profile schema"""
    nickname: Optional[str] = Field(None, max_length=50, description="User nickname")
    bio: Optional[str] = Field(None, max_length=500, description="User bio/description")
    age: Optional[int] = Field(None, ge=13, le=120, description="User age")
    gender: Optional[str] = Field(None, max_length=10, description="User gender")
    location: Optional[str] = Field(None, max_length=100, description="User location")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar image URL")
    interests: Optional[str] = Field(None, max_length=1000, description="User interests")
    occupation: Optional[str] = Field(None, max_length=100, description="User occupation")
    education: Optional[str] = Field(None, max_length=100, description="User education")
    relationship_status: Optional[str] = Field(None, max_length=20, description="Relationship status")


class ProfileCreate(ProfileBase):
    """Schema for creating a profile"""
    pass


class ProfileUpdate(ProfileBase):
    """Schema for updating a profile"""
    pass


class ProfileInDBBase(ProfileBase):
    """Base schema for profile in database"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class Profile(ProfileInDBBase):
    """Schema for profile response"""
    pass


class ProfileInDB(ProfileInDBBase):
    """Schema for profile in database (internal use)"""
    pass


class ProfileSearch(BaseModel):
    """Schema for profile search parameters"""
    nickname: Optional[str] = Field(None, description="Search by nickname")
    bio: Optional[str] = Field(None, description="Search in bio")
    gender: Optional[str] = Field(None, description="Filter by gender")
    min_age: Optional[int] = Field(None, ge=13, description="Minimum age")
    max_age: Optional[int] = Field(None, le=120, description="Maximum age")
    location: Optional[str] = Field(None, description="Search by location")
    interests: Optional[str] = Field(None, description="Search in interests")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of records to return")


class ProfileStats(BaseModel):
    """Schema for profile statistics"""
    total_profiles: int
    gender_distribution: dict
    age_stats: dict
    
    model_config = ConfigDict(from_attributes=True)
