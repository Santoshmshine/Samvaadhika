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
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import sys
import types

from app.config import (
    BASE_DIR, CACHE_DIR, OUTPUTS_DIR, UPLOADS_DIR, MODELS_DIR,
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    TESSERACT_LANGUAGES, SUPPORTED_LANGUAGES,
)

logger = logging.getLogger("samvaadhika.pipeline")

# When running as a PyInstaller bundle, model files are extracted to
# the runtime folder available at `sys._MEIPASS`. Use an "effective"
# models directory so all lookup helpers find bundled models at runtime.
try:
    _meipass = getattr(sys, "_MEIPASS", None)
except Exception:
    _meipass = None

if _meipass:
    MODELS_DIR_EFFECTIVE = Path(_meipass) / "models"
else:
    MODELS_DIR_EFFECTIVE = MODELS_DIR

# ---------------------------------------------------------------------------
# Ensure ffmpeg is on PATH (winget installs to a deep location)
# ---------------------------------------------------------------------------
_FFMPEG_SEARCH_DIRS = [
    BASE_DIR / "ffmpeg" / "bin",  # Bundled ffmpeg in project
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
    Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "ffmpeg" / "bin",
    Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "ffmpeg" / "bin",
]

def _ensure_ffmpeg_on_path():
    """Find ffmpeg installed by winget (or other locations) and add to PATH."""
    # If ffmpeg is already available on PATH, nothing to do
    if shutil.which("ffmpeg"):
        return

    # If running as a PyInstaller bundle, check the extracted runtime folder
    try:
        import sys
        meipass = getattr(sys, '_MEIPASS', None)
    except Exception:
        meipass = None

    if meipass:
        candidate = Path(meipass) / "ffmpeg" / "bin"
        ffexe = candidate / "ffmpeg.exe"
        if ffexe.exists():
            bin_dir = str(candidate)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Added bundled ffmpeg to PATH from: {bin_dir}")
            return

    # Fall back to known search directories on disk (developer bundle or winget)
    for search_root in _FFMPEG_SEARCH_DIRS:
        if not search_root.exists():
            continue
        for ffmpeg_exe in search_root.rglob("ffmpeg.exe"):
            bin_dir = str(ffmpeg_exe.parent)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Added ffmpeg to PATH from: {bin_dir}")
            return

    logger.warning("ffmpeg not found in any known location. Video/audio processing may fail.")

_ensure_ffmpeg_on_path()


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
        model_dir = MODELS_DIR_EFFECTIVE / candidate
        if model_dir.exists():
            return _resolve_hf_cache(model_dir)
    return None


# ---------------------------------------------------------------------------
# Lazy model singletons
# ---------------------------------------------------------------------------
_whisper_model = None
_lang_detector = None


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
                candidate = MODELS_DIR_EFFECTIVE / fname
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
            logger.warning(f"fasttext not available: {e}. Using lightweight fallback detector.")

            # Lightweight fallback detector: detect Devanagari characters for
            # Hindi/Marathi vs Latin for English. This avoids a hard dependency
            # on fastText while still giving reasonable auto-detection for the
            # supported languages (en, hi, mr).
            class _SimpleLangDetector:
                def predict(self, text: str, k: int = 1):
                    # If Devanagari-range characters present, prefer Hindi/Marathi
                    if any('\u0900' <= ch <= '\u097F' for ch in text):
                        return [("__label__hi", 0.99)]
                    # Fallback to English
                    return [("__label__en", 0.99)]

            _lang_detector = _SimpleLangDetector()
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
        predictions = detector.predict(text.replace("\n", " "), k=1)
        label = predictions[0][0].replace("__label__", "")
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
        return text, 1.0

    # Try IndicTrans2 first
    try:
        return _translate_indictrans2(text, source_lang, target_lang)
    except Exception as e:
        logger.exception("IndicTrans2 unavailable, trying argostranslate fallback.")

    # Argostranslate fallback
    try:
        return _translate_argos(text, source_lang, target_lang)
    except Exception as e:
        logger.exception("argostranslate unavailable. Returning stub translation.")

    # Final stub — clearly marked so reviewers know it's a placeholder
    return f"[TRANSLATION STUB: {source_lang}→{target_lang}] {text}", 0.0


