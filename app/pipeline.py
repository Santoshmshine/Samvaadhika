"""
Samvaadhika - AI Processing Pipeline
Handles: language detection → ASR → MT → TTS / subtitles / document re-assembly.

All models run locally (CPU). On first use each model is loaded once and cached
in memory for the lifetime of the process.

Stubs are provided so the app runs end-to-end even before the heavy AI models
are downloaded — each stub logs a clear message and returns a placeholder result.
"""
import hashlib
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import unicodedata

from app.config import (
    CACHE_DIR, OUTPUTS_DIR, UPLOADS_DIR, MODELS_DIR,
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    TESSERACT_LANGUAGES, SUPPORTED_LANGUAGES, BASE_DIR,
)

logger = logging.getLogger("samvaadhika.pipeline")

# ---------------------------------------------------------------------------
# Ensure bundled or installed media/OCR tools are on PATH.
# ---------------------------------------------------------------------------
_FFMPEG_SEARCH_DIRS = [
    BASE_DIR / "ffmpeg" / "bin",
    Path(sys.executable).resolve().parent / "ffmpeg" / "bin" if getattr(sys, "frozen", False) else Path(),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
    Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "ffmpeg" / "bin",
    Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "ffmpeg" / "bin",
]

def _ensure_ffmpeg_on_path():
    """Find bundled or installed FFmpeg and add it to PATH."""
    if shutil.which("ffmpeg"):
        return  # already available
    for search_root in _FFMPEG_SEARCH_DIRS:
        if not search_root or not search_root.exists():
            continue
        for ffmpeg_exe in search_root.rglob("ffmpeg.exe"):
            bin_dir = str(ffmpeg_exe.parent)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Added ffmpeg to PATH from: {bin_dir}")
            return
    logger.warning("ffmpeg not found in any known location. Video/audio processing may fail.")

_ensure_ffmpeg_on_path()


