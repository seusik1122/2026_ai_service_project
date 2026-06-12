from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LectureCreate(BaseModel):
    platform: str
    title: str
    instructor_name: Optional[str] = None
    category: Optional[str] = None
    price: int = 0
    rating: Optional[float] = None
    student_count: Optional[int] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Optional[list[str]] = None
    is_free: bool = False


class ReviewCreate(BaseModel):
    instructor_name: Optional[str] = None
    platform_source: str
    content: str
    is_ad: bool = False
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    original_url: Optional[str] = None


class InstructorUpdate(BaseModel):
    trust_score: float
    positive_ratio: float
    review_count: int
    last_calculated_at: datetime


class ExamCreate(BaseModel):
    exam_name: str
    exam_type: Optional[str] = None
    application_start: Optional[str] = None
    application_end: Optional[str] = None
    exam_date: Optional[str] = None
    result_date: Optional[str] = None
    d_day: Optional[int] = None
    related_keywords: Optional[list[str]] = None


class LectureRequest(BaseModel):
    email: str
    topic: str
    budget: Optional[int] = None
    level: Optional[str] = None
