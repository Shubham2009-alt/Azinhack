from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings

app = FastAPI(
    title="ResearchPilot API",
    description="Evidence-traceable research exploration API.",
    version="0.1.0",
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