def _translate_indictrans2(text: str, src: str, tgt: str) -> Tuple[str, float]:
    """
    IndicTrans2 distilled model via the ai4bharat/IndicTrans2 inference API.
    Requires: pip install transformers sentencepiece sacremoses torch
    and the model checkpoint downloaded to models/indictrans2*/
    """
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    import torch

    model_dir = _find_model_dir(
        "indictrans2",
        "indictrans2-en-indic-dist-200M",
        "indictrans2-indic-en-dist-200M",
        "indictrans2-en-indic-1B",
    )
    if model_dir is None:
        raise FileNotFoundError(
            "IndicTrans2 model not found. Expected at models/indictrans2/ "
            "or models/indictrans2-en-indic-dist-200M/"
        )

    # Language code mapping for IndicTrans2
    lang_map = {"en": "eng_Latn", "hi": "hin_Deva", "mr": "mar_Deva"}
    src_code = lang_map.get(src, "eng_Latn")
    tgt_code = lang_map.get(tgt, "hin_Deva")

    # Some HF model configs import `transformers.onnx` at load-time. If the
    # optional ONNX support isn't installed in the environment, create a
    # minimal shim module to satisfy those imports so models can still load.
    try:
        import importlib
        importlib.import_module('transformers.onnx')
    except Exception:
        # Inject a tiny shim into sys.modules that behaves like a package
        # so imports like `from transformers.onnx.utils import ...` succeed.
        if 'transformers.onnx' not in sys.modules:
            mod = types.ModuleType('transformers.onnx')
            # Mark as package
            mod.__path__ = []
            class OnnxConfig:
                def __init__(self, *args, **kwargs):
                    pass
            class OnnxSeq2SeqConfigWithPast(OnnxConfig):
                pass
            mod.OnnxConfig = OnnxConfig
            mod.OnnxSeq2SeqConfigWithPast = OnnxSeq2SeqConfigWithPast
            mod._has_onnx_support = lambda: False
            # Create a utils submodule with a minimal compute function expected
            utils_mod = types.ModuleType('transformers.onnx.utils')
            def compute_effective_axis_dimension(*args, **kwargs):
                # Best-effort placeholder: return 1 so downstream callers can proceed
                return 1
            utils_mod.compute_effective_axis_dimension = compute_effective_axis_dimension
            sys.modules['transformers.onnx'] = mod
            sys.modules['transformers.onnx.utils'] = utils_mod

    # Compatibility shim: some HF tokenizers (like IndicTrans2's) assume
    # a `_special_tokens_map` attribute exists on the tokenizer base class
    # and will fail during `__init__` otherwise. Ensure the common base
    # classes expose a dict at class-level so instance __setattr__ can mutate it.
    try:
        import transformers.tokenization_utils_base as _tub
        for _cls_name in ('PreTrainedTokenizerBase', 'PreTrainedTokenizer', 'PreTrainedTokenizerFast'):
            if hasattr(_tub, _cls_name):
                _cls = getattr(_tub, _cls_name)
                if not hasattr(_cls, '_special_tokens_map'):
                    setattr(_cls, '_special_tokens_map', {})
                # Add common compatibility defaults accessed by some custom
                # tokenizers (IndicTrans's tokenizer expects these attributes).
                if not hasattr(_cls, 'verbose'):
                    setattr(_cls, 'verbose', False)
                if not hasattr(_cls, 'src_encoder'):
                    setattr(_cls, 'src_encoder', {})
                if not hasattr(_cls, 'tgt_encoder'):
                    setattr(_cls, 'tgt_encoder', {})
                if not hasattr(_cls, 'src_decoder'):
                    setattr(_cls, 'src_decoder', {})
                if not hasattr(_cls, 'tgt_decoder'):
                    setattr(_cls, 'tgt_decoder', {})
    except Exception as _e:
        logger.debug(f"Failed to apply tokenizer compatibility shim: {_e}")

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), trust_remote_code=True)
    model.eval()

    # IndicTrans2 custom tokenizer expects: "src_lang tgt_lang actual_text"
    tagged_text = f"{src_code} {tgt_code} {text}"
    inputs = tokenizer(tagged_text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_length=512, num_beams=1, use_cache=False)

    # Switch tokenizer to target mode for decoding, then restore
    tokenizer._switch_to_target_mode()
    translated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    tokenizer._switch_to_input_mode()
    return translated, 0.85


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
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        segments = [
            {"start": s.start, "end": s.end, "text": s.text.strip()}
            for s in segments_iter
        ]
        return segments, info.language
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        raise


