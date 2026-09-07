# Video Translation (end-to-end)

This document describes the end-to-end flow the repository runs when given a single `.mp4` file as input, from ASR through translation and TTS, and where to find debug artifacts for triage.

**Assumptions & prerequisites**
- Windows environment (dev notes in repo).
- Required external binaries and assets are present under the repo root: `ffmpeg/` (binary), `fonts/` (for subtitle rendering), `fasttext` runtime, and `models/` (ASR/MT/TTS model folders).
- Python dependencies from `requirements.txt` installed in the runtime environment.
- The web worker or CLI runner will place per-job artifacts under `outputs/<job-id>/`.

## High-level pipeline
1. Normalize audio (ffmpeg) → mono, target sample rate.
2. ASR (faster_whisper or Whisper wrapper) producing segments with timestamps and raw text.
3. Language detection (fastText) + heuristics to detect romanized Indic text.
4. Transliteration (Latin→Devanagari) if indicated, or mixed-script normalization.
5. Machine translation (IndicTrans2 via HF Seq2Seq) to target language (e.g., English).
6. Post-processing (glossary application, cleaning) and subtitle generation (SRT).
7. TTS (Parler TTS wrapper) for synthesized audio per-segment or full-file.
8. Multiplex outputs: merged video with translated audio, `subtitles.srt`, per-segment CSV and debug dumps.

## Where code lives
- Pipeline orchestration: `app/pipeline.py` (core steps, ASR/MT/transliteration/TTS). 
- Job orchestration and file I/O: `app/worker.py`.
- Templates / web UI: `app/templates/*` and `app/routes/translate.py`.
- Diagnostic tooling: `tools/analyze_mojibake.py`.

## Per-job outputs (under `outputs/<job-id>/`)
- `subtitles.srt` — translated subtitles with timestamps.
- `translated_audio.wav` or per-segment TTS WAVs (if per-segment synthesis enabled).
- `segment_translations.csv` — CSV with one row per ASR segment, columns include:
  - `segment_index`, `start`, `end`, `orig_raw`, `orig_hex_utf8`, `orig_hex_replace`, `asr_avg_logprob`, `asr_no_speech_prob`, `fixed_text`, `fixed_lang`, `translated_text`, etc.
- `debug_asr/segment_XXXX_raw.txt` and `segment_XXXX_hex_utf8.txt` — raw ASR repr and UTF‑8 hex dump recorded immediately after ASR.
- `debug_parler/` — per-segment Parler tokenizer npy/wav artifacts for TTS debug.

## Running locally (developer)
- To build the onedir distribution:

```powershell
# from repo root on Windows
.
\build.bat
```

- To run a translation job locally (dev server):

```powershell
# Start the app
python launcher.py
# Use the web UI at the configured port or use the translation route to POST an MP4
```

- Quick CLI (example script) for a single MP4 (replace with the repo's runner if provided):

```powershell
python app/worker.py --input myvideo.mp4 --output outputs/test-job
```

## Important implementation details & debugging notes
- Capture raw ASR bytes immediately after transcription into `debug_asr/` to distinguish ASR output vs later corruption.
- Treat Latin script detection as Unicode Latin (including diacritics) when deciding whether to transliterate to Devanagari; ASCII-only heuristics miss romanized Indic text with diacritics.
- `segment_translations.csv` is the canonical per-segment record for triage: check `orig_hex_utf8` to see original byte sequence and `orig_hex_replace` to detect earlier replacement (`0x3f`) losses.
- Parler TTS quirks:
  - We explicitly load `AutoConfig.from_pretrained(model_dir)` and pass it to `from_pretrained(...)` to avoid silent sub-config overwrites.
  - We add a distinct `pad_token` ("<pad>") when missing and attempt to resize model embeddings; fallback to `eos_token` if resizing fails.
  - Tokenization is done with attention masks; `model.generate()` is called with `prompt_attention_mask` only when supported to avoid warnings.

## Common issues & fixes
- Mojibake / mixed script: run `tools/analyze_mojibake.py` against `segment_translations.csv` to see where corruption originates.
- Missing models in onedir: ensure `models/`, `ffmpeg/`, `fonts/`, and `fasttext` assets are copied into the built `samvaadhika` folder by `build.bat` (packaging script must include these directories).
- Parler warnings about decoder config: if you still see warnings, inspect `models/<parler-model>/` for nested `decoder_config.json` and reconcile or remove duplicates.

## Minimal checklist before running a job
- [ ] `ffmpeg/` contains working `ffmpeg` binary for Windows.
- [ ] `models/` contains the required ASR/MT/TTS model subfolders.
- [ ] `fonts/` contains fonts used by subtitles renderer.
- [ ] `requirements.txt` dependencies installed in runtime environment.

## Next improvements to document
- Example cURL / API snippet to submit jobs to the running server.
- Small debugging script that prints all `config.json` files found under a Parler model dir for quick reconciliation.


---
File created: `VIDEO_TRANSLATION.md` — opens at project root.
