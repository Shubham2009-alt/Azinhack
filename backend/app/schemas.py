from datetime import datetime
from typing import Any, Literal
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


class SourceClaimResponse(BaseModel):
    id: UUID
    claim_text: str
    claim_type: str
    evidence_excerpt: str | None
    confidence_label: str
    is_inference: bool


class ResearchSourceResponse(BaseModel):
    id: UUID
    title: str
    canonical_url: str
    publisher: str | None = None
    published_at: datetime | None = None
    publication_year: int | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    citation_count: int | None = None
    retrieval_status: str
    failure_code: str | None = None
    excerpt: str | None = None
    retrieved_at: datetime
    claims: list[SourceClaimResponse] = Field(default_factory=list)


class SourcesResponse(BaseModel):
    run_id: UUID
    status: str
    sources: list[ResearchSourceResponse]
    warning_summary: str | None = None


class ResearchReportResponse(BaseModel):
    run_id: UUID
    question: str
    status: str
    stage: str
    progress: int
    generated_at: datetime | None = None
    structured_sections: dict[str, Any] = Field(default_factory=dict)
    claims: list[SourceClaimResponse] = Field(default_factory=list)
    sources: list[ResearchSourceResponse] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    warning_summary: str | None = None


class GraphNodeResponse(BaseModel):
    id: str
    type: Literal["claim", "source"]
    label: str
    confidence: str | None = None
    source_url: str | None = None
    excerpt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    type: Literal["supports", "contradicts", "qualifies", "derived_from"]
    rationale: str
    confidence: str


class ResearchGraphResponse(BaseModel):
    run_id: UUID
    status: str
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    warning_summary: str | None = None
