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
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# `Tree` helper was introduced in newer PyInstaller versions. Provide a
# lightweight fallback for older PyInstaller builds that don't expose it.
try:
    from PyInstaller.utils.hooks import Tree  # type: ignore
except Exception:
    def Tree(src, prefix=None):
        """Fallback: convert a directory tree into datas-style tuples.

        Returns a list of `(source_path, dest_dir)` tuples suitable for
        appending to `datas`.
        """
        src_path = Path(src)
        if not src_path.exists():
            return []
        out = []
        for p in src_path.rglob('*'):
            if p.is_file():
                # destination directory inside the bundle (prefix/<relative parent>)
                rel_parent = p.parent.relative_to(src_path)
                dest_dir = os.path.join(prefix or '', str(rel_parent))
                out.append((str(p), dest_dir))
        return out

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

# Include local models folder, fonts and ffmpeg runtime so they are bundled
# into the onedir distribution. This allows large model files and ffmpeg
# binaries to be shipped alongside the executable.
datas += Tree("models", prefix="models") if Path("models").exists() else []
datas += Tree("fonts", prefix="fonts") if Path("fonts").exists() else []
datas += Tree("ffmpeg", prefix="ffmpeg") if Path("ffmpeg").exists() else []

# Ensure fastText language-id model files are explicitly included when present
if Path("models/lid.176.ftz").exists():
    datas += [(str(Path("models") / "lid.176.ftz"), "models")]
if Path("models/lid.176.bin").exists():
    datas += [(str(Path("models") / "lid.176.bin"), "models")]

# ── Hidden imports ────────────────────────────────────────────────────────────
# Modules that PyInstaller's static analysis misses because they are
# imported dynamically (e.g. via importlib, __import__, or string names).

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
    # fastText language detector
    "fasttext",
    "fasttext.util",
]

# Add all sqlalchemy submodules (dialects, etc.)
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("transformers")
hiddenimports += collect_submodules("torch")
hiddenimports += collect_submodules("faster_whisper")

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude packages not needed at runtime
        "matplotlib",
        "pandas",
        "scipy",
        "PIL",            # Pillow — add back if OCR is bundled
        "cv2",            # OpenCV — add back if video OCR is bundled
        "tkinter",
        "test",
        # CUDA / GPU-only vendor modules that cause ModuleNotFoundError
        # when building on CPU-only systems. Safe to exclude for CPU builds.
        "cuda",
        "torch._vendor.quack",
        "cupy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
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
    upx=True,           # compress with UPX if available (reduces size ~30%)
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
    upx=True,
    upx_exclude=[],
    name="Samvaadhika",
)
