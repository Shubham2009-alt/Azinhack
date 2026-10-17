from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CreateResearchRunRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    year_min: int | None = Field(default=None, ge=1900, le=2100)
    year_max: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_year_range(self):
        if self.year_min is not None and self.year_max is not None and self.year_min > self.year_max:
            raise ValueError("year_min must be less than or equal to year_max")
        return self

    @model_validator(mode="after")
    def validate_question_not_blank(self):
        if not self.question.strip():
            raise ValueError("question must not be blank")
        return self


class CreateResearchRunResponse(BaseModel):
    run_id: UUID
    status: Literal["queued"]


class ResearchRunStatusResponse(BaseModel):
    run_id: UUID
    question: str
    status: str
    stage: str
    progress: int
    created_at: datetime
    updated_at: datetime
    source_count: int
    usable_source_count: int
    warning_summary: str | None = None
