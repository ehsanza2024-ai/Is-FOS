"use strict";
const $ = (s) => document.querySelector(s),
  app = $("#app"),
  modal = $("#modal");
const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  scale: "M12 3v18 M5 21h14 M4 7h16 M5 7l-3 7h6L5 7 M19 7l-3 7h6l-3-7",
  basket: "M3 9h18l-2 11H5L3 9 M7 9l5-7 5 7 M9 13v4 M15 13v4",
  buy: "M3 4h2l3 12h11l3-9H6 M10 21h.01 M18 21h.01 M12 3v8 M9 8l3 3 3-3",
  sale: "M3 4h2l3 12h11l3-9H6 M10 21h.01 M18 21h.01 M12 11V3 M9 6l3-3 3 3",
  bank: "M3 9h18L12 3 3 9 M3 21h18 M6 10v8 M12 10v8 M18 10v8",
  check: "M3 5h18v14H3z M6 9h5 M6 13h3 M14 13l2 2 3-4",
  book: "M12 5C8 2 4 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-4-1-7-2-10 1z M12 5v16",
  stock: "M3 7l9-5 9 5v10l-9 5-9-5V7 M3 7l9 5 9-5 M12 12v10 M7 4l10 5",
  upload: "M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6",
  report: "M4 21V3h16v18z M8 16v-3 M12 16V8 M16 16v-6",
  settings:
    "M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  spark: "M12 2l3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7",
  plus: "M12 5v14 M5 12h14",
  search: "M21 21l-6-6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  download: "M12 3v13 M7 11l5 5 5-5 M4 16v5h16v-5",
  print: "M6 8V3h12v5 M6 17H3V8h18v9h-3 M6 13h12v8H6z",
  full: "M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5",
  arrow: "M5 12h14 M14 7l5 5-5 5",
  close: "M6 6l12 12 M6 18L18 6",
  shield: "M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4 M8 12l3 3 5-6",
  clock: "M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  leaf: "M20 3C8 1 2 9 6 16c8 6 16-2 14-13 M4 21L16 8",
  logout: "M9 3H3v18h6 M9 12h12 M17 8l4 4-4 4",
};
const icon = (name, cls = "") =>
  `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.book}"/></svg>`;
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fa = (n) =>
  new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(
    Number(n || 0),
  );
const fmtDate = (v) => {
  let s = String(v || "");
  return s.length === 8
    ? s.slice(0, 4) + "/" + s.slice(4, 6) + "/" + s.slice(6)
    : s;
};
const badge = (s, cl = "") =>
  `<span class="badge ${cl || (/برگشت|نامشخص/.test(s) ? "red" : /ثبت‌شده|پیش|بازبینی/.test(s) ? "amber" : "")}">${esc(s)}</span>`;
let S = null,
  health = null,
  page = "dashboard",
  tab = "Parties",
  pageNum = 1,
  search = "",
  from = "",
  to = "",
  unit = "AUTO",
  preview = null,
  backups = [];
const nav = [
  ["dashboard", "میز مدیریت", "grid", "فضای کار"],
  ["weigh", "باسکول و محموله", "scale", "عملیات و تجارت"],
  ["buy", "خرید محصول", "buy", ""],
  ["sale", "فروش محصول", "sale", ""],
  ["stock", "انبار و موجودی", "stock", ""],
  ["bank", "بانک و خزانه", "bank", "مالی و حسابداری"],
  ["bankreview", "تطبیق صورت‌حساب‌ها", "bank", ""],
  ["checks", "مدیریت چک‌ها", "check", ""],
  ["cost", "هزینه و دستمزد", "book", ""],
  ["ledger", "دفترکل و تراز", "report", ""],
  ["import", "استودیو ورود اطلاعات", "upload", "مدیریت داده"],
  ["refs", "تعاریف پایه و شراکت", "settings", ""],
  ["insights", "تحلیل مدیریتی", "spark", ""],
  ["workbench", "همکاری و توسعه", "spark", ""],
  ["help", "راهنما و پشتیبان", "shield", ""],
];
const titles = Object.fromEntries(nav.map((n) => [n[0], n[1]]));
const refTitles = {
  Parties: "اشخاص",
  Baskets: "نوع سبد",
  Products: "محصولات",
  Stores: "انبارها",
  Banks: "بانک‌ها",
  Deals: "قرارداد شراکت",
  Groups: "گروه و زیرگروه",
  Accounts: "سرفصل حساب",
  Operations: "نوع عملیات",
  Currencies: "ارز و نسبت با ریال",
};
const refFields = {
  Currencies: [["name","نام ارز"],["rial_per_unit","ریال معادل یک واحد ارز","number"]],
  Groups: [
    ["name", "نام گروه"],
    ["parent", "گروه والد (اختیاری)", "ref", "Groups"],
    [
      "category",
      "طبقه ریشه",
      "select",
      ["asset", "liability", "equity", "revenue", "expense"],
    ],
    ["note", "یادداشت"],
  ],
  Accounts: [
    ["name", "نام سرفصل"],
    ["group", "گروه حساب", "ref", "Groups"],
    ["category", "طبقه (از گروه تعیین می‌شود)"],
    ["note", "یادداشت"],
  ],
  Operations: [
    ["name", "عنوان عملیات"],
    ["debit", "حساب بدهکار", "ref", "Accounts"],
    ["credit", "حساب بستانکار", "ref", "Accounts"],
    ["note", "یادداشت"],
  ],
  Parties: [
    ["name", "نام طرف حساب"],
    ["code", "کد (خالی = تخصیص خودکار)"],
    ["group", "گروه (اختیاری)", "ref", "Groups"],
    ["note", "توضیحات"],
    ["role", "نقش"],
    ["nature", "ماهیت شخص"],
    ["subgroup", "زیرماهیت"],
    ["accounting_group", "گروه حسابداری"],
    ["audit_group", "گروه حسابرسی"],
    ["active", "فعال", "select", ["بله", "خیر"]],
  ],
  Baskets: [
    ["name", "نام سبد"],
    ["tare", "تارای واقعی هر سبد (کیلوگرم)", "number"],
  ],
  Products: [["name", "نام محصول"],["group","گروه محصول"],["note","شرح رابطه"]],
  Stores: [["name", "نام انبار"]],
  Banks: [["name", "نام حساب بانکی"]],
  Deals: [
    ["name", "عنوان قابل تشخیص قرارداد"],
    ["partner", "نام شریک", "ref", "Parties"],
    ["share_percent", "درصد سهم مجموعه (۰ تا ۱۰۰)", "number"],
    [
      "policy",
      "سیاست حسابداری",
      "select",
      ["نیاز به تعیین", "اصیل؛ تقسیم سود دوره"],
    ],
    ["start", "شروع قرارداد"],
    ["end", "پایان قرارداد"],
    ["product", "محصول", "ref", "Products"],
    ["status", "وضعیت", "select", ["نیاز به بازبینی", "تأیید", "بسته"]],
  ],
};
async function api(url, method = "GET", body) {
  let options = { method, headers: { "X-Mazandasht-Request": "1" } };
  if (body instanceof FormData) options.body = body;
  else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const r = await fetch(url, options);
  if (!r.ok) {
    let d;
    try {
      d = await r.json();
    } catch {
      d = { detail: "خطا در ارتباط با دفتر اکسل" };
    }
    if (r.status === 401 && url != "/api/login") {
      showLogin();
    }
    const err = Error(
      typeof d.detail === "string" ? d.detail : "داده ورودی معتبر نیست",
    );
    err.status = r.status;
    throw err;
  }
  return r.json();
}
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").classList.add("show");
  setTimeout(() => $("#toast").classList.remove("show"), 4500);
}
const money=v=>MazMoney.format(v,unit,S?.Settings,S?.Currencies);
const moneyLabel=()=>MazMoney.view(unit,S?.Settings,S?.Currencies).name;
const btn = (text, action, type = "", ico = "") =>
  `<button class="btn ${type}" data-action="${action}">${ico ? icon(ico) : ""}${text}</button>`;
