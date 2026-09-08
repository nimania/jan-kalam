from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()
mimetypes.add_type("application/manifest+json", ".webmanifest")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI-powered Persian-language news intelligence.",
)

# Dev-friendly CORS. In production, restrict allow_origins to your web app's host.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/api", tags=["meta"])
def api_info() -> dict:
    return {"app": settings.app_name, "docs": "/docs", "api": settings.api_v1_prefix}


# Serve the PWA web app (index.html, styles, app.js, icons, manifest, sw) at root.
# Mounted LAST so the API routes above take precedence.
_WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"
if _WEBAPP_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEBAPP_DIR), html=True), name="webapp")
