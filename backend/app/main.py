import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Claim, ClaimRelation, Report, ResearchRun, Source
from app.rate_limit import enforce_create_run_rate_limit
from app.security import RequestSecurityMiddleware
from app.schemas import (
    CreateResearchRunRequest,
    CreateResearchRunResponse,
    GraphEdgeResponse,
    GraphNodeResponse,
    ResearchGraphResponse,
    ResearchReportResponse,
    ResearchRunStatusResponse,
    ResearchSourceResponse,
    SourceClaimResponse,
    SourcesResponse,
)
from app.services.research_discovery import run_research_discovery
from app.settings import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


logger = logging.getLogger("researchpilot.api")


def _error_payload(code: str, message: str, *, details: list[dict[str, str]] | None = None, request_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        payload["error"] = {**payload["error"], "details": details}
    if request_id is not None:
        payload["error"] = {**payload["error"], "request_id": request_id}
    return payload


app = FastAPI(
    title="ResearchPilot API",
    description="Evidence-traceable research exploration API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.add_middleware(RequestSecurityMiddleware, max_body_bytes=1_048_576)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part not in {"body", "query", "path"}]
        field = location[-1] if location else "body"
        details.append({"field": field, "reason": str(error.get("msg", "Invalid request value."))})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            "VALIDATION_ERROR",
            "The request payload is invalid.",
            details=details,
            request_id=uuid4().hex,
        ),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "HTTP_ERROR"))
        message = str(detail.get("message", "Request failed."))
        details = detail.get("details")
        if not isinstance(details, list):
            details = None
    else:
        code = "HTTP_ERROR"
        message = str(detail)
        details = None
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code, message, details=details if isinstance(details, list) else None, request_id=uuid4().hex),
        headers=exc.headers,
    )


@app.middleware("http")
async def unhandled_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled API exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                "INTERNAL_SERVER_ERROR",
                "An unexpected server error occurred.",
                request_id=uuid4().hex,
            ),
        )


def _get_run_or_404(run_id: str, db: Session) -> ResearchRun:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESEARCH_RUN_NOT_FOUND", "message": "No research run exists for this ID."},
        )
    return run


def _source_response(source: Source, claims: list[Claim] | None = None) -> ResearchSourceResponse:
    return ResearchSourceResponse(
        id=source.id,
        title=source.title,
        canonical_url=source.canonical_url,
        publisher=source.publisher,
        published_at=source.published_at,
        publication_year=source.publication_year,
        authors=source.authors or [],
        venue=source.venue,
        citation_count=source.citation_count,
        retrieval_status=source.retrieval_status,
        failure_code=source.failure_code,
        excerpt=source.excerpt,
        retrieved_at=source.retrieved_at,
        claims=[
            SourceClaimResponse(
                id=claim.id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                evidence_excerpt=claim.evidence_excerpt,
                confidence_label=claim.confidence_label,
                is_inference=claim.is_inference,
            )
            for claim in (claims or [])
        ],
    )


