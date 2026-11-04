# Validation evidence — 2026-11-04

## Automated Python tests

Command: `.venv/bin/python -m pytest -q --durations=5`

Observed final result: **45 passed, 1 warning in 69.97 seconds** on Linux / Python 3.11. The warning is a Starlette/AnyIO test-client deprecation; no failed tests.

Coverage includes integer IRR and IRT conversion, fractional rial rejection, Persian digits, Jalali leap dates, tare missing versus explicit zero, floor-to-five net weight, balanced posting, inventory and COGS, duplicate source/reference, reversal constraints, stale revision, concurrent writes, rollback on validation error, CSV staging and atomic commit, import idempotency, backup/restore, audit tampering, authentication, authorization, Origin/request-header checks, standalone formulas and lossless OOXML patching. A regression test also ensures an existing formula in A1 is never overwritten by a repair banner.

The end-to-end numeric fixture asserts: 100 kg purchase; 40 kg sale; stock 60 kg / 60,000 IRR; bank 175,000 IRR; profit 35,000 IRR; trial balance difference zero.

## Full real-package preservation verification

Commands:

```
python -m scripts.repair_legacy private/sources/v1.10 private/repaired-v1.11
python -m scripts.verify_legacy private/sources/v1.10 private/repaired-v1.11 docs/LEGACY_VERIFICATION.json
```

Observed: **14 workbooks, 27 name selectors; 996,133 original formulas preserved**. Every original formula XML element was compared, every original package member remained, non-worksheet parts other than the intentionally updated workbook metadata were byte-identical, and worksheet extLst elements (including x14 validations) were compared canonically. Detailed per-file results are in `LEGACY_VERIFICATION.json`. This verifies preservation, not formula correctness or calculated business totals.

## Source audit and review staging

- 33 downloaded original workbooks across three generations.
- 2,617,104 formula elements counted structurally across those originals.
- 357 literal dated candidate rows staged, 355 distinct fingerprints, 2 exact repeat occurrences.
- Zero historical financial postings inferred or committed.
- A complete recursive audit of every Drive folder was **not** performed; remaining scope is listed in the consolidated specification.

## Browser smoke checks

Executed using Playwright 1.64.1 and a packaged headless Chromium against the synthetic demo server. The browser dependencies are scratch tools, not application runtime dependencies.

Observed:

- All 13 existing navigation pages opened without JavaScript page/console errors.
- Basket dropdown option labels were Persian names, not basket codes.
- Weigh preview: gross 2140, count 100, tare 1.4 → net 2000 kg.
- 1440×960 desktop: body width/height equalled viewport.
- 1280×720 desktop: body height 720; application footer at y=706; navigation and sidebar footer within viewport.
- 390×844 mobile: body scroll width 390, equal to viewport; application footer at y=832.
- Tables, forms, import previews and help may scroll internally; the page body does not scroll.

`node --check static/app.js` also passed. Browser checks used synthetic data only; they did not establish visual/functional parity with every historical app page.

## Explicitly not verified

Excel Desktop/Office 2013 recalculation and external-link refresh; LibreOffice recalculation; Windows 7; physical printing; statutory/tax accounting; ownership/partnership settlement; real-data financial reconciliation; installer/EXE; large-scale multi-user workloads; full disaster recovery on another machine. There is no claim that these gates have passed.
