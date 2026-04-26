# Light_Novel_Translator Audit Report - 2026-04-26

## Current State

This repository is a local translation and reading workbench for:

- Kakuyomu single-episode URLs.
- Local English/Japanese PDF documents.

The intended pipeline is:

1. Extract source content.
2. Split into paragraphs.
3. Translate to Chinese.
4. Save JSON/HTML under `outputs`.
5. Read in Web UI using reading, bilingual compare, or sentence compare modes.

The current working tree was already dirty before this audit. Existing changes were treated as user-owned and were not reverted.

Current dirty files reported by `git status --short`:

- `app/schemas.py`
- `app/services/html_export.py`
- `app/services/pdf_extractor.py`
- `app/services/pdf_pipeline.py`
- `app/services/translation.py`
- `app/web_ui.py`
- Untracked sample PDF: `The Death and Life of Great American Cities (Jane Jacobs) (z-library.sk, 1lib.sk, z-lib.sk).pdf`

## Audit Scope

Reviewed source, scripts, docs, and relevant local state:

- `app/main.py`
- `app/schemas.py`
- `app/web_ui.py`
- `app/services/html_export.py`
- `app/services/kakuyomu_pipeline.py`
- `app/services/pdf_extractor.py`
- `app/services/pdf_pipeline.py`
- `app/services/translation.py`
- `app/services/ui_jobs.py`
- `app/services/web_extractor.py`
- `scripts/*.py`
- `scripts/*.ps1`
- `requirements.txt`
- `README.md`
- `README.en.md`
- `.gitignore`
- `.gitattributes`
- local sample text files under `data/`

Ignored/generated folders such as `.git`, `outputs`, `.codex-logs`, and `__pycache__` were not treated as source code audit targets.

Three read-only subagent audits were used:

- Backend/API/Pydantic/filesystem audit.
- Web UI/reading UX/responsive layout audit.
- PDF OCR extraction and heading heuristic audit.

## Verification Performed

Lightweight checks performed in the project runtime:

```powershell
& 'D:\anaconda3\envs\ln-translator\python.exe' -m compileall -q app scripts
```

Result: passed, no Python syntax errors reported.

Sample PDF extraction check using the configured project Python:

```text
count 3192
first_page 12
kind_counts {'chapter_heading': 33, 'paragraph': 3099, 'heading': 60}
```

This confirms the current extractor starts the sample book body at page 12, but still emits many heading-like OCR false positives.

No full PDF translation run was started during this audit because that would trigger long model inference. No business code was modified.

## High-Priority Findings

### P1: Saved-result identifiers can escape the library root

Files:

- `app/services/pdf_pipeline.py`
- `app/services/kakuyomu_pipeline.py`

Risk:

`document_id`, `work_id`, and `episode_id` are used directly in filesystem path joins for saved-result loading and metadata generation. Generated IDs are mostly safe, but route parameters are still user-controlled. A local service should still reject dot segments, path separators, drive markers, and unexpected characters before joining paths.

Affected areas:

- `load_saved_pdf_result(document_id)`
- `build_pdf_saved_file_metadata(document_id)`
- `save_pdf_translation_result(result)`
- `load_saved_kakuyomu_result(work_id, episode_id)`
- `build_saved_file_metadata(work_id, episode_id)`
- `save_kakuyomu_translation_result(result)`

Recommended fix:

Add shared helpers such as:

- `validate_storage_id(value: str, label: str) -> str`
- `safe_child(root: Path, *parts: str) -> Path`

Use both an allowlist and a final `resolve()` containment check.

### P2: `debug_limits` is written but not declared in API schemas

Files:

- `app/services/pdf_pipeline.py`
- `app/schemas.py`
- `app/main.py`

Risk:

`build_pdf_translation_result()` attaches `debug_limits` when `PDF_DEBUG_MAX_PAGES` or `PDF_DEBUG_MAX_PARAGRAPHS` is active, but `PDFTranslateResponse` and `PDFSavedResponse` do not declare the field. Pydantic/FastAPI response conversion can drop that field from API responses while saved `result.json` keeps it.

