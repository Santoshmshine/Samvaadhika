import sys
from pathlib import Path
import pytest

# Ensure project root is importable when running pytest from the repo
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _has_devanagari(s: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in s)


def test_transliteration_helper_returns_string():
    from app.pipeline import transliterate_text_if_needed

    src = "namaste"
    out = transliterate_text_if_needed(src, "mr")
    assert isinstance(out, str)


def test_transliteration_skips_when_deva_present():
    from app.pipeline import transliterate_text_if_needed

    src = "नमस्ते"
    out = transliterate_text_if_needed(src, "mr")
    assert out == src


def test_transliteration_may_produce_devanagari():
    from app.pipeline import transliterate_text_if_needed

    src = "namaste"
    out = transliterate_text_if_needed(src, "mr")
    # Either unchanged (no lib) or contains Devanagari
    assert _has_devanagari(out) or out == src
