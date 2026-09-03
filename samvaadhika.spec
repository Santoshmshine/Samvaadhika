# -*- mode: python ; coding: utf-8 -*-
"""
Samvaadhika — PyInstaller spec file
Produces a single-folder distribution (onedir) with one launcher .exe.

Build with:  build.bat   (or: pyinstaller samvaadhika.spec)

Output:  dist/Samvaadhika/Samvaadhika.exe
         dist/Samvaadhika/  <-- everything else bundled here

Why onedir instead of onefile?
  - onefile extracts to a temp folder on every launch (slow, ~10-30 s cold start)
  - onedir launches instantly and is easier for BAIF IT to inspect / back up
  - BAIF IT can drop model checkpoints into dist/Samvaadhika/models/ directly
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Collect all data files that must be bundled ──────────────────────────────

datas = [
    # Jinja2 templates
    ("app/templates",        "app/templates"),
    # Static assets (CSS, JS, images)
    ("app/static",           "app/static"),
]

# Collect Jinja2 template data from the jinja2 package itself
datas += collect_data_files("jinja2")

# SQLAlchemy dialects
datas += collect_data_files("sqlalchemy")

# bcrypt data (passlib was removed)
# datas += collect_data_files("passlib")  # removed — using bcrypt directly

# Transformers model config files (needed for trust_remote_code, tokenizer configs)
datas += collect_data_files("transformers", include_py_files=True)

# sentencepiece data
datas += collect_data_files("sentencepiece")

# Helper: include an entire folder tree (models, ffmpeg, fonts) into datas
from pathlib import Path
def _add_tree(src: str, dest: str):
    p = Path(src)
    if not p.exists():
        return []
    items = []
    for f in p.rglob('*'):
        if f.is_file():
            rel = f.relative_to(p)
            # Skip __pycache__ compiled artifacts (avoid Python-version-specific .pyc files)
            if '__pycache__' in rel.parts:
                continue
            # Datas expects dest to be a directory; provide the relative parent directory
            dest_dir = Path(dest) / rel.parent
            items.append((str(f), str(dest_dir)))
    return items

# Bundle models, ffmpeg binaries, and fonts so the onedir contains them
datas += _add_tree('models', 'models')
datas += _add_tree('ffmpeg', 'ffmpeg')
datas += _add_tree('fonts', 'fonts')

# Include faster_whisper package data (VAD/ONNX assets used at runtime)
datas += collect_data_files("faster_whisper")

# Pillow (PIL) image support for PDF conversion
datas += collect_data_files("PIL")

# Include our local safe tokenizer implementation and build helpers
#datas += [ ("build/safe_tokenization_indictrans.py", "build/safe_tokenization_indictrans.py"),
          # ("build/postbuild_harness.py", "build/postbuild_harness.py") ]

# ── Hidden imports ────────────────────────────────────────────────────────────
# Modules that PyInstaller's static analysis misses because they are
# imported dynamically (e.g. via importlib, __import__, or string names).
# (Moved Parler-TTS / SciPy bundling after hiddenimports declaration)

hiddenimports = [
    # FastAPI / Starlette internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "starlette.routing",
    "starlette.staticfiles",
    "starlette.templating",
    "starlette.middleware.sessions",
    "fastapi.middleware.cors",
    # Jinja2
    "jinja2",
    "jinja2.ext",
    # SQLAlchemy
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.orm",
    # Auth (bcrypt directly, passlib removed)
    "bcrypt",
    "jose",
    "jose.jwt",
    # Multipart (file uploads)
    "multipart",
    "python_multipart",
    # aiofiles (static file serving)
    "aiofiles",
    # Our own app modules
    "app",
    "app.main",
    "app.config",
    "app.database",
    "app.models",
    "app.auth",
    "app.pipeline",
    "app.worker",
    "app.routes",
    "app.routes.auth",
    "app.routes.translate",
    "app.routes.jobs",
    "app.routes.admin",
    # AI / ML packages (lazy-imported in pipeline.py)
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "transformers",
    "transformers.models",
    "transformers.models.auto",
    "transformers.models.auto.modeling_auto",
    "transformers.models.auto.tokenization_auto",
    "sentencepiece",
    "sacremoses",
    "faster_whisper",
    "ctranslate2",
    "pyttsx3",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "comtypes",
    "comtypes.client",
    "numpy",
    "huggingface_hub",
    "safetensors",
    "tokenizers",
    "regex",
    "filelock",
    "tqdm",
    "pdfplumber",
    "docx",
    "pptx",
    "soundfile",
    "fitz",
    "pymupdf",
]

# Add all sqlalchemy submodules (dialects, etc.)
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("transformers")
hiddenimports += collect_submodules("torch")
hiddenimports += collect_submodules("faster_whisper")
hiddenimports += collect_submodules("PIL")

# Additional runtime modules often missed by static analysis
hiddenimports += [
    "onnxruntime",
    "onnx",
    "fasttext",
    "onnxruntime.capi",
    "onnxruntime.capi.onnxruntime_pybind11_state",
]

# Ensure native/packaged assets and runtime packages are collected
datas += collect_data_files("onnxruntime")
datas += collect_data_files("onnx")
datas += collect_data_files("fasttext")

# ── Analysis ──────────────────────────────────────────────────────────────────

# Ensure Parler-TTS and SciPy are bundled (Parler-TTS requires SciPy + compiled extensions)
datas += collect_data_files("scipy")
datas += collect_data_files("parler_tts")
hiddenimports += collect_submodules("parler_tts")
hiddenimports += ["parler_tts"]
# Include faster_whisper package data (VAD/ONNX assets used at runtime)
datas += collect_data_files("faster_whisper")
# Ensure audiotools templates/assets required by Parler-TTS are bundled
datas += collect_data_files("audiotools")

# If PyInstaller misses specific ONNX or model files, explicitly include them.
# Look for ONNX assets under the installed faster_whisper package and for
# fastText language-id models under the local `models/` folder and add them
# to datas so they land in the onedir next to the exe.
try:
    import faster_whisper
    from pathlib import Path
    fw_pkg_dir = Path(faster_whisper.__file__).parent
    assets_dir = fw_pkg_dir / "assets"
    if assets_dir.exists():
        for onnx in assets_dir.rglob("*.onnx"):
            # place under faster_whisper/assets in the dist
            datas.append((str(onnx), str(Path("faster_whisper") / "assets" / onnx.parent.relative_to(assets_dir))))
except Exception:
    # best-effort: continue if package not installed in build env
    pass

# Include any local fastText LID models (common names: lid.*) from repo `models/`
try:
    from pathlib import Path
    repo_models = Path("models")
    if repo_models.exists():
        for lid in repo_models.rglob("lid.*"):
            datas.append((str(lid), "models"))
except Exception:
    pass

# Ensure parler_tts package source files are bundled (TorchScript needs .py source access)
try:
    import parler_tts
    from pathlib import Path
    pt_pkg_dir = Path(parler_tts.__file__).parent
    if pt_pkg_dir.exists():
        for f in pt_pkg_dir.rglob('*'):
            if f.is_file():
                if '__pycache__' in f.parts:
                    continue
                rel = f.relative_to(pt_pkg_dir)
                datas.append((str(f), str(Path('parler_tts') / rel.parent)))
except Exception:
    pass

# Explicitly include audiotools templates used by Parler-TTS
try:
    import audiotools
    from pathlib import Path
    at_pkg_dir = Path(audiotools.__file__).parent
    templates = at_pkg_dir / 'core' / 'templates'
    if templates.exists():
        for f in templates.rglob('*'):
            if f.is_file():
                rel = f.relative_to(at_pkg_dir)
                datas.append((str(f), str(Path('audiotools') / rel.parent)))
except Exception:
    pass

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["move_internal_assets.py"],
    excludes=[
        # Exclude packages not needed at runtime
        "matplotlib",
        "pandas",
        "cv2",            # OpenCV — add back if video OCR is bundled
        "tkinter",
        "test",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Samvaadhika",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # disable UPX to avoid DLL/load issues on some systems
    console=True,       # keep console window so users can see startup progress
                        # change to False for a silent background service
    icon="app/static/images/logo.png",  # .ico preferred; .png accepted by newer PyInstaller
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Samvaadhika",
)