# ---------------------------------------------------------------------------
# TTS — Text to Speech
# ---------------------------------------------------------------------------

def synthesize_speech(text: str, language: str, output_path: Path) -> bool:
    """
    Generate speech audio from text using Indic Parler-TTS (preferred)
    or pyttsx3 stub fallback.
    Returns True on success.
    """
    try:
        return _tts_parler(text, language, output_path)
    except Exception as e:
        logger.warning(f"Parler-TTS unavailable ({e}), trying pyttsx3 stub.")

    try:
        return _tts_pyttsx3(text, language, output_path)
    except Exception as e:
        logger.warning(f"pyttsx3 unavailable ({e}). TTS skipped.")
        return False


def _tts_parler(text: str, language: str, output_path: Path) -> bool:
    """AI4Bharat Indic Parler-TTS — Apache-2.0 licensed."""
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer
    import soundfile as sf

    model_dir = _find_model_dir("indic-parler-tts", "parler-tts")
    if model_dir is None:
        raise FileNotFoundError(
            "Parler-TTS model not found. Expected at models/indic-parler-tts/"
        )

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = ParlerTTSForConditionalGeneration.from_pretrained(str(model_dir))
    model.eval()

    description = "A female speaker delivers a clear, natural voice."
    input_ids = tokenizer(description, return_tensors="pt").input_ids
    prompt_ids = tokenizer(text, return_tensors="pt").input_ids

    with torch.no_grad():
        generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt_ids)

    audio = generation.cpu().numpy().squeeze()
    sf.write(str(output_path), audio, model.config.sampling_rate)
    return True


def _tts_pyttsx3(text: str, language: str, output_path: Path) -> bool:
    """pyttsx3 system TTS stub — English only, for dev/demo."""
    import pyttsx3
    engine = pyttsx3.init()
    engine.save_to_file(text, str(output_path))
    engine.runAndWait()
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


