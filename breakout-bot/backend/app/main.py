"""Application FastAPI : assemblage des routes, cycle de vie (DB, hub
WebSocket, paper manager, planificateurs OI + adaptation)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_adaptive,
    routes_backtest,
    routes_config,
    routes_dashboard,
    routes_data,
    routes_optimize,
    routes_paper,
)
from app.api.deps import ADAPTIVE_SETTINGS_PATH, DB_PATH
from app.api.jobs import job_manager
from app.api.ws import hub
from app.db.connection import init_db
from app.paper.manager import PaperManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("breakout")


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    init_db(DB_PATH)
    hub.bind_loop()
    manager = PaperManager(broadcast=hub.broadcast)
    app.state.paper_manager = manager
    await manager.resume_active_sessions()

    scheduler = BackgroundScheduler(timezone="UTC")
    # collecte continue d'open interest (P0) — toutes les 5 minutes
    scheduler.add_job(manager.collect_oi, IntervalTrigger(minutes=5), id="oi_collector")

    # ré-optimisation adaptative planifiée (si activée dans les réglages)
    def adaptive_tick() -> None:
        from app.adaptive.settings import load_settings
        from app.api.routes_adaptive import run_adaptive_cycle

        settings = load_settings(ADAPTIVE_SETTINGS_PATH)
        if not settings.enabled:
            return
        job_manager.submit(
            "adaptive", lambda progress: run_adaptive_cycle(manager, "auto", progress)
        )

    def reschedule_adaptive() -> None:
        from app.adaptive.settings import load_settings

        settings = load_settings(ADAPTIVE_SETTINGS_PATH)
        trigger = CronTrigger(
            day_of_week=settings.cron_day_of_week, hour=settings.cron_hour_utc, timezone="UTC"
        )
        scheduler.add_job(adaptive_tick, trigger, id="adaptive", replace_existing=True)

    reschedule_adaptive()
    scheduler.start()
    app.state.scheduler = scheduler
    log.info("Breakout bot démarré — base : %s", DB_PATH)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await manager.stop_all()


def create_app() -> FastAPI:
    app = FastAPI(title="Bot Breakout Swing", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_config.router)
    app.include_router(routes_config.router_presets)
    app.include_router(routes_data.router)
    app.include_router(routes_backtest.router)
    app.include_router(routes_optimize.router)
    app.include_router(routes_paper.router)
    app.include_router(routes_adaptive.router)
    app.include_router(routes_dashboard.router)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = job_manager.get(job_id)
        return job or {"id": job_id, "status": "inconnu"}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await hub.handle(ws)

    return app


app = create_app()
