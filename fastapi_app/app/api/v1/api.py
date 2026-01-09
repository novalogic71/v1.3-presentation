#!/usr/bin/env python3
"""
Main API router for the Professional Audio Sync Analyzer.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from typing import List, Optional

from app.api.v1.endpoints import analysis, files, reports, ai, health, batch, repair, analyze_and_repair, ui_state, jobs, componentized, proxy, dashboard

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["analysis"]
)

api_router.include_router(
    files.router,
    prefix="/files",
    tags=["files"]
)

api_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["reports"]
)

api_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    batch.router,
    prefix="/analysis/batch",
    tags=["batch"]
)

api_router.include_router(
    repair.router,
    prefix="/repair",
    tags=["repair"]
)

api_router.include_router(
    analyze_and_repair.router,
    prefix="/workflows",
    tags=["workflows"]
)

api_router.include_router(
    ui_state.router,
    prefix="/ui/state",
    tags=["ui-state"]
)

api_router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["jobs"]
)

api_router.include_router(
    componentized.router,
    prefix="/analysis/componentized",
    tags=["componentized"]
)

api_router.include_router(
    proxy.router,
    prefix="/proxy",
    tags=["proxy"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"]
)
