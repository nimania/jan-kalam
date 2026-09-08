from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness — the process is up."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    """Readiness — dependencies (the database) are reachable."""
    db_ok = True
    detail = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive
        db_ok = False
        detail = str(exc)
    return {"status": "ok" if db_ok else "degraded", "database": detail}
