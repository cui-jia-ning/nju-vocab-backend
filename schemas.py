from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class WordCreate(BaseModel):
    word: str
    meaning: str


class WordResponse(BaseModel):
    id: int
    word: str
    meaning: str

    class Config:
        from_attributes = True


class ReviewItem(BaseModel):
    word_id: int
    word: str
    meaning: str
    review_count: int
    next_review_date: date


class StatsResponse(BaseModel):
    total_users: int
    total_logins_today: int
    unique_logins_today: int
    total_words: int
    total_reviews_today: int
    words_due_today: int
