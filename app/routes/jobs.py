"""
Samvaadhika - Job status and download routes
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import SUPPORTED_LANGUAGES, TEMPLATES_DIR
from app.database import get_db
from app.models import Job, User

router = APIRouter(tags=["jobs"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    jobs = (
        db.query(Job)
        .filter(Job.owner_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "jobs.html",
        {"request": request, "user": user, "jobs": jobs, "languages": SUPPORTED_LANGUAGES},
    )


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.owner_id != user.id and user.role != "admin":
        raise HTTPException(403, "Access denied")

    return JSONResponse({
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "job_type": job.job_type,
        "source_language": job.source_language,
        "target_language": job.target_language,
        "target_language_name": SUPPORTED_LANGUAGES.get(job.target_language, job.target_language),
        "input_filename": job.input_filename,
        "output_text": job.output_text if job.status == "completed" else None,
        "has_output_file": bool(job.output_path and Path(job.output_path).exists()),
        "has_audio": bool(job.audio_output_path and Path(job.audio_output_path).exists()),
        "has_subtitles": bool(job.subtitle_path and Path(job.subtitle_path).exists()),
        "needs_review": job.needs_review,
        "confidence_score": job.confidence_score,
        "review_notes": job.review_notes,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    })


@router.get("/jobs/{job_id}/download")
async def download_output(job_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.owner_id != user.id and user.role != "admin":
        raise HTTPException(403, "Access denied")
    if job.status != "completed":
        raise HTTPException(400, "Job not yet completed")
    if not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(404, "Output file not found")

    return FileResponse(
        path=job.output_path,
        filename=Path(job.output_path).name,
        media_type="application/octet-stream",
    )


@router.get("/jobs/{job_id}/download/audio")
async def download_audio(job_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.owner_id != user.id and user.role != "admin"):
        raise HTTPException(403, "Access denied")
    if not job.audio_output_path or not Path(job.audio_output_path).exists():
        raise HTTPException(404, "Audio output not found")
    return FileResponse(path=job.audio_output_path, filename="translated_audio.wav", media_type="audio/wav")


@router.get("/jobs/{job_id}/download/subtitles")
async def download_subtitles(job_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or (job.owner_id != user.id and user.role != "admin"):
        raise HTTPException(403, "Access denied")
    if not job.subtitle_path or not Path(job.subtitle_path).exists():
        raise HTTPException(404, "Subtitle file not found")
    return FileResponse(path=job.subtitle_path, filename="subtitles.srt", media_type="text/plain")


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.owner_id != user.id and user.role != "admin":
        raise HTTPException(403, "Access denied")
    db.delete(job)
    db.commit()
    return JSONResponse({"message": "Job deleted"})
