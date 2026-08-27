"""
Samvaadhika - AI Processing Pipeline
Handles: language detection  ASR  MT  TTS / subtitles / document re-assembly.

All models run locally (CPU). On first use each model is loaded once and cached
in memory for the lifetime of the process.

Stubs are provided so the app runs end-to-end even before the heavy AI models
are downloaded  each stub logs a clear message and returns a placeholder result.
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
import json

from app.config import (
    BASE_DIR, CACHE_DIR, OUTPUTS_DIR, UPLOADS_DIR, MODELS_DIR,
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    TESSERACT_LANGUAGES, SUPPORTED_LANGUAGES,
)

logger = logging.getLogger("samvaadhika.pipeline")

# Lazy singletons
_whisper_model = None
_lang_detector = None

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
            snapshots = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for snap in snapshots:
                if snap.is_dir() and any(snap.iterdir()):
                    logger.info(f"Resolved HF cache: {base_dir.name} -> {snap}")
                    return snap

    return base_dir


def _find_model_dir(name: str, *alt_names: str) -> Optional[Path]:
    candidates = [name] + list(alt_names)
    for candidate in candidates:
        model_dir = MODELS_DIR_EFFECTIVE / candidate
        if model_dir.exists():
            return _resolve_hf_cache(model_dir)
    return None


# ---------------------------------------------------------------------------
# Lazy model singletons
# ---------------------------------------------------------------------------

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel

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
                logger.warning("fastText model not found (tried lid.176.ftz, lid.176.bin)  using stub.")
                _lang_detector = "stub"
        except Exception as e:
            logger.warning(f"fasttext not available: {e}. Using lightweight fallback detector.")

            class _SimpleLangDetector:
                def predict(self, text: str, k: int = 1):
                    if any('\u0900' <= ch <= '\u097F' for ch in text):
                        return [("__label__hi", 0.99)]
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
    if source_lang == target_lang:
        return text, 1.0

    try:
        return _translate_indictrans2(text, source_lang, target_lang)
    except Exception as e:
        logger.exception("IndicTrans2 unavailable, trying argostranslate fallback.")

    try:
        return _translate_argos(text, source_lang, target_lang)
    except Exception as e:
        logger.exception("argostranslate unavailable. Returning stub translation.")

    return f"[TRANSLATION STUB: {source_lang}{target_lang}] {text}", 0.0


def _translate_indictrans2(text: str, src: str, tgt: str) -> Tuple[str, float]:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    import torch

    model_dir = _find_model_dir(
        "indictrans2",
        "indictrans2-en-indic-dist-200M",
        "indictrans2-indic-en-dist-200M",
        "indictrans2-en-indic-1B",
    )
    if model_dir is None:
        raise FileNotFoundError("IndicTrans2 model not found.")

    lang_map = {"en": "eng_Latn", "hi": "hin_Deva", "mr": "mar_Deva"}
    src_code = lang_map.get(src, "eng_Latn")
    tgt_code = lang_map.get(tgt, "hin_Deva")

    try:
        import importlib
        importlib.import_module('transformers.onnx')
    except Exception:
        if 'transformers.onnx' not in sys.modules:
            mod = types.ModuleType('transformers.onnx')
            mod.__path__ = []
            class OnnxConfig:
                def __init__(self, *a, **k):
                    pass
            class OnnxSeq2SeqConfigWithPast(OnnxConfig):
                pass
            mod.OnnxConfig = OnnxConfig
            mod.OnnxSeq2SeqConfigWithPast = OnnxSeq2SeqConfigWithPast
            mod._has_onnx_support = lambda: False
            utils_mod = types.ModuleType('transformers.onnx.utils')
            def compute_effective_axis_dimension(*a, **k):
                return 1
            utils_mod.compute_effective_axis_dimension = compute_effective_axis_dimension
            sys.modules['transformers.onnx'] = mod
            sys.modules['transformers.onnx.utils'] = utils_mod

    try:
        import transformers.tokenization_utils_base as _tub
        for _cls_name in ('PreTrainedTokenizerBase', 'PreTrainedTokenizer', 'PreTrainedTokenizerFast'):
            if hasattr(_tub, _cls_name):
                _cls = getattr(_tub, _cls_name)
                if not hasattr(_cls, '_special_tokens_map'):
                    setattr(_cls, '_special_tokens_map', {})
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
    except Exception:
        logger.debug("Failed to apply tokenizer compatibility shim")

    logger.info(f"Loading IndicTrans2 from: {model_dir}")
    try:
        sv = Path(model_dir) / "dict.SRC.json"
        tv = Path(model_dir) / "dict.TGT.json"
        if sv.exists():
            with open(sv, 'r', encoding='utf-8') as f:
                _d = json.load(f)
            sample = list(_d.keys())[:20]
            logger.info(f"dict.SRC.json sample keys (repr): {[repr(k) for k in sample]}")
        else:
            logger.info(f"dict.SRC.json not found at: {sv}")
        if tv.exists():
            with open(tv, 'r', encoding='utf-8') as f:
                _d2 = json.load(f)
            sample2 = list(_d2.keys())[:20]
            logger.info(f"dict.TGT.json sample keys (repr): {[repr(k) for k in sample2]}")
        else:
            logger.info(f"dict.TGT.json not found at: {tv}")
    except Exception as _e:
        logger.exception(f"Failed to read vocab files for diagnostics: {_e}")

    tok_kwargs = dict(trust_remote_code=True, use_fast=False)

    def _ensure_special_tokens(vocab_path: Path) -> Optional[Path]:
        try:
            if not vocab_path.exists():
                return None
            with open(vocab_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            def _normalize(k: str) -> str:
                return k.replace('▁', '').strip().strip('"\'')

            special_tokens = ['<unk>', '<pad>', '<s>', '</s>']
            missing = [t for t in special_tokens if t not in data]
            if not missing:
                return vocab_path

            alias_map = {}
            for k in data.keys():
                nk = _normalize(k)
                if nk in missing and nk not in data:
                    alias_map[nk] = k

            if alias_map:
                out = dict(data)
                for canon, aliased in alias_map.items():
                    out[canon] = out[aliased]
                tmpdir = Path(tempfile.mkdtemp())
                outp = tmpdir / vocab_path.name
                with open(outp, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False)
                logger.warning(f"Wrote temporary vocab with canonical tokens: {outp}")
                return outp

            numeric_ids = [int(v) for v in data.values() if str(v).isdigit()]
            maxid = max(numeric_ids) if numeric_ids else 0
            out = dict(data)
            for t in missing:
                maxid += 1
                out[t] = maxid
            tmpdir = Path(tempfile.mkdtemp())
            outp = tmpdir / vocab_path.name
            with open(outp, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False)
            logger.warning(f"Appended missing special tokens and wrote temporary vocab: {outp}")
            return outp
        except Exception as _e:
            logger.exception(f"Failed to ensure special tokens in vocab {vocab_path}: {_e}")
            return vocab_path

    src_vocab = Path(model_dir) / "dict.SRC.json"
    tgt_vocab = Path(model_dir) / "dict.TGT.json"
    # Attempt to repair the snapshot vocab files in-place so the cached
    # tokenizer code and any future loads see canonical token keys.
    def _repair_vocab_inplace(vocab_path: Path) -> Path:
        try:
            if not vocab_path.exists():
                return vocab_path
            with open(vocab_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            def _normalize(k: str) -> str:
                return k.replace('▁', '').strip().strip('"\'')

            out = dict(data)
            # Add canonical normalized keys mapping to original ids
            for k, v in list(data.items()):
                nk = _normalize(k)
                if nk not in out:
                    out[nk] = v

            # Ensure required special tokens exist; append numeric ids if needed
            special_tokens = ['<unk>', '<pad>', '<s>', '</s>']
            numeric_vals = [int(x) for x in out.values() if str(x).isdigit()]
            maxid = max(numeric_vals) if numeric_vals else 0
            changed = False
            for t in special_tokens:
                if t not in out:
                    maxid += 1
                    out[t] = maxid
                    changed = True

            if changed:
                with open(vocab_path, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
                logger.warning(f"Repaired vocab in-place: {vocab_path}")
            return vocab_path
        except Exception as _e:
            logger.exception(f"Failed to repair vocab in-place {vocab_path}: {_e}")
            return vocab_path

    # Repair snapshot files directly (persistent fix)
    safe_src = _repair_vocab_inplace(src_vocab)
    safe_tgt = _repair_vocab_inplace(tgt_vocab)

    try:
        tok_kwargs.update(
            src_vocab_fp=str(safe_src) if safe_src else str(src_vocab),
            tgt_vocab_fp=str(safe_tgt) if safe_tgt else str(tgt_vocab),
            src_spm_fp=str(Path(model_dir) / "model.SRC"),
            tgt_spm_fp=str(Path(model_dir) / "model.TGT"),
        )
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), **tok_kwargs)
        logger.info("IndicTrans2 tokenizer loaded with explicit file paths.")
    except Exception as e:
        logger.exception(f"Loading tokenizer with explicit paths failed: {e}; attempting direct module load and normalized JSON loader.")
        try:
            if safe_src and safe_src.exists():
                with open(safe_src, 'r', encoding='utf-8') as f:
                    src_data = json.load(f)
                sample_keys = list(src_data.keys())[:20]
                logger.debug(f"Sample src vocab keys (reprs): {[repr(k) for k in sample_keys]}")
        except Exception:
            logger.debug("Could not read safe_src vocab for diagnostics.")

        tokenizer_loaded = False
        try:
            import importlib.util
            # Prefer a safe local tokenizer module bundled with the project
            safe_local = Path(__file__).resolve().parents[1] / 'build' / 'safe_tokenization_indictrans.py'
            if safe_local.exists():
                spec = importlib.util.spec_from_file_location('indictrans_local_safe', str(safe_local))
                indic_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(indic_mod)
                if hasattr(indic_mod, 'IndicTransTokenizer'):
                    TokClass = indic_mod.IndicTransTokenizer
                    tokenizer = TokClass(
                        src_vocab_fp=str(safe_src) if safe_src else str(src_vocab),
                        tgt_vocab_fp=str(safe_tgt) if safe_tgt else str(tgt_vocab),
                        src_spm_fp=str(Path(model_dir) / "model.SRC"),
                        tgt_spm_fp=str(Path(model_dir) / "model.TGT"),
                    )
                    logger.info("Loaded local safe IndicTransTokenizer from build/safe_tokenization_indictrans.py")
                    tokenizer_loaded = True

            if not tokenizer_loaded:
                # Prefer tokenization module shipped with the model snapshot (model_dir)
                tok_path = Path(model_dir) / 'tokenization_indictrans.py'
                if not tok_path.exists():
                    # Fallback: search HF modules cache
                    hf_cache = Path.home() / '.cache' / 'huggingface' / 'modules' / 'transformers_modules'
                    if hf_cache.exists():
                        for root, dirs, files in os.walk(hf_cache):
                            if 'tokenization_indictrans.py' in files:
                                tok_path = Path(root) / 'tokenization_indictrans.py'
                                break

                if tok_path and tok_path.exists():
                    spec = importlib.util.spec_from_file_location('indictrans_local', str(tok_path))
                    indic_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(indic_mod)

                    def _patched_load_json(path: str):
                        with open(path, 'r', encoding='utf-8') as f:
                            d = json.load(f)
                        new = {}
                        for k, v in d.items():
                            nk = k.replace('▁', '').strip().strip('"\'')
                            new[nk] = v
                            new[k] = v
                        return new

                    if hasattr(indic_mod, 'IndicTransTokenizer'):
                        indic_mod.IndicTransTokenizer._load_json = staticmethod(_patched_load_json)
                        TokClass = indic_mod.IndicTransTokenizer
                        tokenizer = TokClass(
                            src_vocab_fp=str(safe_src) if safe_src else str(src_vocab),
                            tgt_vocab_fp=str(safe_tgt) if safe_tgt else str(tgt_vocab),
                            src_spm_fp=str(Path(model_dir) / "model.SRC"),
                            tgt_spm_fp=str(Path(model_dir) / "model.TGT"),
                        )
                        logger.info("Loaded IndicTransTokenizer via direct module import with patched JSON loader.")
                    else:
                        logger.debug("tokenization_indictrans.py did not contain IndicTransTokenizer; falling back to AutoTokenizer default.")
                        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
                else:
                    logger.debug("Could not locate tokenization_indictrans.py in HF modules cache; falling back to AutoTokenizer default.")
                    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
        except Exception as e2:
            logger.exception(f"Direct tokenizer module load failed: {e2}; falling back to AutoTokenizer default.")
            # Final fallback: create a minimal tokenizer implementation that
            # uses the snapshot SPM and vocab JSON directly to avoid HF
            # remote/custom-tokenizer import issues.
            try:
                from sentencepiece import SentencePieceProcessor
                import torch

                class MinimalIndicTokenizer:
                    def __init__(self, src_vocab_fp, tgt_vocab_fp, src_spm_fp, tgt_spm_fp):
                        with open(src_vocab_fp, 'r', encoding='utf-8') as f:
                            self.src_encoder = json.load(f)
                        with open(tgt_vocab_fp, 'r', encoding='utf-8') as f:
                            self.tgt_encoder = json.load(f)
                        self.src_decoder = {v: k for k, v in self.src_encoder.items()}
                        self.tgt_decoder = {v: k for k, v in self.tgt_encoder.items()}
                        self.src_spm = SentencePieceProcessor(model_file=str(src_spm_fp))
                        self.tgt_spm = SentencePieceProcessor(model_file=str(tgt_spm_fp))
                        self.unk = '<unk>'
                        self.eos = '</s>'
                        self.pad = '<pad>'
                        # ids
                        self.unk_id = int(self.src_encoder.get(self.unk, 0))
                        self.eos_id = int(self.src_encoder.get(self.eos, 2))

                    def _encode_pieces(self, text: str):
                        return self.src_spm.EncodeAsPieces(text)

                    def __call__(self, text: str, return_tensors=None, padding=True, truncation=True, max_length=512):
                        # text: already tagged like 'src tgt actual_text'
                        parts = text.split(' ', 2)
                        if len(parts) == 3:
                            src_tag, tgt_tag, body = parts
                        else:
                            # fallback
                            src_tag, tgt_tag, body = parts[0], parts[1] if len(parts) > 1 else 'eng_Latn', parts[-1]
                        pieces = [src_tag, tgt_tag] + self._encode_pieces(body)
                        ids = [int(self.src_encoder.get(p, self.unk_id)) for p in pieces]
                        # append eos
                        ids = ids[: max_length - 1] + [self.eos_id]
                        import torch
                        tensor = torch.tensor([ids], dtype=torch.long)
                        attn = torch.ones_like(tensor)
                        return {'input_ids': tensor, 'attention_mask': attn}

                    def _switch_to_target_mode(self):
                        # noop for minimal
                        pass

                    def _switch_to_input_mode(self):
                        pass

                    def decode(self, ids, skip_special_tokens=True):
                        if isinstance(ids, (list, tuple)):
                            seq = ids
                        else:
                            # tensor
                            seq = ids.tolist()
                        # map ids to tokens using tgt_decoder
                        toks = [self.tgt_decoder.get(int(i), '<unk>') for i in seq]
                        # join and replace SPM marker
                        text = ''.join(toks).replace('▁', ' ').strip()
                        return text

                tokenizer = MinimalIndicTokenizer(
                    src_vocab_fp=str(safe_src) if safe_src else str(src_vocab),
                    tgt_vocab_fp=str(safe_tgt) if safe_tgt else str(tgt_vocab),
                    src_spm_fp=Path(model_dir) / 'model.SRC',
                    tgt_spm_fp=Path(model_dir) / 'model.TGT',
                )
                logger.info("Using MinimalIndicTokenizer fallback.")
            except Exception as e3:
                logger.exception(f"Minimal tokenizer fallback failed: {e3}")
                tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)

    # Apply a compatibility shim: some remote model implementations call
    # `tie_weights(recompute_mapping=...)` which older/newer transformers
    # PreTrainedModel.tie_weights may not accept. Patch PreTrainedModel
    # to silently accept and drop `recompute_mapping` for compatibility.
    try:
        import transformers.modeling_utils as _mu
        if hasattr(_mu, 'PreTrainedModel'):
            _orig_tie = getattr(_mu.PreTrainedModel, 'tie_weights', None)

            def _tie_weights_compat(self, *args, **kwargs):
                if _orig_tie is None:
                    return None
                kwargs.pop('recompute_mapping', None)
                return _orig_tie(self, *args, **kwargs)

            setattr(_mu.PreTrainedModel, 'tie_weights', _tie_weights_compat)
            logger.info("Applied tie_weights compatibility shim to transformers.PreTrainedModel")
    except Exception:
        logger.debug("Failed to apply tie_weights shim")

    # Try to patch modeling_indictrans if present so its tie_weights accepts
    # the `recompute_mapping` kwarg which some transformers versions pass.
    try:
        import importlib.util
        mod_path = Path(model_dir) / 'modeling_indictrans.py'
        if not mod_path.exists():
            # fallback: look in HF modules cache
            hf_cache = Path.home() / '.cache' / 'huggingface' / 'modules' / 'transformers_modules'
            if hf_cache.exists():
                for root, dirs, files in os.walk(hf_cache):
                    if 'modeling_indictrans.py' in files:
                        mod_path = Path(root) / 'modeling_indictrans.py'
                        break

        if mod_path and mod_path.exists():
            spec = importlib.util.spec_from_file_location('indictrans_modeling_local', str(mod_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # If the module defines the IndicTrans model class, patch its tie_weights
            cls = getattr(mod, 'IndicTransForConditionalGeneration', None)
            if cls is not None and hasattr(cls, 'tie_weights'):
                _orig = getattr(cls, 'tie_weights')

                def _tie_weights_compat(self, *a, **kw):
                    kw.pop('recompute_mapping', None)
                    return _orig(self, *a, **kw)

                setattr(cls, 'tie_weights', _tie_weights_compat)
                logger.info('Patched IndicTransForConditionalGeneration.tie_weights to accept recompute_mapping')
    except Exception:
        logger.debug('Could not patch modeling_indictrans; proceeding to load model')

    # Attempt to load the IndicTrans model implementation directly from the
    # model snapshot and load weights manually. This avoids calling
    # `from_pretrained(...)` which imports remote/model code that can behave
    # differently inside a frozen exe and trigger signature mismatches.
    model = None
    try:
        import importlib.util
        spec = None
        mod_path = Path(model_dir) / 'modeling_indictrans.py'
        if not mod_path.exists():
            # fallback: search HF modules cache
            hf_cache = Path.home() / '.cache' / 'huggingface' / 'modules' / 'transformers_modules'
            if hf_cache.exists():
                for root, dirs, files in os.walk(hf_cache):
                    if 'modeling_indictrans.py' in files:
                        mod_path = Path(root) / 'modeling_indictrans.py'
                        break

        if mod_path.exists():
            # Some snapshot model files use relative imports (e.g. `from .configuration_indictrans`).
            # Importing them directly fails inside a frozen exe since there is no package
            # context. Workaround: copy snapshot .py files to a temporary directory,
            # rewrite relative imports to absolute, add that temp dir to sys.path,
            # then import the modeling module from there.
            import tempfile
            import shutil

            tempdir = Path(tempfile.mkdtemp(prefix='indictrans_pkg_'))
            try:
                for py in Path(model_dir).glob('*.py'):
                    dst = tempdir / py.name
                    text = py.read_text(encoding='utf-8')
                    # rewrite simple relative imports 'from .name import' -> 'from name import'
                    text = text.replace('from .', 'from ')
                    text = text.replace('import .', 'import ')
                    dst.write_text(text, encoding='utf-8')

                # Ensure tempdir is importable
                sys.path.insert(0, str(tempdir))
                spec = importlib.util.spec_from_file_location('indictrans_modeling_local', str(tempdir / 'modeling_indictrans.py'))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cls = getattr(mod, 'IndicTransForConditionalGeneration', None)
            except Exception:
                # cleanup tempdir on failure
                try:
                    sys.path = [p for p in sys.path if p != str(tempdir)]
                except Exception:
                    pass
                raise
            if cls is not None:
                # Patch tie_weights to accept recompute_mapping kwarg
                if hasattr(cls, 'tie_weights'):
                    _orig_tie = getattr(cls, 'tie_weights')

                    def _tie_weights_compat(self, *a, **kw):
                        kw.pop('recompute_mapping', None)
                        return _orig_tie(self, *a, **kw)

                    setattr(cls, 'tie_weights', _tie_weights_compat)

                # Load config and instantiate
                from transformers import AutoConfig
                cfg = AutoConfig.from_pretrained(str(model_dir))
                model = cls(cfg)

                # Load weights from safetensors or pytorch_model.bin
                weights_loaded = False
                try:
                    # safetensors (preferred)
                    from safetensors.torch import load_file as load_safetensors
                    sf = Path(model_dir) / 'pytorch_model.safetensors'
                    if sf.exists():
                        state = load_safetensors(str(sf))
                        model.load_state_dict(state, strict=False)
                        weights_loaded = True
                except Exception:
                    weights_loaded = False

                if not weights_loaded:
                    # Try PyTorch bin
                    pb = Path(model_dir) / 'pytorch_model.bin'
                    if pb.exists():
                        import torch as _torch
                        state = _torch.load(str(pb), map_location='cpu')
                        # state may be a dict with 'state_dict' key
                        if 'state_dict' in state:
                            state = state['state_dict']
                        model.load_state_dict(state, strict=False)
                        weights_loaded = True

                if not weights_loaded:
                    logger.warning('Could not find safetensors or pytorch_model.bin in snapshot; falling back to AutoModelForSeq2SeqLM.from_pretrained')
                    model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), trust_remote_code=True)
    except Exception as _e:
        logger.exception(f'Failed to load IndicTrans model directly: {_e}; falling back to AutoModelForSeq2SeqLM.from_pretrained')
        model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), trust_remote_code=True)

    model.eval()

    tagged_text = f"{src_code} {tgt_code} {text}"
    inputs = tokenizer(tagged_text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_length=512, num_beams=1, use_cache=False)

    tokenizer._switch_to_target_mode()
    translated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    tokenizer._switch_to_input_mode()
    return translated, 0.85


def _translate_argos(text: str, src: str, tgt: str) -> Tuple[str, float]:
    import argostranslate.package
    import argostranslate.translate

    installed = argostranslate.translate.get_installed_languages()
    src_lang = next((l for l in installed if l.code == src), None)
    tgt_lang = next((l for l in installed if l.code == tgt), None)

    if src_lang is None or tgt_lang is None:
        raise RuntimeError(f"Argostranslate language pair {src}{tgt} not installed.")

    translation = src_lang.get_translation(tgt_lang)
    result = translation.translate(text)
    return result, 0.6


def apply_glossary(text: str, source_lang: str, target_lang: str, db) -> str:
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


def transcribe_audio(audio_path: Path, language: Optional[str] = None) -> Tuple[list, str]:
    model = _get_whisper()
    if model == "stub":
        logger.warning("ASR stub: returning placeholder transcript.")
        return [{"start": 0.0, "end": 5.0, "text": "[ASR not available  install faster-whisper]"}], "en"

    try:
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_iter]
        return segments, info.language
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        raise


def synthesize_speech(text: str, language: str, output_path: Path) -> bool:
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
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer
    import soundfile as sf

    # Minimal loader — actual model selection omitted for brevity; keep stub
    logger.warning("Parler-TTS path used, but detailed loader not implemented in this repair.")
    return False


def _tts_pyttsx3(text: str, language: str, output_path: Path) -> bool:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        return True
    except Exception as e:
        logger.warning(f"pyttsx3 TTS failed: {e}")
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


def _insert_pdf_text(page, rect, text: str, font_path: Optional[Path], fontsize: float) -> bool:
    """Render translated text as an image so Devanagari shaping works reliably."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    scale = 3
    width = max(1, int(rect.width * scale))
    height = max(1, int(rect.height * scale))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = None
    if font_path:
        try:
            font = ImageFont.truetype(str(font_path), max(8, int(fontsize * scale)), index=0)
        except Exception:
            font = None
    if font is None:
        font = ImageFont.load_default()

    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > width - 8:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if not lines:
        return False

    line_height = max(1, int(fontsize * scale * 1.15))
    draw.multiline_text((4, 1), "\n".join(lines), font=font, fill="black", spacing=0)
    stream = BytesIO()
    image.save(stream, format="PNG")
    page.insert_image(rect, stream=stream.getvalue(), overlay=True)
    return True