let stateEpoch = 0;
async function refresh() {
  const epoch = ++stateEpoch;
  const current = await api("/api/state");
  if (epoch !== stateEpoch) return;
  S = current;
  render();
}
function showLogin() {
  app.innerHTML = `<div class="login"><form class="loginbox" id="login"><div class="mark">${icon("leaf")}</div><h1>ورود به مازندشت</h1><p>دفتر شما، روی سیستم شما.<br>سامانه محلی مالی و عملیاتی با هسته اکسل</p><label>نام کاربری<input name="name" autocomplete="username" required></label><label>رمز عبور<input type="password" name="password" autocomplete="current-password" required></label><button class="btn primary" type="submit">ورود امن ${icon("arrow")}</button><div class="formerror" id="loginerror"></div></form></div>`;
  $("#login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api(
        "/api/login",
        "POST",
        Object.fromEntries(new FormData(e.target)),
      );
      await refresh();
    } catch (err) {
      $("#loginerror").textContent = err.message;
    }
  });
}
function render() {
  if (!S) return;
  app.innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand"><div class="mark">${icon("leaf")}</div><div><h1>مازندشت</h1><small>MAZANDASHT</small></div></div><nav>${nav.map(([id, label, i, group]) => `${group ? `<div class="navgroup">${group}</div>` : ""}<button class="navitem ${page === id ? "active" : ""}" data-page="${id}" title="${label}">${icon(i)}<span>${label}</span></button>`).join("")}</nav><div class="sidebarfoot"><i class="pulse"></i><span>متصل به دفتر اکسل محلی</span></div></aside><section class="workspace"><header class="topbar"><div class="breadcrumb">مازندشت <span> / </span><b>${titles[page]}</b></div><div class="topactions"><span class="date">${esc(health?.today)} · دفتر محلی</span><button class="iconbtn" data-action="unit" title="تغییر واحد نمایش">${esc(moneyLabel())}</button><button class="iconbtn" data-action="fullscreen" title="تمام صفحه">${icon("full")}</button><div class="profile"><span class="avatar">م</span><div><strong>${esc(S.user.name)}</strong><small>${esc(S.user.role)} · فضای ${S.demo ? "آموزشی" : "محلی"}</small></div></div><button class="iconbtn" data-action="logout" title="خروج">${icon("logout")}</button></div></header><main class="content"><div class="heading"><div><div class="eyebrow">MAZANDASHT / WORKSPACE</div><h2>${page === "dashboard" ? "همه‌چیز، در یک نگاه." : titles[page]}</h2><p>${subtitle()}</p></div><div class="buttons">${btn("خروجی اکسل", "export", "", "download")}${newButton()}</div></div><div id="pagecontent" class="pagecontent"></div><footer class="footnote"><span>${icon("shield")}ذخیره محلی · ریال صحیح · پشتیبان پیش از هر تغییر</span><span>مازندشت ۰٫۸ · ${S.demo ? "نمونه آموزشی" : "دفتر اکسل"} · ${esc(titles[page])}</span></footer></main></section></div>`;
  $("#pagecontent").className =
    page === "dashboard"
      ? "pagecontent dashcontents"
      : "pagecontent normalcontents";
  if (page === "dashboard")
    $("#pagecontent").innerHTML =
      '<iframe class="unified-reports" title="داشبورد یکپارچه گزارش" src="/reports"></iframe>';
  else if (page === "import") importPage();
  else if (page === "help") help();
  else if (page === "insights") insights();
  else if (page === "workbench") workbench();
  else if (page === "bankreview") bankReviewPage();
  else listPage();
}
function subtitle() {
  return (
    {
      dashboard: "تصویر روشن عملیات و مالی مجموعه، مستقیماً از دفتر اکسل.",
      weigh: "اندازه‌گیری فیزیکی مستقل از سند مالی؛ تارای نامشخص صفر نیست.",
      buy: "خرید قطعی کالای متعلق به مجموعه و افزایش موجودی.",
      sale: "فروش قطعی با کنترل موجودی و بهای تمام‌شده تأییدشده.",
      stock: "موجودی محاسبه‌شده از اسناد قطعی خرید و فروش.",
      bank: "دریافت، پرداخت و سرمایه؛ مبلغ ورود همیشه ریال است.",
      checks: "دفتر چرخه چک؛ تغییر وضعیت به‌تنهایی سند بانکی ایجاد نمی‌کند.",
      cost: "هزینه و دستمزد با ثبت هم‌زمان سند دوبل.",
      ledger: "فقط اسناد قطعی؛ مانده‌ها مستقیماً از دفترکل بازسازی می‌شوند.",
      refs: "نام‌ها در پیش‌زمینه، شناسه‌های پایدار در پس‌زمینه.",
      import: "پیش‌نمایش، کنترل خطا و ثبت یک‌باره فایل بانکی.",
      insights: "تحلیل قاعده‌محور، محلی و قابل ردیابی؛ بدون ارسال داده.",
      help: "راهنمای کار، پشتیبان‌گیری و وضعیت شفاف نسخه.",
    }[page] || ""
  );
}
function newButton() {
  if (["weigh", "buy", "sale", "bank", "checks", "cost", "refs"].includes(page))
    return btn(
      page === "refs" ? "تعریف جدید" : "ثبت جدید",
      "new",
      "primary",
      "plus",
    );
  return btn("پنل گزارش‌ها", "reports", "", "chart");
}
function rowsPerPage() {
  return Math.max(3, Math.min(12, Math.floor((innerHeight - 390) / 44)));
}
function filterRecords(records) {
  const q = search.trim().toLowerCase();
  return records.filter(
    (r) =>
      (!q ||
        Object.entries(r)
          .filter(([k]) => k !== "id" && !k.endsWith("_id"))
          .some(([, v]) =>
            String(v ?? "")
              .toLowerCase()
              .includes(q),
          )) &&
      (!from || !r.date || String(r.date) >= from.replaceAll("/", "")) &&
      (!to || !r.date || String(r.date) <= to.replaceAll("/", "")),
  );
}
const empty = () =>
  `<div class="empty">${icon("book")}هنوز رکوردی در این بخش ثبت نشده است.<br>با «ثبت جدید» شروع کنید یا فیلترها را تغییر دهید.</div>`;
