"""
Samvaadhika - Translation routes
Text translation (instant) and file upload for async processing.
"""
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import (
    ALLOWED_AUDIO_EXTENSIONS, ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS, MAX_AUDIO_SIZE_MB, MAX_DOCUMENT_SIZE_MB,
    MAX_TEXT_LENGTH, MAX_VIDEO_SIZE_MB, SUPPORTED_LANGUAGES,
    TEMPLATES_DIR, UPLOADS_DIR,
)
from app.database import get_db
from app.models import AuditLog, Job, User
from app.pipeline import detect_language, sha256_file, sha256_text, translate_text

router = APIRouter(tags=["translate"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Text translation (synchronous — must feel instant)
# ---------------------------------------------------------------------------

@router.get("/translate", response_class=HTMLResponse)
async def translate_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse(
        "translate.html",
        {"request": request, "user": user, "languages": SUPPORTED_LANGUAGES},
    )


@router.post("/translate/text")
async def translate_text_api(
    request: Request,
    text: str = Form(...),
    source_language: str = Form("auto"),
    target_language: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(400, f"Text exceeds {MAX_TEXT_LENGTH} character limit.")
    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported target language.")

    # Auto-detect source language
    src = source_language if source_language != "auto" else detect_language(text)

    # Check cache — same text + same language pair
    content_hash = sha256_text(f"{src}:{target_language}:{text}")
    cached = db.query(Job).filter(
        Job.input_hash == content_hash,
        Job.status == "completed",
        Job.job_type == "text",
        Job.confidence_score >= 0.7,
    ).first()

    if cached:
        result_text = cached.output_text
        from_cache = True
    else:
        result_text, confidence = translate_text(text, src, target_language)
        from_cache = False

        # Persist as a completed job for audit + reuse
        job = Job(
            owner_id=user.id,
            job_type="text",
            source_language=src,
            target_language=target_language,
            input_text=text,
            input_hash=content_hash,
            output_text=result_text,
            confidence_score=confidence,
            needs_review=confidence < 0.7,
            status="completed",
            progress=100,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(job)

    log = AuditLog(
        user_id=user.id,
        action="translate_text",
        detail=f"{src}→{target_language}, {len(text)} chars",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()

    return JSONResponse({
        "translated_text": result_text,
        "source_language": src,
        "source_language_name": SUPPORTED_LANGUAGES.get(src, src),
        "from_cache": from_cache,
    })


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "user": user, "languages": SUPPORTED_LANGUAGES},
    )


@router.post("/upload/file")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    source_language: str = Form("auto"),
    target_language: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported target language.")

    ext = Path(file.filename).suffix.lower()
    all_allowed = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS
    if ext not in all_allowed:
        raise HTTPException(400, f"File type '{ext}' not supported.")

    # Determine job type and size limit
    if ext in ALLOWED_AUDIO_EXTENSIONS:
        job_type = "audio"
        max_mb = MAX_AUDIO_SIZE_MB
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        job_type = "video"
        max_mb = MAX_VIDEO_SIZE_MB
    else:
        job_type = "document"
        max_mb = MAX_DOCUMENT_SIZE_MB

    # For large audio/video files disable server-side auto-detect: require explicit source language
    if job_type in ("audio", "video") and source_language == "auto":
        raise HTTPException(400, "Please select the source language for audio/video uploads (auto-detect disabled).")

    # Save upload
    upload_path = UPLOADS_DIR / f"{user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    content = await file.read()

    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_mb:
        raise HTTPException(400, f"File size {size_mb:.1f} MB exceeds {max_mb} MB limit.")

    upload_path.write_bytes(content)

    # Hash for dedup
    file_hash = sha256_file(upload_path)
    cached = db.query(Job).filter(
        Job.input_hash == file_hash,
        Job.target_language == target_language,
        Job.status == "completed",
    ).first()

    if cached:
        log = AuditLog(
            user_id=user.id,
            action="upload_file_cache_hit",
            detail=f"{file.filename} → reused job {cached.id[:8]}",
            ip_address=request.client.host,
        )
        db.add(log)
        db.commit()
        return JSONResponse({"job_id": cached.id, "from_cache": True})

    # Detect source language from filename/metadata if auto
    src = source_language if source_language != "auto" else None

    job = Job(
        owner_id=user.id,
        job_type=job_type,
        source_language=src,
        target_language=target_language,
        input_filename=file.filename,
        input_path=str(upload_path),
        input_hash=file_hash,
        status="queued",
        progress=0,
    )
    db.add(job)

    log = AuditLog(
        user_id=user.id,
        action="upload_file",
        detail=f"{file.filename} ({job_type}, {size_mb:.1f} MB) → {target_language}",
        ip_address=request.client.host,
    )
    db.add(log)
    db.commit()

    return JSONResponse({"job_id": job.id, "from_cache": False})
