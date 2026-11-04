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
let catalog,
  report,
  health,
  tab = "overview",
  unit = "IRR",
  currentPage = 1,
  generation = 0;
const tabs = {
  overview: "نمای مدیریت",
  profit: "سود و زیان",
  balance: "وضعیت مالی",
  accounts: "مانده اشخاص",
  statement: "صورت‌حساب شخص",
  banks: "مانده بانک‌ها",
  unbilled: "رسیدهای فاکتورنشده",
  checks: "چک‌ها",
  stock: "موجودی",
  trial: "تراز دوره",
  help: "راهنمای اتصال",
};
function money(value) {
  let n = BigInt(value || "0");
  const sign = n < 0n ? "−" : "";
  if (n < 0n) n = -n;
  return (
    sign +
    new Intl.NumberFormat("fa-IR").format(unit === "IRR" ? n : n / 10n) +
    (unit === "IRT" && n % 10n ? "٫" + fa(n % 10n) : "")
  );
}
const unitName = () => (unit === "IRR" ? "ریال" : "تومان");
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
  root.innerHTML = `<main class="report-shell"><header class="report-top"><div class="report-brand"><h1>مازندشت · پنل گزارش</h1><p>${esc(catalog.user.name)} · فقط مشاهده از دفتر مرکزی</p></div><div class="buttons">${catalog.central ? '<a class="btn" href="/">بازگشت به ثبت مرکزی</a>' : ""}<span class="badge">ثبت فقط در سیستم مرکزی</span><button class="btn" data-action="unit">${unitName()}</button><button class="btn" data-action="print">چاپ / PDF</button><button class="btn" data-action="logout">خروج</button></div></header>${catalog.demo ? '<div class="notice">پیش‌نمایش با داده ساختگی؛ این ارقام سوابق واقعی شما نیستند. نصب واقعی به‌صورت پیش‌فرض دفتر خالی و ورود اجباری دارد.</div>' : ""}<form id="filters" class="report-filters"><label>طرف حساب<select name="party"><option value="">کل مجموعه</option>${catalog.parties.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("")}</select></label><label>از تاریخ شمسی<input name="start" placeholder="۱۴۰۵/۰۱/۰۱" inputmode="numeric"></label><label>تا تاریخ شمسی<input name="end" placeholder="۱۴۰۵/۰۸/۱۳" inputmode="numeric"></label><button class="btn primary" type="submit">اعمال فیلتر / تازه‌سازی</button></form><nav class="report-tabs" aria-label="نوع گزارش">${Object.entries(
    tabs,
  )
    .map(
      ([k, v]) =>
        `<button class="btn ${tab === k ? "selected" : ""}" data-tab="${k}">${v}</button>`,
    )
    .join(
      "",
    )}</nav><div class="report-status" id="status" aria-live="polite">در حال خواندن دفتر…</div><section class="report-body" id="body"></section><footer>مازندشت ۰٫۶ · فقط‌خواندنی · گزارش مدیریتی، نه صورت مالی قانونی · اطلاعات در مرورگر برای استفاده آفلاین ذخیره نمی‌شوند.</footer></main>`;
  q("#filters").addEventListener("submit", (e) => {
    e.preventDefault();
    load();
  });
}
async function load(auto = false) {
  const turn = ++generation;
  const filter =
    auto && report
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
  return `<div class="panel"><div class="report-table"><table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${visible.map((r) => `<tr>${columns.map((c) => `<td>${typeof c === "function" ? c(r) : esc(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${paginate ? `<div class="pagination"><span>${fa(records.length)} ردیف · صفحه ${fa(currentPage)} از ${fa(total)}</span><div class="buttons"><button class="btn" data-action="prev" ${currentPage <= 1 ? "disabled" : ""}>قبلی</button><button class="btn" data-action="next" ${currentPage >= total ? "disabled" : ""}>بعدی</button></div></div>` : ""}</div>`;
}
function card(title, value, kind = "money") {
  return `<div class="card"><div class="stathead">${title}</div><div class="statnum">${kind === "money" ? money(value) : fa(value)} <span>${kind === "money" ? unitName() : "مورد"}</span></div></div>`;
}
function contents(print = false) {
  const p = report.profit_loss,
    b = report.balance_sheet,
    pages = !print;
  if (tab === "overview")
    return `<div class="report-cards">${card("درآمد فروش دوره", p.revenue)}${card("سود خالص دوره", p.net_profit)}${card("هزینه‌های دوره", p.expenses)}${card("اسناد قطعی دوره", report.counts.posted_period, "count")}${card("قبض فاقد سند متصل", report.counts.pending_receipts, "count")}${card("چک‌های باز", report.counts.open_checks, "count")}</div><ul class="report-notes">${report.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`;
  if (tab === "profit")
    return table(
      ["شرح", `مبلغ (${unitName()})`],
      [
        ["درآمد فروش", p.revenue],
        ["بهای تمام‌شده", p.cogs],
        ["هزینه عملیاتی", p.operating_expense],
        ["دستمزد", p.wages],
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
  const b = e.target.closest("[data-tab],[data-action]");
  if (!b) return;
  try {
    if (b.dataset.tab) {
      tab = b.dataset.tab;
      currentPage = 1;
      render();
      return;
    }
    const a = b.dataset.action;
    if (a === "print") print();
    else if (a === "unit") {
      unit = unit === "IRR" ? "IRT" : "IRR";
      b.textContent = unitName();
      render();
    } else if (a === "prev") {
      currentPage--;
      render();
    } else if (a === "next") {
      currentPage++;
      render();
    } else if (a === "logout") {
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
