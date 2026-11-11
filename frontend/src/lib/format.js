export const inr = (n) =>
  `₹${Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export const signedInr = (n) => `${n < 0 ? "−" : "+"}${inr(Math.abs(n))}`;

export const fmtDate = (iso) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";

export const calc = (amount, cfg) => {
  const a = Number(amount) || 0;
  const fee = +((a * (cfg?.fee_percent ?? 20)) / 100).toFixed(2);
  return { fee, real: +(a - fee).toFixed(2), promo: +(a * (cfg?.promo_multiplier ?? 5)).toFixed(2) };
};

export const METHODS = [
  { value: "upi", label: "UPI", hint: "Instant · India" },
  { value: "netbanking", label: "NetBanking", hint: "All major banks" },
  { value: "card", label: "Credit / Debit Card", hint: "Visa · Mastercard" },
  { value: "aed_wire", label: "AED Bank Wire", hint: "UAE · GCC" },
  { value: "usdt", label: "USDT", hint: "TRC-20 / ERC-20" },
];

export const methodLabel = (v) => METHODS.find((m) => m.value === v)?.label || v;

export const TX_TYPES = {
  deposit: "Deposit",
  service_fee: "Service Fee",
  promo_credit: "Promo Credit",
  admin_adjustment: "Adjustment",
};

export function downloadCSV(filename, rows) {
  const csv = rows.map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
