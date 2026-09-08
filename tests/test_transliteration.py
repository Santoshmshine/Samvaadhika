import sys
import threading
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


def test_clean_english_segment_is_not_transliterated_with_english_asr_hint():
    from app.pipeline import detect_and_fix_transliterated_segment

    src = "But imagine instead that you have a special notebook where you can directly store"
    fixed, language = detect_and_fix_transliterated_segment(src, asr_hint="en")

    assert fixed == src
    assert language == "en"


def test_translation_cache_hash_is_versioned():
    from app.pipeline import sha256_text, translation_cache_hash

    text = "My name is Mohit."
    assert translation_cache_hash(text, "en", "hi") != sha256_text(f"en:hi:{text}")
    assert translation_cache_hash(text, "en", "hi") != translation_cache_hash(text, "en", "mr")


def test_translation_preserves_urls_and_newlines():
    from app.pipeline import _translate_preserving_protected_text

    seen = []

    def translate_part(text):
        seen.append(text)
        return text.upper()

    result = _translate_preserving_protected_text(
        "hello https://example.com\nsecond line", translate_part
    )

    assert result == "HELLO https://example.com\nSECOND LINE"
    assert seen == ["hello", "second line"]


def test_english_translation_part_tokenizes_punctuation():
    from app.pipeline import _prepare_translation_part

    assert _prepare_translation_part("Hello 123!", "en") == "Hello 123 !"


@pytest.mark.parametrize(
    ("text", "source", "target", "expected"),
    [
        (
            "It is raining cats and dogs outside.",
            "en",
            "mr",
            "बाहेर मुसळधार पाऊस पडत आहे।",
        ),
        ("ऊँट के मुँह में जीरा।", "hi", "en", "Too little for a great need."),
    ],
)
def test_curated_idioms_preserve_meaning(text, source, target, expected):
    from app.pipeline import _curated_idiom_translation

    assert _curated_idiom_translation(text, source, target) == expected


def test_indictrans2_reuses_model_and_preserves_protected_text(monkeypatch, tmp_path):
    import app.pipeline as pipeline

    class FakeTokenizer:
        def __init__(self):
            self.inputs = []
            self.target_mode_count = 0
            self.input_mode_count = 0

        def __call__(self, text, **kwargs):
            self.inputs.append(text)
            return {"input_ids": [text]}

        def _switch_to_target_mode(self):
            self.target_mode_count += 1

        def decode(self, output, skip_special_tokens):
            return output.upper()

        def _switch_to_input_mode(self):
            self.input_mode_count += 1

    class FakeModel:
        def __init__(self):
            self.generate_calls = []

        def generate(self, **kwargs):
            self.generate_calls.append(kwargs)
            return [kwargs["input_ids"][0].split(" ", 2)[2]]

    tokenizer = FakeTokenizer()
    model = FakeModel()
    load_calls = []

    def get_model(model_dir):
        load_calls.append(model_dir)
        return tokenizer, model, threading.Lock()

    monkeypatch.setattr(pipeline, "_find_model_dir", lambda *args: tmp_path)
    monkeypatch.setattr(pipeline, "_get_translation_model", get_model)

    translated, confidence = pipeline._translate_indictrans2(
        "hello https://example.com\nsecond line", "en", "hi"
    )

    assert translated == "HELLO https://example.com\nSECOND LINE"
    assert confidence == 0.88
    assert len(load_calls) == 1
    assert all(call["num_beams"] == 5 for call in model.generate_calls)
    assert tokenizer.inputs == [
        "eng_Latn hin_Deva hello",
        "eng_Latn hin_Deva second line",
    ]
    assert tokenizer.target_mode_count == tokenizer.input_mode_count == 2