This creates divergence between:

- direct API response,
- saved JSON,
- Web UI data,
- history display.

Recommended fix:

Add a `PDFDebugLimits` schema and optional `debug_limits` fields to PDF response/history models. Also make the UI visibly mark debug-limited PDF results.

### P2: PDF extraction can return an empty successful document after filtering

Files:

- `app/services/pdf_extractor.py`
- `app/services/pdf_pipeline.py`

Risk:

The extractor raises if the PDF has no raw extractable text, but after front-matter/OCR filtering it can return an empty list. The pipeline will translate an empty list and may save a successful zero-paragraph result.

Recommended fix:

Fail fast after filtering:

- If no paragraphs remain, raise `ValueError`.
- Include diagnostic context: raw block count, filtered block count, detected start page, debug limits if active.

### P2: UI jobs are unbounded background threads

File:

- `app/services/ui_jobs.py`

Risk:

Each UI job creates a daemon thread. The in-memory job dictionary never evicts old jobs. Repeated requests can exhaust CPU/GPU memory, especially because PDF extraction and model inference are expensive.

Recommended fix:

Add:

- bounded executor or queue,
- maximum concurrent translation jobs,
- queue limit,
- job TTL/cleanup,
- clear `429` or `503` response when saturated.

## PDF Extraction Findings

### Current behavior

The PDF extractor now works in three broad stages:

1. Read PyMuPDF text blocks, clean whitespace/soft hyphen/zero-width characters, estimate body font size, remove repeated margin text and obvious noise.
2. Classify blocks as `chapter_heading`, `heading`, or `paragraph` using font/style, regex, casing, and sentence-like heuristics.
3. Detect main-content start page, skip earlier front matter, then filter running headers, footers, OCR heading noise, and demote suspicious headings.

`chapter_heading` is now threaded through:

- `app/schemas.py`
- `app/services/html_export.py`
- `app/web_ui.py`
- `app/services/pdf_pipeline.py`

### Sample PDF evidence

The sample PDF currently extracts:

- 3192 total blocks.
- first retained page: 12.
- `chapter_heading`: 33.
- `heading`: 60.
- `paragraph`: 3099.

Good result:

- First retained block is page 12 `Introduction`, which matches the expected body start.

Remaining false-positive headings observed:

- `And`
- `Street!"`
- `Vacuums.`
- `Third,`
- `I`
- `100.`
- `Index`
- index/advertisement/publisher-list style lines after the main book content.

### High-risk heuristic sources

`SECTION_PATTERN` is too broad for numeric fragments:

- `^\d+(\.\d+)*\b` can classify short number-leading OCR fragments as headings.

`_looks_like_sentence()` is too strict:

- It requires at least 7 words before treating text as sentence-like.
- Short body fragments and first sentences can still become headings.

Heading demotion depends on `page_has_body`:

- If a page is initially all headings/fragments, the second-pass demotion can be skipped.

No end-matter detection:

- The extractor detects the start of main content but does not stop at `Index`, publisher catalog pages, ISBN-heavy pages, or advertisement sections.

TOC generation is too trusting:

- `html_export.py` includes both `heading` and `chapter_heading` in generated contents, so false OCR headings pollute the reading-page table of contents.

### Recommended PDF extraction work

1. Replace boolean heading classification with scoring:
   - font/style score,
   - text-shape score,
   - page-position score,
   - neighboring-body score,
   - OCR-noise penalty,
   - end-matter penalty.

2. Broaden short sentence/body-fragment detection:
   - lowercase ratio,
   - trailing punctuation,
   - stopword-only fragments,
   - comma-ending fragments,
   - common sentence starters.

3. Run heading demotion even on pages without initial `paragraph` blocks.

4. Add end-matter detection:
   - stop or downgrade after `Index`,
   - detect publisher catalog patterns,
   - detect short-entry + page-number dense pages,
   - detect ISBN/series-code dense pages.

