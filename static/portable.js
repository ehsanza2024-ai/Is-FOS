"use strict";
window.MazReport = {
  async decrypt(file, password) {
    if (!crypto.subtle)
      throw Error(
        "این مرورگر به HTTPS و WebCrypto نیاز دارد؛ در Safari/Chrome جدید باز کنید.",
      );
    if (file.size > 80 * 1024 * 1024)
      throw Error("فایل بیش از ۸۰ مگابایت است.");
    const box = JSON.parse(await file.text());
    if (
      box.format !== "mazandasht.report" ||
      box.version !== 1 ||
      box.kdf !== "PBKDF2-SHA256" ||
      box.iterations !== 310000
    )
      throw Error("نسخه یا ساختار بسته معتبر نیست.");
    const bytes = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
    const material = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(password),
      "PBKDF2",
      false,
      ["deriveKey"],
    );
    try {
      const key = await crypto.subtle.deriveKey(
        {
          name: "PBKDF2",
          hash: "SHA-256",
          salt: bytes(box.salt),
          iterations: 310000,
        },
        material,
        { name: "AES-GCM", length: 256 },
        false,
        ["decrypt"],
      );
      const plain = await crypto.subtle.decrypt(
        {
          name: "AES-GCM",
          iv: bytes(box.nonce),
          additionalData: new TextEncoder().encode("mazandasht.report.v1"),
        },
        key,
        bytes(box.ciphertext),
      );
      if (plain.byteLength > 50 * 1024 * 1024) throw Error();
      const data = JSON.parse(new TextDecoder().decode(plain));
      if (
        data.format !== "mazandasht.payload" ||
        String(data.schema) !== "1" ||
        !Array.isArray(data.periods) ||
        !data.periods.length
      )
        throw Error();
      return data;
    } catch (e) {
      throw Error("رمز نادرست است یا بسته گزارش سالم/معتبر نیست.");
    }
  },
  filter(base, party) {
    const r = structuredClone(base);
    if (!party) return r;
    const B = (x) => BigInt(x || "0");
    r.filters.party = party;
    r.events = r.events.filter((e) => e.party === party);
    r.trial.forEach((t) => {
      t.debit = "0";
      t.credit = "0";
      t.balance = "0";
    });
    const chart = new Map(r.trial.map((t) => [t.name, t]));
    for (const e of r.events)
      for (const l of e.lines) {
        const t = chart.get(l.account);
        if (!t) throw Error("حساب تعریف‌نشده در فایل گزارش");
        t.debit = String(B(t.debit) + B(l.debit) * B(e.sign));
        t.credit = String(B(t.credit) + B(l.credit) * B(e.sign));
        t.balance = String(B(t.debit) - B(t.credit));
      }
    const cat = (c) =>
      r.trial
        .filter((t) => t.category === c)
        .reduce((a, t) => a + B(t.balance), 0n);
    const bal = (n) => B(chart.get(n)?.balance);
    const income = -cat("revenue"),
      expenses = cat("expense");
    r.profit_loss = {
      revenue: String(income),
      expenses: String(expenses),
      net_profit: String(income - expenses),
      cogs: String(bal("بهای تمام‌شده")),
      operating_expense: String(bal("هزینه عملیاتی")),
      wages: String(bal("هزینه دستمزد")),
      partner_profit_expense: String(bal("سهم سود شریک")),
      partner_loss_income: String(-bal("سهم زیان شریک")),
    };
    r.parties = r.parties.filter((p) => p.name === party);
    const rows = r.statement.rows.filter((e) => e.party === party),
      movement = rows.reduce((a, e) => a + B(e.debit) - B(e.credit), 0n),
      closing = B(r.parties[0]?.net);
    let running = closing - movement;
    r.statement = {
      opening: String(running),
      closing: String(closing),
      rows: rows.map((e) => {
        running += B(e.debit) - B(e.credit);
        return { ...e, balance: String(running) };
      }),
    };
    r.unbilled_receipts = r.unbilled_receipts.filter((e) => e.party === party);
    r.checks = r.checks.filter((e) => e.party === party);
    r.counts = {
      posted_period: String(r.events.length),
      pending_receipts: String(r.unbilled_receipts.length),
      open_checks: String(
        r.checks.filter((e) => !["وصول‌شده", "باطل‌شده"].includes(e.state))
          .length,
      ),
    };
    return r;
  },
};