def translate_pdf(input_path: Path, output_path: Path, source_lang: str, target_lang: str, db) -> Tuple[bool, str]:
    """
    Extract text from PDF, translate, and write a translated PDF output.
    Falls back to plain-text output if fpdf2 is not available.
    Returns (success, notes).
    """
    try:
        import pdfplumber
        # Extract text page-by-page
        pages_text = []
        with pdfplumber.open(str(input_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                else:
                    # Scanned page — try OCR
                    if _tesseract_available():
                        img = page.to_image(resolution=200).original
                        import pytesseract
                        ocr_text = pytesseract.image_to_string(img, lang=TESSERACT_LANGUAGES)
                        pages_text.append(ocr_text)
                    else:
                        pages_text.append("[OCR not available for this page]")

        # Translate each page
        translated_pages = []
        for page_text in pages_text:
            if page_text.strip():
                translated, _ = translate_text(page_text, source_lang, target_lang)
                translated = apply_glossary(translated, source_lang, target_lang, db)
                translated_pages.append(translated)
            else:
                translated_pages.append("")

        # Try to produce a PDF output
        try:
            _write_translated_pdf(translated_pages, output_path, target_lang)
            return True, "PDF translated to PDF"
        except Exception as pdf_err:
            logger.warning(f"PDF generation failed ({pdf_err}), falling back to text output.")
            # Fallback: write as plain text with .txt extension
            txt_path = output_path.with_suffix(".txt")
            txt_path.write_text("\n\n".join(translated_pages), encoding="utf-8")
            return True, "PDF translated to text (fpdf2 not available for PDF output)"

    except Exception as e:
        logger.error(f"PDF translation failed: {e}")
        raise


def _write_translated_pdf(pages: list, output_path: Path, target_lang: str):
    """
    Write translated text pages into a new PDF using fpdf2.
    Supports Devanagari (Hindi/Marathi) via bundled Nirmala UI font or system fonts.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Try to add a Unicode font that supports Devanagari
    font_name = "Helvetica"
    unicode_font_added = False

    # Search for Unicode-capable fonts — prioritize bundled fonts, then system fonts
    font_search_paths = [
        # Bundled fonts in project (Nirmala UI supports Devanagari + Latin)
        BASE_DIR / "fonts" / "Nirmala.ttf",
        BASE_DIR / "fonts" / "NirmalaS.ttf",
        # System fonts (Windows)
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/NotoSansDevanagari-Regular.ttf"),
        Path("C:/Windows/Fonts/NotoSans-Regular.ttf"),
        Path("C:/Windows/Fonts/mangal.ttf"),
        Path("C:/Windows/Fonts/aparaj.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]

    for fp in font_search_paths:
        if fp.exists():
            try:
                pdf.add_font("UnicodeFont", "", str(fp))
                font_name = "UnicodeFont"
                unicode_font_added = True
                logger.info(f"PDF using Unicode font: {fp.name}")
                break
            except Exception as fe:
                logger.warning(f"Failed to add font {fp}: {fe}")

    if not unicode_font_added:
        if target_lang in ("hi", "mr"):
            logger.warning("No Unicode font found. PDF may not render Hindi/Marathi correctly.")
        # For English, Helvetica works fine

    for page_text in pages:
        pdf.add_page()
        pdf.set_font(font_name, size=11)
        # Split into lines and write
        for line in page_text.split("\n"):
            pdf.multi_cell(0, 7, line)
            pdf.ln(1)

    pdf.output(str(output_path))
    logger.info(f"Translated PDF written to {output_path}")


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


def mux_translated_video(
    original_video: Path,
    translated_audio: Path,
    subtitle_path: Optional[Path],
    output_path: Path,
) -> bool:
    """
    Mux translated audio (and optionally burn-in subtitles) back into the
    original video, producing a fully translated video file.

    Strategy:
      1. Replace the audio track with the translated audio.
      2. If subtitles are available, burn them into the video as soft subs.
      3. Keep the original video stream untouched.
    """
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg not found. Install ffmpeg and add to PATH.")

    # Build ffmpeg command
    # -map 0:v  → take video from original
    # -map 1:a  → take audio from translated audio
    # -c:v copy → don't re-encode video (fast)
    # -c:a aac  → encode audio as AAC for broad compatibility
    # -shortest → stop when the shorter stream ends
    cmd = [
        "ffmpeg", "-y",
        "-i", str(original_video),
        "-i", str(translated_audio),
    ]

    if subtitle_path and subtitle_path.exists():
        # Burn subtitles into video using the subtitles filter
        cmd += [
            "-filter_complex",
            f"[0:v]subtitles='{str(subtitle_path).replace(chr(92), chr(47))}'[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(output_path),
        ]
    else:
        # No subtitles — just replace audio, copy video stream
        cmd += [
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(output_path),
        ]

    logger.info(f"Muxing translated video: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, timeout=600)

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        logger.error(f"Video muxing failed: {stderr}")

        # Fallback: try without subtitle burn-in if that was the issue
        if subtitle_path and "subtitles" in stderr.lower():
            logger.info("Retrying video mux without subtitle burn-in...")
            cmd_fallback = [
                "ffmpeg", "-y",
                "-i", str(original_video),
                "-i", str(translated_audio),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]
            result = subprocess.run(cmd_fallback, capture_output=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"Video muxing failed (fallback): {result.stderr.decode(errors='replace')}")
        else:
            raise RuntimeError(f"Video muxing failed: {stderr}")

    logger.info(f"Translated video saved to {output_path}")
    return True