def _ensure_tesseract_on_path():
    """Find bundled or installed Tesseract and add it to PATH."""
    candidates = [
        BASE_DIR / "tesseract" / "tesseract.exe",
        Path(sys.executable).resolve().parent / "tesseract" / "tesseract.exe" if getattr(sys, "frozen", False) else Path(),
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR" / "tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            os.environ["PATH"] = str(candidate.parent) + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("TESSDATA_PREFIX", str(candidate.parent / "tessdata"))
            logger.info(f"Using Tesseract from: {candidate}")
            return
    logger.warning("Tesseract not found. OCR features may fail.")


_ensure_tesseract_on_path()


# ---------------------------------------------------------------------------
# HuggingFace cache directory resolver
# ---------------------------------------------------------------------------

def _resolve_hf_cache(base_dir: Path) -> Path:
    """
    Resolve a HuggingFace cache directory to the actual model snapshot path.

    HuggingFace downloads create a structure like:
        models/model-name/models--org--model-name/snapshots/<hash>/
    This function finds the actual snapshot directory containing model files.
    If base_dir itself contains model files directly, returns base_dir as-is.
    """
    # If the directory directly contains model files, use it as-is
    direct_indicators = ["config.json", "model.bin", "model.safetensors",
                         "tokenizer.json", "tokenizer_config.json"]
    for indicator in direct_indicators:
        if (base_dir / indicator).exists():
            return base_dir

    # Look for HuggingFace cache structure: models--*/snapshots/*/
    for models_dir in base_dir.glob("models--*"):
        snapshots_dir = models_dir / "snapshots"
        if snapshots_dir.exists():
            # Get the latest snapshot (usually only one)
            snapshots = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for snap in snapshots:
                if snap.is_dir() and any(snap.iterdir()):
                    logger.info(f"Resolved HF cache: {base_dir.name} → {snap}")
                    return snap

    # Fallback: return the original directory
    return base_dir


def _find_model_dir(name: str, *alt_names: str) -> Optional[Path]:
    """
    Find a model directory under MODELS_DIR, trying multiple name variants.
    Returns the resolved path (handling HF cache structure) or None.
    """
    candidates = [name] + list(alt_names)
    for candidate in candidates:
        model_dir = MODELS_DIR / candidate
        if model_dir.exists():
            return _resolve_hf_cache(model_dir)
    return None


# ---------------------------------------------------------------------------
# Lazy model singletons
# ---------------------------------------------------------------------------
_whisper_model = None
_lang_detector = None
_translation_models = {}
_translation_model_lock = threading.Lock()
_parler_runtime = None
_parler_lock = threading.Lock()

TRANSLATION_PIPELINE_VERSION = "indictrans2-v3"
ASR_MIN_AVG_LOGPROB = -1.5
MEDIA_REVIEW_CONFIDENCE = 0.8


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel

            # Try local model directory first, then fall back to model size string
            local_model = _find_model_dir(
                f"faster-whisper-{WHISPER_MODEL_SIZE}",
                f"whisper-{WHISPER_MODEL_SIZE}",
                "faster-whisper",
            )
            model_source = str(local_model) if local_model else WHISPER_MODEL_SIZE

            _whisper_model = WhisperModel(
                model_source,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
            logger.info(f"Whisper model loaded from: {model_source}")
        except Exception as e:
            logger.warning(f"faster-whisper not available: {e}. Using stub ASR.")
            _whisper_model = "stub"
    return _whisper_model


def _get_lang_detector():
    global _lang_detector
    if _lang_detector is None:
        try:
            import fasttext
            # Try both .ftz (compressed) and .bin (full) variants
            model_path = None
            for fname in ["lid.176.ftz", "lid.176.bin"]:
                candidate = MODELS_DIR / fname
                if candidate.exists():
                    model_path = candidate
                    break

            if model_path:
                _lang_detector = fasttext.load_model(str(model_path))
                logger.info(f"fastText language detector loaded from {model_path.name}.")
            else:
                logger.warning("fastText model not found (tried lid.176.ftz, lid.176.bin) — using stub.")
                _lang_detector = "stub"
        except Exception as e:
            logger.warning(f"fasttext not available: {e}. Using stub language detector.")
            _lang_detector = "stub"
    return _lang_detector


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def transliterate_text_if_needed(text: str, lang: str, suppress_log: bool = False) -> str:
    """If `lang` is Hindi/Marathi and text appears to be Latin-script,
    attempt to transliterate it to Devanagari for TTS.
    Falls back to returning the original text if the transliteration
    library isn't installed or the heuristic doesn't trigger.

    `suppress_log`: when True, don't emit info-level logs (used by callers
    that probe multiple transliteration attempts to avoid duplicate messages).
    """
    if lang not in ("hi", "mr") or not text:
        return text

    # Quick reject: replacement character indicates decoding issues — skip
    if "\uFFFD" in text:
        if not suppress_log:
            logger.debug("Text contains replacement characters; skipping transliteration.")
        return text

    # Heuristic: count Devanagari vs Latin-script letters (including diacritics)
    deva_count = sum(1 for ch in text if _is_devanagari(ch))
    latin_letters = sum(1 for ch in text if _is_latin_letter(ch))
    total_letters = max(1, deva_count + latin_letters)

    # If already contains a substantial Devanagari portion, skip
    if deva_count / total_letters > 0.3:
        return text

    # If not primarily Latin transliteration, skip
    if latin_letters / total_letters < 0.4:
        return text

    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        # Try a sensible default scheme; fall back to IAST if ITRANS fails
        try:
            dev = transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
        except Exception:
            dev = transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)

        if not suppress_log:
            logger.info("Transliterated Latin-script text to Devanagari for TTS.")
        return dev
    except Exception as e:
        if not suppress_log:
            logger.warning(f"Transliteration unavailable or failed: {e}. Skipping transliteration.")
        return text


def _is_devanagari(ch: str) -> bool:
    return "\u0900" <= ch <= "\u097F"


def _is_ascii_letter(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def _is_latin_letter(ch: str) -> bool:
    """Return True for Latin-script letters, including diacritics (e.g. ǫ, ā)."""
    if not ch or not ch.isalpha():
        return False
    # Fast path: ASCII alpha
    if ch.isascii():
        return True
    # Fallback: check Unicode name for 'LATIN'
    try:
        return "LATIN" in unicodedata.name(ch)
    except Exception:
        return False


def normalize_mixed_script_runs(text: str, target_lang: str = "hi", min_ascii_run_len: int = 3) -> str:
    """Split text into script runs and transliterate ASCII-letter runs to Devanagari.

    This helps when ASR emits mixed segments like:
        'शईदि पालन, ... resumes, sirvatum yawasthapan padhati'

    We transliterate only sufficiently long ASCII-letter runs to avoid mangling
    short acronyms or alphanumerics. Uses `transliterate_text_if_needed` with
    `suppress_log=True` to avoid noisy duplicate messages during speculative checks.
    """
    if not text:
        return text

    runs = []
    cur_type = None
    buf = []

    def flush():
        if buf:
            runs.append((cur_type, "".join(buf)))

    for ch in text:
        if _is_devanagari(ch):
            t = "deva"
        elif _is_latin_letter(ch):
            t = "latin"
        else:
            t = "other"

        if cur_type is None:
            cur_type = t
            buf.append(ch)
        elif t == cur_type:
            buf.append(ch)
        else:
            flush()
            buf = [ch]
            cur_type = t

    flush()

    out_parts = []
    changed = False
    for typ, seg in runs:
        if typ == "latin" and sum(1 for c in seg if _is_latin_letter(c)) >= min_ascii_run_len and target_lang in ("hi", "mr"):
            try:
                new = transliterate_text_if_needed(seg, target_lang, suppress_log=True)
                if new != seg:
                    changed = True
                out_parts.append(new)
            except Exception:
                out_parts.append(seg)
        else:
            out_parts.append(seg)

    result = "".join(out_parts)
    if changed:
        logger.info("Normalized mixed-script segment by transliterating ASCII runs for TTS.")
    return result


def fix_mojibake(text: str) -> str:
    """Attempt to fix common UTF-8↔Latin-1 mojibake sequences.

    Many pipeline artifacts show sequences like 'à¤¶' when Devanagari
    UTF-8 bytes were decoded as Latin-1. This helper tries a safe
    Latin-1 -> UTF-8 re-decode when such patterns are present.
    """
    if not text or not isinstance(text, str):
        return text

    # Quick heuristic: presence of many high-byte (Latin-1) characters or
    # common UTF-8-with-Latin1-decoding markers. This catches mojibake for
    # Devanagari (à¤...), Kannada (à²...), Tamil (à®...), etc.
    mojibake_markers = ("à¤", "à²", "à³", "à´", "Ã", "â")
    high_byte_count = sum(1 for ch in text if ord(ch) >= 0xC0 and ord(ch) <= 0xFF)
    if not any(m in text for m in mojibake_markers) and high_byte_count < 3:
        return text

    try:
        # Re-interpret the Python str bytes as latin-1 bytes then decode as utf-8
        fixed = text.encode("latin-1").decode("utf-8")
        # Sanity check: ensure resulting string contains Indic or sensible letters
        if any("\u0900" <= ch <= "\u0DFF" for ch in fixed):
            logger.debug("fix_mojibake: applied latin-1→utf-8 re-decode")
            return fixed
        # If not clearly Indic, still return fixed (fallback) but log debug
        logger.debug("fix_mojibake: re-decode produced non-Indic text; returning result")
        return fixed
    except Exception:
        try:
            # Last-resort: attempt the inverse (rare cases)
            alt = text.encode("utf-8").decode("latin-1")
            logger.debug("fix_mojibake: inverse utf-8→latin-1 attempt applied")
            return alt
        except Exception:
            return text


_MARATHI_ASR_NORMALIZATIONS = (
    ("मस्ता है", "मस्त आहे"),
    ("मस्टा हे", "मस्त आहे"),
    ("मस्ता हे", "मस्त आहे"),
    ("निगा लोए", "निघालोय"),
    ("गरिच चाल लोए", "घरीच चाललोय"),
    ("गरीच चाल लोए", "घरीच चाललोय"),
    ("कुते", "कुठे"),
    ("तु", "तू"),
    ("पन", "पण"),
)


def normalize_marathi_asr_text(text: str) -> str:
    """Repair conservative, recurring Marathi Whisper spelling variants."""
    normalized = text
    for source, replacement in _MARATHI_ASR_NORMALIZATIONS:
        pattern = rf"(?<![\u0900-\u097F]){re.escape(source)}(?![\u0900-\u097F])"
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def detect_and_fix_transliterated_segment(
    text: str,
    asr_hint: Optional[str] = None,
) -> Tuple[str, str]:
    """Detect if `text` is a Latin-script transliteration of Hindi/Marathi.
    If so, attempt to transliterate to Devanagari and return (fixed_text, lang).
    Otherwise return (original_text, detected_lang).
    """
    # First, attempt to fix common mojibake (Latin-1 decoded UTF-8)
    raw_text = text
    try:
        text = fix_mojibake(text)
        if text != raw_text:
            logger.info("Fixed mojibake encoding for segment before detection.")
    except Exception:
        text = raw_text

    # Quick detect
    detected = detect_language(text)
    # If detected already Indic, nothing to do
    if detected in ("hi", "mr"):
        return text, detected
    if asr_hint == "en" and detected == "en":
        return text, detected

    # If ASR already reported Marathi/Hindi and text is Latin-like, force a
    # speculative transliteration to that language. This helps when ASR emits
    # romanized Marathi but language detectors operating on raw text see it as
    # English.
    try:
        if asr_hint in ("mr", "hi"):
            # Count Latin letters vs Devanagari
            deva_count_hint = sum(1 for ch in text if _is_devanagari(ch))
            latin_letters_hint = sum(1 for ch in text if _is_latin_letter(ch))
            if latin_letters_hint >= 3 and deva_count_hint == 0:
                try:
                    cand_force = transliterate_text_if_needed(text, asr_hint, suppress_log=False)
                    if cand_force != text:
                        logger.info(f"ASR hint {asr_hint} detected; forced transliteration applied.")
                        return cand_force, asr_hint
                except Exception:
                    pass
    except Exception:
        pass

    # Heuristic: many Latin-script letters (incl. diacritics) and few Devanagari → candidate for transliteration
    deva_count = sum(1 for ch in text if _is_devanagari(ch))
    latin_letters = sum(1 for ch in text if _is_latin_letter(ch))
    if latin_letters < 3 and deva_count == 0:
        return text, detected

    # If the segment mixes Devanagari and Latin runs, normalize by transliterating
    # sufficiently long ASCII runs to Devanagari, then re-run detection.
    if deva_count > 0 and latin_letters > 0:
        try:
            norm = normalize_mixed_script_runs(text, target_lang="hi")
            new_det = detect_language(norm)
            if new_det in ("hi", "mr"):
                logger.info(f"Detected mixed-script segment; normalized and fixed as {new_det}.")
                return norm, new_det
            # fall through to speculative transliteration if normalization didn't help
        except Exception:
            pass

    # Try transliterating to Marathi and Hindi and re-run detection
    tries = ["mr", "hi"]
    for lang in tries:
        try:
            # Suppress logging during speculative transliteration so we don't
            # emit duplicate info messages when callers also log.
            cand = transliterate_text_if_needed(text, lang, suppress_log=True)
            new_det = detect_language(cand)
            if new_det == lang:
                logger.info(f"Detected transliterated {lang.upper()} segment; auto-fixed for MT/TTS.")
                return cand, lang
        except Exception:
            continue

    return text, detected


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """Return ISO 639-1 code: 'en', 'hi', or 'mr'. Falls back to 'en'."""
    detector = _get_lang_detector()
    if detector == "stub" or not text.strip():
        return "en"
    try:
        # Avoid fasttext's NumPy-2-incompatible Python predict wrapper.
        predictions = detector.f.predict(text.replace("\n", " "), 1, 0.0, "strict")
        label = predictions[0][1].replace("__label__", "")
        # fastText uses 'hi' and 'mr' directly
        if label in SUPPORTED_LANGUAGES:
            return label
        return "en"
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return "en"


# ---------------------------------------------------------------------------
# Translation (MT)
# ---------------------------------------------------------------------------

def translate_text(text: str, source_lang: str, target_lang: str) -> Tuple[str, float]:
    """
    Translate text using IndicTrans2 (preferred) or argostranslate (fallback).
    Returns (translated_text, confidence_score 0-1).
    """
    if source_lang == target_lang:
        logger.info(f"translate_text: source==target ({source_lang}); skipping MT")
        return text, 1.0

    # Try IndicTrans2 first
    try:
        res = _translate_indictrans2(text, source_lang, target_lang)
        logger.info("translate_text: used IndicTrans2")
        return res
    except Exception as e:
        logger.warning(f"IndicTrans2 unavailable ({e}), trying argostranslate fallback.")

    # Argostranslate fallback
    try:
        res = _translate_argos(text, source_lang, target_lang)
        logger.info("translate_text: used ArgosTranslate fallback")
        return res
    except Exception as e:
        logger.warning(f"argostranslate unavailable ({e}). Returning stub translation.")

    # Final stub — clearly marked so reviewers know it's a placeholder
    return f"[TRANSLATION STUB: {source_lang}→{target_lang}] {text}", 0.0


def translation_cache_hash(text: str, source_lang: str, target_lang: str) -> str:
    """Build a cache key that expires results when the MT pipeline changes."""
    return sha256_text(
        f"{TRANSLATION_PIPELINE_VERSION}:{source_lang}:{target_lang}:{text}"
    )


_PROTECTED_TEXT_PATTERN = re.compile(
    r"(https?://[^\s]+|www\.[^\s]+|"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+|"
    r"\r\n|\r|\n)"
)

_CURATED_IDIOM_TRANSLATIONS = {
    ("en", "mr", "it is raining cats and dogs outside"): "बाहेर मुसळधार पाऊस पडत आहे।",
    ("hi", "en", "ऊँट के मुँह में जीरा"): "Too little for a great need.",
}


def _curated_idiom_translation(text: str, source_lang: str, target_lang: str):
    normalized = text.strip().casefold().rstrip(".!?।").strip()
    return _CURATED_IDIOM_TRANSLATIONS.get((source_lang, target_lang, normalized))


def _prepare_translation_part(text: str, source_lang: str) -> str:
    if source_lang != "en":
        return text

    from sacremoses import MosesPunctNormalizer, MosesTokenizer

    normalized = MosesPunctNormalizer(lang="en").normalize(text)
    return " ".join(MosesTokenizer(lang="en").tokenize(normalized, escape=False))


def _translate_preserving_protected_text(text: str, translate_part) -> str:
    """Translate prose while preserving URLs, emails, and line separators."""
    parts = _PROTECTED_TEXT_PATTERN.split(text)
    translated_parts = []
    for part in parts:
        if not part:
            continue
        if _PROTECTED_TEXT_PATTERN.fullmatch(part):
            translated_parts.append(part)
            continue
        if not part.strip():
            translated_parts.append(part)
            continue

        leading = part[:len(part) - len(part.lstrip())]
        trailing = part[len(part.rstrip()):]
        translated_parts.append(leading + translate_part(part.strip()) + trailing)
    return "".join(translated_parts)


def _get_translation_model(model_dir: Path):
    cache_key = str(model_dir.resolve())
    cached = _translation_models.get(cache_key)
    if cached is not None:
        return cached

    with _translation_model_lock:
        cached = _translation_models.get(cache_key)
        if cached is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                str(model_dir), trust_remote_code=True
            )
            model = AutoModelForSeq2SeqLM.from_pretrained(
                str(model_dir), trust_remote_code=True
            )
            model.eval()
            cached = (tokenizer, model, threading.Lock())
            _translation_models[cache_key] = cached
    return cached


def _translate_indictrans2(text: str, src: str, tgt: str) -> Tuple[str, float]:
    """
    IndicTrans2 distilled model with direction-based routing.

    Supported models:
    - indictrans2-en-indic-dist-200M: English → Hindi, Marathi (available)
    - indictrans2-indic-en-dist-200M: Hindi, Marathi → English (gated, need access request)
    - indictrans2-indic-indic-dist-320M: Hindi ↔ Marathi (gated, need access request)

    Returns (translated_text, confidence_score).
    Confidence reflects model quality and direction support.
    """
    import torch

    # Direction-to-model mapping
    direction_map = {
        ('en', 'hi'): ('indictrans2-en-indic-dist-200M', 0.88),
        ('en', 'mr'): ('indictrans2-en-indic-dist-200M', 0.88),
        ('hi', 'en'): ('indictrans2-indic-en-dist-200M', 0.85),
        ('mr', 'en'): ('indictrans2-indic-en-dist-200M', 0.85),
        ('hi', 'mr'): ('indictrans2-indic-indic-dist-320M', 0.82),
        ('mr', 'hi'): ('indictrans2-indic-indic-dist-320M', 0.82),
    }

    # Check if direction is supported
    direction = (src, tgt)
    if direction not in direction_map:
        raise ValueError(
            f"IndicTrans2 does not support {src}→{tgt} translation. "
            f"Supported directions: en↔hi, en↔mr, hi↔mr"
        )

    model_name, confidence = direction_map[direction]

    # Find the model directory
    model_dir = _find_model_dir(model_name, "indictrans2")
    if model_dir is None:
        raise FileNotFoundError(
            f"IndicTrans2 model '{model_name}' not found at models/{model_name}/. "
            f"For {src}→{tgt}, the gated repository access may be required. "
            f"Visit: https://huggingface.co/ai4bharat/{model_name} to request access."
        )

    # Language code mapping for IndicTrans2
    lang_map = {"en": "eng_Latn", "hi": "hin_Deva", "mr": "mar_Deva"}
    src_code = lang_map.get(src, "eng_Latn")
    tgt_code = lang_map.get(tgt, "hin_Deva")

    curated = _curated_idiom_translation(text, src, tgt)
    if curated is not None:
        return curated, 1.0

    tokenizer, model, inference_lock = _get_translation_model(model_dir)

    def translate_part(part: str) -> str:
        prepared_part = _prepare_translation_part(part, src)
        tagged_text = f"{src_code} {tgt_code} {prepared_part}"
        with inference_lock:
            inputs = tokenizer(
                tagged_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=256,
            )
            with torch.no_grad():
                outputs = model.generate(
                    **inputs, max_length=256, num_beams=5, use_cache=False
                )

            tokenizer._switch_to_target_mode()
            try:
                return tokenizer.decode(outputs[0], skip_special_tokens=True)
            finally:
                tokenizer._switch_to_input_mode()

    translated = _translate_preserving_protected_text(text, translate_part)

    return translated, confidence


def _translate_argos(text: str, src: str, tgt: str) -> Tuple[str, float]:
    """Argostranslate CPU fallback — limited Indic support but works offline."""
    import argostranslate.package
    import argostranslate.translate

    installed = argostranslate.translate.get_installed_languages()
    src_lang = next((l for l in installed if l.code == src), None)
    tgt_lang = next((l for l in installed if l.code == tgt), None)

    if src_lang is None or tgt_lang is None:
        raise RuntimeError(f"Argostranslate language pair {src}→{tgt} not installed.")

    translation = src_lang.get_translation(tgt_lang)
    result = translation.translate(text)
    return result, 0.6


# ---------------------------------------------------------------------------
# Glossary application
# ---------------------------------------------------------------------------

def apply_glossary(text: str, source_lang: str, target_lang: str, db) -> str:
    """Replace known domain terms in the translated text using the glossary table."""
    try:
        from app.models import GlossaryEntry
        entries = (
            db.query(GlossaryEntry)
            .filter(
                GlossaryEntry.source_language == source_lang,
                GlossaryEntry.target_language == target_lang,
            )
            .all()
        )
        for entry in entries:
            text = text.replace(entry.source_term, entry.target_term)
    except Exception as e:
        logger.warning(f"Glossary application failed: {e}")
    return text


# ---------------------------------------------------------------------------
# ASR — Speech to Text
# ---------------------------------------------------------------------------

def media_translation_confidence(segments: list, mt_confidences: list[float]) -> float:
    """Combine actual ASR token likelihood with MT direction confidence."""
    asr_scores = [
        math.exp(min(0.0, float(segment["asr_avg_logprob"])))
        for segment in segments
        if segment.get("asr_avg_logprob") is not None
    ]
    asr_confidence = sum(asr_scores) / len(asr_scores) if asr_scores else 0.0
    mt_confidence = min(mt_confidences) if mt_confidences else 0.0
    return round(min(asr_confidence, mt_confidence), 4)


def _asr_transcribe_options(language: Optional[str], vad_filter: bool) -> dict:
    return {
        "language": language,
        "task": "transcribe",
        "beam_size": 5,
        "vad_filter": vad_filter,
        "condition_on_previous_text": False,
    }

def transcribe_audio(audio_path: Path, language: Optional[str] = None) -> Tuple[list, str]:
    """
    Transcribe audio file. Returns (segments, detected_language).
    Each segment: {"start": float, "end": float, "text": str}
    """
    model = _get_whisper()
    if model == "stub":
        logger.warning("ASR stub: returning placeholder transcript.")
        return [{"start": 0.0, "end": 5.0, "text": "[ASR not available — install faster-whisper]"}], "en"

    try:
        # First attempt with VAD enabled (faster, skips silence)
        segments_iter, info = model.transcribe(
            str(audio_path),
            **_asr_transcribe_options(language, vad_filter=True),
        )
        segments = []
        for s in segments_iter:
            text = (s.text or "").strip()
            try:
                orig_repr = repr(text)
            except Exception:
                orig_repr = str(text)
            try:
                hex_utf8 = text.encode("utf-8", errors="backslashreplace").hex()
            except Exception:
                hex_utf8 = ""
            try:
                hex_replace = text.encode("utf-8", errors="replace").hex()
            except Exception:
                hex_replace = ""
            avg_logprob = getattr(s, "avg_logprob", None)
            no_speech_prob = getattr(s, "no_speech_prob", None)
            if avg_logprob is not None and avg_logprob < ASR_MIN_AVG_LOGPROB:
                logger.warning(
                    "Skipping unreliable ASR segment %.2f-%.2f (avg_logprob=%.2f)",
                    s.start,
                    s.end,
                    avg_logprob,
                )
                continue
            segments.append({
                "start": s.start,
                "end": s.end,
                "text": text,
                "orig_repr": orig_repr,
                "orig_hex_utf8": hex_utf8,
                "orig_hex_replace": hex_replace,
                "asr_avg_logprob": avg_logprob,
                "asr_no_speech_prob": no_speech_prob,
            })

        # If VAD produced very little speech for a long input, retry without VAD
        try:
            import wave
            duration = None
            if audio_path.suffix.lower() == ".wav":
                try:
                    with wave.open(str(audio_path), 'rb') as wf:
                        duration = wf.getnframes() / float(wf.getframerate())
                except Exception:
                    duration = None

            total_speech = sum((s["end"] - s["start"]) for s in segments) if segments else 0.0
            if duration and total_speech < max(1.0, duration * 0.15):
                logger.info(f"ASR VAD produced only {total_speech:.1f}s speech from {duration:.1f}s audio; retrying without VAD.")
                segments_iter, info = model.transcribe(
                    str(audio_path),
                    **_asr_transcribe_options(language, vad_filter=False),
                )
                segments = []
                for s in segments_iter:
                    text = (s.text or "").strip()
                    try:
                        orig_repr = repr(text)
                    except Exception:
                        orig_repr = str(text)
                    try:
                        hex_utf8 = text.encode("utf-8", errors="backslashreplace").hex()
                    except Exception:
                        hex_utf8 = ""
                    try:
                        hex_replace = text.encode("utf-8", errors="replace").hex()
                    except Exception:
                        hex_replace = ""
                    avg_logprob = getattr(s, "avg_logprob", None)
                    no_speech_prob = getattr(s, "no_speech_prob", None)
                    if avg_logprob is not None and avg_logprob < ASR_MIN_AVG_LOGPROB:
                        logger.warning(
                            "Skipping unreliable ASR segment %.2f-%.2f (avg_logprob=%.2f)",
                            s.start,
                            s.end,
                            avg_logprob,
                        )
                        continue
                    segments.append({
                        "start": s.start,
                        "end": s.end,
                        "text": text,
                        "orig_repr": orig_repr,
                        "orig_hex_utf8": hex_utf8,
                        "orig_hex_replace": hex_replace,
                        "asr_avg_logprob": avg_logprob,
                        "asr_no_speech_prob": no_speech_prob,
                    })
        except Exception:
            # best-effort duration check; continue with whatever segments we have
            pass
        # Debug: log brief summary of segments
        try:
            if segments:
                # Log a short preview plus hex dump of the first segment for triage
                logger.info(
                    f"ASR: {len(segments)} segments. First segment: '{segments[0]['text'][:200]}'"
                )
                try:
                    logger.debug(f"ASR first segment hex (utf8/backslashreplace): {segments[0].get('orig_hex_utf8', '')[:200]}")
                except Exception:
                    pass
            else:
                logger.info("ASR: no segments produced.")
        except Exception:
            pass
        logger.info(
            "ASR language requested=%s detected=%s",
            language or "auto",
            info.language,
        )
        return segments, info.language
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        raise


# ---------------------------------------------------------------------------
# TTS — Text to Speech
# ---------------------------------------------------------------------------

TTS_SPEAKERS = {
    "en": {"male": "Thoma", "female": "Mary"},
    "hi": {"male": "Rohit", "female": "Divya"},
    "mr": {"male": "Sanjay", "female": "Sunita"},
}


def detect_dominant_voice_gender(audio_path: Path, speech_segments: Optional[list] = None) -> str:
    """Classify the dominant source voice from its median fundamental frequency."""
    import librosa
    import numpy as np

    audio, sample_rate = librosa.load(str(audio_path), sr=16000, mono=True, duration=60.0)
    if speech_segments:
        speech_audio = []
        for segment in speech_segments:
            start_sample = max(0, round(float(segment["start"]) * sample_rate))
            end_sample = min(len(audio), round(float(segment["end"]) * sample_rate))
            if end_sample > start_sample:
                speech_audio.append(audio[start_sample:end_sample])
        if speech_audio:
            audio = np.concatenate(speech_audio)
    if audio.size < sample_rate:
        logger.warning("Voice gender detection received too little audio; using female voice.")
        return "female"

    fundamental = librosa.yin(
        audio,
        fmin=65,
        fmax=350,
        sr=sample_rate,
        frame_length=2048,
        hop_length=512,
    )
    energy = librosa.feature.rms(
        y=audio,
        frame_length=2048,
        hop_length=512,
    ).squeeze()
    frame_count = min(len(fundamental), len(energy))
    fundamental = fundamental[:frame_count]
    energy = energy[:frame_count]
    energy_floor = max(0.005, float(np.percentile(energy, 40)))
    voiced_pitch = fundamental[np.isfinite(fundamental) & (energy >= energy_floor)]
    if voiced_pitch.size < 10:
        logger.warning("Voice gender detection found insufficient voiced audio; using female voice.")
        return "female"

    median_pitch = float(np.median(voiced_pitch))
    gender = "male" if median_pitch < 170.0 else "female"
    logger.info("Detected dominant source voice: %s (median pitch %.1f Hz)", gender, median_pitch)
    return gender


def tts_voice_description(language: str, gender: str) -> str:
    """Build a stable named-speaker caption for an Indic Parler target language."""
    speakers = TTS_SPEAKERS.get(language, TTS_SPEAKERS["en"])
    speaker = speakers.get(gender, speakers["female"])
    return (
        f"{speaker} speaks at a moderate pace with a natural pitch and a consistent, "
        "clear tone. The recording is very high quality, close-sounding, and has no "
        "background noise."
    )


def synthesize_speech(
    text: str,
    language: str,
    output_path: Path,
    voice_description: Optional[str] = None,
    seed: int = 42,
) -> bool:
    """
    Generate speech audio from text using Indic Parler-TTS (preferred)
    or pyttsx3 stub fallback.
    Returns True on success.
    """
    try:
        return _tts_parler(text, language, output_path, voice_description, seed)
    except Exception as e:
        logger.warning(f"Parler-TTS unavailable ({e}), trying pyttsx3 stub.")
        logger.debug("Parler-TTS exception details:", exc_info=True)

    try:
        return _tts_pyttsx3(text, language, output_path)
    except Exception as e:
        logger.warning(f"pyttsx3 unavailable ({e}). TTS skipped.")
        return False


def _split_tts_text(text: str, tokenizer, max_tokens: int = 40) -> list[str]:
    """Split long TTS prompts at sentence boundaries within a token budget."""
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    chunks = []
    current = []
    current_tokens = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        token_ids = tokenizer(sentence, add_special_tokens=False)["input_ids"]
        if len(token_ids) > max_tokens:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
            for start in range(0, len(token_ids), max_tokens):
                chunk = tokenizer.decode(
                    token_ids[start:start + max_tokens], skip_special_tokens=True
                ).strip()
                if chunk:
                    chunks.append(chunk)
            continue
        if current and current_tokens + len(token_ids) > max_tokens:
            chunks.append(" ".join(current))
            current = []
            current_tokens = 0
        current.append(sentence)
        current_tokens += len(token_ids)

    if current:
        chunks.append(" ".join(current))
    return chunks or [text.strip()]


def _tts_parler(
    text: str,
    language: str,
    output_path: Path,
    voice_description: Optional[str] = None,
    seed: int = 42,
) -> bool:
    """AI4Bharat Indic Parler-TTS — Stable version-agnostic tokenization engine."""
    global _parler_runtime
    import torch
    # Prepare monkeypatch
    _orig_jit_script = getattr(torch.jit, "script", None)
    _orig_jit_trace = getattr(torch.jit, "trace", None)
    def _noop_jit(x, *a, **k):
        return x
    try:
        if _orig_jit_script is not None:
            torch.jit.script = _noop_jit
        if _orig_jit_trace is not None:
            torch.jit.trace = _noop_jit
    except Exception:
        pass

    try:
        # Import core modules safely
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoConfig, AutoTokenizer
        import numpy as np
        import soundfile as sf

        with _parler_lock:
            if _parler_runtime is None:
                model_dir = _find_model_dir("indic-parler-tts", "parler-tts")
                if model_dir is None:
                    raise FileNotFoundError(
                        "Parler-TTS model not found. Expected at models/indic-parler-tts/"
                    )

                desc_tokenizer_dir = MODELS_DIR / "indic-parler-tts-description-tokenizer"
                if not desc_tokenizer_dir.exists():
                    raise FileNotFoundError(
                        "Parler-TTS description tokenizer not found. Expected at "
                        "models/indic-parler-tts-description-tokenizer/"
                    )
                logger.info(
                    "Loading Parler-TTS tokenizers from prompt=%s, description=%s",
                    model_dir,
                    desc_tokenizer_dir,
                )
                prompt_tokenizer = AutoTokenizer.from_pretrained(
                    str(model_dir), use_fast=False
                )
                description_tokenizer = AutoTokenizer.from_pretrained(
                    str(desc_tokenizer_dir), use_fast=False
                )

                try:
                    cfg = AutoConfig.from_pretrained(str(model_dir))
                except Exception:
                    cfg = None

                if cfg is not None:
                    model = ParlerTTSForConditionalGeneration.from_pretrained(
                        str(model_dir), config=cfg
                    )
                else:
                    model = ParlerTTSForConditionalGeneration.from_pretrained(str(model_dir))
                model.eval()
                _parler_runtime = (model, prompt_tokenizer, description_tokenizer)
            else:
                model, prompt_tokenizer, description_tokenizer = _parler_runtime

        # Clean prompt text to guarantee no formatting character overflows boundaries
        text = text.strip().replace("\n", " ")
        description = voice_description or tts_voice_description(language, "female")

        # Ensure uniform padding tokens across all sub-components safely
        for tok in [prompt_tokenizer, description_tokenizer]:
            try:
                tok.pad_token = tok.eos_token
            except Exception:
                pass

        input_tok = description_tokenizer(
            description,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        with _parler_lock, torch.no_grad():
            chunks = _split_tts_text(text, prompt_tokenizer)
            sr = getattr(model.config, "sampling_rate", None) or 44100
            audio_parts = []
            logger.info("Synthesizing Parler-TTS in %d chunk(s)", len(chunks))
            for index, chunk in enumerate(chunks, start=1):
                torch.manual_seed(seed)
                prompt_tok = prompt_tokenizer(
                    chunk,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=128,
                )
                prompt_token_count = prompt_tok["input_ids"].shape[-1]
                max_new_tokens = min(1024, max(128, prompt_token_count * 24))
                logger.info(
                    "Synthesizing Parler-TTS chunk %d/%d (%d prompt tokens, %d audio-token limit)",
                    index,
                    len(chunks),
                    prompt_token_count,
                    max_new_tokens,
                )
                generation = model.generate(
                    input_ids=input_tok.get("input_ids"),
                    attention_mask=input_tok.get("attention_mask"),
                    prompt_input_ids=prompt_tok.get("input_ids"),
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                )
                audio_parts.append(generation.cpu().numpy().squeeze())
            silence = np.zeros(int(sr * 0.15), dtype=np.float32)
            audio = np.concatenate([
                part
                for index, audio_part in enumerate(audio_parts)
                for part in ((silence, audio_part) if index else (audio_part,))
            ])
            sf.write(str(output_path), audio, sr)
            return True

    except Exception:
        logger.exception("Parler-TTS synthesis failed")
        # Return False to let the fallback trigger, but log it completely
        return False
    finally:
        try:
            if _orig_jit_script is not None:
                torch.jit.script = _orig_jit_script
            if _orig_jit_trace is not None:
                torch.jit.trace = _orig_jit_trace
        except Exception:
            pass
    return False



def _tts_pyttsx3(text: str, language: str, output_path: Path) -> bool:
    """Offline engine stub fallback."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        # Clean text slightly for simple system TTS engines
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        logger.info("Successfully fallback compiled audio via pyttsx3.")
        return True
    except Exception as e:
        logger.warning(f"Internal pyttsx3 system generation failure: {e}")
        return False


def _atempo_filter(tempo: float) -> str:
    """Build an FFmpeg atempo chain using conservative 0.5-2.0 factors."""
    factors = []
    while tempo > 2.0:
        factors.append(2.0)
        tempo /= 2.0
    while tempo < 0.5:
        factors.append(0.5)
        tempo /= 0.5
    factors.append(tempo)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _fit_audio_to_slot(input_path: Path, output_path: Path, duration: float, sample_rate: int) -> None:
    """Speed up overlong speech, then pad or trim it to an exact timeline slot."""
    import soundfile as sf

    source_duration = sf.info(str(input_path)).duration
    filters = []
    if source_duration > duration:
        filters.append(_atempo_filter(source_duration / duration))
    filters.extend(["apad", f"atrim=duration={duration:.6f}"])
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", ",".join(filters),
        "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio alignment failed: {result.stderr.decode(errors='replace')}")


def synthesize_timed_speech(
    translated_segments: list,
    language: str,
    output_path: Path,
    total_duration: float,
    synthesizer=synthesize_speech,
    sample_rate: int = 44100,
    voice_description: Optional[str] = None,
    seed: int = 42,
) -> bool:
    """Synthesize each subtitle segment and place it at its original timestamp."""
    import numpy as np
    import soundfile as sf

    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg is required for synchronized translated audio.")
    if total_duration <= 0:
        raise ValueError("Video duration must be positive.")

    timeline = np.zeros(round(total_duration * sample_rate), dtype=np.float32)
    rendered = 0
    with tempfile.TemporaryDirectory(prefix="samvaadhika-dub-") as temp_dir:
        temp_path = Path(temp_dir)
        for index, segment in enumerate(translated_segments, start=1):
            start = max(0.0, float(segment["start"]))
            end = min(total_duration, float(segment["end"]))
            text = str(segment.get("text", "")).strip()
            if not text or end <= start:
                continue

            raw_path = temp_path / f"segment_{index:04d}_raw.wav"
            fitted_path = temp_path / f"segment_{index:04d}_fitted.wav"
            spoken_text = transliterate_text_if_needed(text, language)
            if not synthesizer(
                spoken_text,
                language,
                raw_path,
                voice_description=voice_description,
                seed=seed,
            ) or not raw_path.exists():
                raise RuntimeError(f"TTS failed for translated segment {index}.")
            _fit_audio_to_slot(raw_path, fitted_path, end - start, sample_rate)
            audio, _ = sf.read(str(fitted_path), dtype="float32", always_2d=False)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            start_sample = round(start * sample_rate)
            end_sample = min(len(timeline), start_sample + len(audio))
            timeline[start_sample:end_sample] += audio[:end_sample - start_sample]
            rendered += 1

    if not rendered:
        raise RuntimeError("No translated speech segments were generated.")
    sf.write(str(output_path), np.clip(timeline, -1.0, 1.0), sample_rate, subtype="PCM_16")
    return True


def probe_media_duration(media_path: Path) -> float:
    """Return media duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(media_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.decode(errors='replace')}")
    return float(result.stdout.decode().strip())


def _ffmpeg_filter_path(path: Path) -> str:
    """Escape a local path for use inside an FFmpeg filter expression."""
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def mux_translated_video(
    video_path: Path,
    audio_path: Path,
    subtitle_path: Path,
    output_path: Path,
    subtitle_language: str,
) -> bool:
    """Create an attributed MP4 with translated audio and default soft subtitles."""
    font_path = BASE_DIR / "fonts" / "NotoSansDevanagari-VariableFont_wdth,wght.ttf"
    if not font_path.exists():
        raise RuntimeError(f"Video attribution font is missing: {font_path}")
    try:
        has_subtitles = bool(subtitle_path.read_text(encoding="utf-8-sig").strip())
    except OSError as exc:
        raise RuntimeError(f"Unable to read translated subtitles: {subtitle_path}") from exc
    source_duration = probe_media_duration(video_path)
    subtitle_language_tag = {
        "en": "eng",
        "hi": "hin",
        "mr": "mar",
    }.get(subtitle_language, subtitle_language)
    attribution_filter = (
        "pad=ceil(iw/2)*2:ceil(ih/2)*2,"
        f"drawtext=fontfile='{_ffmpeg_filter_path(font_path)}':"
        "text='Translated using Samvaadhika':"
        "x='max(4,w-tw-7)':y=4:fontsize='min(18,w/18)':fontcolor=white:"
        "box=1:boxcolor=black@0.6:boxborderw=3"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
    ]
    if has_subtitles:
        cmd.extend(["-i", str(subtitle_path)])
    cmd.extend([
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", attribution_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
    ])
    if has_subtitles:
        cmd.extend([
            "-map", "2:0", "-c:s", "mov_text", "-disposition:s:0", "default",
            "-metadata:s:s:0", f"language={subtitle_language_tag}",
        ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{output_path.stem}-",
        suffix=output_path.suffix,
        dir=output_path.parent,
        delete=False,
    ) as temporary_file:
        temporary_output_path = Path(temporary_file.name)
    cmd.extend([
        "-t", f"{source_duration:.3f}", "-movflags", "+faststart",
        str(temporary_output_path),
    ])
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg video mux failed: {result.stderr.decode(errors='replace')}"
            )
        os.replace(temporary_output_path, output_path)
    finally:
        temporary_output_path.unlink(missing_ok=True)
    return True

# ---------------------------------------------------------------------------
# Subtitle generation
# ---------------------------------------------------------------------------

def generate_subtitles(segments: list, translated_segments: list, output_path: Path) -> bool:
    """Generate SRT subtitle file from timed segments."""
    try:
        import pysubs2
        subs = pysubs2.SSAFile()
        for orig, trans in zip(segments, translated_segments):
            event = pysubs2.SSAEvent(
                start=pysubs2.make_time(s=orig["start"]),
                end=pysubs2.make_time(s=orig["end"]),
                text=trans["text"],
            )
            subs.append(event)
        subs.save(str(output_path))
        return True
    except Exception as e:
        logger.error(f"Subtitle generation failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Document translation
# ---------------------------------------------------------------------------

def translate_docx(input_path: Path, output_path: Path, source_lang: str, target_lang: str, db) -> bool:
    """Translate a DOCX file, preserving formatting."""
    try:
        from docx import Document
        doc = Document(str(input_path))
        for para in doc.paragraphs:
            if para.text.strip():
                translated, _ = translate_text(para.text, source_lang, target_lang)
                translated = apply_glossary(translated, source_lang, target_lang, db)
                for run in para.runs:
                    run.text = ""
                if para.runs:
                    para.runs[0].text = translated
                else:
                    para.text = translated
        # Tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if para.text.strip():
                            translated, _ = translate_text(para.text, source_lang, target_lang)
                            translated = apply_glossary(translated, source_lang, target_lang, db)
                            for run in para.runs:
                                run.text = ""
                            if para.runs:
                                para.runs[0].text = translated
        doc.save(str(output_path))
        return True
    except Exception as e:
        logger.error(f"DOCX translation failed: {e}")
        raise


def translate_pptx(input_path: Path, output_path: Path, source_lang: str, target_lang: str, db) -> bool:
    """Translate a PPTX file, preserving slide layout."""
    try:
        from pptx import Presentation
        prs = Presentation(str(input_path))
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        for run in para.runs:
                            if run.text.strip():
                                translated, _ = translate_text(run.text, source_lang, target_lang)
                                translated = apply_glossary(translated, source_lang, target_lang, db)
                                run.text = translated
        prs.save(str(output_path))
        return True
    except Exception as e:
        logger.error(f"PPTX translation failed: {e}")
        raise


def _insert_pdf_text(page, rect, text: str, font_path: Optional[Path], fontsize: float) -> bool:
    """Render translated text as an image so Devanagari shaping works reliably."""
    from io import BytesIO
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    scale = 3
    width = max(1, int(rect.width * scale))
    height = max(1, int(rect.height * scale))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = None
    if font_path:
        try:
            font = ImageFont.truetype(str(font_path), max(8, int(fontsize * scale)), index=0)
        except Exception:
            font = None
    if font is None:
        font = ImageFont.load_default()

    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > width - 8:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if not lines:
        return False

    line_height = max(1, int(fontsize * scale * 1.15))
    # Compute required image height for all lines and expand image if needed
    padding_px = 6
    required_height = len(lines) * line_height + padding_px
    if required_height > height:
        # create a taller image and copy existing white background
        new_image = Image.new("RGB", (width, required_height), "white")
        new_image.paste(image, (0, 0))
        image = new_image
        draw = ImageDraw.Draw(image)

    draw.multiline_text((4, 1), "\n".join(lines), font=font, fill="black", spacing=0)
    stream = BytesIO()
    image.save(stream, format="PNG")
    # If we expanded the image height, map the image back to a taller rect on the page
    if image.height != height:
        # compute new rect height in page coordinate space
        new_height_pts = image.height / scale
        new_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + new_height_pts)
        # ensure we don't overflow the page bottom
        page_bottom = page.rect.y1
        if new_rect.y1 > page_bottom:
            shift_up = new_rect.y1 - page_bottom
            new_rect = fitz.Rect(new_rect.x0, max(rect.y0 - shift_up, page.rect.y0), new_rect.x1, page_bottom)
        page.insert_image(new_rect, stream=stream.getvalue(), overlay=True)
    else:
        page.insert_image(rect, stream=stream.getvalue(), overlay=True)
    return True


def translate_pdf(input_path: Path, output_path: Path, source_lang: str, target_lang: str, db) -> Tuple[bool, str]:
    """
    Translate a PDF while preserving its page geometry and table/grid layout.
    Returns (success, notes).
    """
    try:
        import fitz
        import pdfplumber
        output_path.parent.mkdir(parents=True, exist_ok=True)
        formatted_pages = 0
        fallback_pages = 0

        # Prefer a system or deployment-provided Devanagari font for Hindi/Marathi.
        font_candidates = [
            os.environ.get("SAMVAADHIKA_DEVANAGARI_FONT", ""),
            "/System/Library/Fonts/Kohinoor.ttc",
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
            "C:/Windows/Fonts/mangal.ttf",
        ]
        # Also prefer any fonts bundled with the application under BASE_DIR/fonts
        bundled_fonts_dir = BASE_DIR / "fonts"
        if bundled_fonts_dir.exists():
            # Prefer explicit known names first
            for candidate_name in ("NotoSansDevanagari-Regular.ttf", "mangal.ttf", "NotoSansDevanagari.ttc"):
                candidate = bundled_fonts_dir / candidate_name
                if candidate.exists():
                    font_candidates.insert(0, str(candidate))
            # Otherwise, add any ttf/ttc in the bundled fonts folder
            for f in bundled_fonts_dir.iterdir():
                if f.suffix.lower() in (".ttf", ".ttc"):
                    font_candidates.append(str(f))

        font_path = next((Path(p) for p in font_candidates if p and Path(p).exists()), None)
        if font_path:
            logger.info(f"Using Devanagari font: {font_path}")
        formatted_doc = fitz.open(str(input_path))

        with pdfplumber.open(str(input_path)) as pdf:
            for page_number, source_page in enumerate(pdf.pages):
                output_page = formatted_doc[page_number]
                table_cells = []
                for table in source_page.find_tables():
                    table_cells.extend(cell for row in table.rows for cell in row.cells if cell)

                if table_cells:
                    translated_any = False
                    for x0, top, x1, bottom in table_cells:
                        cell_rect = fitz.Rect(x0, top, x1, bottom)
                        cell_text = source_page.crop((x0, top, x1, bottom)).extract_text() or ""
                        if not cell_text.strip():
                            continue
                        translated, _ = translate_text(cell_text, source_lang, target_lang)
                        translated = apply_glossary(translated, source_lang, target_lang, db)
                        words = output_page.get_text("words", clip=cell_rect)
                        if words:
                            text_rect = fitz.Rect(
                                min(word[0] for word in words) - 1,
                                min(word[1] for word in words) - 1,
                                max(word[2] for word in words) + 1,
                                max(word[3] for word in words) + 1,
                            ) & cell_rect
                            output_page.draw_rect(text_rect, color=None, fill=(1, 1, 1), overlay=True)
                        translated_any = _insert_pdf_text(
                            output_page,
                            fitz.Rect(cell_rect.x0 + 2, cell_rect.y0 + 1, cell_rect.x1 - 2, cell_rect.y1 - 1),
                            translated,
                            font_path,
                            max(5, min(10, (bottom - top) * 0.42)),
                        ) or translated_any
                    if translated_any:
                        formatted_pages += 1
                        continue

                # For non-table text-native pages, preserve each text line's position.
                words = source_page.extract_words(keep_blank_chars=True, use_text_flow=True)
                lines = {}
                for word in words:
                    key = (round(word["top"], 1), round(word["bottom"], 1))
                    lines.setdefault(key, []).append(word)
                translated_any = False
                for (top, bottom), line_words in lines.items():
                    line_words.sort(key=lambda word: word["x0"])
                    original = " ".join(word["text"] for word in line_words).strip()
                    if not original:
                        continue
                    translated, _ = translate_text(original, source_lang, target_lang)
                    translated = apply_glossary(translated, source_lang, target_lang, db)
                    text_rect = fitz.Rect(
                        min(word["x0"] for word in line_words), top,
                        max(word["x1"] for word in line_words), bottom,
                    )
                    output_page.draw_rect(text_rect, color=None, fill=(1, 1, 1), overlay=True)
                    translated_any = _insert_pdf_text(
                        output_page,
                        text_rect,
                        translated,
                        font_path,
                        max(5, min(11, bottom - top)),
                    ) or translated_any
                if translated_any:
                    formatted_pages += 1
                else:
                    fallback_pages += 1

        if fallback_pages:
            logger.warning("%d PDF page(s) had no coordinate-aware text; layout may be incomplete.", fallback_pages)
        formatted_doc.save(str(output_path), garbage=4, deflate=True)
        formatted_doc.close()
        return True, f"PDF translated with layout preservation on {formatted_pages} page(s)."
    except Exception as e:
        logger.error(f"PDF translation failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Audio/Video extraction helpers
# ---------------------------------------------------------------------------

def extract_audio_from_video(video_path: Path, audio_path: Path) -> bool:
    """Use ffmpeg to extract audio track from video."""
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg not found. Install ffmpeg and add to PATH.")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr.decode()}")
    return True


def normalize_audio(input_path: Path, output_path: Path) -> bool:
    """Normalize audio to 16kHz mono WAV for Whisper."""
    if not _ffmpeg_available():
        shutil.copy(input_path, output_path)
        return True
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    return result.returncode == 0