def translate_pdf(input_path: Path, output_path: Path, source_lang: str, target_lang: str, db) -> Tuple[bool, str]:
    """
    Translate a PDF while preserving its page geometry and table/grid layout.
    Returns (success, notes).
    """
    try:
        import fitz
        import pdfplumber
        output_path.parent.mkdir(parents=True, exist_ok=True)
        formatted_pages = 0
        fallback_pages = 0

        # Prefer a system or deployment-provided Devanagari font for Hindi/Marathi.
        font_candidates = [
            os.environ.get("SAMVAADHIKA_DEVANAGARI_FONT", ""),
            "/System/Library/Fonts/Kohinoor.ttc",
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
            "C:/Windows/Fonts/mangal.ttf",
        ]
        font_path = next((Path(p) for p in font_candidates if p and Path(p).exists()), None)
        formatted_doc = fitz.open(str(input_path))

        with pdfplumber.open(str(input_path)) as pdf:
            for page_number, source_page in enumerate(pdf.pages):
                output_page = formatted_doc[page_number]
                table_cells = []
                for table in source_page.find_tables():
                    table_cells.extend(cell for row in table.rows for cell in row.cells if cell)

                if table_cells:
                    translated_any = False
                    for x0, top, x1, bottom in table_cells:
                        cell_rect = fitz.Rect(x0, top, x1, bottom)
                        cell_text = source_page.crop((x0, top, x1, bottom)).extract_text() or ""
                        if not cell_text.strip():
                            continue
                        translated, _ = translate_text(cell_text, source_lang, target_lang)
                        translated = apply_glossary(translated, source_lang, target_lang, db)
                        words = output_page.get_text("words", clip=cell_rect)
                        if words:
                            text_rect = fitz.Rect(
                                min(word[0] for word in words) - 1,
                                min(word[1] for word in words) - 1,
                                max(word[2] for word in words) + 1,
                                max(word[3] for word in words) + 1,
                            ) & cell_rect
                            output_page.draw_rect(text_rect, color=None, fill=(1, 1, 1), overlay=True)
                        translated_any = _insert_pdf_text(
                            output_page,
                            fitz.Rect(cell_rect.x0 + 2, cell_rect.y0 + 1, cell_rect.x1 - 2, cell_rect.y1 - 1),
                            translated,
                            font_path,
                            max(5, min(10, (bottom - top) * 0.42)),
                        ) or translated_any
                    if translated_any:
                        formatted_pages += 1
                        continue

                # For non-table text-native pages, preserve each text line's position.
                words = source_page.extract_words(keep_blank_chars=True, use_text_flow=True)
                lines = {}
                for word in words:
                    key = (round(word["top"], 1), round(word["bottom"], 1))
                    lines.setdefault(key, []).append(word)
                translated_any = False
                for (top, bottom), line_words in lines.items():
                    line_words.sort(key=lambda word: word["x0"])
                    original = " ".join(word["text"] for word in line_words).strip()
                    if not original:
                        continue
                    translated, _ = translate_text(original, source_lang, target_lang)
                    translated = apply_glossary(translated, source_lang, target_lang, db)
                    text_rect = fitz.Rect(
                        min(word["x0"] for word in line_words), top,
                        max(word["x1"] for word in line_words), bottom,
                    )
                    output_page.draw_rect(text_rect, color=None, fill=(1, 1, 1), overlay=True)
                    translated_any = _insert_pdf_text(
                        output_page,
                        text_rect,
                        translated,
                        font_path,
                        max(5, min(11, bottom - top)),
                    ) or translated_any
                if translated_any:
                    formatted_pages += 1
                else:
                    fallback_pages += 1

        if fallback_pages:
            logger.warning("%d PDF page(s) had no coordinate-aware text; layout may be incomplete.", fallback_pages)
        formatted_doc.save(str(output_path), garbage=4, deflate=True)
        formatted_doc.close()
        return True, f"PDF translated with layout preservation on {formatted_pages} page(s)."
    except Exception as e:
        logger.error(f"PDF translation failed: {e}")
        raise


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
