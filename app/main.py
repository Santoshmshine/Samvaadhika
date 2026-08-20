"""
Samvaadhika — Offline Multilingual Translation Platform for BAIF
Single FastAPI process: web UI + API + background worker, all in one.
Run with:  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    APP_NAME, APP_TAGLINE, APP_VERSION,
    STATIC_DIR, TEMPLATES_DIR, SUPPORTED_LANGUAGES,
)
from app.database import init_db
from app.worker import start_worker, stop_worker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("samvaadhika")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    init_db()
    start_worker()
    yield
    stop_worker()
    logger.info(f"{APP_NAME} shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    description=APP_TAGLINE,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
from app.routes.auth import router as auth_router
from app.routes.translate import router as translate_router
from app.routes.jobs import router as jobs_router
from app.routes.admin import router as admin_router

app.include_router(auth_router)
app.include_router(translate_router)
app.include_router(jobs_router)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect root to dashboard (or login if not authenticated)."""
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/auth/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    from app.auth import get_optional_user
    from app.database import SessionLocal
    from app.models import Job

    db = SessionLocal()
    try:
        user = get_optional_user(request, db)
        if not user:
            return RedirectResponse("/auth/login", status_code=302)

        # Recent jobs for this user
        recent_jobs = (
            db.query(Job)
            .filter(Job.owner_id == user.id)
            .order_by(Job.created_at.desc())
            .limit(5)
            .all()
        )
        # Stats
        stats = {
            "total": db.query(Job).filter(Job.owner_id == user.id).count(),
            "completed": db.query(Job).filter(Job.owner_id == user.id, Job.status == "completed").count(),
            "queued": db.query(Job).filter(Job.owner_id == user.id, Job.status.in_(["queued", "processing"])).count(),
            "failed": db.query(Job).filter(Job.owner_id == user.id, Job.status == "failed").count(),
        }
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "recent_jobs": recent_jobs,
                "stats": stats,
                "languages": SUPPORTED_LANGUAGES,
            },
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check (for monitoring / Windows Service watchdog)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}
