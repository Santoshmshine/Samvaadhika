"""
Samvaadhika - Admin routes
User approval, glossary management, audit log, system stats.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_admin, get_password_hash
from app.config import SUPPORTED_LANGUAGES, TEMPLATES_DIR
from app.database import get_db
from app.models import AuditLog, GlossaryEntry, Job, User

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)

    total_users = db.query(User).count()
    pending_users = db.query(User).filter(User.is_approved == False, User.role != "admin").count()
    total_jobs = db.query(Job).count()
    jobs_by_status = {
        "queued": db.query(Job).filter(Job.status == "queued").count(),
        "processing": db.query(Job).filter(Job.status == "processing").count(),
        "completed": db.query(Job).filter(Job.status == "completed").count(),
        "failed": db.query(Job).filter(Job.status == "failed").count(),
    }
    recent_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": admin,
            "total_users": total_users,
            "pending_users": pending_users,
            "total_jobs": total_jobs,
            "jobs_by_status": jobs_by_status,
            "recent_logs": recent_logs,
            "languages": SUPPORTED_LANGUAGES,
        },
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "user": admin, "users": users},
    )


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    target.is_approved = True
    log = AuditLog(
        user_id=admin.id,
        action="approve_user",
        detail=f"Approved: {target.username}",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()
    return JSONResponse({"message": f"User {target.username} approved."})


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == admin.id:
        raise HTTPException(400, "Cannot deactivate yourself")
    target.is_active = False
    log = AuditLog(
        user_id=admin.id,
        action="deactivate_user",
        detail=f"Deactivated: {target.username}",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()
    return JSONResponse({"message": f"User {target.username} deactivated."})


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = get_current_admin(request, db)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    target.hashed_password = get_password_hash(new_password)
    log = AuditLog(
        user_id=admin.id,
        action="reset_password",
        detail=f"Reset password for: {target.username}",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()
    return JSONResponse({"message": "Password reset successfully."})


# ---------------------------------------------------------------------------
# Glossary management
# ---------------------------------------------------------------------------

@router.get("/glossary", response_class=HTMLResponse)
async def glossary_page(request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    entries = db.query(GlossaryEntry).order_by(GlossaryEntry.source_term).all()
    return templates.TemplateResponse(
        "admin_glossary.html",
        {
            "request": request,
            "user": admin,
            "entries": entries,
            "languages": SUPPORTED_LANGUAGES,
        },
    )


@router.post("/glossary/add")
async def add_glossary_entry(
    request: Request,
    source_term: str = Form(...),
    source_language: str = Form(...),
    target_term: str = Form(...),
    target_language: str = Form(...),
    domain: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = get_current_admin(request, db)
    entry = GlossaryEntry(
        source_term=source_term.strip(),
        source_language=source_language,
        target_term=target_term.strip(),
        target_language=target_language,
        domain=domain.strip() or None,
        created_by=admin.id,
    )
    db.add(entry)
    log = AuditLog(
        user_id=admin.id,
        action="add_glossary",
        detail=f"{source_term} ({source_language}) → {target_term} ({target_language})",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()
    return JSONResponse({"message": "Glossary entry added.", "id": entry.id})


@router.delete("/glossary/{entry_id}")
async def delete_glossary_entry(entry_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    entry = db.query(GlossaryEntry).filter(GlossaryEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    db.delete(entry)
    log = AuditLog(
        user_id=admin.id,
        action="delete_glossary",
        detail=f"Deleted: {entry.source_term}",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()
    return JSONResponse({"message": "Entry deleted."})


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/audit", response_class=HTMLResponse)
async def audit_log(request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "admin_audit.html",
        {"request": request, "user": admin, "logs": logs},
    )


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------

@router.get("/jobs", response_class=HTMLResponse)
async def all_jobs(request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "admin_jobs.html",
        {"request": request, "user": admin, "jobs": jobs, "languages": SUPPORTED_LANGUAGES},
    )


@router.post("/jobs/{job_id}/requeue")
async def requeue_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    job.status = "queued"
    job.progress = 0
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    log = AuditLog(
        user_id=admin.id,
        action="requeue_job",
        detail=f"Requeued job {job_id[:8]}",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()
    return JSONResponse({"message": "Job requeued."})
