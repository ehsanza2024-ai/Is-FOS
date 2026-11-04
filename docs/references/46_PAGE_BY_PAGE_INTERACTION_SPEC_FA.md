# مشخصات اجرایی صفحه‌به‌صفحه و رابط‌های عملیاتی Mazand FOS

این کاتالوگ، قرارداد طراحی/تعامل هر صفحه است. مقادیر عددی و وضعیت‌ها در مثال‌ها ساختگی‌اند. هر screen بعد از پیاده‌سازی باید Screen ID، route، component owner، API/query، permissions، help keys، test IDs، screenshots و وضعیت `implemented/verified` داشته باشد. منو به‌تنهایی نشانه قابلیت نیست.

## قرارداد مشترک در همه صفحه‌ها

- پوسته RTL دارای topbar، navigation، work area با `min-height:0` و وضعیت connection است.
- صفحات فهرست: filter row، active filters، count/freshness، table/list، selection/action menu و empty/loading/error states.
- صفحات عملیاتی: عنوان و وضعیت سند، Workbench مرحله‌ای، draft save state، footer ثابت و dirty confirmation.
- هر number field: واحد، precision، min/max/negative policy و keyboard input مشخص.
- هر KPI/balance: مبنا، بازه زمانی، زمان به‌روزرسانی و منبع/Drill-down.
- Side-pane برای quick-create؛ Dialog تودرتو ممنوع.
- هر action، permission سمت API دارد. UI disabled state باید دلیل را نشان دهد.
- صفحه باید حداقل در اندازه wide، desktop compact و narrow با zoom بالا بررسی شود.

---

## SCR-HOME-001 — اتاق فرمان مدیر

**هدف:** نشان‌دادن اقدام‌های نیازمند تصمیم، نه فقط نمودار.

**Layout:** Header با بازه/انبار/دوره و freshness؛ ردیف ۴–۶ کارت KPI؛ بخش نمودار ورود/خروج؛ لیست فعالیت اخیر؛ سررسید چک؛ مرکز مغایرت؛ کارت مانده‌های مهم و وضعیت backup/sync. در عرض متوسط پنل‌ها دو ستونه و در باریک تک‌ستونه شوند.

**KPI contract:** عنوان، مقدار، واحد/ارز، بازه، baseline، تغییر نسبت به baseline، زمان freshness، tooltip و drilldown. مقدار null با `—` یا برچسب «نامشخص»، نه صفر.

**Actions:** بازه، فیلتر، شخصی‌سازی کارت‌های مجاز، Reset layout، بازکردن لیست منبع، رفتن به استثنا.

**Errors/states:** offline، partial sync، stale data، empty system، permission-limited view، chart unavailable. هیچ KPI نمونه‌ای بدون برچسب Demo در mode عملیاتی نشان داده نشود.

**Tests:** فیلتر مشترک، drilldown filters, role visibility, missing data, RTL screenshot, KPI totals vs source query.

## SCR-SEARCH-001 — جست‌وجوی سراسری و Command Palette

**Layout:** input با keyboard shortcut کشف‌پذیر؛ دسته‌بندی نتایج Party، سند، فاکتور، بانک، قبض، حساب، محصول/انبار و help. نتیجه عنوان، نوع، شماره، تاریخ، وضعیت و چند فیلد امن دارد.

**Rules:** فقط نتایج مجاز query شوند؛ autocomplete نباید اسم/موجودی حساب یا سازمان غیرمجاز را افشا کند. شماره‌های فارسی/لاتین و aliasهای تاییدشده normalize شوند. بازکردن نتیجه context و ID واقعی را حفظ کند.

**Tests:** permission boundary، Persian/Arabic digit search، no-results، latency، keyboard navigation، exact ID match.

## SCR-MD-001 — مرکز اطلاعات پایه

**Layout:** دسته‌های Party/CustomerType، کدینگ حساب، بانک/حساب بانکی، محصول/درجه/واحد، انبار، BasketType، مرکز هزینه، کارمند/گروه کاری، template چاپ و mapping import. هر کاشی شمار رکورد فعال و هشدار کیفیت داده نشان می‌دهد.

**Actions:** create, search, edit, deactivate, inspect references, export scoped data, view audit. حذف ارجاع‌دار ممنوع و حذف نهایی فقط با policy.

## SCR-MD-002 — نوع مشتری

**Fields:** internal ID، کد ثابت، نام فارسی، نام انگلیسی اختیاری، شرح، ترتیب نمایش، فعال/غیرفعال، تاریخ اعتبار و تعداد ارجاعات.

