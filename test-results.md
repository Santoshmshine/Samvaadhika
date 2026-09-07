# Samvaadhika Test Run 8 Results

## Run Metadata

- Date: 2026-09-08
- Application: Samvaadhika 1.0.0
- URL: `http://127.0.0.1:8000`
- Execution: VS Code integrated Playwright browser
- Python: 3.12.10
- Branch under test: `feature/video-enhancement`
- Base commit: `5d83ae8acc97d91960e293247c3e27eab85d8dae`
- Cases: TT-01 through TT-37
- Primary screenshots: 37
- Additional concurrency screenshot: 1

## Overall Result

| Status | Count |
|---|---:|
| Passed | 35 |
| Failed | 2 |
| Needs Review | 0 |
| Not Run | 0 |
| Total | 37 |

Pass rate: **94.6%**.

## Direction Summary

| Direction | Passed | Failed | Total | Pass Rate |
|---|---:|---:|---:|---:|
| English to Hindi | 19 | 1 | 20 | 95% |
| English to Marathi | 3 | 0 | 3 | 100% |
| Hindi to English | 2 | 0 | 2 | 100% |
| Marathi to English | 1 | 0 | 1 | 100% |
| Hindi to Marathi | 3 | 1 | 4 | 75% |
| Marathi to Hindi | 2 | 0 | 2 | 100% |

## Case Results

| Cases | Status | Notes |
|---|---|---|
| TT-01 to TT-08 | Passed | Basic directions, auto-detection, same-language handling, whitespace, URL, punctuation, and number retention worked. |
| TT-09 | Failed | Exactly 10,000 characters produced no result after more than 240 seconds and blocked the server. |
| TT-10 to TT-27 | Passed | Validation, authentication, cache behavior, persistence, audit, fallback handling, concurrency, conversation, idioms, and gender agreement worked. |
| TT-28 | Failed | `१२३` was rendered as `123`; value and currency meaning were retained but script fidelity failed. |
| TT-29 to TT-37 | Passed | UI rendering, multiline formatting, punctuation, terminology, long sentences, repeatability, and reverse/cross-Indic routes worked. |

## Key Improvements Since Test Run 7

Test Run 7 produced 22 passes, 10 failures, 4 review cases, and 1 not-run case. Test Run 8 produced 35 passes and 2 failures.

Confirmed corrections include:

- Hindi-to-English and Marathi-to-English routing.
- Hindi-to-Marathi and Marathi-to-Hindi routing.
- Versioned cache keys that bypass historical stale translations.
- Full URL retention in TT-08.
- Natural conversational output without stray tokens in TT-23 and TT-31.
- Semantic idiom translations in TT-25 and TT-26.
- Correct gender agreement in TT-27.
- Preserved multiline separation in TT-30.
- Successful execution of TT-20 using safe failure isolation.
- Successful restart-persistence and concurrency checks.

## Validation Details

- TT-14: first request was uncached; identical second request was cached.
- TT-20: an unsupported source direction safely forced both translation providers to fail; two responses returned a marked confidence-zero stub and neither was cached.
- TT-21: a fresh translation remained cached after a real Uvicorn restart.
- TT-22: simultaneous authenticated tabs received distinct matching outputs.
- TT-17 and TT-18: persisted jobs and audit entries were verified in browser views.
- The application was restarted after TT-09 and left running after the run.

## Evidence

Complete execution data and screenshots are stored outside this branch at:

`C:\Users\mohit\git\testcases\ghcp\test run 8`

The folder contains the canonical case snapshots, the completed execution CSV, 37 primary screenshots, and the additional TT-22 session screenshot.

## Conclusion

The stale-cache incident and the major translation-quality regressions are resolved. Release readiness is still blocked by the maximum-length request behavior in TT-09. TT-28 is a localized script-fidelity defect that should be corrected alongside numeric entity preservation tests.
