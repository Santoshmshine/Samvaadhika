# PDF Translation Formatting Update

## Purpose

This document records the current PDF translation implementation and the proposed changes required to preserve tables, grids, page structure, and basic formatting while translating English content into Hindi or Marathi.

## Confirmed Example: `Class - 6A.pdf`

The uploaded file was a one-page, text-native PDF containing a student table/grid.

Observed characteristics:

- The PDF contains extractable text.
- `pdfplumber` detects one table.
- The PDF has no scanned-page images, so OCR is not required for this file.
- The translation text is correct.
- The generated output is a `.txt` file, so the original grid and page layout cannot be retained.

This is a document-output limitation, not an IndicTrans2 translation-quality failure.

## Current Implementation

### Upload and queue

1. The user uploads a PDF through `POST /upload/file`.
2. `app/routes/translate.py` saves the file under `uploads/` and creates a queued `Job` with `job_type="document"`.
3. `app/worker.py` picks up the job in the in-process worker thread pool.
4. The worker sees the `.pdf` extension and calls `translate_pdf()`.

### Current PDF processing

`app/pipeline.py::translate_pdf()` currently:

1. Opens the PDF with `pdfplumber`.
2. Calls `page.extract_text()` for every page.
3. Uses Tesseract only when a page has no extractable text.
4. Joins all page text into one large string.
5. Calls `translate_text()` once for the complete document.
6. Applies the glossary to the translated string.
7. Writes the result to a plain UTF-8 text file.

`app/worker.py` creates this output path:

```text
outputs/<job-id>/translated_<input-stem>.txt
```

The worker also stores this review note:

```text
PDF translated to plain text - layout not preserved.
```

### Current flow diagram

```text
PDF upload
    |
    v
Queued document job
    |
    v
pdfplumber extracts page text
    |
    +--> no text --> optional Tesseract OCR
    |
    v
One combined text string
    |
    v
IndicTrans2 / Argos / stub translation
    |
    v
Plain TXT output
```

### What the current flow loses

- Table rows and columns
- Grid lines and cell borders
- Cell positions and widths
- Font size, font family, and emphasis
- Page margins and page breaks
- Text alignment
- Headers and footers
- Original PDF page dimensions
- Relationship between translated text and its original coordinates

## Suggested Update

Add a layout-preserving PDF path for text-native PDFs. Keep the current plain-text path as a fallback for PDFs whose layout cannot be reconstructed reliably.

### Recommended strategy

Use the original PDF as the visual base and create a translated PDF by overlaying translated text at the original text or table coordinates.

For table-heavy PDFs such as `Class - 6A`, use this sequence:

1. Detect whether the page has extractable tables with `page.extract_tables()`.
2. Extract table cells together with their bounding boxes using a coordinate-aware table/text extraction method.
3. Translate each cell independently rather than translating the entire page as one string.
4. Draw a white rectangle over the original cell text while leaving borders and grid lines intact.
5. Draw the translated text inside the same cell rectangle.
6. Preserve the original page size, table geometry, and non-text graphics.
7. Save a PDF output instead of only a TXT output.

The implementation should use a PDF writing library already compatible with the project or add a maintained PDF generation/overlay dependency. The writer must support Devanagari fonts and embed the selected font in the output PDF.

### Output policy

Recommended output behavior:

| Input PDF type | Primary output | Fallback or notes |
|---|---|---|
| Text-native PDF with detectable table/grid | Formatted translated PDF | Optional TXT companion |
| Text-native PDF without reliable layout extraction | Formatted coordinate-overlay PDF | Mark uncertain pages for review |
| Scanned PDF | OCR-based formatted PDF where coordinates are available | Plain TXT or review note when OCR/layout reconstruction fails |
| Complex or unsupported PDF | Plain TXT | Explicitly state that layout was not preserved |

The output filename should retain the PDF extension:

```text
outputs/<job-id>/translated_<input-stem>.pdf
```

A companion text file may be generated for accessibility and auditing, but it should not be presented as the only translated document when formatted PDF reconstruction succeeds.

## Before and After Flow

| Stage | Current behavior | Suggested behavior |
|---|---|---|
| Upload | Save PDF and queue document job | Save PDF and queue document job |
| File classification | Select `translate_pdf()` for `.pdf` | Select layout-aware PDF processor for `.pdf` |
| Text extraction | Extract one text string per page | Extract text blocks and table cells with coordinates |
| Table handling | `extract_tables()` is not used by the current translator | Use table structure, cell bounds, and row/column relationships |
| Translation unit | Translate the entire document text | Translate cells/blocks independently, preserving placement |
| Glossary | Apply glossary to the combined translated text | Apply glossary to each translated cell/block |
| Rendering | Write translated text to `.txt` | Overlay translated text onto a PDF page or rebuild a formatted page |
| Borders/grid | Lost | Retained from the original PDF or explicitly redrawn |
| Output | `translated_<name>.txt` | `translated_<name>.pdf`, optionally plus `.txt` |
| Review note | Always says layout was not preserved | Report actual preservation status and any uncertain pages |
| Download UI | Downloads the text output for PDF jobs | Downloads the formatted PDF and optionally the text companion |

## IndicTrans2 and Language Handling

The layout change should not alter the translation model contract:

- English uses `eng_Latn`.
- Hindi uses `hin_Deva`.
- Marathi uses `mar_Deva`.
- `translate_text()` remains the single translation API used by document processors.
- IndicTrans2 remains the preferred local model.
- Argos Translate remains an optional fallback.
- Stub output must never be treated as a successful formatted translation.

Cell-level translation may improve table output because each name, heading, and cell remains attached to its original location. However, translated text can be longer than English text, so the renderer must wrap or shrink text within cell bounds without moving grid lines.

## Dependencies and Assets for the Update

Already used by the current PDF path:

- `pdfplumber` for PDF reading, text extraction, and table detection.
- `pytesseract` for OCR integration.
- External Tesseract executable and language data for scanned PDFs.
- `transformers`, `torch`, and the local IndicTrans2 checkpoint for translation.

Likely additional requirement:

- A PDF writer/overlay library capable of preserving or drawing pages, coordinates, and embedded Devanagari fonts.

The selected PDF writer must be tested with:

- Hindi output
- Marathi output
- Multi-line cell text
- Long names and identifiers
- Existing grid lines
- Page boundaries and margins
- PDF viewers commonly used by BAIF

## Acceptance Criteria

The update should be considered successful when:

1. Uploading `Class - 6A.pdf` produces a PDF output rather than only a TXT output.
2. The output retains the page size and visible table/grid structure.
3. Every original table row remains in the same order.
4. English names and identifiers are translated or retained according to the selected language behavior without merging adjacent cells.
5. Hindi output renders with an embedded or reliably available Devanagari font.
6. Marathi output renders with an embedded or reliably available Devanagari font.
7. A long translated value wraps or scales inside its cell instead of crossing grid lines.
8. PDFs that cannot be reconstructed still produce a clearly labeled plain-text fallback.
9. The job review note accurately reports whether layout preservation succeeded.
10. Existing DOCX, PPTX, audio, video, and text translation flows continue to work.

## Implementation Status

The layout-preserving PDF path is now implemented for text-native PDFs with detectable text tables and coordinate-aware text blocks. The worker produces a formatted `.pdf` output and records the pages processed with layout preservation. Plain-text output remains documented as a fallback for PDFs where usable coordinates cannot be recovered.
