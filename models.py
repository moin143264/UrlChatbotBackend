"""
Pydantic models for request/response validation
Compatible with Python 3.13 and Pydantic 2.x
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field, validator


class ScrapingRequest(BaseModel):
    """Request model for sitemap scraping"""
    sitemap_url: HttpUrl = Field(..., description="URL of the sitemap.xml file")
    user_id: int = Field(..., description="ID of the user requesting scraping")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sitemap_url": "https://example.com/sitemap.xml",
                "user_id": 1
            }
        }


class ChatRequest(BaseModel):
    """Request model for chat interactions"""
    question: str = Field(..., min_length=1, max_length=1000, description="User's question")
    user_id: int = Field(..., description="ID of the user asking the question")
    context_limit: Optional[int] = Field(default=5, ge=1, le=10, description="Maximum number of context sources")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are your business hours?",
                "user_id": 1,
                "context_limit": 5
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat interactions"""
    answer: str = Field(..., description="AI-generated answer")
    source_urls: List[str] = Field(default=[], description="URLs of sources used for the answer")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    context_found: bool = Field(..., description="Whether relevant context was found")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Our business hours are Monday to Friday, 9 AM to 5 PM.",
                "source_urls": ["https://example.com/contact", "https://example.com/about"],
                "response_time_ms": 1250,
                "context_found": True,
                "timestamp": "2024-01-15T10:30:00"
            }
        }


class ScrapingStatus(BaseModel):
    """Model for scraping status information"""
    sitemap_id: int
    sitemap_url: str
    domain: str
    total_pages: int = 0
    scraped_pages: int = 0
    failed_pages: int = 0
    status: str  # pending, scraping, completed, failed
    last_scraped: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "sitemap_id": 1,
                "sitemap_url": "https://example.com/sitemap.xml",
                "domain": "example.com",
                "total_pages": 25,
                "scraped_pages": 23,
                "failed_pages": 2,
                "status": "completed",
                "last_scraped": "2024-01-15T10:30:00",
                "created_at": "2024-01-15T09:00:00"
            }
        }


class PageData(BaseModel):
    """Model for scraped page data"""
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    headings: Optional[str] = None
    image_url: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: Optional[str] = None
    status: str = "pending"
    
    @validator('content')
    def validate_content_length(cls, v):
        if v and len(v) > 100000:  # Limit content to 100KB
            return v[:100000] + "... [Content truncated]"
        return v


class SystemStats(BaseModel):
    """Model for system statistics"""
    total_users: int = 0
    total_pages: int = 0
    total_chats: int = 0
    active_sitemaps: int = 0
    recent_chats: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_users": 15,
                "total_pages": 1250,
                "total_chats": 3420,
                "active_sitemaps": 5,
                "recent_chats": 45,
                "timestamp": "2024-01-15T10:30:00"
            }
        }


class ApiResponse(BaseModel):
    """Generic API response model"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"result": "example"},
                "error": None,
                "timestamp": "2024-01-15T10:30:00"
            }
        }
