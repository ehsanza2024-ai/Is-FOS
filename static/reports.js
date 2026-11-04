"use strict";
const q = (s) => document.querySelector(s),
  root = q("#reportapp");
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fa = (v) =>
  new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 3 }).format(
    Number(v || 0),
  );
const portable =
  document.body.dataset.mode === "portable" || location.protocol === "file:";
let cloudBundle = null;
let catalog,
  report,
  health,
  tab = "overview",
  unit = "AUTO",
  currentPage = 1,
  generation = 0;
const dataLabels = {
  Parties: "اشخاص",
  Accounts: "سرفصل‌ها",
  Groups: "گروه‌ها",
  Operations: "عملیات",
  Deals: "قراردادها",
  Baskets: "سبدها",
  Products: "محصولات",
  Stores: "انبارها",
  Banks: "بانک‌ها",
  Weigh: "باسکول",
  Checks: "چک‌ها",
  name: "نام",
  code: "کد شخص",
  role: "نقش",
  active: "فعال",
  note: "توضیحات",
  group: "گروه",
  category: "طبقه",
  parent: "والد",
  debit: "بدهکار",
  credit: "بستانکار",
  partner: "شریک",
  share: "سهم مجموعه (۰ تا ۱)",
  start: "شروع",
  end: "پایان",
  product: "محصول",
  status: "وضعیت",
  policy: "سیاست",
  tare: "تارا (کیلوگرم)",
  date: "تاریخ",
  operation: "عملیات",
  party: "طرف حساب",
  store: "انبار",
  basket: "سبد",
  count: "تعداد",
  gross: "وزن ناخالص",
  loss: "افت٪",
  waste: "ضایعات",
  net: "وزن خالص",
  reference: "مرجع",
  deal: "قرارداد",
  number: "شماره چک",
  direction: "جهت",
  bank: "بانک",
  amount: "مبلغ ریال",
  due: "سررسید",
  state: "وضعیت",
};
const tabs = {
  overview: "نمای مدیریت",
  profit: "سود و زیان",
  balance: "وضعیت مالی",
  accounts: "مانده اشخاص",
  statement: "صورت‌حساب شخص",
  banks: "مانده بانک‌ها",
  banksource: "صورت‌حساب‌های واردشده",
  physical: "گردش فیزیکی و سبد امانی",
  unbilled: "رسیدهای فاکتورنشده",
  checks: "چک‌ها",
  stock: "موجودی",
  trial: "تراز دوره",
  partnerships: "شراکت و تسهیم",
  events: "گردش عملیات",
  tables: "مرکز داده",
  help: "راهنمای اتصال",
};
function currencyView(){return MazMoney.view(unit,report?.settings,report?.currencies);}
const money=v=>MazMoney.format(v,unit,report?.settings,report?.currencies);
const unitName=()=>currencyView().name;
const date = (v) => {
  let s = String(v || "");
  return s.length === 8
    ? s.slice(0, 4) + "/" + s.slice(4, 6) + "/" + s.slice(6)
    : s;
};
function toast(t) {
  q("#toast").textContent = t;
  q("#toast").classList.add("show");
  setTimeout(() => q("#toast").classList.remove("show"), 4000);
}
async function api(path, method = "GET", data) {
  if (portable) {
    if (method !== "GET") throw Error("فایل گزارش فقط‌خواندنی است");
    if (path === "/api/health") return { ok: true, version: "0.8.0" };
    if (path === "/api/catalog")
      return {
        user: { name: "مشاهده‌گر خصوصی" },
        read_only: true,
        demo: cloudBundle.synthetic,
        parties: cloudBundle.tables.Parties.map((p) => p.name),
        source: "فایل رمزگشایی‌شده Drive",
        revision: cloudBundle.revision,
      };
    if (path.startsWith("/api/reports")) {
      const p = new URL(path, location.href).searchParams;
      const period = cloudBundle.periods.find(
        (x) => x.id === (p.get("period") || "all"),
      );
      if (!period) throw Error("این دوره در فایل منتشر نشده است");
      return MazReport.filter(period.report, p.get("party") || "");
    }
    throw Error("این ابزار فقط گزارش می‌خواند");
  }
  const r = await fetch(path, {
    method,
    headers: {
      "X-Mazandasht-Request": "1",
      ...(data ? { "Content-Type": "application/json" } : {}),
    },
    ...(data ? { body: JSON.stringify(data) } : {}),
  });
  const b = await r.json();
  if (!r.ok) {
    const e = Error(
      typeof b.detail === "string" ? b.detail : "خطای ارتباط با سیستم مرکزی",
    );
    e.status = r.status;
    throw e;
  }
  return b;
}
function login() {
  root.innerHTML = `<div class="login"><form class="loginbox" id="login"><h1>گزارش‌های مازندشت</h1><p>پنل فقط‌خواندنی سیستم مرکزی<br>ثبت و اصلاح سند از موبایل و شبکه مجاز نیست.</p><label>نام کاربری<input name="name" autocomplete="username" required></label><label>رمز عبور<input name="password" type="password" autocomplete="current-password" required></label><button type="submit" class="btn primary">مشاهده گزارش‌ها</button><div id="loginerror" class="formerror" role="alert"></div><div class="report-login-note">کاربر و رمز را مدیر سیستم مرکزی تعریف می‌کند. این پنل به روشن‌بودن سیستم مرکزی و اتصال شبکه نیاز دارد.</div></form></div>`;
  q("#login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = e.target.querySelector("button");
    button.disabled = true;
    try {
      await api(
        "/api/login",
        "POST",
        Object.fromEntries(new FormData(e.target)),
      );
      await init();
    } catch (err) {
      q("#loginerror").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}
function shell() {
  root.innerHTML = `<main class="report-shell"><header class="report-top"><div class="report-brand"><h1>مازندشت · پنل گزارش</h1><p>${esc(catalog.user.name)} · ${portable ? "گزارش خصوصی از فایل آنلاین" : "دفتر مرکزی / گزارش زنده"}</p></div><div class="buttons">${catalog.central && window.self === window.top ? '<a class="btn" href="/" target="_top">بازگشت به ثبت مرکزی</a>' : ""}<span class="badge">ثبت فقط در سیستم مرکزی</span><button class="btn" data-action="source">${portable ? "بارگیری فایل Drive" : "فایل گزارش ابری"}</button><button class="btn" data-action="unit">${unitName()}</button><button class="btn" data-action="print">چاپ / PDF</button><button class="btn" data-action="logout">خروج</button></div></header><form id="filters" class="report-filters"><label>طرف حساب<select name="party"><option value="">کل مجموعه</option>${catalog.parties.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("")}</select></label>${portable ? `<label>دوره منتشرشده<select name="period">${cloudBundle.periods.map((x) => `<option value="${esc(x.id)}">${esc(x.label)}</option>`).join("")}</select></label>` : `<label>از تاریخ شمسی<input name="start" placeholder="۱۴۰۵/۰۱/۰۱" inputmode="numeric"></label><label>تا تاریخ شمسی<input name="end" placeholder="۱۴۰۵/۰۸/۱۳" inputmode="numeric"></label>`}<button class="btn primary" type="submit">اعمال فیلتر / تازه‌سازی</button></form><nav class="report-tabs" aria-label="نوع گزارش">${Object.entries(
    tabs,
  )
    .map(
      ([k, v]) =>
        `<button class="btn ${tab === k ? "selected" : ""}" data-tab="${k}">${v}</button>`,
    )
    .join(
      "",
    )}</nav><div class="report-status" id="status" aria-live="polite">در حال خواندن دفتر…</div><section class="report-body" id="body"></section><footer>${catalog.demo ? "منبع: داده نمونه · " : ""}مازندشت ۰٫۷ · ${portable ? "نسخه فایل، بدون همگام‌سازی زنده" : "فقط‌خواندنی"} · اطلاعات مالی فقط در حافظه همین صفحه خوانده می‌شوند.</footer></main>`;
  q("#filters").addEventListener("submit", (e) => {
    e.preventDefault();
    load();
  });
}
async function load(auto = false) {
  const turn = ++generation;
  const filter =
    auto && report && !portable
      ? {
          party: report.filters.party,
          start: report.filters.from,
          end: report.filters.to,
        }
      : Object.fromEntries(new FormData(q("#filters")));
  const params = new URLSearchParams(
    Object.entries(filter).filter(([, v]) => v),
  );
  q("#status").textContent = "در حال دریافت گزارش…";
  try {
    const result = await api("/api/reports?" + params);
    if (turn !== generation) return;
    report = result;
    if (!auto) currentPage = 1;
    render();
  } catch (e) {
    if (turn !== generation) return;
    if (e.status === 401) {
      catalog = null;
      login();
    } else {
      q("#status").textContent =
        "فیلتر اعمال نشد؛ گزارش قبلی معتبر برای فیلتر قبلی است: " + e.message;
      q("#status").classList.add("report-error");
    }
  }
}
function metadata() {
  return `منبع: ${esc(catalog.source)} · نسخه ${esc(report.revision.slice(0, 12))} · دریافت ${new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", timeStyle: "medium" }).format(new Date(report.generated_at))} · واحد ${unitName()} · ${report.filters.party ? esc(report.filters.party) : "کل مجموعه"} · ${date(report.filters.from) || "ابتدای دفتر"} تا ${date(report.filters.to) || "آخرین سند"}`;
}
function table(headers, records, columns, paginate = true) {
  const size = 20,
    total = Math.max(1, Math.ceil(records.length / size));
  currentPage = Math.min(currentPage, total);
  const visible = paginate
    ? records.slice((currentPage - 1) * size, currentPage * size)
    : records;
  if (!records.length)
    return '<div class="empty">برای این فیلتر رکوردی ثبت نشده است.</div>';
  return `<div class="panel"><div class="report-table"><table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${visible.map((r) => `<tr class="${reportRowClass(r)}">${columns.map((c) => `<td>${typeof c === "function" ? c(r) : esc(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${paginate ? `<div class="pagination"><span>${fa(records.length)} ردیف · صفحه ${fa(currentPage)} از ${fa(total)}</span><div class="buttons"><button class="btn" data-action="prev" ${currentPage <= 1 ? "disabled" : ""}>قبلی</button><button class="btn" data-action="next" ${currentPage >= total ? "disabled" : ""}>بعدی</button></div></div>` : ""}</div>`;
}
function trend() {
  const totals = new Map();
  for (const e of report.events)
    if (e.kind === "فروش")
      totals.set(
        String(e.date),
        (totals.get(String(e.date)) || 0n) + BigInt(e.amount) * BigInt(e.sign),
      );
  const entries = [...totals].slice(-14);
  if (!entries.length) return "";
  const maximum = entries.reduce(
    (a, [, v]) => (v < 0n ? a : v > a ? v : a),
    1n,
  );
  return `<div class="report-trend"><h3>روند فروش · روزهای دارای گردش · ${unitName()}</h3><svg viewBox="0 0 700 130" role="img" aria-label="روند واقعی فروش روزانه"><path class="axis" d="M0 105H700"/>${entries
    .map(([day, v], i) => {
      const x = 15 + i * (670 / entries.length),
        h = Number(((v < 0n ? -v : v) * 80n) / maximum);
      return `<rect class="bar" x="${x}" y="${105 - Math.min(h, 90)}" width="${Math.max(8, Math.min(32, 500 / entries.length))}" height="${Math.min(h, 90)}" rx="5"><title>${esc(date(day))}: ${money(v)} ${unitName()}</title></rect><text x="${x}" y="125">${esc(day.slice(4, 6) + "/" + day.slice(6))}</text>`;
    })
    .join("")}</svg></div>`;
}
function card(title, value, kind = "money") {
  return `<div class="card"><div class="stathead">${title}</div><div class="statnum">${kind === "money" ? money(value) : fa(value)} <span>${kind === "money" ? unitName() : "مورد"}</span></div></div>`;
}
function contents(print = false) {
  const p = report.profit_loss,
    b = report.balance_sheet,
    pages = !print;
  if (tab === "overview")
    return (
      `<section class="report-hero"><div><span class="hero-kicker">MAZANDASHT / INTELLIGENCE</span><h2>نبض کسب‌وکار،<br>روشن و قابل اتکا.</h2><p>از گردش بانک تا سهم شراکت؛ هر عدد با منبع مشخص.</p><div class="hero-chips"><span>دفتر مستقیم Excel</span><span>${portable ? "گزارش رمزگذاری‌شده" : "گزارش زنده"}</span><span>${fa(report.events.length)} گردش دوره</span></div></div><div class="weather" id="weather"><span>آب‌وهوای منطقه</span><strong>مکان را انتخاب کنید</strong><button class="btn" data-action="weather">تنظیم منطقه</button></div><div class="orb orb-one"></div><div class="orb orb-two"></div></section>` +
      `<div class="report-cards">${card("کل درآمد دوره", p.revenue)}${card("سود خالص دوره", p.net_profit)}${card("هزینه‌های دوره", p.expenses)}${card("اسناد قطعی دوره", report.counts.posted_period, "count")}${card("قبض فاقد سند متصل", report.counts.pending_receipts, "count")}${card("چک‌های باز", report.counts.open_checks, "count")}</div>${trend()}<ul class="report-notes">${report.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`
    );
  if (tab === "events")
    return table(
      [
        "تاریخ",
        "عملیات",
        "طرف حساب",
        "قرارداد",
        `مبلغ (${unitName()})`,
        "مرجع",
      ],
      report.events,
      [
        (r) => esc(date(r.date)),
        "kind",
        "party",
        "deal",
        (r) => money(BigInt(r.amount) * BigInt(r.sign)),
        "reference",
      ],
      pages,
    );
  if (tab === "partnerships")
    return (
      '<div class="report-summary">مدل اصیل و تقسیم سود دوره؛ سود عملیاتی قبل از تخصیص است. پرداخت بانکی جداگانه ثبت می‌شود. مالکیت مشترک/امانی این مدل نیست.</div>' +
      table(
        [
          "قرارداد",
          "شریک",
          "درصد مجموعه",
          "سود عملیاتی",
          "سهم مجموعه",
          "سهم شریک",
          "تخصیص‌شده",
          "وضعیت",
        ],
        report.partnerships || [],
        [
          "deal",
          "partner",
          (r) => (r.error ? "—" : fa(Number(r.company_share) * 100) + "٪"),
          (r) => (r.error ? "—" : money(r.operating_profit)),
          (r) => (r.error ? "—" : money(r.company_profit)),
          (r) => (r.error ? "—" : money(r.partner_share_amount)),
          (r) => (r.error ? "—" : money(r.allocated)),
          (r) => esc(r.error || r.policy),
        ],
        pages,
      )
    );
  if (tab === "tables") {
    if (!portable)
      return '<div class="report-help">مرکز داده تفصیلی در فایل گزارش رمزگذاری‌شده منتشر می‌شود. برای اطلاعات زنده از تب‌های گردش، اشخاص، چک، موجودی و شراکت استفاده کنید.</div>';
    return `<div class="report-summary">${Object.entries(cloudBundle.tables)
      .map(
        ([k, v]) =>
          `<button class="btn" data-table="${k}">${esc(dataLabels[k] || k)} · ${fa(v.length)}</button>`,
      )
      .join("")}</div><div id="cloudtable">فهرست موردنظر را انتخاب کنید.</div>`;
  }
  if (tab === "profit")
    return table(
      ["شرح", `مبلغ (${unitName()})`],
      [
        ...report.trial
          .filter(
            (t) =>
              t.category === "revenue" &&
              (BigInt(t.debit) !== 0n || BigInt(t.credit) !== 0n),
          )
          .map((t) => ["درآمد · " + t.name, String(-BigInt(t.balance))]),
        ["جمع درآمد", p.revenue],
        ...report.trial
          .filter(
            (t) =>
              t.category === "expense" &&
              (BigInt(t.debit) !== 0n || BigInt(t.credit) !== 0n),
          )
          .map((t) => ["هزینه · " + t.name, t.balance]),
        ["جمع هزینه‌ها", p.expenses],
        ["سود خالص", p.net_profit],
      ],
      [(r) => esc(r[0]), (r) => money(r[1])],
      false,
    );
  if (tab === "balance")
    return table(
      ["عنوان کل مجموعه تا تاریخ پایان", `مانده (${unitName()})`],
      [
        ["دارایی‌ها", b.assets],
        ["بدهی‌ها", b.liabilities],
        ["سرمایه", b.capital],
        ["سود انباشته باز دفتر", b.retained_profit],
        ["اختلاف معادله (باید صفر باشد)", b.difference],
      ],
      [(r) => esc(r[0]), (r) => money(r[1])],
      false,
    );
  if (tab === "accounts")
    return table(
      [
        "طرف حساب",
        `دریافتنی (${unitName()})`,
        `پرداختنی (${unitName()})`,
        `خالص طلب مجموعه (${unitName()})`,
      ],
      report.parties,
      [
        "name",
        (r) => money(r.receivable),
        (r) => money(r.payable),
        (r) => money(r.net),
      ],
      pages,
    );
  if (tab === "banks")
    return table(
      ["نام حساب بانکی", `مانده کل مجموعه تا پایان (${unitName()})`],
      report.banks,
      ["name", (r) => money(r.balance)],
      pages,
    );
  if (tab === "statement") {
    if (!report.filters.party)
      return '<div class="empty">برای صورت‌حساب، یک طرف حساب را انتخاب و فیلتر را اعمال کنید.</div>';
    return (
      `<div class="report-summary">مانده قبل از دوره: ${money(report.statement.opening)} ${unitName()} · مانده پایان: ${money(report.statement.closing)} ${unitName()} · مثبت: طلب مجموعه / منفی: بدهی مجموعه</div>` +
      table(
        [
          "تاریخ",
          "نوع سند",
          "مرجع",
          `بدهکار (${unitName()})`,
          `بستانکار (${unitName()})`,
          `مانده (${unitName()})`,
          "شرح",
        ],
        report.statement.rows,
        [
          (r) => esc(date(r.date)),
          "kind",
          "reference",
          (r) => money(r.debit),
          (r) => money(r.credit),
          (r) => money(r.balance),
          "note",
        ],
        pages,
      )
    );
  }
  if (tab === "banksource") return '<div class="report-summary">'+esc(report.bank_statements?.note || "")+'</div>'+table(["تاریخ","بانک","واریز","برداشت","شخص","عملیات","وضعیت","اصلاح"],report.bank_statements?.rows||[],[r=>date(r.date),"bank",r=>money(r.deposit||0),r=>money(r.withdrawal||0),"party","kind","status","correction"],pages);
  if (tab === "physical") return '<div class="report-summary">'+esc(report.physical?.note || "")+'</div>'+table(["شخص","محصول","نوع سبد","انبار","کیلوگرم"],report.physical?.balances||[],["party","product","basket","store",r=>fa(r.qty)],pages)+'<h3>سبد امانی؛ مثبت یعنی نزد طرف حساب</h3>'+table(["شخص","نوع سبد","تعداد"],report.physical?.custody||[],["party","basket",r=>fa(r.count)],false);
  if (tab === "unbilled")
    return (
      '<div class="report-summary">قبض‌های فاقد سند خرید/فروش متصل؛ این عنوان لزوماً به معنی صادرنشدن فاکتور کاغذی نیست. سند برگشت‌خورده مصرف نهایی قبض محسوب نمی‌شود.</div>' +
      table(
        [
          "تاریخ",
          "شماره قبض",
          "طرف حساب",
          "عملیات",
          "محصول",
          "انبار",
          "خالص (کیلوگرم)",
          "قرارداد",
        ],
        report.unbilled_receipts,
        [
          (r) => esc(date(r.date)),
          "reference",
          "party",
          "operation",
          "product",
          "store",
          (r) => (r.net === null ? "نیازمند بررسی" : fa(r.net)),
          "deal",
        ],
        pages,
      )
    );
  if (tab === "checks")
    return table(
      [
        "شماره",
        "جهت",
        "طرف حساب",
        "بانک",
        `مبلغ (${unitName()})`,
        "سررسید",
        "وضعیت جاری",
      ],
      report.checks,
      [
        "number",
        "direction",
        "party",
        "bank",
        (r) => money(r.amount),
        (r) => esc(date(r.due)),
        "state",
      ],
      pages,
    );
  if (tab === "stock")
    return table(
      ["محصول", "انبار", "موجودی کل مجموعه (کیلوگرم)"],
      report.stock,
      ["product", "store", (r) => fa(r.qty)],
      pages,
    );
  if (tab === "trial")
    return table(
      [
        "حساب",
        `گردش بدهکار (${unitName()})`,
        `گردش بستانکار (${unitName()})`,
        `خالص گردش دوره (${unitName()})`,
      ],
      report.trial,
      [
        "name",
        (r) => money(r.debit),
        (r) => money(r.credit),
        (r) => money(r.balance),
      ],
      pages,
    );
  return `<article class="panel report-help"><h3>داشبورد فقط نمایش می‌دهد</h3><p>ثبت، اصلاح، تأیید، ورود فایل، بازیابی و تغییر کاربران فقط روی سیستم مرکزی انجام می‌شوند. این محدودیت در سرور اعمال شده، نه فقط با مخفی‌کردن دکمه‌ها.</p><p>روی iPhone و iPad، نشانی داشبورد سیستم مرکزی را در Safari باز کنید. از Share → Add to Home Screen می‌توانید میان‌بر بسازید؛ افزونه، فایل APK یا برنامه App Store لازم نیست. دستگاه و سیستم مرکزی باید در یک شبکه امن یا VPN باشند. برای دسترسی اینترنتی HTTPS و VPN لازم است؛ پورت ثبت را روی اینترنت باز نکنید.</p><p>برنامه هر ۳۰ ثانیه، فقط وقتی صفحه نمایان است، گزارش را تازه می‌کند. تغییرات نهایی از همان فایل مرکزی خوانده می‌شوند؛ پشتیبان‌ها منبع جداگانه جمع‌زدن تراکنش نیستند. اتصال به دفتر قدیمی یا JSON پشتیبان بدون تطبیق انجام نمی‌شود.</p><p>حساب گزارش‌خوان فعلی به گزارش‌های کل مجموعه دسترسی دارد؛ این نسخه پرتال مشتری با جداسازی اطلاعات هر مشتری نیست.</p></article>`;
}
function render() {
  if (!report) return;
  q("#status").classList.remove("report-error");
  q("#status").innerHTML = metadata();
  q("#body").innerHTML = contents();
  if (tab === "overview") renderWeather();
  document
    .querySelectorAll("[data-tab]")
    .forEach((b) => b.classList.toggle("selected", b.dataset.tab === tab));
}
function print() {
  if (!report) return;
  const w = window.open("", "_blank");
  if (!w) return toast("اجازه بازشدن پنجره چاپ را فعال کنید.");
  w.document.write(
    `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>${esc(tabs[tab])}</title><link rel="stylesheet" href="/static/print.css"></head><body><h1>مازندشت</h1><h2>${esc(tabs[tab])}</h2><p>${metadata()}</p>${contents(true)}<footer>گزارش مدیریتی دفتر مرکزی · ${catalog.demo ? "داده ساختگی" : "فقط‌خواندنی"}</footer></body></html>`,
  );
  w.document.close();
  w.addEventListener("load", () => w.print(), { once: true });
}
root.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-tab],[data-action],[data-table]");
  if (!b) return;
  try {
    if (b.dataset.table) {
      const rows = cloudBundle.tables[b.dataset.table];
      const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter(
        (k) => !k.endsWith("_id") && k !== "id",
      );
      q("#cloudtable").innerHTML = table(
        cols.map((k) => dataLabels[k] || k),
        rows,
        cols,
        false,
      );
      return;
    }
    if (b.dataset.tab) {
      tab = b.dataset.tab;
      currentPage = 1;
      render();
      return;
    }
    const a = b.dataset.action;
    if (a === "source") {
      if (portable) {
        cloudBundle = null;
        catalog = null;
        report = null;
        fileGate();
      } else window.open("/viewer", "_blank");
    } else if (a === "weather") weatherSettings();
    else if (a === "print") print();
    else if (a === "unit") {
      const choices=MazMoney.units(report?.currencies);
      unit=choices[(choices.indexOf(unit)+1)%choices.length];
      b.textContent = unitName();
      render();
    } else if (a === "prev") {
      currentPage--;
      render();
    } else if (a === "next") {
      currentPage++;
      render();
    } else if (a === "logout") {
      if (portable) {
        cloudBundle = null;
        catalog = null;
        report = null;
        fileGate();
        return;
      }
      await api("/api/logout", "POST", {});
      const demo = catalog.demo;
      catalog = null;
      report = null;
      if (demo) await init();
      else login();
    }
  } catch (err) {
    toast(err.message);
  }
});
async function init() {
  if (portable && !cloudBundle) {
    fileGate();
    return;
  }
  try {
    health = await api("/api/health");
    catalog = await api("/api/catalog");
    shell();
    await load();
  } catch (e) {
    if (e.status === 401) login();
    else
      root.innerHTML = `<div class="errorpanel"><h2>اتصال به دفتر مرکزی برقرار نشد</h2><p>${esc(e.message)}</p><p>سرویس مرکزی، مسیر فایل و اتصال شبکه را بررسی کنید.</p></div>`;
  }
}
setInterval(() => {
  if (catalog && q("#filters") && document.visibilityState === "visible")
    load(true);
}, 30000);
init();

function fileGate() {
  root.innerHTML = `<div class="cloud-gate"><div class="cloud-story"><span class="hero-kicker">MAZANDASHT / PRIVATE REPORTS</span><h1>دفتر شما،<br>هرجا که هستید.</h1><p>یک داشبورد؛ از فایل خصوصی Drive تا گزارش‌های کامل کسب‌وکار.<br>فایل و رمز شما به این وب‌سایت آپلود نمی‌شوند.</p><div class="hero-chips"><span>AES-256-GCM</span><span>فقط گزارش</span><span>بدون حساب ابری جدید</span></div></div><form id="open-cloud" class="cloud-form"><h2>بازکردن گزارش خصوصی</h2><p>فایل .mazreport را از پوشه خصوصی Drive دانلود یا از Files انتخاب کنید. رمز گزارش را جداگانه از مدیر بگیرید.</p><label>فایل گزارش<input id="cloud-file" type="file" accept=".mazreport" required></label><label>رمز فایل<input id="cloud-password" type="password" autocomplete="off" required></label><button class="btn primary" type="submit">رمزگشایی و مشاهده گزارش</button><div id="cloud-error" role="alert"></div><small>گزارش، نسخه زمان انتشار است؛ اتصال مستقیم یا همگام‌سازی خودکار با Drive نیست.</small></form></div>`;
  q("#open-cloud").addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = e.target.querySelector("button");
    button.disabled = true;
    try {
      cloudBundle = await MazReport.decrypt(
        q("#cloud-file").files[0],
        q("#cloud-password").value,
      );
      q("#cloud-password").value = "";
      await init();
    } catch (error) {
      cloudBundle = null;
      q("#cloud-error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
}
let weatherState = null,
  weatherLocation = null;
function weatherSettings() {
  const host = q("#weather");
  if (!host) return;
  host.innerHTML = `<form id="weather-form"><label>نام منطقه<input name="label" placeholder="مثلاً ساری" required></label><div class="weather-coordinates"><label>عرض جغرافیایی<input name="lat" type="number" min="-90" max="90" step="any" required></label><label>طول جغرافیایی<input name="lon" type="number" min="-180" max="180" step="any" required></label></div><button class="btn" type="submit">دریافت آب‌وهوا</button><small>فقط مختصات برای Open-Meteo ارسال می‌شود؛ هیچ داده مالی ارسال نمی‌شود.</small></form>`;
  q("#weather-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = Object.fromEntries(new FormData(e.target));
    weatherLocation = {
      label: v.label,
      lat: Number(v.lat),
      lon: Number(v.lon),
    };
    await loadWeather();
  });
}
async function loadWeather() {
  if (!weatherLocation) return;
  const host = q("#weather");
  if (host) host.textContent = "دریافت وضعیت واقعی منطقه…";
  try {
    const u = new URL("https://api.open-meteo.com/v1/forecast");
    u.search = new URLSearchParams({
      latitude: weatherLocation.lat,
      longitude: weatherLocation.lon,
      current: "temperature_2m,weather_code,wind_speed_10m,is_day",
      timezone: "auto",
    });
    const response = await fetch(u, {
      signal: AbortSignal.timeout(8000),
      referrerPolicy: "no-referrer",
      credentials: "omit",
    });
    if (!response.ok) throw Error();
    const d = await response.json();
    if (
      typeof d.current?.temperature_2m !== "number" ||
      typeof d.current?.weather_code !== "number"
    )
      throw Error();
    weatherState = { ...d.current, units: d.current_units };
    renderWeather();
  } catch (e) {
    weatherState = null;
    if (q("#weather"))
      q("#weather").innerHTML =
        '<strong>اتصال آب‌وهوا برقرار نشد</strong><small>داده تخمینی نمایش داده نمی‌شود؛ شبکه یا ارائه‌دهنده در دسترس نیست.</small><button class="btn" data-action="weather">تنظیم دوباره منطقه</button>';
  }
}
function renderWeather() {
  const host = q("#weather");
  if (!host) return;
  if (!weatherState) {
    if (weatherLocation) loadWeather();
    return;
  }
  const rainy = weatherState.weather_code >= 50,
    cloudy = weatherState.weather_code > 0;
  host.className = "weather " + (rainy ? "rainy" : cloudy ? "cloudy" : "sunny");
  host.innerHTML = `<span class="weather-orbit">${rainy ? "☂" : cloudy ? "☁" : "☀"}</span><span>${esc(weatherLocation.label)}</span><strong>${fa(weatherState.temperature_2m)}° <small>${rainy ? "بارش" : cloudy ? "ابری / مه" : "آسمان صاف"}</small></strong><small>باد ${fa(weatherState.wind_speed_10m)} ${esc(weatherState.units.wind_speed_10m)} · ${esc(weatherState.time)}</small><button class="btn" data-action="weather">تغییر منطقه</button><small>Open-Meteo · وضعیت دریافتی، نه پیش‌بینی ساختگی</small>`;
}

function reportRowClass(r) { if (r.deposit && BigInt(r.deposit)>0n) return "row-deposit";const op=r.operation||"";return /انتقال|سورتینگ|سردخانه/.test(op)?"row-transfer":/سبد/.test(op)?"row-basket":/مرجوعی|برگشت/.test(op)?"row-return":/خرید|^ورود/.test(op)?"row-in":/فروش|^خروج/.test(op)?"row-out":"";}
