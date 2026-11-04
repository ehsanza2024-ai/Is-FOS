"use strict";
const fieldLabels = {
  asset: "دارایی",
  liability: "بدهی",
  equity: "سرمایه",
  revenue: "درآمد",
  expense: "هزینه",
  date: "تاریخ",
  kind: "عملیات",
  party_code: "کد شخص",
  party: "صاحب حساب",
  bank: "بانک",
  amount: "مبلغ منبع",
  unit: "واحد IRR / IRT",
  reference: "مرجع یکتا",
  note: "توضیحات",
  active: "فعال (بله / خیر)",
  group: "گروه",
  role: "نقش",
};

async function quickDefinition(sheet, target = null) {
  const prior = document.querySelector("#quick-dialog");
  if (prior) prior.remove();
  const dialog = document.createElement("dialog");
  dialog.id = "quick-dialog";
  const extras =
    sheet === "Groups"
      ? `<label>والد (اختیاری)<select name="parent"><option value="">گروه ریشه</option>${S.Groups.map((x) => `<option>${esc(x.name)}</option>`).join("")}</select></label><label>طبقه ریشه<select name="category">${["asset", "liability", "equity", "revenue", "expense"].map((x) => `<option value="${x}">${fieldLabels[x]}</option>`).join("")}</select></label>`
      : sheet === "Accounts"
        ? `<label>گروه<select name="group" required>${S.Groups.map((x) => `<option>${esc(x.name)}</option>`).join("")}</select></label>`
        : "";
  dialog.innerHTML = `<form><h3>تعریف سریع ${esc(refTitles[sheet] || sheet)}</h3><label>نام<input name="name" required maxlength="120" autofocus></label>${extras}<p>شناسه و کد به‌صورت خودکار ساخته می‌شوند؛ جزئیات را بعداً در تعاریف پایه تکمیل کنید.</p><div class="formerror"></div><div class="buttons"><button class="btn primary" type="submit">ایجاد</button><button class="btn" type="button" data-cancel>انصراف</button></div></form>`;
  document.body.append(dialog);
  dialog.showModal();
  dialog.querySelector("[data-cancel]").onclick = () => dialog.close();
  dialog.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const data = Object.fromEntries(new FormData(e.target));
      const result = await api("/api/references/" + sheet, "POST", {
        data,
        revision: S.revision,
      });
      S = await api("/api/state");
      if (target) {
        document
          .querySelectorAll(`select[data-ref="${sheet}"]`)
          .forEach((select) => {
            select.append(new Option(result.name, result.name));
            if (select.name === target) select.value = result.name;
          });
      }
      dialog.close();
      toast("تعریف جدید ثبت شد؛ جزئیات قابل تکمیل است.");
    } catch (error) {
      dialog.querySelector(".formerror").textContent = error.message;
    }
  };
}
const selectedImportRows = new Set();
let selectedBatch = "";
function previewHTML() {
  if (!preview) return "";
  if (selectedBatch !== preview.id) {
    selectedImportRows.clear();
    selectedBatch = preview.id;
    importReviewPage = 1;
  }
  const size = 80,
    total = Math.max(1, Math.ceil(preview.rows.length / size));
  importReviewPage = Math.min(importReviewPage, total);
  const offset = (importReviewPage - 1) * size;
  return (
    `<div class="toolbar"><button class="btn" data-import-selected>ثبت انتخاب‌شده‌ها (${fa(selectedImportRows.size)})</button><strong>${fa(preview.total)} ردیف؛ ${fa(preview.valid)} معتبر</strong><span class="badge">${fa(preview.errors.length)} نیازمند اصلاح</span><button class="btn" data-review-nav="-1" ${importReviewPage <= 1 ? "disabled" : ""}>قبلی</button><span>${fa(importReviewPage)} از ${fa(total)}</span><button class="btn" data-review-nav="1" ${importReviewPage >= total ? "disabled" : ""}>بعدی</button><button class="btn" data-action="quick-party">＋ شخص جدید</button><button class="btn" data-review-revalidate>بازبینی دوباره</button><button class="btn primary" data-action="commit" ${preview.errors.length ? "disabled" : ""}>ثبت همه؛ در حد ظرفیت آزاد دفتر</button></div>` +
    table(
      [
        "انتخاب",
        "ردیف اصل",
        "تاریخ",
        "عملیات",
        "کد شخص",
        "نام صاحب حساب",
        "بانک",
        "مبلغ منبع / واحد",
        "مرجع",
        "کنترل",
        "اصلاح",
      ],
      preview.rows
        .slice(offset, offset + size)
        .map((r, j) => {
          const i = offset + j,
            err = preview.errors.find((x) => x.index === i);
          return `<tr><td><input type="checkbox" data-import-check="${i}" ${selectedImportRows.has(i) ? "checked" : ""} ${err ? "disabled" : ""} aria-label="انتخاب ردیف ${i + 1}"></td><td>${fa(r.source_row)}</td><td>${esc(r.date)}</td><td>${esc(r.kind)}</td><td>${esc(r.party_code)}</td><td>${esc(r.party)}</td><td>${esc(r.bank)}</td><td>${esc(r.amount)} ${esc(r.unit)}</td><td>${esc(r.reference)}</td><td>${err ? badge(esc(err.message), "red") : badge("معتبر")}</td><td><button class="btn" data-review-row="${i}">اصلاح</button></td></tr>`;
        })
        .join(""),
    )
  );
}
async function revalidateImport(updates = []) {
  preview = await api("/api/import/" + preview.id + "/rows", "POST", {
    updates,
    revision: S.revision,
  });
  ++stateEpoch;
  S.revision = preview.revision;
  $("#importresult").innerHTML = previewHTML();
}
async function workbench() {
  const [state, reports] = await Promise.all([
    api("/api/collaboration"),
    api("/api/reports"),
  ]);
  if (page !== "workbench") return;
  $("#pagecontent").innerHTML =
    `<div class="workbench"><section class="panel"><div class="panelhead"><h3>اتاق همکاری و مشاوره</h3><span class="badge">محلی و قابل ردیابی</span></div><div class="team-grid">${state.agents.map((a) => `<article><span>✧</span><strong>${esc(a.name)}</strong><p>${esc(a.scope)}</p></article>`).join("")}</div><div class="workbench-content"><p>${esc(state.mode)}؛ این فضا پیشنهاد و راهنما می‌سازد، نه تغییر خودکار داده مالی.</p><form id="ask-team"><textarea name="question" maxlength="6000" placeholder="مثلاً برای ثبت هزینه مشترک و تقسیم سود شریک چه کار کنم؟" required></textarea><button class="btn primary">تقسیم درخواست و دریافت راهنما</button></form><div id="team-answer"></div></div></section><section class="panel"><div class="panelhead"><h3>شراکت؛ درصد، دوره و تخصیص</h3><button class="btn" data-allocate>تخصیص دوره با تأیید مدیر</button></div><div class="workbench-content">${table(["قرارداد", "سیاست", "سود عملیاتی", "سهم مجموعه", "سهم شریک", "تخصیص"], reports.partnerships.map((r) => `<tr><td>${esc(r.deal)}</td><td>${esc(r.error || r.policy)}</td><td>${r.error ? "—" : money(r.operating_profit)}</td><td>${r.error ? "—" : money(r.company_profit)}</td><td>${r.error ? "—" : money(r.partner_share_amount)}</td><td>${r.error ? "—" : money(r.allocated)}</td></tr>`).join(""))}<p>این مدل برای مجموعه اصیل با کالای متعلق به مجموعه است. تخصیص، سند بدهی/طلب شریک است؛ پرداخت بانکی را جدا ثبت کنید. دوره تخصیص‌یافته تا برگشت سند تخصیص، ثبت/برگشت زیربنایی نمی‌پذیرد.</p></div></section><section class="panel"><div class="panelhead"><h3>انتشار گزارش خصوصی روی Drive</h3><button class="btn primary" data-publish>ساخت فایل رمزگذاری‌شده</button></div><div class="workbench-content">فایل .mazreport را در پوشه خصوصی Drive خود قرار دهید؛ همان داشبورد واحد از فایل دانلودشده گزارش می‌خواند. رمز را جدا بفرستید. حساب‌های ورود، کلیدها و مکالمات دستیار در فایل گزارش نیستند. این انتشار نسخه‌ای است، نه همگام‌سازی خودکار Drive.<p><a href="/viewer">بازکردن مشاهده‌گر فایل گزارش</a></p></div></section><section class="panel"><div class="panelhead"><h3>دانش و مسیر تکامل</h3><a class="btn" href="/api/collaboration/export">دریافت کامل دفتر متنی</a></div><div class="workbench-content"><form id="knowledge-form"><select name="kind"><option value="knowledge">دانش تأییدشده توسط مدیر</option><option value="proposal">پیشنهاد تغییر ساختار</option></select><textarea name="text" maxlength="6000" placeholder="قاعده کسب‌وکار یا پیشنهاد توسعه؛ این متن خودکار اجرا نمی‌شود" required></textarea><button class="btn">ثبت در دفتر تکامل</button></form><div class="evolution-list">${state.history
      .slice(-15)
      .reverse()
      .map(
        (e) =>
          `<article><strong>${esc(e.kind)}</strong><small>${esc(e.timestamp)} · ${esc(e.actor)}</small><p>${esc(JSON.stringify(e.content))}</p><code>${esc(e.hash.slice(0, 16))}</code></article>`,
      )
      .join(
        "",
      )}</div><small>مسیر: evolution.jsonl کنار دفتر مرکزی؛ زنجیره هش برای ردیابی است، نه امضای بیرونی ضد دست‌کاری مدیر سیستم‌عامل.</small></div></section><section class="panel"><div class="panelhead"><h3>کاربر گزارش‌خوان</h3></div><div class="workbench-content"><form id="create-user"><input name="name" placeholder="نام ورود جدید" required><input name="password" type="password" minlength="12" autocomplete="new-password" placeholder="رمز حداقل ۱۲ نویسه" required><select name="role"><option value="viewer">فقط گزارش</option><option value="operator">اپراتور مرکزی</option><option value="finance">مالی مرکزی</option></select><button class="btn">ایجاد حساب با تأیید مدیر</button></form></div></section></div>`;
  $("#ask-team").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const answer = await api(
        "/api/collaboration",
        "POST",
        Object.fromEntries(new FormData(e.target)),
      );
      $("#team-answer").innerHTML = answer.tasks
        .map(
          (t) =>
            `<article class="advice-card"><strong>${esc(state.agents.find((a) => a.id === t.agent)?.name)}</strong><p>${esc(t.answer)}</p></article>`,
        )
        .join("");
    } catch (error) {
      toast(error.message);
    }
  };
  $("#knowledge-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(
        "/api/knowledge",
        "POST",
        Object.fromEntries(new FormData(e.target)),
      );
      await workbench();
      toast("یادداشت ثبت شد؛ تغییری در دفتر مالی اجرا نشد.");
    } catch (error) {
      toast(error.message);
    }
  };
  $("#create-user").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(
        "/api/users",
        "POST",
        Object.fromEntries(new FormData(e.target)),
      );
      e.target.reset();
      toast("کاربر ایجاد شد.");
    } catch (error) {
      toast(error.message);
    }
  };
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest(
    '[data-import-check],[data-import-selected],[data-quick],[data-review-row],[data-review-nav],[data-review-revalidate],[data-publish],[data-allocate],[data-details],[data-action="quick-party"]',
  );
  if (!b) return;
  try {
    if (b.hasAttribute("data-import-check")) {
      const i = Number(b.dataset.importCheck);
      if (b.checked) selectedImportRows.add(i);
      else selectedImportRows.delete(i);
      document.querySelector("[data-import-selected]").textContent =
        "ثبت انتخاب‌شده‌ها (" + fa(selectedImportRows.size) + ")";
      return;
    }
    if (b.hasAttribute("data-import-selected")) {
      if (!selectedImportRows.size) return toast("ردیف معتبر را انتخاب کنید");
      if (
        !confirm(
          "ردیف‌های انتخاب‌شده ثبت می‌شوند و این نوبت بسته می‌شود؛ برای باقی ردیف‌ها فایل جدا بسازید. ادامه؟",
        )
      )
        return;
      await api("/api/import/" + preview.id + "/commit", "POST", {
        selected: [...selectedImportRows],
        revision: S.revision,
      });
      preview = null;
      await refresh();
      toast("فقط ردیف‌های انتخاب‌شده ثبت شد.");
      return;
    }
    if (b.dataset.quick)
      return quickDefinition(b.dataset.quick, b.dataset.target);
    if (b.dataset.action === "quick-party") return quickDefinition("Parties");
    if (b.dataset.reviewNav) {
      importReviewPage += Number(b.dataset.reviewNav);
      $("#importresult").innerHTML = previewHTML();
      return;
    }
    if (b.hasAttribute("data-review-revalidate"))
      return await revalidateImport();
    if (b.dataset.reviewRow) {
      const i = Number(b.dataset.reviewRow),
        r = preview.rows[i];
      openModal(
        "اصلاح ردیف " + fa(r.source_row),
        [
          "date",
          "kind",
          "party_code",
          "party",
          "bank",
          "amount",
          "unit",
          "reference",
          "note",
        ]
          .map((k) => field([k, fieldLabels[k] || k], r[k] || ""))
          .join(""),
        async (changes) => {
          await revalidateImport([{ index: i, changes }]);
        },
        "اصلاح و بازبینی",
      );
      return;
    }
    if (b.dataset.details) {
      const row = S[tab].find((x) => x.id === b.dataset.details);
      const allowed = {
        Parties: ["role", "active", "group", "note"],
        Groups: ["note"],
        Accounts: ["note", "active"],
        Operations: ["note", "active"],
        Deals: ["note"],
      }[tab];
      if (!allowed) return toast("جزئیات این عنوان از فرم تعریف مدیریت می‌شود");
      openModal(
        "تکمیل جزئیات " + row.name,
        allowed
          .map((k) => field([k, fieldLabels[k] || k], row[k] || ""))
          .join(""),
        (changes) =>
          api("/api/references/" + tab + "/" + row.id + "/details", "POST", {
            changes,
            revision: S.revision,
          }),
      );
      return;
    }
    if (b.hasAttribute("data-publish")) {
      openModal(
        "انتشار گزارش خصوصی",
        field(["password", "رمز گزارش (حداقل ۱۲ نویسه)", "password"]) +
          field(["repeat", "تکرار رمز", "password"]),
        async (data) => {
          if (data.password !== data.repeat) throw Error("رمزها یکسان نیستند");
          const result = await api("/api/report-package", "POST", {
            password: data.password,
          });
          window.location.href = result.download;
        },
        "رمزگذاری و دریافت فایل",
      );
      return;
    }
    if (b.hasAttribute("data-allocate")) {
      openModal(
        "تخصیص قطعی سود/زیان شریک",
        field(["deal", "قرارداد", "ref", "Deals"]) +
          field(["start", "از تاریخ"]) +
          field(["end", "تا تاریخ"]) +
          "<p>قبل از تأیید، گزارش دوره و بهای تمام‌شده را کنترل کنید؛ این ثبت پرداخت بانکی نیست.</p>",
        (data) =>
          api("/api/partnership/allocate", "POST", {
            ...data,
            revision: S.revision,
          }),
        "تأیید و ثبت سند تخصیص",
      );
      return;
    }
  } catch (error) {
    toast(error.message);
  }
});
