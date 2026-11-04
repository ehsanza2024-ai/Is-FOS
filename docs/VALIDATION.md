# Validation evidence — 2026-11-04

## Automated Python tests

Command: `.venv/bin/python -m pytest -q --durations=5`

Observed final result: **78 passed, 1 warning in 119.27 seconds** on Linux / Python 3.11. The warning is a Starlette/AnyIO test-client deprecation; no failed tests.

Coverage includes integer IRR and IRT conversion, fractional rial rejection, Persian digits, Jalali leap dates, tare missing versus explicit zero, floor-to-five net weight, balanced posting, inventory and COGS, duplicate source/reference, reversal constraints, stale revision, concurrent writes, rollback on validation error, CSV staging and atomic commit, import idempotency, backup/restore, audit tampering, authentication, authorization, Origin/request-header checks, standalone formulas and lossless OOXML patching. Version 0.6 adds real core-API integration through the installed-window boundary and remote dashboard: a private loopback window logs in and posts a controlled capital event; an ordinary local browser is refused, while a LAN admin reads the resulting bank balance and cannot post/export. Tests also cover one-use/expiry desktop cookies, forged forwarded IPs, admin-versus-viewer read-only enforcement, separate dashboard cookies, no financial/auth/backup change on blocked routes, missing-file bootstrap refusal, demo-to-real replacement refusal, filters and as-of/opening/closing/reversals, large-integer JSON, safe first setup/rerun, occupied ports, receipt release after reversal, blank-row physical addresses for cheque/import updates, and missing cheque amounts not becoming zero. A regression test also ensures an existing formula in A1 is never overwritten by a repair banner.

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

## Previous 0.5 central-client browser baseline

Executed using Playwright 1.64.1 and a packaged headless Chromium against the synthetic demo server. The browser dependencies are scratch tools, not application runtime dependencies.

Observed:

- All 13 existing navigation pages opened without JavaScript page/console errors.
- Basket dropdown option labels were Persian names, not basket codes.
- Weigh preview: gross 2140, count 100, tare 1.4 → net 2000 kg.
- 1440×960 desktop: body width/height equalled viewport.
- 1280×720 desktop: body height 720; application footer at y=706; navigation and sidebar footer within viewport.
- 390×844 mobile: body scroll width 390, equal to viewport; application footer at y=832.
- Tables, forms, import previews and help may scroll internally; the page body does not scroll.

`node --check static/app.js` also passed for that baseline. Browser checks used synthetic data only; they did not establish visual/functional parity with every historical app page.

## Version 0.6 read-only dashboard browser checks

Executed with Playwright 1.64.1 and headless Chromium 153 against the current synthetic read-only server, without disabling browser web security. All 11 report/help tabs, including the selected-party statement, opened without JavaScript errors. Repeated at 1440×960, 1280×720 and 390×844: body width/height never exceeded viewport and the fixed footer remained visible; reports/tabs can scroll inside their panes. Jalali Persian-digit filters, selected-party opening/closing statement and IRR/IRT switching were exercised. `money('9007199254740993')` rendered exactly `۹٬۰۰۷٬۱۹۹٬۲۵۴٬۷۴۰٬۹۹۳`, not a rounded JavaScript number. Expected negative network probes returned POST events **403**, raw ledger export **404**, and central-entry JavaScript **404**. No unexpected page/console errors occurred; console resource errors for those deliberate negative probes were excluded, not application failures.

`node --check` passed for both JavaScript clients; `sh -n` passed for install/start/dashboard launchers; Python `compileall` passed. Windows PythonNET/CLR/CFFI wheel availability was checked for CPython 3.11/win_amd64; this is dependency retrieval evidence, **not execution of Windows setup or the native WebView**.

Synthetic screenshot: `images/reports-demo.png`. This screenshot and the online preview are explicitly sample data, not imported historical balances. Native Excel still has its own 15-significant-digit calculation limits; exact integer JSON/UI does not prove recalculation parity for arbitrarily large Excel aggregates.

## Explicitly not verified

Excel Desktop/Office 2013 recalculation and external-link refresh; LibreOffice recalculation; Windows 7; physical printing; statutory/tax accounting; ownership/partnership settlement; real-data financial reconciliation; signed installer/EXE; actual install.bat/PowerShell execution, native pywebview/WebView2 on Windows, graphical Linux shell, Safari/iOS, real-network TLS/VPN/firewall acceptance; large-scale multi-user workloads; full disaster recovery on another machine. There is no claim that these gates have passed.
