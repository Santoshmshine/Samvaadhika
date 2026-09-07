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
    # Debug: log ASR segments summary
    try:
        if segments:
            logger.info(f"Job {job.id[:8]} ASR produced {len(segments)} segments. First: '{segments[0]['text'][:200]}'")
        else:
            logger.info(f"Job {job.id[:8]} ASR produced no segments.")
    except Exception:
        pass
    job.progress = 50
    db.commit()

    # Prepare debug dir for ASR raw dumps
    debug_asr_dir = job_out_dir / "debug_asr"
    debug_asr_dir.mkdir(parents=True, exist_ok=True)

    # Step 3: Translate each segment
    translated_segments = []
    from app.pipeline import detect_and_fix_transliterated_segment, fix_mojibake
    report_rows = []
    for idx, seg in enumerate(segments, start=1):
        # write per-segment debug files capturing the raw text repr and hex
        try:
            txt_path = debug_asr_dir / f"segment_{idx:04d}_raw.txt"
            with txt_path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
                fh.write(seg.get("orig_repr", seg.get("text", "")))
            hex_path = debug_asr_dir / f"segment_{idx:04d}_hex_utf8.txt"
            with hex_path.open("w", encoding="utf-8") as fh:
                fh.write(seg.get("orig_hex_utf8", ""))
        except Exception:
            pass

        
        # Attempt to detect and fix Latin-script transliteration (e.g., 'vityanigi riva')
        fixed_text, fixed_lang = detect_and_fix_transliterated_segment(seg["text"], asr_hint=detected_lang)
        try:
            if fixed_text != seg["text"]:
                logger.info(
                    f"Job {job.id[:8]} segment fixed: '{seg['text'][:200]}' -> '{fixed_text[:200]}'"
                )
            else:
                logger.debug(f"Job {job.id[:8]} segment unchanged: '{seg['text'][:200]}'")
        except Exception:
            pass

        if fixed_lang in ("hi", "mr") and job.source_language is None:
            logger.info(f"Job {job.id[:8]} source_language updated: {job.source_language} -> {fixed_lang}")
            job.source_language = fixed_lang
            db.commit()

        t_text, conf = translate_text(fixed_text, job.source_language, job.target_language)
        t_text = apply_glossary(t_text, job.source_language, job.target_language, db)
        translated_segments.append({"start": seg["start"], "end": seg["end"], "text": t_text})
        # record for per-job report
        try:
            orig_raw = seg["text"]
            try:
                orig_clean = fix_mojibake(orig_raw)
            except Exception:
                orig_clean = orig_raw
            report_rows.append({
                "start": seg["start"],
                "end": seg["end"],
                "orig_raw": orig_raw,
                "orig_clean": orig_clean,
                "orig_repr": seg.get("orig_repr", ""),
                "orig_hex_utf8": seg.get("orig_hex_utf8", ""),
                "orig_hex_replace": seg.get("orig_hex_replace", ""),
                "asr_avg_logprob": seg.get("asr_avg_logprob", None),
                "asr_no_speech_prob": seg.get("asr_no_speech_prob", None),
                "fixed": fixed_text,
                "fixed_lang": fixed_lang,
                "translated": t_text,
                "confidence": conf,
            })
        except Exception:
            pass
    job.progress = 70
    db.commit()

    # Write per-job CSV report of segment translations for debugging
    try:
        import csv
        report_path = job_out_dir / "segment_translations.csv"
        with report_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "start", "end", "orig_raw", "orig_clean",
                    "orig_repr", "orig_hex_utf8", "orig_hex_replace",
                    "asr_avg_logprob", "asr_no_speech_prob",
                    "fixed", "fixed_lang", "translated", "confidence",
                ],
            )
            writer.writeheader()
            for r in report_rows:
                writer.writerow(r)
        logger.info(f"Wrote segment translation report: {report_path}")
    except Exception as e:
        logger.debug(f"Failed to write segment report: {e}")

    # Step 4: TTS — preserve input filename for the generated audio
    input_base = Path(job.input_path).stem
    tts_path = job_out_dir / f"translated_{input_base}.wav"
    full_translated = " ".join(s["text"] for s in translated_segments)
    try:
        from app.pipeline import transliterate_text_if_needed
        full_translated = transliterate_text_if_needed(full_translated, job.target_language)
    except Exception:
        pass
    logger.info(f"Job {job.id[:8]} full translated text length: {len(full_translated)} chars")
    logger.debug(f"Job {job.id[:8]} full translated text preview: '{full_translated[:400]}'")
    synthesize_speech(full_translated, job.target_language, tts_path)
    job.audio_output_path = str(tts_path)
    job.output_text = full_translated
    job.progress = 85
    db.commit()

    # Step 5: Subtitles — preserve input filename for subtitle file
    srt_path = job_out_dir / f"translated_{input_base}.srt"
    generate_subtitles(segments, translated_segments, srt_path)
    job.subtitle_path = str(srt_path)
    job.progress = 100


