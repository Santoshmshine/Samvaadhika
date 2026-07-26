"""
Samvaadhika - Background Job Worker
SQLite-backed job queue processed by a thread pool in the same process.
No Redis, no Celery — just threads + SQLite, as per the "keep it simple" brief.
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app.config import WORKER_THREADS, OUTPUTS_DIR, UPLOADS_DIR, CACHE_DIR
from app.database import SessionLocal
from app.models import Job

logger = logging.getLogger("samvaadhika.worker")

_executor: ThreadPoolExecutor = None
_running = False
_poll_thread: threading.Thread = None


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------

def start_worker():
    """Start the background worker pool. Called once at app startup."""
    global _executor, _running, _poll_thread
    _executor = ThreadPoolExecutor(max_workers=WORKER_THREADS, thread_name_prefix="samvaadhika-worker")
    _running = True
    _poll_thread = threading.Thread(target=_poll_loop, daemon=True, name="job-poller")
    _poll_thread.start()
    logger.info(f"Worker started with {WORKER_THREADS} threads.")


def stop_worker():
    """Graceful shutdown — wait for in-flight jobs to finish."""
    global _running
    _running = False
    if _executor:
        _executor.shutdown(wait=True)
    logger.info("Worker stopped.")


def _poll_loop():
    """Poll the DB every 2 seconds for queued jobs and dispatch them."""
    while _running:
        try:
            _dispatch_queued_jobs()
        except Exception as e:
            logger.error(f"Poll loop error: {e}")
        time.sleep(2)


def _dispatch_queued_jobs():
    db = SessionLocal()
    try:
        queued = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at)
            .limit(WORKER_THREADS)
            .all()
        )
        for job in queued:
            job.status = "processing"
            job.started_at = datetime.utcnow()
            db.commit()
            _executor.submit(_process_job, job.id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job processor
# ---------------------------------------------------------------------------

def _process_job(job_id: str):
    """Run the full pipeline for a single job. Updates DB on completion/failure."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        logger.info(f"Processing job {job_id[:8]} type={job.job_type}")

        if job.job_type == "text":
            _process_text_job(job, db)
        elif job.job_type == "audio":
            _process_audio_job(job, db)
        elif job.job_type == "video":
            _process_video_job(job, db)
        elif job.job_type == "document":
            _process_document_job(job, db)
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Job {job_id[:8]} completed.")

    except Exception as e:
        logger.error(f"Job {job_id[:8]} failed: {e}", exc_info=True)
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Per-type processors
# ---------------------------------------------------------------------------

def _process_text_job(job: Job, db):
    from app.pipeline import translate_text, detect_language, apply_glossary

    text = job.input_text or ""
    src = job.source_language or detect_language(text)
    job.source_language = src
    db.commit()

    translated, confidence = translate_text(text, src, job.target_language)
    translated = apply_glossary(translated, src, job.target_language, db)

    job.output_text = translated
    job.confidence_score = confidence
    job.needs_review = confidence < 0.7
    job.progress = 100


def _process_audio_job(job: Job, db):
    from app.pipeline import (
        normalize_audio, transcribe_audio, translate_text,
        apply_glossary, synthesize_speech, generate_subtitles,
    )

    input_path = Path(job.input_path)
    job_out_dir = OUTPUTS_DIR / job.id
    job_out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Normalize audio
    wav_path = job_out_dir / "input_normalized.wav"
    normalize_audio(input_path, wav_path)
    job.progress = 20
    db.commit()

    # Step 2: ASR
    segments, detected_lang = transcribe_audio(wav_path, job.source_language)
    job.source_language = job.source_language or detected_lang
    job.progress = 50
    db.commit()

    # Step 3: Translate each segment
    translated_segments = []
    for seg in segments:
        t_text, conf = translate_text(seg["text"], job.source_language, job.target_language)
        t_text = apply_glossary(t_text, job.source_language, job.target_language, db)
        translated_segments.append({"start": seg["start"], "end": seg["end"], "text": t_text})
    job.progress = 70
    db.commit()

    # Step 4: TTS
    tts_path = job_out_dir / f"translated_audio.wav"
    full_translated = " ".join(s["text"] for s in translated_segments)
    synthesize_speech(full_translated, job.target_language, tts_path)
    job.audio_output_path = str(tts_path)
    job.output_text = full_translated
    job.progress = 85
    db.commit()

    # Step 5: Subtitles
    srt_path = job_out_dir / "subtitles.srt"
    generate_subtitles(segments, translated_segments, srt_path)
    job.subtitle_path = str(srt_path)
    job.progress = 100


def _process_video_job(job: Job, db):
    from app.pipeline import extract_audio_from_video
    import tempfile

    input_path = Path(job.input_path)
    job_out_dir = OUTPUTS_DIR / job.id
    job_out_dir.mkdir(parents=True, exist_ok=True)

    # Extract audio
    audio_path = job_out_dir / "extracted_audio.wav"
    extract_audio_from_video(input_path, audio_path)
    job.progress = 20
    db.commit()

    # Reuse audio pipeline
    audio_job = Job(
        id=job.id,
        job_type="audio",
        source_language=job.source_language,
        target_language=job.target_language,
        input_path=str(audio_path),
        owner_id=job.owner_id,
    )
    _process_audio_job(audio_job, db)

    # Copy results back
    job.output_text = audio_job.output_text
    job.audio_output_path = audio_job.audio_output_path
    job.subtitle_path = audio_job.subtitle_path
    job.source_language = audio_job.source_language
    job.progress = 100


def _process_document_job(job: Job, db):
    from app.pipeline import translate_docx, translate_pptx, translate_pdf

    input_path = Path(job.input_path)
    job_out_dir = OUTPUTS_DIR / job.id
    job_out_dir.mkdir(parents=True, exist_ok=True)

    ext = input_path.suffix.lower()
    src = job.source_language or "en"

    if ext == ".docx":
        out_path = job_out_dir / f"translated_{input_path.name}"
        translate_docx(input_path, out_path, src, job.target_language, db)
        job.output_path = str(out_path)
    elif ext == ".pptx":
        out_path = job_out_dir / f"translated_{input_path.name}"
        translate_pptx(input_path, out_path, src, job.target_language, db)
        job.output_path = str(out_path)
    elif ext == ".pdf":
        out_path = job_out_dir / f"translated_{input_path.stem}.txt"
        translate_pdf(input_path, out_path, src, job.target_language, db)
        job.output_path = str(out_path)
        job.review_notes = "PDF translated to plain text — layout not preserved."
    else:
        raise ValueError(f"Unsupported document type: {ext}")

    job.progress = 100