function table(headers, body) {
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
}
function eventTable(records, actions = true) {
  if (!records.length) return empty();
  return table(
    [
      "تاریخ",
      "رویداد",
      "طرف حساب",
      `مبلغ (${moneyLabel()})`,
      "وضعیت",
      ...(actions ? ["عملیات"] : []),
    ],
    records
      .map(
        (r) =>
          `<tr><td>${fmtDate(r.date)}</td><td><strong>${esc(r.kind)}</strong></td><td>${esc(r.party)}</td><td>${money(r.amount * r.sign)}</td><td>${badge(r.sign === -1 ? "برگشت" : "قطعی")}</td>${actions ? `<td>${r.sign !== -1 && !S.Events.some((x) => x.reversal_of === r.id) ? `<button class="btn danger" data-reverse="${esc(r.id)}">برگشت با علت</button>` : "—"}</td>` : ""}</tr>`,
      )
      .join(""),
  );
}
function listRecords() {
  if (page === "refs") return S[tab];
  if (page === "stock") return S.stock;
  if (page === "ledger") return S.trial;
  if (page === "checks") return S.Checks;
  if (page === "weigh") return S.Weigh;
  return S.Events.filter((x) =>
    page === "buy"
      ? x.kind === "خرید"
      : page === "sale"
        ? x.kind === "فروش"
        : page === "bank"
          ? ["دریافت", "پرداخت", "سرمایه"].includes(x.kind)
          : !["خرید", "فروش", "دریافت", "پرداخت", "سرمایه"].includes(x.kind),
  );
}
function listPage() {
  let records = filterRecords(listRecords()),
    count = rowsPerPage(),
    pages = Math.max(1, Math.ceil(records.length / count));
  pageNum = Math.min(pageNum, pages);
  let visible = records.slice((pageNum - 1) * count, pageNum * count);
  $("#pagecontent").innerHTML = `${
    page === "refs"
      ? `<div class="tabs">${Object.entries(refTitles)
          .map(
            ([k, v]) =>
              `<button class="btn ${tab === k ? "selected" : ""}" data-tab="${k}">${v}</button>`,
          )
          .join("")}</div>`
      : ""
  }<section class="panel fullpanel"><div class="toolbar"><div class="search">${icon("search")}<input id="search" placeholder="جست‌وجو در نام، شرح یا مرجع…" value="${esc(search)}" aria-label="جست‌وجو"></div>${!["refs", "stock", "ledger"].includes(page) ? `<input id="from" placeholder="از تاریخ: ۱۴۰۵/۰۱/۰۱" value="${esc(from)}" aria-label="از تاریخ"><input id="to" placeholder="تا تاریخ" value="${esc(to)}" aria-label="تا تاریخ">` : ""}<span class="badge">${fa(records.length)} ${page === "ledger" ? "حساب" : "رکورد"}</span><div class="buttons">${btn("تازه‌سازی", "refresh", "", "clock")}${btn("چاپ", "print", "", "print")}</div></div><div class="tablewrap" id="listtable">${renderList(visible)}</div><div class="pagination"><span>صفحه ${fa(pageNum)} از ${fa(pages)} · ${fa(records.length)} مورد</span><div class="buttons"><button class="btn" data-action="prev" ${pageNum <= 1 ? "disabled" : ""}>قبلی</button><button class="btn" data-action="next" ${pageNum >= pages ? "disabled" : ""}>بعدی</button></div></div></section>`;
  ["search", "from", "to"].forEach((id) => {
    const el = $("#" + id);
    if (el)
      el.addEventListener("input", () => {
        let pos = el.selectionStart;
        const val = el.value.replace(/[۰-۹]/g, (c) => "۰۱۲۳۴۵۶۷۸۹".indexOf(c));
        if (id === "search") search = val;
        else if (id === "from") from = val;
        else to = val;
        pageNum = 1;
        listPage();
        let next = $("#" + id);
        next.focus();
        next.setSelectionRange(pos, pos);
      });
  });
}
function renderList(records) {
  if (!records.length) return empty();
  if (page === "refs") {
    let fields = refFields[tab];
    return table(
      ["ردیف", ...fields.map((x) => x[1]), "تکمیل جزئیات"],
      records
        .map(
          (r, i) =>
            `<tr><td>${fa((pageNum - 1) * rowsPerPage() + i + 1)}</td>${fields.map(([k]) => `<td>${k === "share_percent" ? fa(Number(r.share) * 100) + "٪" : r[k] === null || r[k] === "" ? badge("تکمیل نشده", "amber") : esc(fieldLabels[r[k]] || r[k])}</td>`).join("")}<td><button class="btn" data-details="${esc(r.id)}">تکمیل جزئیات</button></td></tr>`,
        )
        .join(""),
    );
  }
  if (page === "stock")
    return table(
      ["محصول", "انبار", "موجودی (کیلوگرم)"],
      records
        .map(
          (r) =>
            `<tr><td><strong>${esc(r.product)}</strong></td><td>${esc(r.store)}</td><td>${fa(r.qty)}</td></tr>`,
        )
        .join(""),
    );
  if (page === "ledger")
    return table(
      [
        "نام حساب",
        `بدهکار (${moneyLabel()})`,
        `بستانکار (${moneyLabel()})`,
        `مانده (${moneyLabel()})`,
      ],
      records
        .map(
          (r) =>
            `<tr><td><strong>${esc(r.name)}</strong></td><td>${money(r.debit)}</td><td>${money(r.credit)}</td><td>${money(r.balance)}</td></tr>`,
        )
        .join(""),
    );
  if (page === "weigh")
    return table(
      [
        "تاریخ",
        "عملیات",
        "طرف حساب",
        "محصول",
        "نوع سبد",
        "وزن خالص (کیلوگرم)",
        "شماره قبض",
        "اصلاح",
      ],
      records
        .map(
          (r) =>
            `<tr class="${movementClass(r)}"><td>${fmtDate(r.date)}</td><td>${esc(r.operation)}</td><td>${esc(r.party)}</td><td>${esc(r.product)}</td><td>${esc(r.basket)}</td><td>${r.net === null ? badge("نیازمند بازبینی", "amber") : fa(r.net)}</td><td>${esc(r.reference)}</td><td><button class="btn" data-edit-weigh="${esc(r.id)}">اصلاح</button></td></tr>`,
        )
        .join(""),
    );
  if (page === "checks")
    return table(
      [
        "شماره چک",
        "جهت",
        "طرف حساب",
        "بانک",
        `مبلغ (${moneyLabel()})`,
        "سررسید",
        "وضعیت",
        "انتقال",
      ],
      records
        .map(
          (r) =>
            `<tr><td><strong>${esc(r.number)}</strong></td><td>${esc(r.direction)}</td><td>${esc(r.party)}</td><td>${esc(r.bank)}</td><td>${money(r.amount)}</td><td>${fmtDate(r.due)}</td><td>${badge(r.state)}</td><td>${(S.check_transitions[r.state] || []).length ? `<select data-check="${esc(r.id)}" aria-label="تغییر وضعیت چک"><option value="">انتخاب وضعیت</option>${S.check_transitions[r.state].map((x) => `<option>${esc(fieldLabels[x] || x)}</option>`).join("")}</select>` : "—"}</td></tr>`,
        )
        .join(""),
    );
  return eventTable(records);
}
function field(
  [name, label, type = "text", options],
  value = "",
  full = false,
) {
  let input;
  if (type === "ref")
    input = `<select data-ref="${options}" name="${name}"><option value="">انتخاب ${label}…</option>${S[options].map((x) => `<option value="${esc(x.name)}" ${x.name === value ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select>`;
  else if (type === "select")
    input = `<select name="${name}">${options.map((x) => `<option value="${esc(x)}" ${x === value ? "selected" : ""}>${esc(fieldLabels[x] || x)}</option>`).join("")}</select>`;
  else
    input = `<input name="${name}" type="${type === "number" ? "text" : type}" ${type === "number" ? 'inputmode="decimal"' : ""} value="${esc(value)}" ${name === "date" || name === "due" || name === "start" || name === "end" ? 'placeholder="۱۴۰۵/۰۸/۱۳"' : ""} ${name === "name" ? "required" : ""}>`;
  return `<div class="field ${full ? "full" : ""}"><label>${label}${type === "ref" && ["Parties", "Groups", "Accounts"].includes(options) ? ` <button type="button" class="quick-link" data-quick="${options}" data-target="${name}">＋ تعریف سریع</button>` : ""}</label>${input}</div>`;
}
function openModal(title, content, onSubmit, submit = "ثبت و ذخیره") {
  modal.innerHTML = `<form id="entryform"><div class="modalhead"><h3>${title}</h3><button type="button" class="iconbtn" data-action="close">${icon("close")}</button></div><div class="modalbody"><div class="formgrid">${content}</div><div class="formerror" id="formerror" role="alert"></div></div><div class="modalfoot"><button type="button" class="btn" data-action="close">انصراف</button><button class="btn primary" type="submit">${submit}</button></div></form>`;
  modal.showModal();
  $("#entryform").addEventListener("submit", async (e) => {
    e.preventDefault();
    let b = e.target.querySelector('button[type="submit"]');
    b.disabled = true;
    $("#formerror").textContent = "";
    try {
      await onSubmit(Object.fromEntries(new FormData(e.target)));
      await refresh();
      modal.close();
      toast("اطلاعات در فایل اکسل ذخیره شد؛ پشتیبان قبلی محفوظ است.");
    } catch (err) {
      $("#formerror").textContent = err.message;
    } finally {
      b.disabled = false;
    }
  });
}
function newEntry(editId = null) {
  if (page === "refs") {
    openModal(
      "تعریف " + refTitles[tab],
      refFields[tab].map((f) => field(f)).join(""),
      (data) =>
        api("/api/references/" + tab, "POST", { data, revision: S.revision }),
    );
    return;
  }
  if (page === "weigh") {
    const editRecord=editId?S.Weigh.find(x=>x.id===editId):null;
    const fields = [
      ["date", "تاریخ شمسی"],
      ["operation", "نوع عملیات", "select", (S.WeighOps || []).map(x => x.name)],
      ["party", "طرف حساب", "ref", "Parties"],
      ["product", "محصول", "ref", "Products"],
      ["store", "انبار", "ref", "Stores"],
      ["basket", "نام نوع سبد", "ref", "Baskets"],
      ["count", "تعداد سبد", "number"],
      ["gross", "وزن باسکول (کیلوگرم)", "number"],
      ["tare", "تارای دستی هر سبد (اختیاری)", "number"],
      ["loss", "درصد افت", "number"],
      ["waste", "ضایعات (کیلوگرم)", "number"],
      ["reference", "شماره قبض"],
      ["deal", "قرارداد شراکت (اختیاری)", "ref", "Deals"],
      ["destination", "مقصد انتقال (برای انتقال لازم)", "ref", "Stores"],
      ["basket_out", "سبد امانی تحویلی", "number"],
      ["basket_return", "سبد امانی برگشتی", "number"],
      ["round_base", "مبنای گردکردن؛ صفر یعنی دقیق", "number"],
      ["amount", "مبلغ تعهد/درآمد ویژه (ریال)", "number"],
      ["note", "شرح"],
    ];
    openModal(
      editRecord?"اصلاح ردیف باسکول با حفظ اصل منبع":"ثبت قبض باسکول",
      fields
        .map((f) =>
          field(
            f,
            editRecord ? (editRecord[f[0]] ?? "") : f[0] === "date"
              ? health.today
              : ["loss", "waste"].includes(f[0])
                ? "0"
                : "",
          ),
        )
        .join("") +
        '<div class="calculation" id="netpreview">نوع سبد را با نام انتخاب کنید؛ تارای دستی صفر نیز معتبر است.</div>',
      (data) => api(editRecord?"/api/weigh/"+editRecord.id:"/api/weigh", editRecord?"PATCH":"POST", { data, revision: S.revision }),
    );
    $("#entryform").addEventListener("input", calcNet);
    return;
  }
  if (page === "checks") {
    const fields = [
      ["number", "شماره چک"],
      ["direction", "جهت چک", "select", ["دریافتی", "پرداختی"]],
      ["date", "تاریخ ثبت"],
      ["due", "سررسید"],
      ["party", "طرف حساب", "ref", "Parties"],
      ["bank", "بانک", "ref", "Banks"],
      ["amount", "مبلغ (ریال)", "number"],
      ["reference", "شماره مرجع"],
      ["note", "شرح"],
    ];
    openModal(
      "ثبت چک جدید",
      fields.map((f) => field(f, f[0] === "date" ? health.today : "")).join(""),
      (data) => api("/api/checks", "POST", { data, revision: S.revision }),
    );
    return;
  }
  const kind =
    page === "buy"
      ? "خرید"
      : page === "sale"
        ? "فروش"
        : page === "bank"
          ? "دریافت"
          : "هزینه";
  openModal(
    "ثبت سند " + kind,
    eventFields(kind),
    (data) => api("/api/events", "POST", { data, revision: S.revision }),
    "ثبت قطعی و سند دوبل",
  );
  $('#entryform [name="kind"]').addEventListener("change", (e) => {
    let v = Object.fromEntries(new FormData($("#entryform")));
    modal.querySelector(".formgrid").innerHTML = eventFields(e.target.value, v);
    bindKind();
  });
  function bindKind() {
    $('#entryform [name="kind"]').addEventListener("change", (e) => {
      let v = Object.fromEntries(new FormData($("#entryform")));
      modal.querySelector(".formgrid").innerHTML = eventFields(
        e.target.value,
        v,
      );
      bindKind();
    });
  }
}
function eventFields(kind, v = {}) {
  let kinds =
    page === "bank"
      ? ["دریافت", "پرداخت", "سرمایه"]
      : page === "cost"
        ? [
            ...new Set([
              "هزینه",
              "دستمزد",
              ...(S.Operations || [])
                .filter(
                  (x) =>
                    x.active === "بله" &&
                    ![
                      "خرید",
                      "فروش",
                      "تخصیص سود شریک",
                      "تخصیص زیان شریک",
                    ].includes(x.name),
                )
                .map((x) => x.name),
            ]),
          ]
        : [kind];
  let fields = [
    ["date", "تاریخ شمسی"],
    ["kind", "نوع رویداد", "select", kinds],
    ["party", "طرف حساب", "ref", "Parties"],
    ["deal", "قرارداد شراکت (اختیاری)", "ref", "Deals"],
  ];
  if (["خرید", "فروش"].includes(kind))
    fields.push(
      ["product", "محصول", "ref", "Products"],
      ["store", "انبار", "ref", "Stores"],
      ["qty", "مقدار خالص (کیلوگرم)", "number"],
      ["rate", "فی هر کیلوگرم (ریال)", "number"],
    );
  else
    fields.push(
      ["bank", "حساب بانکی", "ref", "Banks"],
      ["amount", "مبلغ (ریال)", "number"],
    );
  if (kind === "فروش")
    fields.push(["cost", "بهای تمام‌شده کل فروش (ریال)", "number"]);
  fields.push(
    ["reference", "مرجع یکتا (برای جلوگیری از ثبت تکراری)"],
    ["note", "شرح"],
  );
  return (
    (["خرید", "فروش"].includes(kind)
      ? `<div class="field full"><label>باسکول منبع (اختیاری؛ نام و قبض به جای کد)</label><select name="source_weigh"><option value="">ثبت مستقل / انتخاب قبض…</option>${S.Weigh.map((x) => `<option value="${esc(x.id)}" ${v.source_weigh === x.id ? "selected" : ""}>${esc(x.reference)} · ${esc(x.party)} · ${fmtDate(x.date)}</option>`).join("")}</select></div>`
      : "") +
    fields
      .map((f) =>
        field(
          f,
          v[f[0]] ??
            (f[0] === "date" ? health.today : f[0] === "kind" ? kind : ""),
        ),
      )
      .join("") +
    '<div class="calculation">ثبت قطعی، سند دوبل متوازن ایجاد می‌کند. اصلاح فقط با برگشت سند است. شراکت فقط با سیاست صریح اصیل/تقسیم سود دوره فعال است؛ مالکیت مشترک و امانی را با آن اشتباه نگیرید.</div>'
  );
}
function calcNet() {
  const f = Object.fromEntries(new FormData($("#entryform"))),
    b = S.Baskets.find((x) => x.name === f.basket);
  const normalize = (v) =>
    String(v)
      .replace(/[۰-۹]/g, (c) => "۰۱۲۳۴۵۶۷۸۹".indexOf(c))
      .replaceAll(",", "");
  let tare = (f.tare || "").trim() !== "" ? normalize(f.tare) : b?.tare;
  if (tare === null || tare === undefined || tare === "") {
    $("#netpreview").textContent =
      "تارای این سبد مشخص نیست؛ وزن واقعی را وارد کنید.";
    return;
  }
  if (["خروج سبد امانت","ورود سبد خالی","ورود سبد","خروج سبد","انعام مصطفی","هزینه باسکول احمد زاهدی","هزینه باسکول احمد موسویان","درآمد باسکول"].includes(f.operation)) { $("#netpreview").textContent = "این عملیات وزن میوه ندارد؛ گردش سبد یا تعهد مالی مستقل ثبت می‌شود."; return; }
  let n =
    (Number(normalize(f.gross)) - Number(normalize(f.count)) * Number(tare)) *
      (1 - Number(normalize(f.loss)) / 100) -
    Number(normalize(f.waste));
  $("#netpreview").textContent =
    n < 0
      ? "وزن خالص منفی است؛ ورودی‌ها را اصلاح کنید."
      : `پیش‌نمایش وزن خالص: ${fa(f.round_base === "0" ? n : Math.floor(n / Number(f.round_base || 5)) * Number(f.round_base || 5))} کیلوگرم · تارا: ${fa(tare)} کیلوگرم · محاسبه نهایی در سرور انجام می‌شود.`;
}
function importPage() {
  $("#pagecontent").innerHTML =
    `<section class="panel fullpanel"><div class="panelhead"><h3>ورود امن گردش بانکی</h3>${badge("بدون ثبت خودکار")}</div><div class="importarea"><div class="dropzone">${icon("upload")}<strong>فایل CSV یا XLSX را انتخاب کنید</strong><p>بازبینی تا ۵۰ هزار ردیف · حداکثر ۲۰ مگابایت؛ همه ردیف‌ها قابل پیمایش‌اند<br>شیت قابل انتخاب، ردیف اول سرستون؛ واحد منبع را صریح تعیین کنید</p><input type="file" id="importfile" accept=".csv,.xlsx" aria-label="فایل ورودی">${btn("بررسی و پیش‌نمایش", "preview", "primary", "search")}</div><div class="schema"><b>قرارداد ستون‌های پشتیبانی‌شده</b><code>date, kind, party, bank, amount, reference, note</code>ستون amount در قرارداد نمونه به ریال است؛ برای منبع دیگر _unit برابر IRR یا IRT بگذارید. یا سرستون‌های فارسی: تاریخ، نوع عملیات، طرف حساب، بانک، مبلغ، شماره مرجع، شرح.<br>نوع عملیات: دریافت / پرداخت / هزینه / سرمایه.<br>نام طرف حساب و بانک باید از قبل تعریف شده باشد. تشخیص حدسی واریز و برداشت انجام نمی‌شود.<br><label>نگاشت ستون‌ها / شیت / مقدار پیش‌فرض (JSON، اختیاری)<textarea id="importmapping" placeholder='{"date":"تاریخ تراکنش","_defaults":{"bank":"نام بانک","kind":"دریافت"}}'></textarea></label>${btn("تعریف سریع شخص", "quick-party")}${btn("دریافت نمونه CSV", "sample")}</div></div><div id="importresult" class="tablewrap">${preview ? previewHTML() : ""}</div></section>`;
}
let importReviewPage = 1;
function oldPreviewHTML() {
  return `<div class="toolbar"><strong>${fa(preview.valid)} ردیف معتبر از ${fa(preview.total)}</strong>${preview.errors.length ? badge(fa(preview.errors.length) + " خطا", "red") : badge("آماده ثبت")}<button class="btn primary" data-action="commit" ${preview.errors.length ? "disabled" : ""}>ثبت یک‌باره نوبت</button></div>${table(
    ["ردیف", "تاریخ", "عملیات", "طرف حساب", "بانک", "مبلغ (ریال)", "کنترل"],
    preview.rows
      .slice(0, 100)
      .map(
        (r, i) =>
          `<tr><td>${fa(i + 2)}</td><td>${esc(r.date)}</td><td>${esc(r.kind)}</td><td>${esc(r.party)}</td><td>${esc(r.bank)}</td><td>${esc(r.amount)}</td><td>${
            preview.errors.some((x) => x.row === i + 2)
              ? badge(
                  preview.errors
                    .filter((x) => x.row === i + 2)
                    .map((x) => x.message)
                    .join("؛ "),
                  "red",
                )
              : badge("معتبر")
          }</td></tr>`,
      )
      .join(""),
  )}`;
}
async function doPreview() {
  let f = $("#importfile").files[0];
  if (!f) return toast("ابتدا فایل را انتخاب کنید.");
  let form = new FormData();
  form.append("file", f);
  form.append("revision", S.revision);
  const mapping = $("#importmapping")?.value?.trim();
  if (mapping) form.append("mapping", mapping);
  preview = await api("/api/import/preview", "POST", form);
  ++stateEpoch;
  S.revision = preview.revision;
  $("#importresult").innerHTML = previewHTML();
}
async function help() {
  $("#pagecontent").innerHTML =
    `<section class="panel fullpanel"><div class="tabs panelhead"><strong>دفتر شما، مستقل از نرم‌افزار</strong>${btn("پشتیبان جدید", "backup", "primary", "shield")}</div><article class="document"><h3>شروع کار با مازندشت</h3><p>۱. در «تعاریف پایه» نام اشخاص، نوع سبد و تارای واقعی، محصولات، انبارها و بانک‌ها را تعریف کنید.<br>۲. قبض باسکول را ثبت کنید؛ باسکول بار به‌تنهایی سند مالی نیست؛ عملیات ویژه انعام/هزینه خدمات، تعهد جدا ایجاد می‌کند.<br>۳. خرید یا فروش عادی را ثبت کنید. فروش نیازمند موجودی کافی و بهای تمام‌شده تأییدشده است.<br>۴. دریافت، پرداخت، هزینه و دستمزد، سند دوبل ایجاد می‌کنند. همه مبالغ ورود ریال هستند؛ کلید واحد بالا فقط نمایش را عوض می‌کند.<br>۵. برای اصلاح سند قطعی از «برگشت با علت» استفاده کنید؛ اصل سند حفظ می‌شود.</p><h3>فایل اکسل مستقل</h3><p>از «خروجی اکسل» فایل کامل را بگیرید. برگه <code>Guide</code> راهنمای مستقل است. در <code>Events</code> رویداد وارد کنید؛ <code>Journal</code>، <code>Trial</code> و <code>Stock</code> با فرمول کار می‌کنند. کدها پنهان‌اند و فهرست‌ها نام نشان می‌دهند. اکسل و نرم‌افزار را هم‌زمان روی یک فایل ویرایش نکنید. برای کار دوباره نرم‌افزار، همان فایل را با برنامه بسته در پوشه داده جایگزین کنید؛ قالب و نسخه ساختار باید حفظ شده باشد.</p><h3>وضعیت واقعی نسخه</h3><p>این نسخه توسعه است و تأیید حسابداری رسمی/مالیاتی ندارد. باسکول و صورت‌حساب‌ها در دفتر یکپارچه نگهداری می‌شوند؛ اتصال ردیف بانک به سند مالی، نیازمند تطبیق شخص و ماهیت است. تقسیم سود دوره برای مدل اصیل با درصد تاریخی و قفل دوره فعال است؛ مدل مالکیت مشترک/امانی، ارزش‌گذاری خودکار موجودی، حقوق با بیمه/مالیات، بستن کامل دوره، باسکول سخت‌افزاری و مدل زبانی متصل هنوز وجود ندارند. چک‌ها فقط دفتر چرخه عملیاتی دارند؛ وصول را با ثبت بانکی تطبیق دهید. موجودی مالی از اسناد قطعی محاسبه می‌شود؛ گردش فیزیکی انبار و سبد امانی گزارش مستقل دارد. انتقال از مبدأ کم و به مقصد اضافه می‌کند.</p><h3>پشتیبان و بازیابی</h3><p>قبل از هر تغییر، یک کپی کامل محلی ساخته می‌شود. بازیابی فقط برای مدیر است و خودش نیز پشتیبان دارد. زنجیره ممیزی هنگام نوشتن کنترل می‌شود؛ این حفاظت در برابر دست‌کاری همه فایل‌ها توسط مدیر سیستم‌عامل، تضمین رمزنگاری بیرونی ندارد.</p><h3>منبع داده و تفاوت پشتیبان</h3><div id="provenance"></div><h3>اصلاحات اکسل‌های قدیمی کجاست؟</h3><p>پنجره حاضر از فایل یکپارچه Mazandasht.xlsx می‌خواند، نه خودکار از ۱۴ فایل قدیمی. نسخه‌های اصلاح‌شده در پوشه Excel-v1.11 بسته خصوصی هستند. ستون‌های تازه با عنوان «انتخاب نام» در سمت انتهایی برگه ورودی اضافه شده‌اند؛ برای باسکول Entry ستون‌های AR تا AW و برای سبد Entry ستون‌های T و U را ببینید. راهنمای نقشه کامل کنار بسته قرار دارد. داده آموزشیِ پیش‌نمایش سوابق واقعی شما نیست.</p><div id="backuplist"></div><h3>ممیزی اخیر</h3>${table(
      ["زمان UTC", "کاربر", "عملیات"],
      (S.Audit || [])
        .slice(-5)
        .reverse()
        .map(
          (x) =>
            `<tr><td>${esc(x.timestamp)}</td><td>${esc(x.actor)}</td><td>${esc(x.action)}</td></tr>`,
        )
        .join(""),
    )}</article></section>`;
  if (S.user.role === "admin") {
    const source = await api("/api/provenance");
    if (page === "help" && $("#provenance"))
      $("#provenance").innerHTML =
        `<p>فایل فعال: <code>${esc(source.source)}</code><br>اثر انگشت: <code>${esc(source.revision)}</code><br>حالت: ${source.demo ? "ساختگی" : "دفتر محلی واقعی / خالی"} · ${fa(source.events)} سند / ${fa(source.weigh)} قبض</p><p>${esc(source.explanation)}</p>${source.backup ? `<p>آخرین پشتیبان: ${esc(source.backup.name)} · ${fa(source.backup.events)} سند · ${source.backup.same_bytes ? "همسان با فایل جاری" : "با فایل جاری متفاوت است"}<br>${fa(source.backup.new_event_ids.length)} شناسه سند تازه نسبت به این پشتیبان، ${fa(source.backup.removed_event_ids.length)} شناسه حذف/بازیابی‌شده. ${fa(source.backup.changed_events.length)} سند با تفاوت فیلد ورودی. این مقایسه فایل است، نه تطبیق مالی کامل تاریخچه.</p>` : "<p>هنوز پشتیبانی برای این دفتر ثبت نشده است.</p>"}`;
    backups = await api("/api/backups");
    if (page === "help" && $("#backuplist"))
      $("#backuplist").innerHTML = table(
        ["پشتیبان‌های اخیر", "حجم", "عملیات"],
        backups
          .slice(0, 5)
          .map(
            (x) =>
              `<tr><td>${esc(x.name)}</td><td>${fa(x.bytes / 1024)} KB</td><td><button class="btn danger" data-restore="${esc(x.name)}">بازیابی</button></td></tr>`,
          )
          .join(""),
      );
  }
}
async function insights() {
  let data = await api("/api/insights");
  if (page !== "insights") return;
  $("#pagecontent").innerHTML =
    `<section class="panel fullpanel"><div class="panelhead"><h3>اعداد قابل توضیح، تصمیم‌های روشن</h3>${badge("محلی و قاعده‌محور")}</div><div class="insightgrid">${data.items.map((x) => `<div class="insight">${esc(x.title)}<b>${fa(x.value)} <span>${esc(x.unit)}</span></b><small>${esc(x.source)}</small></div>`).join("")}</div><div class="greenbox"><strong>درباره هوش مصنوعی</strong>${esc(data.mode)}. هیچ پیشنهاد تحلیلی در این نسخه مجوز ثبت سند یا تغییر داده ندارد.</div></section>`;
}
function printReport() {
  let records =
    page === "dashboard"
      ? S.Events.filter((e) => e.status === "قطعی")
      : filterRecords(listRecords() || []);
  let html;
  if (page === "dashboard") html = eventTable(records, false);
  else if (["help", "import", "insights"].includes(page))
    html = $("#pagecontent").innerHTML;
  else html = renderList(records);
  const win = window.open("", "_blank");
  if (!win) return toast("برای چاپ، اجازه بازشدن پنجره جدید بدهید.");
  win.document.write(
    `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>گزارش ${titles[page]}</title><link rel="stylesheet" href="/static/print.css"></head><body><h1>مازندشت</h1><h2>${esc(titles[page])}</h2><p>نسخه گزارش: ${esc(S.revision.slice(0, 12))} · واحد: ${moneyLabel()} · زمان: ${esc(health.today)} · ${S.demo ? "نمونه آموزشی" : "دفتر محلی"}</p>${html}<footer>گزارش مدیریتی نسخه توسعه · منبع: فایل اکسل محلی</footer></body></html>`,
  );
  win.document.close();
  win.addEventListener("load", () => win.print(), { once: true });
}
async function handleAction(action) {
  if (action === "close") modal.close();
  else if (action === "new") newEntry();
  else if (action === "reports") window.location.assign("/reports");
  else if (action === "refresh") await refresh();
  else if (action === "unit") {
    const units=MazMoney.units(S.Currencies);unit=units[(units.indexOf(unit)+1)%units.length];
    render();
  } else if (action === "fullscreen") {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      toast("مرورگر اجازه تمام‌صفحه نداد؛ از F11 استفاده کنید.");
    }
  } else if (action === "export") window.location.href = "/api/export";
  else if (action === "prev") {
    pageNum--;
    listPage();
  } else if (action === "next") {
    pageNum++;
    listPage();
  } else if (action === "print") printReport();
  else if (action === "preview") await doPreview();
  else if (action === "commit") {
    await api("/api/import/" + preview.id + "/commit", "POST", {
      revision: S.revision,
    });
    preview = null;
    await refresh();
    toast("نوبت ورود اطلاعات به‌صورت کامل ثبت شد.");
  } else if (action === "sample") {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob(
        [
          "\uFEFFdate,kind,party,bank,amount,reference,note\n14050813,دریافت,خریدار نمونه,بانک آموزشی,1000000,TEST-001,نمونه آموزشی\n",
        ],
        { type: "text/csv;charset=utf-8" },
      ),
    );
    a.download = "bank-import-sample.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  } else if (action === "backup") {
    await api("/api/backup", "POST", {});
    await help();
    toast("پشتیبان کامل ایجاد شد.");
  } else if (action === "logout") {
    await api("/api/logout", "POST", {});
    S = null;
    showLogin();
  }
}
document.addEventListener("click", async (e) => {
  let target = e.target.closest(
    "[data-page],[data-action],[data-tab],[data-reverse],[data-restore]",
  );
  if (!target) return;
  try {
    if (target.dataset.page) {
      page = target.dataset.page;
      pageNum = 1;
      search = "";
      from = "";
      to = "";
      render();
    } else if (target.dataset.tab) {
      tab = target.dataset.tab;
      pageNum = 1;
      search = "";
      listPage();
    } else if (target.dataset.reverse) {
      const id = target.dataset.reverse;
      openModal(
        "برگشت سند قطعی",
        field(["reason", "علت برگشت"], "", true),
        (data) =>
          api("/api/events/" + id + "/reverse", "POST", {
            reason: data.reason,
            revision: S.revision,
          }),
        "ایجاد سند معکوس",
      );
    } else if (target.dataset.restore) {
      const name = target.dataset.restore;
      openModal(
        "بازیابی پشتیبان",
        '<div class="field full"><p>دفتر فعلی با پشتیبان انتخاب‌شده جایگزین می‌شود. از وضعیت فعلی نیز پشتیبان نگه داشته خواهد شد.</p></div>',
        () => api("/api/restore", "POST", { name, revision: S.revision }),
        "بازیابی دفتر",
      );
    } else await handleAction(target.dataset.action);
  } catch (err) {
    toast(err.message);
  }
});
document.addEventListener("change", async (e) => {
  if (e.target.name === "source_weigh") {
    const row = S.Weigh.find((x) => x.id === e.target.value);
    if (row)
      for (const key of ["party", "product", "store", "qty"]) {
        const input = modal.querySelector(`[name="${key}"]`);
        if (input)
          input.value = key === "qty" ? (row.net ?? "") : (row[key] ?? "");
      }
    return;
  }
  if (!e.target.dataset.check || !e.target.value) return;
  try {
    await api("/api/checks/" + e.target.dataset.check + "/state", "POST", {
      state: e.target.value,
      revision: S.revision,
    });
    await refresh();
    toast("چرخه چک به‌روزرسانی شد؛ سند بانکی خودکار ایجاد نشده است.");
  } catch (err) {
    toast(err.message);
    e.target.value = "";
  }
});
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (S) render();
  }, 150);
});
(async () => {
  try {
    health = await api("/api/health");
    await refresh();
  } catch (err) {
    if (!S && err.status === 401) showLogin();
    else if (!S)
      app.innerHTML = `<div class="errorpanel"><h2>دفتر نیازمند بررسی است</h2><p>${esc(err.message)}</p><p>قبل از ادامه، فایل و نسخه پشتیبان را بررسی کنید. اطلاعات ناقص به‌صورت حدسی خوانده نمی‌شوند.</p></div>`;
    else toast(err.message);
  }
})();

document.addEventListener("click",e=>{const b=e.target.closest("[data-edit-weigh]");if(b)newEntry(b.dataset.editWeigh);});