**Rules:** نوع جدید بدون build code در dropdown، filter و template mapping ظاهر شود. نام نمایشی قابل تغییر است؛ FK بر ID ثابت است. غیر‌فعال‌سازی تاریخچه را حذف نمی‌کند. CustomerType صرفاً طبقه‌بندی است؛ حسابداری را بدون posting policy جدا تعیین نمی‌کند.

**Tests:** add → party form available → report filter available → deactivate → historical invoice unchanged.

## SCR-PARTY-001 — طرف‌حساب

**Fields:** Party ID، code، official/display name، alias، roles، CustomerType، contacts allowed، status، ledger mapping and history note. اطلاعات شخصی اختیاری تا حد نیاز.

**Layout:** فرم پایه در panel؛ سمت دیگر summaryهای جدا: مانده مالی قطعی، گردش عملیات بار، آخرین اسناد، هشدار duplicate/quality. Quick-create context-preserving.

**Rules:** Party می‌تواند نقش‌های متعدد داشته باشد. duplicate name پیشنهاد است نه merge خودکار. Merge، permission ویژه، preview all links, transaction, audit and recovery plan می‌خواهد.

## SCR-PARTY-STMT-001 — صورت‌حساب طرف‌حساب

**Filters:** Party, range, document status, operation/finance view, warehouse, currency display, include corrections. Default range می‌تواند کل تاریخچه مجاز باشد.

**Sections:**
1. مشخصات Party و نوع گزارش/قالب؛
2. مانده اول مالی و مبنای تاریخ؛
3. گردش مالی posted: debit/credit، ref، date، running balance؛
4. گردش بار: gross/net/loss/billable, basket, product, movement date؛
5. bank/receipt/payment allocation؛
6. unresolved items and related journal where permission allows.

**Rules:** مالی و وزن در دو سکشن/واحد مستقل باقی بمانند. Running balance از ledger یا allocation policy محاسبه شود. row click به سند منبع با همان filter باز شود. قالب و عنوان ستون تابع `CustomerType`/template است اما formula گزارش قابل override از قالب نیست.

**Tests:** beginning + debit-credit activity = ending; range filtering; negative balance warning; print; role restriction; linked bar and financial records are not summed together.

## SCR-LOAD-001 — قبض باسکول و ورود بار

**Layout:** هدر قبض/وضعیت/زمان، capture zone با وزن بزرگ، وضعیت دستگاه، طرف/محصول/انبار، ردیف‌های بار و event timeline. group row add button (+) باید کوچک اما قابل کشف باشد.

**Fields:** ticket ID, operation date/time, gross, unit, stable flag, scale/device source, operator, basket count/type, tare snapshot, fruit net, vehicle/driver optional per policy, Party, product/grade, warehouse, source, note.

**Rules:** capture raw and normalized values distinguishable. Manual entry marks source. Duplicate capture cannot create duplicate movement. Change after confirmed ticket requires permission/reason/history.

## SCR-INV-PUR-001 / SCR-INV-SALE-001 — فاکتور خرید/فروش مرکبات

**Workbench tabs:** سربرگ، اقلام/وزن، گردش بار، تسویه، بازبینی، چاپ. Only current step content shown; footer remains available. Table scroll is internal.

**Row fields:** operation date, product/grade, basket type/count, tare snapshot, gross, fruit net, loss %, loss kg, billable kg, unit price/basis, line total, movement/ticket link, status/warnings. Columns can be arranged according to screen width and saved layout; essential computed fields never silently hidden from audit/preview.

**Draft/commit:** autosave state visible; `Save draft` is separate from Validate and Post. Post check validates Party, product, basket tare, rate unit, math, period, movement allocation, permission and accounting policy. Retry idempotent.

**Panel Party movements:** date range, load rows and financial records separate, checkbox selection, already-linked warning, balance label, selected weight/amount and remaining amount. Parent invoice state survives child quick-create.

## SCR-SORT-001 — عملیات سورتینگ

**Layout:** input references, source weight and products; output matrix by grade/product; actual waste reason/category; difference/tolerance; confirmation and movement preview.

**Fields:** run ID, date, warehouse/source, input movements, outputs, actual waste weight and reason, measurement source, operator, quality note, approval.

**Rules:** contractual loss is not automatically actual waste. Output + waste + explained difference reconciles to input within explicit tolerance. Tolerance is config and nonmandatory only where decision allows; changing tolerance is auditable.

