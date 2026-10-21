from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class BaseResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    data: Optional[T] = Field(default=None, description="Response data")
    errors: Optional[List[str]] = Field(default=None, description="List of error messages")


class PaginatedResponse(BaseResponse[List[T]], Generic[T]):
    """Paginated response wrapper."""
    
    meta: Optional[PaginationMeta] = Field(default=None, description="Pagination info")


def success_response(
    data: Any = None,
    message: str = "Success",
) -> Dict[str, Any]:
    """Create a success response dictionary."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "errors": None,
    }


def error_response(
    message: str = "An error occurred",
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create an error response dictionary."""
    return {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors or [message],
    }


def paginated_response(
    data: List[Any],
    total: int,
    page: int,
    per_page: int,
    message: str = "Success",
) -> Dict[str, Any]:
    """Create a paginated response dictionary."""
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return {
        "success": True,
        "message": message,
        "data": data,
        "errors": None,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }
