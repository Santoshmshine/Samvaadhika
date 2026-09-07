# Test Run 8 Failure Details

## Overview

Test Run 8 executed all 37 browser cases against the updated localhost application. Thirty-five passed and two failed. There were no `Needs Review` or `Not Run` cases.

| Case | Area | Status | Severity |
|---|---|---|---|
| TT-09 | Maximum-length translation | Failed | High |
| TT-28 | Devanagari numeral preservation | Failed | Medium |

## TT-09: Maximum-Length Request Blocks Processing

### Input

- Source language: English
- Target language: Hindi
- Source: exactly 10,000 ASCII characters

### Expected

The configured maximum-length request should complete successfully or return a controlled response without leaving the application unresponsive.

### Actual

- The browser accepted the request.
- The Translate button remained disabled and no result appeared after more than 240 seconds.
- The synchronous model call blocked the Uvicorn application process during inference.
- Uvicorn had to be restarted before testing could continue.

### User Impact

A single maximum-length text request can monopolize the web process, delaying health checks and requests from other users.

### Likely Cause

The asynchronous FastAPI route calls CPU-bound translation synchronously. Five-beam generation is allowed to run against a very large accepted input, with generation configured up to 512 tokens. The HTTP layer has no bounded inference timeout, chunking policy, or worker isolation for this path.

### Recommended Correction

1. Split long text into sentence- or paragraph-bounded chunks before inference.
2. Enforce a model-aware token limit in addition to the character limit.
3. Run CPU-bound translation outside the event loop or route long requests through the background worker.
4. Add a controlled timeout/error response and a regression test at exactly the configured maximum.

### Evidence

`C:\Users\mohit\git\testcases\ghcp\test run 8\evidence\TT-09.png`

## TT-28: Devanagari Digits Converted to ASCII

### Input

- Source language: Hindi
- Target language: Marathi
- Source: `मुझे १२३ रुपये दीजिए।`

### Expected

`मला १२३ रुपये द्या।`

The amount, monetary meaning, and Devanagari numeral script should remain intact.

### Actual

`मला ₹123 द्या.`

The translation preserved the value and monetary meaning, but converted `१२३` to ASCII `123`.

### User Impact

The sentence remains understandable, but script fidelity is lost. This matters for localized educational material, copied financial values, and workflows requiring source-script preservation.

### Likely Cause

IndicTrans2 normalizes or generates numeric entities independently of the source numeral script. The current protected-text handling preserves URLs and line separators but does not restore source-script numeral spans after translation.

### Recommended Correction

1. Capture numeral spans and their original scripts before model inference.
2. Restore corresponding numeric values using the source numeral glyphs after decoding.
3. Keep currency symbols and surrounding spacing intact.
4. Add focused tests for Devanagari numerals, mixed-script numbers, decimals, dates, percentages, and currency amounts.

### Evidence

`C:\Users\mohit\git\testcases\ghcp\test run 8\evidence\TT-28.png`

## Resolved Regressions Confirmed

The prior stale-cache, URL, multiline, conversational-token, idiom, gender-agreement, and reverse/cross-Indic routing failures did not recur. Those cases passed in Test Run 8.
