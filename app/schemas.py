from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Token ---
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- User ---
class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    class Config:
        from_attributes = True

# --- Progress ---
class ProgressUpdate(BaseModel):
    chapter_index: int
    progress_percent: float

class ProgressResponse(BaseModel):
    book_id: int
    chapter_index: int
    progress_percent: float
    last_read_at: datetime
    class Config:
        from_attributes = True

# --- Book Content ---
class ChapterResponse(BaseModel):
    id: int
    title: str
    order: int
    file_name: str
    size_bytes: int
    class Config:
        from_attributes = True

class BookResponse(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    cover_path: Optional[str] = None
    file_path: str
    file_size: int
    chapters: List[ChapterResponse] = [] 
    class Config:
        from_attributes = True

# --- Transaction ---
class TransactionResponse(BaseModel):
    id: int
    action: str
    book_title: str
    file_size: int
    timestamp: datetime
    class Config:
        from_attributes = True