def _process_video_job(job: Job, db):
    from app.pipeline import (
        extract_audio_from_video, normalize_audio, transcribe_audio,
        translate_text, apply_glossary, synthesize_speech, generate_subtitles,
    )

    input_path = Path(job.input_path)
    job_out_dir = OUTPUTS_DIR / job.id
    job_out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract audio from video
    audio_path = job_out_dir / "extracted_audio.wav"
    extract_audio_from_video(input_path, audio_path)
    job.progress = 10
    db.commit()

    # Step 2: Normalize audio
    wav_path = job_out_dir / "input_normalized.wav"
    normalize_audio(audio_path, wav_path)
    job.progress = 20
    db.commit()

    # Step 3: ASR (speech-to-text)
    segments, detected_lang = transcribe_audio(wav_path, job.source_language)
    job.source_language = job.source_language or detected_lang
    job.progress = 50
    db.commit()

    # Prepare debug dir for ASR raw dumps
    debug_asr_dir = job_out_dir / "debug_asr"
    debug_asr_dir.mkdir(parents=True, exist_ok=True)

    # Step 4: Translate each segment
    translated_segments = []
    from app.pipeline import detect_and_fix_transliterated_segment, fix_mojibake
    report_rows = []
    for idx, seg in enumerate(segments, start=1):
        try:
            txt_path = debug_asr_dir / f"segment_{idx:04d}_raw.txt"
            with txt_path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
                fh.write(seg.get("orig_repr", seg.get("text", "")))
            hex_path = debug_asr_dir / f"segment_{idx:04d}_hex_utf8.txt"
            with hex_path.open("w", encoding="utf-8") as fh:
                fh.write(seg.get("orig_hex_utf8", ""))
        except Exception:
            pass

        fixed_text, fixed_lang = detect_and_fix_transliterated_segment(seg["text"], asr_hint=detected_lang)
        try:
            if fixed_text != seg["text"]:
                logger.info(
                    f"Job {job.id[:8]} segment fixed: '{seg['text'][:200]}' -> '{fixed_text[:200]}'"
                )
            else:
                logger.debug(f"Job {job.id[:8]} segment unchanged: '{seg['text'][:200]}'")
        except Exception:
            pass
        if fixed_lang in ("hi", "mr") and (job.source_language is None or job.source_language == "en"):
            logger.info(f"Job {job.id[:8]} source_language updated: {job.source_language} -> {fixed_lang}")
            job.source_language = fixed_lang
            db.commit()

        t_text, conf = translate_text(fixed_text, job.source_language, job.target_language)
        t_text = apply_glossary(t_text, job.source_language, job.target_language, db)
        translated_segments.append({"start": seg["start"], "end": seg["end"], "text": t_text})
        try:
            orig_raw = seg["text"]
            try:
                orig_clean = fix_mojibake(orig_raw)
            except Exception:
                orig_clean = orig_raw
            report_rows.append({
                "start": seg["start"],
                "end": seg["end"],
                "orig_raw": orig_raw,
                "orig_clean": orig_clean,
                "orig_repr": seg.get("orig_repr", ""),
                "orig_hex_utf8": seg.get("orig_hex_utf8", ""),
                "orig_hex_replace": seg.get("orig_hex_replace", ""),
                "asr_avg_logprob": seg.get("asr_avg_logprob", None),
                "asr_no_speech_prob": seg.get("asr_no_speech_prob", None),
                "fixed": fixed_text,
                "fixed_lang": fixed_lang,
                "translated": t_text,
                "confidence": conf,
            })
        except Exception:
            pass
    job.progress = 70
    db.commit()

    # Write per-job CSV report of segment translations for debugging
    try:
        import csv
        report_path = job_out_dir / "segment_translations.csv"
        with report_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "start", "end", "orig_raw", "orig_clean",
                    "orig_repr", "orig_hex_utf8", "orig_hex_replace",
                    "asr_avg_logprob", "asr_no_speech_prob",
                    "fixed", "fixed_lang", "translated", "confidence",
                ],
            )
            writer.writeheader()
            for r in report_rows:
                writer.writerow(r)
        logger.info(f"Wrote segment translation report: {report_path}")
    except Exception as e:
        logger.debug(f"Failed to write segment report: {e}")

    full_translated = " ".join(s["text"] for s in translated_segments)
    try:
        from app.pipeline import transliterate_text_if_needed
        full_translated = transliterate_text_if_needed(full_translated, job.target_language)
    except Exception:
        pass
    job.output_text = full_translated

    # Write subtitles before TTS so a slow or failed speech model does not
    # prevent the translated SRT from being delivered.
    input_base = Path(job.input_path).stem
    srt_path = job_out_dir / f"translated_{input_base}.srt"
    generate_subtitles(segments, translated_segments, srt_path)
    if srt_path.exists():
        job.subtitle_path = str(srt_path)
    job.progress = 85
    db.commit()

    # Step 5: TTS (text-to-speech) — preserve input filename
    tts_path = job_out_dir / f"translated_{input_base}.wav"
    tts_ok = synthesize_speech(full_translated, job.target_language, tts_path)
    if tts_ok and tts_path.exists():
        job.audio_output_path = str(tts_path)
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
        # Preserve the original filename (including spaces and extension)
        out_path = job_out_dir / f"translated_{input_path.name}"
        _, notes = translate_pdf(input_path, out_path, src, job.target_language, db)
        job.output_path = str(out_path)
        job.review_notes = notes
    else:
        raise ValueError(f"Unsupported document type: {ext}")

    job.progress = 100
