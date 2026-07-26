# Samvaadhika
### Offline Multilingual Translation Platform for BAIF
> *bridging BAIF's eLearning languages*

---

## What it does

Samvaadhika translates BAIF's eLearning content — text, audio, video, and documents — between **English, Hindi (हिन्दी), and Marathi (मराठी)**, entirely offline on a single Windows machine. No cloud APIs, no per-use cost, no internet required at inference time.

**Three clicks: upload → choose language → download.**

---

## Quick start (Windows)

### Prerequisites
- Windows 10 / 11
- Python 3.10 or later — [python.org](https://www.python.org/downloads/)
- [ffmpeg](https://ffmpeg.org/download.html) — add to PATH (needed for audio/video)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) — install with Hindi + Marathi language packs (needed for scanned PDFs)

### 1. First-time setup
```
Double-click:  setup.bat
```
This creates a virtual environment, installs all Python dependencies, and initialises the SQLite database.

### 2. Start the app
```
Double-click:  run.bat
```
Then open your browser at **http://localhost:8000**

### 3. Default admin login
| Field    | Value                  |
|----------|------------------------|
| Username | `admin`                |
| Password | `Samvaadhika@2024`     |

> ⚠ **Change the admin password immediately after first login.**

---

## AI model setup (download separately)

The app runs with stub/fallback translation out of the box. For full AI quality, download these models into the `models/` folder:

| Model | Folder | Purpose |
|---|---|---|
| [IndicTrans2 distilled](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M) | `models/indictrans2/` | English ↔ Hindi ↔ Marathi translation |
| [faster-whisper small](https://huggingface.co/Systran/faster-whisper-small) | auto-downloaded on first use | Speech-to-text (ASR) |
| [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) | `models/indic-parler-tts/` | Text-to-speech (TTS) |
| [fastText lid.176.ftz](https://fasttext.cc/docs/en/language-identification.html) | `models/lid.176.ftz` | Language detection |

All models are MIT or Apache-2.0 licensed — free with no usage restrictions.

---

## Project structure

```
Samvaadhika/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # All settings (ports, limits, paths)
│   ├── database.py      # SQLite session + init
│   ├── models.py        # SQLAlchemy ORM models
│   ├── auth.py          # JWT auth + password hashing
│   ├── pipeline.py      # AI pipeline (ASR → MT → TTS → OCR)
│   ├── worker.py        # Background job thread pool
│   ├── routes/
│   │   ├── auth.py      # Login / logout / register
│   │   ├── translate.py # Text translate + file upload
│   │   ├── jobs.py      # Job status + download
│   │   └── admin.py     # User mgmt, glossary, audit log
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS, JS, images
├── data/                # SQLite database file
├── uploads/             # Uploaded files (temp)
├── outputs/             # Translated output files
├── cache/               # Content-hash dedup cache
├── models/              # AI model checkpoints
├── requirements.txt
├── setup.bat            # One-time setup
└── run.bat              # Start the app
```

---

## Features

| Feature | Status |
|---|---|
| Instant text translation (EN ↔ HI ↔ MR) | ✅ MVP |
| DOCX translation (format-preserving) | ✅ MVP |
| PPTX translation (format-preserving) | ✅ MVP |
| Audio → transcript → translation → TTS + SRT | ✅ MVP |
| Video → audio extraction → full audio pipeline | ✅ MVP |
| Auto language detection + manual override | ✅ MVP |
| Async job queue with live status polling | ✅ MVP |
| Content-hash dedup (never reprocess same file) | ✅ MVP |
| Admin approval workflow for new users | ✅ MVP |
| Domain glossary (agricultural/BAIF terms) | ✅ MVP |
| Audit log (who translated what and when) | ✅ MVP |
| PDF translation (text-native) | 🔶 Best effort |
| Scanned PDF OCR (Tesseract) | 🔶 Best effort |
| XLSX / CSV translation | 🔶 Stretch goal |
| On-screen text in video (OCR) | 🔶 Best effort |

---

## Supported languages

| Code | Language |
|------|----------|
| `en` | English |
| `hi` | Hindi (हिन्दी) |
| `mr` | Marathi (मराठी) |

---

## Admin operations

| Task | Where |
|---|---|
| Approve new user accounts | `/admin/users` |
| Add/remove domain glossary terms | `/admin/glossary` |
| View audit log | `/admin/audit` |
| Monitor / requeue failed jobs | `/admin/jobs` |
| View system stats | `/admin/` |

---

## Configuration

Edit [`app/config.py`](app/config.py) to change:
- Port number (`PORT = 8000`)
- File size / duration limits
- Whisper model size (`tiny` / `base` / `small` / `medium`)
- Worker thread count
- Default admin credentials (change before deployment)

---

## Responsible technology

- **Privacy** — nothing leaves BAIF's premises; no cloud calls at inference time
- **Audit trail** — every translation is logged with user, timestamp, and IP
- **Confidence flagging** — low-confidence translations are flagged for human review
- **Domain glossary** — prevents mistranslation of sensitive agricultural/veterinary terms
- **Accessibility** — Devanagari rendering tested; TTS output for low-literacy users

---

## Handover

For BAIF IT staff:
- **Backup**: copy the `data/samvaadhika.db` file and the `outputs/` folder
- **Restore**: replace those files on the new machine and run `run.bat`
- **Add a language**: update `SUPPORTED_LANGUAGES` in `app/config.py` and download the corresponding IndicTrans2 checkpoint
- **Windows Service**: use [NSSM](https://nssm.cc/) to wrap `run.bat` as a Windows Service so it starts automatically on reboot

---

*Samvaadhika — Tech for Good Hackathon, HSBC × BAIF, 2024*