5. Keep `chapter_heading` as the only default TOC source in reading HTML. Treat ordinary `heading` as visual subheads unless confidence is high.

6. Add a debug report output for extractor decisions:
   - page summaries,
   - kept/dropped/demoted counts,
   - filter reason counts and sample blocks.

## Web UI / Reading UX Findings

### P2: Main reading area is cramped at common desktop widths

File:

- `app/web_ui.py`

Risk:

The page uses a fixed `320px` sidebar plus main content until the viewport is below `1100px`. At widths such as 1100-1280px, the main panel becomes narrow. PDF paragraphs, bilingual compare columns, and sentence rows wrap frequently.

Recommended fix:

- Raise the single-column breakpoint to around 1200-1280px, or convert the sidebar into a top task panel.
- Let compare/sentence layouts respond to container width, not only viewport width.

### P2: Compare sentence highlighting is mouse-first

File:

- `app/web_ui.py`

Risk:

Sentence matches are rendered as plain `span` elements and rely on `mouseover`, `mouseleave`, and `click`. Keyboard users cannot focus sentence matches, and touch users get weak persistent state.

Recommended fix:

- Add `tabindex="0"` to sentence spans or render them as buttons.
- Add `Enter`/`Space` behavior.
- Add `:focus-visible`.
- Use `aria-selected` or equivalent state.

### P2: Long job progress lacks live-region semantics

File:

- `app/web_ui.py`

Risk:

Status and progress are visual `div`s. Screen readers may not announce long PDF extraction/translation status, failures, or completion.

Recommended fix:

