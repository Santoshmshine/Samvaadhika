---
name: Samvaadhika
description: "Use for work on the Samvaadhika offline BAIF translation platform, especially EN to HI/MR translation, IndicTrans2, model assets, FastAPI routes, background jobs, packaging, and dependency readiness."
---

# Samvaadhika Application Context

## Mission and Runtime Shape

Samvaadhika is an offline, local-first multilingual translation platform for BAIF eLearning content. It is a FastAPI web application served on localhost, with Jinja2 templates, SQLite persistence through SQLAlchemy, and a small in-process thread pool for file jobs.

The supported language codes are:

| Code | Language |
|---|---|
| `en` | English |
| `hi` | Hindi |
| `mr` | Marathi |

The configured runtime is CPU-oriented. The intended production packaging is a Windows PyInstaller onedir distribution; the source workflow is for a developer machine with Python 3.10+.

Important directories:

- `app/main.py`: FastAPI application startup and route registration.
- `app/config.py`: paths, supported languages, limits, worker count, and Whisper settings.
- `app/routes/translate.py`: browser pages, synchronous text translation endpoint, and file upload endpoint.
- `app/pipeline.py`: language detection, machine translation, ASR, TTS, subtitles, and document helpers.
- `app/worker.py`: SQLite-backed queue and audio/video/document processing.
- `app/templates/`: Jinja2 UI templates.
- `app/static/`: CSS, JavaScript, and images.
- `models/`: local model checkpoints. These are runtime assets, not Python packages.
- `data/`: runtime SQLite database and logs.
- `uploads/`, `outputs/`, `cache/`: runtime file and deduplication storage.
- `requirements.txt`: declared Python dependencies.
- `setup.bat`: source installation and database initialization on Windows.
- `run.bat`: source application launcher.
- `build.bat` and `samvaadhika.spec`: PyInstaller build workflow.

## English to Hindi and Marathi Support

### Text translation path

1. The user opens `/translate`, rendered by `app/routes/translate.py` using `app/templates/translate.html`.
2. The form submits to `POST /translate/text` with `text`, `source_language`, and `target_language`.
3. `target_language` must be one of `en`, `hi`, or `mr`; unsupported values return HTTP 400.
4. When source is `auto`, `detect_language()` uses `models/lid.176.ftz` through fastText. Detection returns `en`, `hi`, or `mr`; failures default to `en`.
5. The endpoint hashes the source, target, and text and reuses a completed text job when available.
6. Otherwise `translate_text()` tries local IndicTrans2 first, Argos Translate second, and finally returns a visibly marked stub string with confidence `0.0`.
7. The result is stored in SQLite as a completed `Job`, with confidence and a human-review flag. Every request also creates an `AuditLog` entry.

Only completed text jobs with confidence `>= 0.7` are reusable. Stub results and the lower-confidence Argos fallback must not be cached permanently, because doing so would prevent a later IndicTrans2 retry after the model becomes available.

### IndicTrans2 language mapping

`app/pipeline.py` maps application codes to IndicTrans2 codes:

- `en` -> `eng_Latn`
- `hi` -> `hin_Deva`
- `mr` -> `mar_Deva`

The model loader searches for a local model directory named `models/indictrans2/`, `models/indictrans2-en-indic-dist-200M/`, `models/indictrans2-indic-en-dist-200M/`, or `models/indictrans2-en-indic-1B/`. It supports a direct model directory and Hugging Face snapshot cache layouts. It loads with `AutoTokenizer` and `AutoModelForSeq2SeqLM`, adds the source and target language codes to the input, and decodes in target mode.

Therefore EN -> HI and EN -> MR are supported by the application design through the same IndicTrans2 model, provided that the complete checkpoint and tokenizer files exist locally and the ML dependencies are installed. The reverse directions are also represented by the language map, subject to the same model capability and asset requirements.

### Files and media

- DOCX: paragraphs and tables are translated, with basic formatting preservation.
- PPTX: text runs are translated while retaining slide structure.
- PDF: extracted text is translated to a plain `.txt`; scanned pages require Tesseract OCR. Layout is not preserved.
- Audio/video: FFmpeg normalizes or extracts audio, faster-whisper transcribes it, each segment is translated, TTS is attempted, and SRT subtitles are generated.
- The document worker currently handles `.docx`, `.pptx`, and `.pdf`. Although `.xlsx` and `.csv` are listed as allowed upload extensions, the worker raises `Unsupported document type` for them. Do not describe XLSX/CSV translation as working unless implementing it.

For file jobs, `source_language=auto` is not language-detected before queuing. The audio/video path obtains the language from Whisper; the document path defaults an unspecified source to `en`.

Glossary entries are applied after translation by `apply_glossary()` for matching source and target language pairs.

## Translation Fallback and Quality Rules

Never describe the stub as real translation. The fallback sequence is:

1. IndicTrans2: preferred local neural MT, confidence `0.85`.
2. Argos Translate: optional offline fallback, confidence `0.6`.
3. Stub: returns `[TRANSLATION STUB: src->tgt] original text`, confidence `0.0`.

The endpoint marks confidence below `0.7` as needing review. A successful HTTP response does not prove that real MT occurred; inspect the result and logs or verify the model assets.

## Dependency and Asset Inventory

### Declared in `requirements.txt`

- Web: `fastapi`, `starlette`, `uvicorn`, `jinja2`, `python-multipart`, `itsdangerous`, `aiofiles`.
- Database: `sqlalchemy`.
- Auth: `bcrypt`, `python-jose[cryptography]`.
- Documents: `python-docx`, `python-pptx`, `openpyxl`, `pdfplumber`.
- OCR/image: `Pillow`, `pytesseract`; OpenCV is commented out.
- ASR: `faster-whisper`.
- Subtitles/audio helpers: `pysubs2`, `ffmpeg-python`.
- MT: `transformers`, `torch`, `sentencepiece`, `sacremoses`, `safetensors`, `huggingface_hub`, `tokenizers`.
- TTS fallback: `pyttsx3`.
- Utilities: `httpx`, `tqdm`, `loguru`.

### Runtime packages and platform dependencies

The following runtime imports are now declared in `requirements.txt`:

- `fasttext-wheel`: provides the `fasttext` module required for the bundled `lid.176.ftz` language detector.
- `argostranslate`: optional offline translation fallback.
- `parler-tts`: preferred Indic Parler-TTS implementation.
- `soundfile`: writes Parler-TTS audio output.
- `comtypes`: Windows-only dependency for the `pyttsx3` SAPI5 path.

`ffmpeg-python` is only a Python wrapper. The pipeline executes the external `ffmpeg` binary and requires it on PATH. `pytesseract` is only a Python wrapper and requires the external `tesseract` executable plus `eng`, `hin`, and `mar` language data.

### Model and external assets

- Present in the repository at the last verification: `models/lid.176.ftz` and `models/indictrans2/`.
- The `models/indictrans2/` directory currently contains documentation rather than a verified complete checkpoint. Confirm `config.json`, tokenizer files, and model weights before claiming IndicTrans2 is usable.
- faster-whisper may auto-download its `small` model on first use if network access is available, despite the offline deployment goal. A local Whisper checkpoint is preferable for a truly offline package.
- Indic Parler-TTS is documented but no checkpoint is included in the repository.
- Model downloads are not performed by `setup.bat`; `models_scripts/indictrans2.py` downloads IndicTrans2 and requires Hugging Face access/token handling.

## Resolution Status Snapshot

This snapshot was checked on 2026-08-24 from the macOS workspace and repository virtual environment:

- System `python3 -m pip check`: no broken installed distributions were reported, but the system interpreter had none of the application Python packages importable.
- `.venv/bin/python -m pip check`: no broken installed distributions were reported; all declared packages and the translation/TTS imports (`fasttext`, `argostranslate`, `parler_tts`, and `soundfile`) were importable. `comtypes` was correctly skipped on macOS by its platform marker.
- `/opt/homebrew/bin/ffmpeg` was available.
- Tesseract was not available on PATH.
- `models/lid.176.ftz` existed.
- The complete IndicTrans2 checkpoint was downloaded into `models/indictrans2/`; both EN -> HI and EN -> MR were verified through `app.pipeline.translate_text()` with confidence `0.85`.
- Hugging Face runtime caching is configured under the project `cache/huggingface/` directory to avoid inaccessible user-cache permissions in the web process.

This macOS check does not prove whether a separate Windows `venv` or built executable is resolved. On Windows, run `setup.bat` in a clean environment, then verify imports, model files, FFmpeg, Tesseract, and an actual EN -> HI and EN -> MR request. `pip check` alone only checks installed package metadata; it does not check external binaries, model files, or an actual non-stub translation.

Overall status at this snapshot: the repository `.venv` Python packages and real EN -> HI/MR translation are **resolved and verified**. Tesseract is still unresolved for scanned PDFs, and the current standalone package workflow still requires separately bundling or downloading model assets.

## Agent Working Rules

- Preserve `en`, `hi`, and `mr` codes and the IndicTrans2 mapping unless a language-support change is intentional.
- Keep translation local/offline at inference time; do not add cloud translation calls without an explicit product decision.
- When changing dependencies, update both `requirements.txt` and the Windows setup/build documentation, then test in the supported Python/Windows environment.
- Treat models, FFmpeg, Tesseract, and language data as separate deployment prerequisites.
- Test both `en -> hi` and `en -> mr` with a known sentence and confirm the response is not the stub marker.
- Do not claim XLSX/CSV support based only on the upload allow-list.
- Keep audit logging, content-hash caching, confidence scores, and review flags intact when modifying translation behavior.
