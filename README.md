# Samvaadhika
### Offline Multilingual Translation Platform for BAIF
> *bridging BAIF's eLearning languages*

---

## Deployment options

| Option | Who runs it | Python needed? |
|---|---|---|
| **Standalone .exe** (recommended for BAIF) | BAIF IT — just unzip + double-click | No |
| **Python source** (for developers) | Developer machine with Python 3.10+ | Yes |

---

## Option A — Standalone Windows Executable (no Python needed)

### For BAIF IT staff (receiving the package)

1. Unzip `Samvaadhika.zip` to any folder (e.g. `C:\Samvaadhika\`)
2. Double-click **`install.bat`** — creates Desktop and Start Menu shortcuts
3. Double-click the **Samvaadhika** desktop shortcut
4. Browser opens automatically at `http://localhost:8000`

**That's it. No Python, no internet, no IT admin rights required.**

Default login: `admin` / `Samvaadhika@2024` — change after first login.

### For developers — building the .exe

Prerequisites (developer machine only):
- Python 3.10+
- Internet access to download packages (one-time, during build only)

```
build.bat
```

Output: `dist\Samvaadhika\` — zip this folder and send to BAIF IT.

**Key files:**

| File | Purpose |
|---|---|
| [`launcher.py`](launcher.py) | PyInstaller entry point — fixes paths, opens browser, starts Uvicorn |
| [`samvaadhika.spec`](samvaadhika.spec) | PyInstaller spec — controls what gets bundled |
| [`build.bat`](build.bat) | Developer build script (runs PyInstaller) |
| [`install.bat`](install.bat) | End-user installer (runs on BAIF PC, no Python needed) |

### Optional: Auto-start on Windows boot (Windows Service)

`install.bat` offers to install Samvaadhika as a Windows Service using [NSSM](https://nssm.cc/).
Place `nssm.exe` in the same folder as `Samvaadhika.exe` before running `install.bat`.
Once installed as a service, the app starts automatically on every reboot — no login required.

---

## Option B — Python source (developers / hackathon demo)

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

---

## Default admin login

| Field    | Value                  |
|----------|------------------------|
| Username | `admin`                |
| Password | `Samvaadhika@2024`     |

> **Change the admin password immediately after first login.**

## Admin portal

Sign in with an approved administrator account and open `/admin/`. The admin dashboard provides an all-time overview of:

- Total users and pending registrations
- Total translation jobs and job status counts
- Translation usage by target language
- Translation usage by type (`text`, `document`, `audio`, and `video`)
- Top users by translation-job count
- Recent audit activity

Use `/admin/users` to manage accounts. Administrators can approve self-registered users, deactivate accounts, reset passwords, and create new users directly. Admin-created users are active and approved immediately. The create-user form supports the `user` and `admin` roles and requires a password of at least eight characters. Standard users can translate and view their own jobs but receive HTTP 403 for admin pages.

---

## AI model setup (download separately)

The app runs with stub/fallback translation out of the box. For full AI quality, download these models into the `models/` folder (next to `Samvaadhika.exe` for the standalone build, or in the project root for the Python build):

| Model | Folder | Purpose |
|---|---|---|
| [IndicTrans2 distilled](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M) | `models/indictrans2/` | English to/from Hindi/Marathi translation |
| [faster-whisper small](https://huggingface.co/Systran/faster-whisper-small) | auto-downloaded on first use | Speech-to-text (ASR) |
| [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) | `models/indic-parler-tts/` | Text-to-speech (TTS) |
| [fastText lid.176.ftz](https://fasttext.cc/docs/en/language-identification.html) | `models/lid.176.ftz` | Language detection |

All models are MIT or Apache-2.0 licensed — free with no usage restrictions.

### Download IndicTrans2

`setup.bat` installs Python packages but does not download model checkpoints. From the project root, set your Hugging Face token in the current terminal and run the downloader:

**macOS / Linux:**

```bash
read -s HF_TOKEN
export HF_TOKEN
.venv/bin/python models_scripts/indictrans2.py
```

**Windows:**

```bat
set HF_TOKEN=your-token-here
venv\Scripts\python.exe models_scripts\indictrans2.py
```

The script downloads the complete `ai4bharat/indictrans2-en-indic-dist-200M` checkpoint into `models/indictrans2/`. Confirm that the directory contains `config.json`, tokenizer files, and model weight files before starting the application. Never commit or hardcode the token. If a token was exposed in a source file or terminal history, revoke it and create a replacement before continuing.

---

## Project structure

```
Samvaadhika/
├── launcher.py          # PyInstaller entry point (standalone exe)
├── samvaadhika.spec     # PyInstaller build spec
├── build.bat            # Developer: build the .exe
├── install.bat          # BAIF IT: install shortcuts (no Python needed)
├── setup.bat            # Developer: Python venv setup
├── run.bat              # Developer: start the app
├── requirements.txt     # Python dependencies
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
│   └── static/          # CSS, JS, images (logo)
├── data/                # SQLite database file (created at runtime)
├── uploads/             # Uploaded files (created at runtime)
├── outputs/             # Translated output files (created at runtime)
├── cache/               # Content-hash and Hugging Face runtime cache
└── models/              # AI model checkpoints (download separately)
```

---

## Features

| Feature | Status |
|---|---|
| Instant text translation (EN / HI / MR) | MVP |
| DOCX translation (format-preserving) | MVP |
| PPTX translation (format-preserving) | MVP |
| Audio to transcript to translation to TTS + SRT | MVP |
| Video to audio extraction to full audio pipeline | MVP |
| Auto language detection + manual override | MVP |
| Async job queue with live status polling | MVP |
| Content-hash dedup (never reprocess same file) | MVP |
| Admin dashboard with translation, language, type, status, and user metrics | MVP |
| Admin user creation, approval, deactivation, and password reset | MVP |
| Domain glossary (agricultural/BAIF terms) | MVP |
| Audit log (who translated what and when) | MVP |
| Standalone Windows .exe (no Python needed) | MVP |
| PDF translation (text-native, tables/grids preserved where detectable) | MVP |
| Scanned PDF OCR (Tesseract) | Best effort |
| XLSX / CSV translation | Stretch goal |
| On-screen text in video (OCR) | Best effort |

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
| View translation metrics and recent activity | `/admin/` |
| Create users and assign `user` or `admin` roles | `/admin/users` |
| Approve new user accounts | `/admin/users` |
| Deactivate users or reset passwords | `/admin/users` |
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

Hugging Face runtime files are cached under `cache/huggingface/` so the application can load local model code without relying on an inaccessible user-level cache. Set `SAMVAADHIKA_DEVANAGARI_FONT` to a `.ttf` or compatible font path when deploying on a machine without a usable Devanagari font.

## PDF formatting behavior

Text-native PDFs with detectable tables or text coordinates are translated into a new PDF that retains the original page size, table/grid geometry, and text placement. Hindi and Marathi text is rendered using a Devanagari-capable font. The output is stored as `translated_<name>.pdf` and can be downloaded from the Jobs page.

For scanned or complex PDFs where usable coordinates cannot be recovered, the result may be marked for review and layout preservation may be incomplete. Tesseract with `eng`, `hin`, and `mar` language data is required for scanned-page OCR.

---

## Responsible technology

- **Privacy** — nothing leaves BAIF's premises; no cloud calls at inference time
- **Audit trail** — every translation is logged with user, timestamp, and IP
- **Confidence flagging** — low-confidence translations are flagged for human review
- **Domain glossary** — prevents mistranslation of sensitive agricultural/veterinary terms
- **Accessibility** — Devanagari rendering tested; TTS output for low-literacy users

---

## Handover for BAIF IT

| Task | How |
|---|---|
| **Backup** | Copy `data/samvaadhika.db` and the `outputs/` folder |
| **Restore** | Replace those files on the new machine and launch the exe |
| **Add a language** | Update `SUPPORTED_LANGUAGES` in `app/config.py` and rebuild |
| **Windows Service** | Use NSSM (prompted during `install.bat`) |
| **Change port** | Set `PORT` in `app/config.py` and rebuild, or set env var `SAMVAADHIKA_PORT` |

---

*Samvaadhika — Tech for Good Hackathon, HSBC x BAIF, 2024*