- Add `role="status"` and `aria-live="polite"` to status.
- Add progressbar semantics: `role="progressbar"`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`.
- Use alert semantics for failures.

### P2: Long PDF paths and IDs can overflow sidebar/history cards

File:

- `app/web_ui.py`

Risk:

PDF document IDs and long filenames are shown in constrained sidebar cards. Several text containers lack `overflow-wrap:anywhere`.

Recommended fix:

- Add `overflow-wrap:anywhere` to history titles, `small`, and meta card spans.
- Prefer short filename display plus full path in a copyable field.

### P3: Exported reading HTML uses `lang="en"` for Chinese reading content

File:

- `app/services/html_export.py`

Risk:

Generated reading pages mostly display Chinese translated text but declare the document language as English. This hurts screen-reader pronunciation, browser language behavior, and font fallback.

Recommended fix:

- Use `lang="zh-CN"` for merged reading pages.
- Use local `lang` attributes for original-text notes if needed.

### P3: PDF form has misleading storage strategy text

File:

- `app/web_ui.py`

Risk:

The PDF panel contains a disabled storage strategy input whose initial HTML value is still `outputs/library/kakuyomu/<work-id>/<episode-id>`. JavaScript updates it after initialization, but the static markup is misleading and fragile.

Recommended fix:

- Set the PDF panel value to `outputs/library/pdf/<document-id>` in the HTML template.
- Consider removing the duplicate storage strategy fields.

## Backend/API Findings

### P3: Invalid `PDF_DEBUG_*` values are silently ignored

File:

- `app/services/pdf_pipeline.py`

Risk:

`PDF_DEBUG_MAX_PAGES=abc`, `0`, or negative values are ignored without warning. Debug runs can look unrestricted without explanation.

Recommended fix:

- Log invalid debug env values.
- Include active debug limits in job status and saved metadata.

### P3: Output URL encoding is inconsistent

Files:

- `app/services/pdf_pipeline.py`
- `app/services/kakuyomu_pipeline.py`

Risk:

Some generated URLs quote identifiers and others do not. Current generated IDs are mostly safe, but this should be normalized with identifier validation.

Recommended fix:

- Validate IDs first.
- Quote all route path components consistently.

### P3: PDF extraction heuristics are English-biased

File:

- `app/services/pdf_extractor.py`

Risk:

PDF requests allow `source_language="ja"`, but front-matter keywords, heading regex, casing logic, stopwords, and title rules are mostly English/Latin-script oriented.

Recommended fix:

- Pass source language into extraction options or create language-specific heuristic profiles.
- Add Japanese heading/front-matter patterns before treating Japanese PDF support as reliable.

## Documentation / Maintenance Findings

### README content is stale

Files:

- `README.md`
- `README.en.md`

Risk:

The README still describes an earlier phase and says English academic translation is not integrated, while the current code has `/translate/en`, NLLB/M2M-style handling, PDF translate/save APIs, Web UI history, and debug-limited PDF translation.

Recommended fix:

- Refresh docs after the next code pass.
- Include current EN/JA model environment variables.
- Document PDF debug limits and whether they are UI-exposed.
- Document generated PDF library paths.

### `app/web_ui.py` and `scripts/batch_translate.py` are large single files

Files:

- `app/web_ui.py` around 1152 lines.
- `scripts/batch_translate.py` around 1005 lines.

Risk:

Both are usable but hard to maintain. Web UI mixes Python template, CSS, HTML, and JS. Batch script duplicates HTML rendering patterns already present in `html_export.py`.

Recommended fix:

- Later, split Web UI template pieces or move static frontend assets out of the Python string.
- Reuse `app/services/html_export.py` more consistently from scripts.

## Suggested Fix Order

1. Add safe storage ID/path helpers and cover PDF/Kakuyomu load/save/history paths.
2. Add `debug_limits` to schemas and UI/history, then expose PDF debug mode in Web UI.
3. Fail fast on empty filtered PDF extraction.
4. Improve Web UI medium-width reading layout, long-path wrapping, and status/progress semantics.
5. Tighten PDF heading heuristics:
   - short-fragment demotion,
   - end-matter detection,
   - TOC only from high-confidence chapter headings.
6. Add extractor debug report for page/block decisions.
7. Add bounded UI job queue and job TTL cleanup.
8. Refresh README files to match shipped behavior.

Completed follow-up after this audit:

- Added `scripts/debug_pdf_extraction.py` and `build_pdf_extraction_debug_report()` for page/block filtering reports.
- Refreshed `README.md`, `README.en.md`, and `TESTING_GUIDE.md` to describe English translation, PDF save/history, Web UI debug caps, output paths, and the extractor debug-report workflow.
- Added basic Japanese PDF heading/body heuristics for `第N章` / `第N話` style headings, Japanese TOC/front-matter signals, and long Japanese body sentence detection.

## Suggested Regression Tests

Add tests or scripts for:

- Storage identifier traversal rejection:
  - `..`
  - `.`
  - `a/b`
  - `a\b`
  - drive-like markers.

- PDF debug schema round trip:
  - `PDF_DEBUG_MAX_PAGES=2`
  - `PDF_DEBUG_MAX_PARAGRAPHS=24`
  - document ID suffix `-debug-p2-n24`
  - API response and saved JSON both include `debug_limits`.

- Empty extraction failure:
  - no saved zero-paragraph result.

- Sample PDF extraction:
  - first retained page is 12,
  - first block is `Introduction`,
  - known bad headings like `And`, `Third,`, `I`, and `100.` are not heading-like.

- End matter:
  - `Index` and publisher catalog pages are excluded or clearly downgraded.

- UI responsive checks:
  - 1366x768,
  - 1280x720,
  - 1112x834,
  - 1024x768,
  - 820x1180,
  - 390x844.

- Keyboard accessibility:
  - Tab to source selector,
  - submit,
  - history load,
  - mode switching,
  - sentence compare focus/highlight.

## Immediate Next Development Choices

Best next step:

1. Implement safe ID/path helpers and `debug_limits` schema support first. This is low risk and fixes correctness/security foundations.

Then:

2. Expose PDF debug caps in Web UI so future PDF work is faster and repeatable.

Then:

3. Tighten PDF heading/end-matter heuristics using the sample PDF as a regression anchor.
