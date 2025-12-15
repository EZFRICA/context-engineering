"""
Pydantic models for input validation and data structures.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime


class FactCreate(BaseModel):
    """Model for creating a new fact."""
    content: str = Field(..., min_length=1, max_length=5000, description="Fact content")
    context_scope: str = Field(..., min_length=1, description="Context/trip identifier")
    tags: List[str] = Field(default_factory=list, description="Fact tags")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('content')
    def content_not_empty(cls, v: str) -> str:
        """Validate content is not empty or whitespace."""
        if not v.strip():
            raise ValueError('Content cannot be empty or whitespace')
        return v.strip()
    
    @validator('context_scope')
    def scope_valid(cls, v: str) -> str:
        """Validate scope format."""
        if not v.strip():
            raise ValueError('Context scope cannot be empty')
        return v.strip().lower().replace(' ', '_')
    
    @validator('tags')
    def tags_valid(cls, v: List[str]) -> List[str]:
        """Clean and validate tags."""
        return [tag.strip() for tag in v if tag.strip()]


class FactResponse(BaseModel):
    """Model for fact responses."""
    id: str
    content: str
    context_scope: str
    tags: List[str]
    payload: Dict[str, Any]
    created_at: datetime
    source: str
    approved_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MemoryQuery(BaseModel):
    """Model for memory search queries."""
    scope_id: str = Field(..., description="Context/trip identifier")
    query: Optional[str] = Field(None, description="Search query")
    limit: int = Field(default=5, ge=1, le=100, description="Max results")
    
    @validator('scope_id')
    def scope_not_empty(cls, v: str) -> str:
        """Validate scope is not empty."""
        if not v.strip():
            raise ValueError('Scope ID cannot be empty')
        return v.strip()


class TripCreate(BaseModel):
    """Model for creating a new trip."""
    destination: str = Field(..., min_length=1, description="Trip destination")
    
    @validator('destination')
    def destination_valid(cls, v: str) -> str:
        """Validate and format destination."""
        if not v.strip():
            raise ValueError('Destination cannot be empty')
        # Convert to scope_id format
        return v.strip().lower().replace(' ', '_')
