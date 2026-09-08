from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, health, sources, stories, topics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(stories.router)
api_router.include_router(sources.router)
api_router.include_router(topics.router)
api_router.include_router(admin.router)
