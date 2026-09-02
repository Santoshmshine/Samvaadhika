"""
Runtime hook: relocate any bundled `_internal` asset folders (models, ffmpeg, fonts)
to the top-level application folder when running the onedir distribution.

This runs early during frozen app startup and ensures runtime code finds
`dist/Samvaadhika/models/` instead of `dist/Samvaadhika/_internal/models/`.
"""
from pathlib import Path
import shutil
import sys


def _relocate():
    try:
        exe = Path(sys.argv[0]).resolve()
        base = exe.parent
        internal = base / "_internal"
        if not internal.exists():
            return

        for name in ("models", "ffmpeg", "fonts"):
            src = internal / name
            dst = base / name
            if not src.exists():
                continue
            # Ensure destination exists
            dst.mkdir(parents=True, exist_ok=True)
            # Move every item from src into dst (merge)
            for item in src.iterdir():
                try:
                    target = dst / item.name
                    if item.is_dir():
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.move(str(item), str(target))
                    else:
                        # overwrite if exists
                        if target.exists():
                            try:
                                target.unlink()
                            except Exception:
                                pass
                        shutil.move(str(item), str(target))
                except Exception:
                    # best-effort; don't raise in runtime hook
                    continue

        # Try to remove the now-empty internal folder
        try:
            # remove only if empty
            if internal.exists() and not any(internal.iterdir()):
                internal.rmdir()
        except Exception:
            pass
    except Exception:
        return


_relocate()