## SCR-STOCK-001 — کارت گردش موجودی

**Filters:** warehouse, product, grade, date, movement type, posting status, source. Columns: date, event type, ref, in/out, UoM, running aggregate balance, warehouse, operator, status.

**Actions:** source view, authorized correction/reversal, stock count worksheet, export. No direct balance edit. If lot identity absent, report only aggregate; do not synthesize lots.

## SCR-BASKET-001 — گردش سبد

**Fields:** BasketType, tare unit snapshot, count in/out, Party/warehouse, movement date, purpose (loan/return/transfer/loss), related doc, discrepancy reason. Basket count/tare profile is master data; basket custody is a movement ledger. Difference between basket quantity and basket tare is explicit.

**Tests:** return/loan/transfer, missing tare, changed tare profile does not mutate old ticket, count balance and report line.

## SCR-BANK-001 — فهرست گردش بانک

**Sections:** raw source/normalized rows, account selection, range, status and matching hints. Columns include transaction date, bank value date if available, description, withdrawal, deposit, normalized direction, reference, potential party, allocated/unallocated amount, status, import batch.

**Rules:** statement balance and GL bank account balance are different measures. Detail view shows raw row unchanged and transformation history. Opening a transaction doesn't post a journal.

## SCR-BANK-MATCH-001 — تطبیق بانک

**Layout:** left/source transaction list, center candidate matcher/allocation editor, right target documents and residual summary; on narrow width these become switchable panes. Supports one-to-one, one-to-many and many-to-one.

**Allocation contract:** show source amount, assigned amounts, remaining residual, candidate confidence/reasons and target reference. Save draft reconciliation separate from confirming/posting. Inaccurate match can be undone through linked correction; audit records actor/reason.

**Tests:** over-allocation, multiple invoices, unmatched transaction, duplicate source, wrong Party, date mismatch, retry, permissions, residual reporting.

## SCR-TRE-001 — دریافت/پرداخت و انتقال

**Fields:** operation date, type, Party, amount/currency, cash/bank account, method, external reference, allocation target(s), status, source, note. Transfer between owned accounts is one domain event with two legs. Partial settlement/overpayment behavior must be explicit.

## SCR-CHEQUE-001 — مرکز چک‌ها

**Views:** received, issued, due soon, overdue, returned, cleared/cashed, voided. Columns include number/serial, amount, due date, party, bank/account, current state, last event and linked document. Status changes are event-sourced/audited; changing state doesn't auto-post twice.

## SCR-BARF-001 — صافی بارفروش

**Header:** Party/barforoosh, date range, settlement period, layout version, physical book invoice reference. **Operation section:** each load/sales row with date, product, gross/net/loss/billable, price and amount. **Financial section:** commission, freight/costs, receipts/payments, bank allocations and residual. Totals show distinct physical weight and monetary balance. Discrepancy drill-down links both sections without mixing their units.

## SCR-JRN-001 — سند حسابداری

**Header:** internal ID/print number, operation date, fiscal period, description, source type/id, status and user. **Lines:** account, subsidiary/Party, cost center, description, debit, credit, currency/base amount, source reference. Footer shows total debit, total credit and difference. Draft can save incomplete; post requires balance and valid accounts/period/permissions. `POSTED` read-only with correction/reversal action.

## SCR-GL-001 — دفتر روزنامه/کل/معین

Read-only ledger report with range, account/party/cost center, journal state, debit/credit, running balance and source link. Export includes filters/version/time. Corrections shown as separate linked rows; old line silently hidden/edited is forbidden.

## SCR-TB-001 — تراز آزمایشی ۴/۶ ستونه

Mode selector: 4-column (period debit turnover, period credit turnover, ending debit balance, ending credit balance) or 6-column (opening debit, opening credit, period debit, period credit, ending debit, ending credit). Opening/period/closing bases are explained by Tooltip. Account hierarchy, include-zero option, unmapped accounts and debit/credit total controls are visible.

**Critical:** Trial Balance is not Balance Sheet. The report must reconcile posted journal and carry-forward policy.

## SCR-FS-BS-001 — صورت وضعیت مالی/ترازنامه

Display as-of date, classification version, assets/liabilities/equity grouping and unmapped-account warnings. Current/noncurrent mapping explicit. Clicking category drills to accounts then journal lines. No guessing based on account name. Unclassified or out-of-balance condition gets quality banner.

## SCR-FS-PL-001 — سود و زیان

