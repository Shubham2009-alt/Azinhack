from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import ResearchRun, Source
from app.schemas import CreateResearchRunRequest, CreateResearchRunResponse, ResearchRunStatusResponse
from app.services.research_discovery import run_research_discovery
from app.settings import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ResearchPilot API",
    description="Evidence-traceable research exploration API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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
)
def create_research_run(
    payload: CreateResearchRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CreateResearchRunResponse:
    """Persist a validated research request; processing is added in a later step."""
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
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESEARCH_RUN_NOT_FOUND", "message": "No research run exists for this ID."},
        )

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