@app.get("/api/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return application liveness without exposing configuration or credentials."""
    return {"status": "ok", "service": "researchpilot-api"}


@app.post(
    "/api/research-runs",
    response_model=CreateResearchRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["research"],
    dependencies=[Depends(enforce_create_run_rate_limit)],
)
def create_research_run(
    payload: CreateResearchRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CreateResearchRunResponse:
    """Persist a validated research request and schedule source discovery."""
    run = ResearchRun(
        question=payload.question.strip(),
        year_min=payload.year_min,
        year_max=payload.year_max,
        status="queued",
        stage="queued",
        progress=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(run_research_discovery, run.id)
    return CreateResearchRunResponse(run_id=run.id, status="queued")


@app.get(
    "/api/research-runs/{run_id}",
    response_model=ResearchRunStatusResponse,
    tags=["research"],
)
def get_research_run(run_id: str, db: Session = Depends(get_db)) -> ResearchRunStatusResponse:
    """Return persisted status and source counts for a research run."""
    run = _get_run_or_404(run_id, db)
    source_count = db.scalar(select(func.count(Source.id)).where(Source.run_id == run.id)) or 0
    usable_source_count = db.scalar(
        select(func.count(Source.id)).where(
            Source.run_id == run.id,
            Source.retrieval_status == "retrieved",
        )
    ) or 0
    return ResearchRunStatusResponse(
        run_id=run.id,
        question=run.question,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        created_at=run.created_at,
        updated_at=run.updated_at,
        source_count=source_count,
        usable_source_count=usable_source_count,
        warning_summary=run.warning_summary,
    )


@app.get("/api/research-runs/{run_id}/sources", response_model=SourcesResponse, tags=["research"])
def get_research_sources(run_id: str, db: Session = Depends(get_db)) -> SourcesResponse:
    """Return source metadata and linked claims, never full stored page text."""
    run = _get_run_or_404(run_id, db)
    sources = list(db.scalars(select(Source).where(Source.run_id == run.id).order_by(Source.title, Source.id)))
    claims = list(db.scalars(select(Claim).where(Claim.run_id == run.id).order_by(Claim.created_at, Claim.id)))
    claims_by_source: dict[str, list[Claim]] = {}
    for claim in claims:
        if claim.source_id:
            claims_by_source.setdefault(claim.source_id, []).append(claim)
    return SourcesResponse(
        run_id=run.id,
        status=run.status,
        sources=[_source_response(source, claims_by_source.get(source.id, [])) for source in sources],
        warning_summary=run.warning_summary,
    )


@app.get("/api/research-runs/{run_id}/report", response_model=ResearchReportResponse, tags=["research"])
def get_research_report(run_id: str, db: Session = Depends(get_db)) -> ResearchReportResponse:
    """Return the report draft and source-linked evidence, including partial results."""
    run = _get_run_or_404(run_id, db)
    report = db.scalar(select(Report).where(Report.run_id == run.id))
    claims = list(db.scalars(select(Claim).where(Claim.run_id == run.id).order_by(Claim.created_at, Claim.id)))
    sources = list(db.scalars(select(Source).where(Source.run_id == run.id).order_by(Source.title, Source.id)))
    claims_by_source: dict[str, list[Claim]] = {}
    for claim in claims:
        if claim.source_id:
            claims_by_source.setdefault(claim.source_id, []).append(claim)
    return ResearchReportResponse(
        run_id=run.id,
        question=run.question,
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        generated_at=report.generated_at if report else None,
        structured_sections=report.structured_sections if report else {},
        claims=[
            SourceClaimResponse(
                id=claim.id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                evidence_excerpt=claim.evidence_excerpt,
                confidence_label=claim.confidence_label,
                is_inference=claim.is_inference,
            )
            for claim in claims
        ],
        sources=[_source_response(source, claims_by_source.get(source.id, [])) for source in sources],
        validation_warnings=(report.validation_warnings or []) if report else [],
        warning_summary=run.warning_summary,
    )


@app.get("/api/research-runs/{run_id}/graph", response_model=ResearchGraphResponse, tags=["research"])
def get_research_graph(run_id: str, db: Session = Depends(get_db)) -> ResearchGraphResponse:
    """Return source/claim nodes and persisted validated relationships."""
    run = _get_run_or_404(run_id, db)
    sources = list(db.scalars(select(Source).where(Source.run_id == run.id)))
    claims = list(db.scalars(select(Claim).where(Claim.run_id == run.id)))
    claim_ids = {claim.id for claim in claims}
    source_by_id = {source.id: source for source in sources}
    nodes: list[GraphNodeResponse] = []
    edges: list[GraphEdgeResponse] = []

    for source in sources:
        nodes.append(GraphNodeResponse(
            id=source.id,
            type="source",
            label=source.title[:240],
            source_url=source.canonical_url,
            excerpt=source.excerpt,
            metadata={
                "retrieval_status": source.retrieval_status,
                "publisher": source.publisher,
                "published_at": source.published_at.isoformat() if source.published_at else None,
            },
        ))
    for claim in claims:
        source = source_by_id.get(claim.source_id or "")
        nodes.append(GraphNodeResponse(
            id=claim.id,
            type="claim",
            label=claim.claim_text[:240],
            confidence=claim.confidence_label,
            source_url=source.canonical_url if source else None,
            excerpt=claim.evidence_excerpt,
            metadata={
                "claim_type": claim.claim_type,
                "is_inference": claim.is_inference,
                "source_id": claim.source_id,
            },
        ))
        if source and claim.evidence_excerpt and claim.evidence_excerpt in (source.content_text or ""):
            edges.append(GraphEdgeResponse(
                source=source.id,
                target=claim.id,
                type="supports",
                rationale="Evidence excerpt matches the retrieved source text.",
                confidence=claim.confidence_label,
            ))

    if claim_ids:
        relations = list(db.scalars(select(ClaimRelation).where(
            ClaimRelation.from_claim_id.in_(claim_ids),
            ClaimRelation.to_claim_id.in_(claim_ids),
        )))
    else:
        relations = []
    for relation in relations:
        edges.append(GraphEdgeResponse(
            source=relation.from_claim_id,
            target=relation.to_claim_id,
            type=relation.relationship,
            rationale=relation.rationale,
            confidence=relation.confidence_label,
        ))
    return ResearchGraphResponse(
        run_id=run.id,
        status=run.status,
        nodes=nodes,
        edges=edges,
        warning_summary=run.warning_summary,
    )
