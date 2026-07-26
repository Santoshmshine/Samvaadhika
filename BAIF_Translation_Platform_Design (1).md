# Offline Multilingual Translation Platform for BAIF
### Tech for Good Hackathon — Solution Design

---

## 1. Problem framing

BAIF runs eLearning modules for an audience that spans field staff and farmers as well as office staff. Today that content is effectively locked to whatever language it was authored in. The ask is a tool that takes text, audio, or video, and produces Hindi/Marathi/English versions of it — text, dubbed speech, and subtitles — entirely on a BAIF-owned Windows 11 machine, with zero per-use cost and zero dependency on HSBC or any cloud service.

Three constraints shape every decision below:
- **Open-source only, on-prem only.** No paid APIs (no Google/Azure/AWS translation or speech services), no calls out to the internet at inference time.
- **Modest hardware.** i5 11th-gen+ / Ryzen 5, 16 GB RAM, no GPU mentioned — so every model has to run acceptably on CPU.
- **"Keep it simple."** The brief explicitly asks for a lightweight, minimalist build, not a microservices platform. That single line drives a lot of the architecture choices here — every place we could reach for Docker/Kubernetes/Redis/Celery, we instead reach for "one Python process + a file on disk."

---

## 2. Architecture overview

The system is one application with three layers, all running on a single machine (or the file server, with other PCs hitting it over the LAN browser):

| Layer | Responsibility |
|---|---|
| **Input & access** | Web UI (upload, translate-now box), login/roles, job queue |
| **AI pipeline** | Language ID → ASR (speech-to-text) → MT (translation) → TTS / subtitle / document re-assembly, plus OCR for scans and on-screen text in video |
| **Storage & reuse** | SQLite for metadata/users/audit log, a file-based cache keyed by content hash so a file already translated is never reprocessed |

There's no separate "backend server" and "database server" and "queue server" — it's a single FastAPI process, a SQLite file, and a folder of cached outputs. That's deliberate: fewer moving parts to install, fewer things that can fail on a machine with no IT admin watching it, and nothing that needs internet access to run.

---

## 3. Tech stack (all open source, CPU-friendly)

| Function | Choice | Why |
|---|---|---|
| Speech-to-text (ASR) | **faster-whisper** (Whisper + CTranslate2, int8 quantized) for general robustness; **AI4Bharat IndicConformer / IndicWhisper** (MIT-licensed checkpoints) for Hindi/Marathi accuracy | Both confirmed MIT — free with no restrictions; CPU-quantized for the available hardware |
| Translation (MT) | **AI4Bharat IndicTrans2** (distilled variant) | Purpose-built for English↔Indic and Indic↔Indic, including Hindi and Marathi; the distilled model is small enough for CPU inference; trained to preserve meaning rather than do literal word-swap, which directly addresses BAIF's "translate for meaning" requirement |
| Text-to-speech (TTS) | **AI4Bharat Indic Parler-TTS** | Apache-2.0 licensed (verified) — free to use, no commercial restriction; covers Hindi and Marathi voices |
| OCR (scanned PDFs, on-screen video text) | **Tesseract OCR** with Hindi (`hin`) + Marathi (`mar`) + English (`eng`) language packs | Apache-2.0, mature Devanagari support |
| Language detection | **fastText `lid.176`** (lightweight) | Tiny model, near-instant, good enough to distinguish Hindi/Marathi/English before routing |
| Document parsing (DOCX/PPTX/XLSX) | **python-docx**, **python-pptx**, **openpyxl** | MIT-licensed, edit text runs in place so formatting/layout survives translation |
| PDF text & layout | **pdfplumber** for extraction (MIT/BSD); render-only use of PyMuPDF if needed | Avoids leaning on PyMuPDF's AGPL license for the core extraction path — AGPL is open-source but its copyleft terms are worth avoiding if BAIF ever wants to keep parts of the codebase closed |
| Subtitles | **ffmpeg** (audio/video extraction, burned-in captions) + **pysubs2** (SRT/VTT generation) | Industry-standard, free, scriptable |
| App backend | **FastAPI** + **Uvicorn**, server-rendered **Jinja2** templates + light JS | No Node build pipeline, no internet needed to assemble the frontend — keeps the "avoid tech depth" instruction front and center |
| Data store | **SQLite** (single file) | Zero-config, no DB server to install or patch, trivial to back up (copy one file) |
| Background jobs | A simple **job table in SQLite + a worker thread pool** in the same process | Async processing without standing up Redis/Celery; if BAIF later wants this distributed across machines, this is the one piece that would be swapped out |
| Packaging / deployment | Python bundled via PyInstaller or an embeddable distribution, installed as a **Windows Service** (e.g. via NSSM) so it survives reboots without IT intervention | Runs as `http://<machine-name>:port` in a browser — works for a single standalone PC or for everyone on the LAN if installed on the file server |

**Resource budget (rough, to be validated by benchmarking during build):** IndicTrans2 distilled + a quantized Whisper-small + a TTS model + Tesseract, loaded together, should sit in roughly 3–5 GB of RAM — comfortably inside the 16 GB envelope with room for Windows and concurrent jobs. Throughput (e.g. how long a 30-minute audio file takes to process on 6 CPU cores) needs to be measured on real BAIF hardware before committing to a "max wait time" promise in the demo — CPU-only speech models are usably fast for batch/async work, but not instant, which is exactly why the brief asks for async job status rather than a spinner.

---

## 4. Processing pipeline by input type

**Short text (the one place that must feel instant):**
Text in → language ID → IndicTrans2 → translated text out. Runs in-process, target latency low single-digit seconds. If the full offline model genuinely can't hit acceptable latency on a given machine, the request drops into the same async queue as everything else with a visible "queued" state — graceful degradation rather than a hung UI.

**Audio file (≤30 min, ≤50 MB compressed / 150 MB WAV):**
Validate format/size/duration → ffmpeg normalizes to a working WAV → chunked ASR transcription → IndicTrans2 on the transcript → TTS renders translated audio → outputs: translated text, translated audio file, optional SRT/VTT timed to the original audio.

**Video file (≤15 min, ≤200 MB, 720p/1080p):**
ffmpeg extracts the audio track → same ASR/MT/TTS pipeline as audio → subtitle file generated and either delivered as a sidecar SRT/VTT or burned in via ffmpeg → **on-screen text/graphics** (signage, captions baked into the footage) are handled as a separate, explicitly best-effort step: sample frames at intervals, run Tesseract on each sampled frame, translate any detected text, and either overlay it back on the frame or surface it as an extra subtitle track. This is flagged in the UI as lower-confidence than spoken-word translation, since small, stylised, or fast-moving on-screen text is genuinely hard for OCR.

**Documents (PDF / DOCX / PPTX / XLSX-CSV):**
MVP prioritises **DOCX and PPTX** first (these map most directly to BAIF's eLearning authoring formats), then PDF, with XLSX/CSV as a stretch goal — explicitly scoped that way per the brief's "prioritise 3–4, be explicit" instruction. Native text runs are extracted, translated, and written back into the original structure so formatting/layout survives as "format-preserving, best effort." Scanned PDFs route through Tesseract OCR first; if OCR confidence is too low, the file is flagged with a clear message and a fallback path (e.g., "manually re-key this page" or "request a text-native version") rather than silently producing garbage.

---

## 5. Must-have features — how each is covered

| Requirement | Design answer |
|---|---|
| Offline short-text translation | In-process IndicTrans2 call, no network hop, queue + degrade gracefully if latency targets aren't met on a given machine |
| File translation: PDF + DOCX + PPTX + XLSX/CSV | DOCX + PPTX as MVP priority, PDF next, XLSX/CSV stretch — each documented explicitly rather than implied |
| OCR for scanned PDFs | Tesseract with pre-processing (deskew/binarize); explicit low-confidence flag + fallback workflow when it can't cope |
| Auto source-language detection + user-selected target | fastText language ID on upload, target language is a simple dropdown |
| Async processing with visible status | SQLite-backed job table: Queued → Processing → Completed/Failed, polled by the UI, with an in-app notification when done |
| Download in original format (best effort) | Re-injection into the original DOCX/PPTX/XLSX structure; PDF and anything format-fragile is labelled "best effort" rather than guaranteed |
| Admin-approved access + roles | Two roles — Admin (approves users, manages glossary, views audit log) and Authorised User (uploads/translates within granted scope); new accounts sit in a pending state until an Admin approves them |

---

## 6. Translation quality — meaning over mechanics

BAIF specifically flagged "translation checks for meaning, not regular conversion." Three things address that directly:
1. **Model choice** — IndicTrans2 is trained for semantic translation between Indian languages rather than literal substitution, which already puts it ahead of a naive dictionary-style approach.
2. **Domain glossary** — agricultural/veterinary terminology (and BAIF-specific program names) gets a small override dictionary so domain terms translate consistently across modules rather than drifting module to module.
3. **Confidence flagging, not silent failure** — segments where the model's own confidence is low (or where a back-translation check diverges significantly from the source) get visibly flagged for human review rather than shipped as if they were certain. This also gives BAIF L&D staff a lightweight review queue instead of having to re-watch every translated video end to end.

---

## 7. Responsible technology (explicit, not a footnote)

- **Privacy** — nothing leaves BAIF's premises; no cloud calls at inference time; role-based access controls who can see what; an audit log records who translated what and when.
- **Bias & fairness** — the domain glossary and human-review queue exist precisely to catch mistranslation of sensitive terms (gender, caste-related, or culturally loaded vocabulary) before they reach learners; model selection is checked against published Indic-language benchmarks rather than assumed to be fine.
- **Safety** — uploaded files are processed in a sandboxed working directory and validated against the documented format/size/duration limits before anything touches the AI pipeline, reducing the blast radius of a malformed or oversized file.
- **Accessibility** — UI text in plain language for users with lower digital literacy, captions for hearing-impaired learners, voice output (TTS) for low-literacy learners, and screen-reader-friendly markup. Devanagari rendering is tested explicitly since it's easy to get font fallback wrong on a stock Windows install.

---

## 8. Edge cases considered

- **Audio quality** — field recordings with background noise, wind, or multiple overlapping speakers; ASR confidence scoring surfaces low-quality transcripts rather than presenting them as ground truth.
- **Code-mixed speech** — Hindi/Marathi speech with English agricultural terms mixed in (very common in field training); glossary and language-ID-per-segment (rather than per-file) help here.
- **Hindi vs Marathi ambiguity** — both use Devanagari script, so short or ambiguous text snippets can confuse language ID; the UI allows a manual override when auto-detection is uncertain.
- **Oversized/over-length files** — graceful rejection with a clear message and (where feasible) a "split this file" suggestion, rather than a silent crash.
- **Corrupted or unsupported files** — validated at upload before any processing starts.
- **Duplicate uploads** — content-hash based dedup feeds the reuse/cache layer, so the same file translated twice doesn't burn compute twice.
- **Interrupted processing** (power cut, app restart) — job status persisted in SQLite so an interrupted job is visibly "failed/incomplete" and can be safely re-queued, not silently lost.
- **Concurrent access on a shared file server** — file-locking on the shared cache/output directory to avoid two users colliding on the same file.
- **Storage growth** — BAIF wants to keep past translations for reuse, so a retention/cleanup policy (e.g., admin-configurable, not auto-deleting anything by default) is part of the design rather than an afterthought.

---

## 9. Scalability & production readiness

The MVP intentionally runs as a single process on a single machine — that's what "lightweight, minimalist, deployed in production" calls for, and it matches the actual deployment target (a standalone PC or file server, not a server farm). The pipeline stages are still cleanly separated internally (ingestion → ASR → MT → TTS/OCR → storage), so if BAIF's needs grow — more concurrent users, more languages, heavier video volumes — the worker piece can be pulled out to run on a second machine without redesigning the rest. IndicTrans2 also already supports many more Indian languages than the three in scope today, so adding a language later is a configuration change, not a rebuild.

---

## 10. MVP scope for the hackathon vs. roadmap

**In scope for the demo:**
- Text translation (instant, offline)
- DOCX + PPTX file translation, format-preserving
- Audio transcription → translation → TTS + SRT/VTT subtitles
- Auto language detection + manual override
- Async job queue with visible status
- Admin/Authorised User roles with approval workflow
- Reuse cache (hash-based dedup)

**Explicitly deferred / flagged as best-effort:**
- PDF and XLSX/CSV translation (stretch goal, documented as such)
- OCR for scanned PDFs (basic pass, documented limitations)
- On-screen text/image translation inside video (best-effort, lower confidence, clearly labelled)
- Multi-machine/distributed deployment (architecture supports it later; not built for the hackathon)

---

## 11. Mapping to the evaluation criteria

| Criterion | Where it's addressed |
|---|---|
| **Overall impact** | Directly targets BAIF's stated problem — eLearning content locked out of Hindi/Marathi for non-English-first learners (§1, §6) |
| **Innovation** | Reuse/cache layer, confidence-flagged human-review loop, and the on-screen-text-in-video pass go beyond a bare "translate this file" tool |
| **Translation feasibility & UX** | IndicTrans2 for meaning-preserving translation; simple upload → translate → download flow; auto-detect + manual override (§4, §6) |
| **Scalability** | Single-machine MVP with a pipeline architecture that scales out later without a rebuild (§9) |
| **Responsible tech** | Privacy, bias, safety, accessibility addressed explicitly, not as an afterthought (§7) |
| **Delivery quality** | Working demo + this design doc + handover docs + training session for BAIF IT, as the brief requires (§12) |

---

## 12. Handover plan (post-selection)

Per BAIF's stated requirement: complete source code transfer to BAIF IT, written handover documentation (setup, model files, glossary management, backup/restore of the SQLite file and cache), and a training/knowledge-transfer session for BAIF IT staff covering day-to-day operation (approving users, monitoring job queue, adding new domain-glossary terms) and basic troubleshooting.

---

## 13. Open questions / risks to validate during build

- **Model licensing — verified.** IndicTrans2 (MIT), IndicConformer/IndicWhisper (MIT), Indic Parler-TTS (Apache-2.0), faster-whisper (MIT), and Tesseract (Apache-2.0) are all confirmed free with no usage restrictions, satisfying BAIF's zero-cost, open-source-only requirement. One nuance to carry into implementation: use the MIT-licensed `indic-conformer-600m-multilingual` checkpoint specifically — an older NeMo-based IndicConformer checkpoint on Hugging Face is CC-BY-4.0 instead (still free, just needs attribution rather than being unrestricted).
- **Real-world latency on BAIF's actual hardware** — the resource/latency estimates here are reasoned from known CPU-inference behavior of these model families, not yet benchmarked on a BAIF machine; this should be one of the first things validated once test hardware is available.
- **OCR accuracy on real field-recorded video** — frame-sampled OCR on agricultural demo footage (often handheld, variable lighting) will likely need tuning; worth setting expectations with BAIF as "best effort" up front rather than over-promising.
