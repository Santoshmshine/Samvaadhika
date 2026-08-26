"""
Samvaadhika - Admin routes
User approval, glossary management, audit log, system stats.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_password_hash
from app.config import SUPPORTED_LANGUAGES, TEMPLATES_DIR
from app.database import get_db
from app.models import AuditLog, GlossaryEntry, Job, User

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def require_admin(request: Request, db: Session) -> User:
    admin = get_current_user(request, db)
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return admin


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)

    total_users = db.query(User).count()
    pending_users = db.query(User).filter(User.is_approved == False, User.role != "admin").count()
    total_jobs = db.query(Job).count()
    jobs_by_status = {
        "queued": db.query(Job).filter(Job.status == "queued").count(),
        "processing": db.query(Job).filter(Job.status == "processing").count(),
        "completed": db.query(Job).filter(Job.status == "completed").count(),
        "failed": db.query(Job).filter(Job.status == "failed").count(),
    }
    jobs_by_language = {
        language: db.query(Job).filter(Job.target_language == language).count()
        for language in SUPPORTED_LANGUAGES
    }
    jobs_by_type = {
        job_type: db.query(Job).filter(Job.job_type == job_type).count()
        for job_type in ("text", "document", "audio", "video")
    }
    translations_by_user = (
        db.query(User.username, func.count(Job.id))
        .join(Job, Job.owner_id == User.id)
        .group_by(User.id, User.username)
        .order_by(func.count(Job.id).desc())
        .limit(10)
        .all()
    )
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
            "jobs_by_language": jobs_by_language,
            "jobs_by_type": jobs_by_type,
            "translations_by_user": translations_by_user,
            "recent_logs": recent_logs,
            "languages": SUPPORTED_LANGUAGES,
        },
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "user": admin, "users": users},
    )


@router.post("/users/create")
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    role: str = Form("user"),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    username = username.strip()
    email = email.strip().lower()
    full_name = full_name.strip()
    if role not in ("user", "admin"):
        raise HTTPException(400, "Invalid role")
    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.query(User).filter((User.username == username) | (User.email == email)).first():
        raise HTTPException(409, "Username or email already registered")

    target = User(
        username=username,
        email=email,
        full_name=full_name or username,
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_approved=True,
    )
    db.add(target)
    db.add(AuditLog(
        user_id=admin.id,
        action="create_user",
        detail=f"Created {role}: {username}",
        ip_address=request.client.host,
    ))
    db.commit()
    return JSONResponse({"message": f"User {username} created and approved."})


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
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
    admin = require_admin(request, db)
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "admin_jobs.html",
        {"request": request, "user": admin, "jobs": jobs, "languages": SUPPORTED_LANGUAGES},
    )


@router.post("/jobs/{job_id}/requeue")
async def requeue_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
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
