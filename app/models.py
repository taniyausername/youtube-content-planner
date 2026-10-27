from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    niche: str = Field(min_length=2, max_length=120)
    audience: str = Field(default='Beginner creators', min_length=2, max_length=120)
    format: Literal['Tutorial', 'Explainer', 'Comparison', 'Case study'] = 'Tutorial'
    mode: Literal['demo', 'live'] = 'demo'
    days: int = Field(default=30, ge=7, le=180)
    max_videos: int = Field(default=30, ge=10, le=100)

    @field_validator('niche', 'audience')
    @classmethod
    def trim(cls, value: str) -> str:
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Enter at least two non-whitespace characters.')
        return value


class Video(BaseModel):
    id: str
    title: str
    description: str = ''
    channel_id: str
    channel_title: str
    published_at: datetime
    observed_at: datetime
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    category_id: str = ''
    synthetic: bool = False

    @field_validator('published_at', 'observed_at')
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError('Timestamps must include a timezone.')
        return value