Period selection, accounting basis, revenue, cost, expense and net result according to approved CoA mapping. Draft excluded from official amount unless shown separately. Drilldown to account/entry. Comparative prior period shows baseline. Unmapped accounts visibly marked.

## SCR-FS-CF-001 — جریان وجوه نقد

Method/policy (direct/indirect as decided), period, cash/bank account scope, operation categories, exclusions and reconciliation to cash movement. If required source data is insufficient, show partial status rather than fabricated cash flow.

## SCR-IMP-001 — Import Studio

Full-page wizard in a fixed-height workspace: Source → Data type → Mapping → Transform → Dry-run → Preview → Resolve queue → Commit → Result. Source sheet and header detection are explicit. Each row carries raw input, normalized value, errors/warnings, action, duplicate candidate and destination link. Commit button disabled for blocking issues; before commit display record counts/totals. Import isn't final until outcome/reconciliation is shown.

## SCR-REPORT-001 — گزارش‌ساز

Allowed data models, fields, filters, groups, sorting, metrics, chart, preview, saved report version, export scope and permission. Arbitrary formulas that bypass finance policy are not allowed. Definition records formula/joins/null behavior/time cutoff/source. Drilldown preserves filters. Report definition may be saved separately from result snapshot.

## SCR-PRINT-001 — Print Builder

Left: template catalog by document type/customer type. Center: paper canvas with page breaks. Right: format properties (paper/orientation/margins/header/footer/columns/rows/signatures). Column controls include visibility, order, width, label, number format, alignment and wrap. Footer provides actual-size preview, print, export and reset default. Template version snapshot prevents history mutation.

## SCR-USER-001 — کاربران/نقش/مجوز

Role × permission matrix scoped by organization/site/warehouse/period; show effective access and inheritance. Grant/revoke actions audited; critical roles require reauthentication where feasible. Test API unauthorized even if UI element hidden.

## SCR-BKP-001 — مرکز Backup/Restore

Displays last successful backup, verified checksum, target path status, scheduled policy, available space, schema/app version and last Restore test status. Actions: backup now, verify, restore to isolated environment, restore production (special gate). Confirmation names source and target; before restore create protective snapshot. A backup file's presence isn't a passed health status.

## SCR-SYNC-001 — مرکز Sync/Conflict

Views: pending, sent, acknowledged, failed, conflict, schema-incompatible. Each row shows op ID, device, time, entity, impact and retry eligibility. Conflict view compares old/new values, source device/user and effect on money/stock. Posted journal/stock event cannot silent-merge. Resolution follows policy and adds Audit.

## SCR-SCALE-001 — مانیتور باسکول

Large current weight, unit, stable/unsteady indicator, device connection and last received time; ticket fields and capture button only if actual hardware supports them. Raw reading and normalized weight visible separately. Simulator banner is always present in demo mode. Device protocol/settings hidden from unauthorized user but visible to technician role.

## SCR-DQ-001 — کیفیت داده و مرکز استثناها

Queues for orphan references, missing tare, incomplete invoice/expected movement, unallocated bank row, Party/GL mismatch, negative stock, unbalanced draft, pending sync, stale backup and report mapping. Each item shows rule ID, severity, evidence/source, suggested action, owner and current status. Resolve closes current issue, not audit history.

## SCR-HELP-001 — Help Center

Offline indexed help articles, current-page contextual guides, glossary, keyboard shortcuts, tutorials for role, troubleshooting and app version. Search supports Persian normalization. Each article version maps to app version; help must not contradict active formula/policy.

## SCR-CLOSE-001 — پایان روز/بستن دوره

Preflight checklist: drafts, bank unallocated rows, stock exceptions, pending sync, journal balance, subledger/GL mismatches, backup verified, period policy and date cutoff. Closing is a controlled state transition with generated checklist snapshot and audit. Reopen uses role/reason; no hidden silent reopen.

## SCR-AUDIT-001 — دفتر رویدادهای Audit

Filters: actor, entity, action, date, correlation ID, event severity. Before/after is redacted and permission-limited. Export requires permission. Normal user can't erase. Search results show source link and event chain without exposing unrelated sensitive payload.

## Completion standard

Every listed Screen ID must be classified in release traceability as `NOT IMPLEMENTED`, `IMPLEMENTED UNVERIFIED`, `VERIFIED` or `OUT OF SCOPE WITH APPROVAL`. UI-only mock receives no higher status than `MOCK ONLY`. For all implemented screens store screenshot evidence and tests against their contract.
