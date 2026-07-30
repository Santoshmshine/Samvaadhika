"""
Samvaadhika — PyInstaller entry point.

When PyInstaller bundles the app, this file is the __main__ module.
It:
  1. Fixes sys._MEIPASS paths so templates/static are found at runtime.
  2. Initialises the database (creates tables + default admin).
  3. Finds a free port (auto-increments if default is busy).
  4. Opens the browser automatically.
  5. Starts Uvicorn in the same process (no subprocess needed).

The user just double-clicks Samvaadhika.exe — no Python, no terminal.
"""

import multiprocessing
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


# ── PyInstaller runtime path fix ──────────────────────────────────────────────
# When frozen, all bundled files live under sys._MEIPASS.
# We add it to sys.path so our `app` package is importable.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    # Also set the working directory to the folder containing the .exe
    # so that data/, uploads/, outputs/, models/ are created next to it.
    EXE_DIR = Path(sys.executable).parent
    os.chdir(EXE_DIR)
else:
    BASE_DIR = Path(__file__).parent
    EXE_DIR = BASE_DIR

sys.path.insert(0, str(BASE_DIR))

# Override config paths BEFORE importing app modules
os.environ.setdefault("SAMVAADHIKA_BASE", str(EXE_DIR))


# ── Patch config to use exe-relative paths ────────────────────────────────────
import app.config as _cfg  # noqa: E402

_cfg.BASE_DIR      = EXE_DIR
_cfg.DATA_DIR      = EXE_DIR / "data"
_cfg.UPLOADS_DIR   = EXE_DIR / "uploads"
_cfg.CACHE_DIR     = EXE_DIR / "cache"
_cfg.OUTPUTS_DIR   = EXE_DIR / "outputs"
_cfg.MODELS_DIR    = EXE_DIR / "models"
_cfg.STATIC_DIR    = BASE_DIR / "app" / "static"
_cfg.TEMPLATES_DIR = BASE_DIR / "app" / "templates"
_cfg.DATABASE_URL  = f"sqlite:///{_cfg.DATA_DIR}/samvaadhika.db"
_cfg.LOG_FILE      = _cfg.DATA_DIR / "samvaadhika.log"

for d in [_cfg.DATA_DIR, _cfg.UPLOADS_DIR, _cfg.CACHE_DIR,
          _cfg.OUTPUTS_DIR, _cfg.MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── Logging ───────────────────────────────────────────────────────────────────
import logging  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(_cfg.LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("samvaadhika.launcher")


# ── Port utilities ────────────────────────────────────────────────────────────
def _is_port_free(host: str, port: int) -> bool:
    """Check if a TCP port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def _find_free_port(host: str, start_port: int, max_tries: int = 20) -> int:
    """Find the first free port starting from start_port."""
    for offset in range(max_tries):
        port = start_port + offset
        if _is_port_free(host, port):
            return port
    raise RuntimeError(
        f"No free port found in range {start_port}-{start_port + max_tries - 1}. "
        f"Close other applications or set SAMVAADHIKA_PORT environment variable."
    )


# ── Database init ─────────────────────────────────────────────────────────────
def _init():
    from app.database import init_db
    init_db()
    logger.info("Database initialised.")


# ── Browser opener (waits for server to be ready) ────────────────────────────
def _open_browser(port: int):
    import urllib.request
    url = f"http://localhost:{port}"
    for _ in range(30):          # try for up to 15 seconds
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            webbrowser.open(url)
            logger.info(f"Browser opened at {url}")
            return
        except Exception:
            time.sleep(0.5)
    logger.warning("Could not confirm server ready — opening browser anyway.")
    webbrowser.open(url)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Required for PyInstaller + multiprocessing on Windows
    multiprocessing.freeze_support()

    host = os.environ.get("SAMVAADHIKA_HOST", _cfg.HOST)
    preferred_port = int(os.environ.get("SAMVAADHIKA_PORT", _cfg.PORT))

    # Find a free port (auto-increment if preferred is busy)
    port = _find_free_port(host, preferred_port)
    if port != preferred_port:
        logger.info(f"Port {preferred_port} is busy, using port {port} instead.")

    logger.info(f"Samvaadhika v{_cfg.APP_VERSION} starting on {host}:{port}")
    _init()

    # Open browser in background thread after server is ready
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()

    # Start Uvicorn — this blocks until the user closes the window
    import uvicorn  # noqa: E402
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        # No --reload in production exe
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Print the full traceback so the console window shows the error
        print("\n" + "=" * 60)
        print("SAMVAADHIKA ERROR — the application failed to start.")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        # Log to file as well
        try:
            logger.exception("Fatal error during startup")
        except Exception:
            pass
        # Keep the console window open so the user can read the error
        if getattr(sys, "frozen", False):
            print("\nPress Enter to close this window...")
            input()
        sys.exit(1)
