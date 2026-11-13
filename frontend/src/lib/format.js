export const usd = (n) =>
  `${Number(n) < 0 ? "-" : ""}$${Math.abs(Number(n || 0)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const localMoney = (n, cur) =>
  cur === "INR"
    ? `₹${Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`
    : `${Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 })} ${cur || ""}`.trim();

export const signedUsd = (n) => `${n < 0 ? "−" : "+"}${usd(Math.abs(n))}`;

export const fmtDate = (iso) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";

export const calc = (amount, cfg) => ({
  credits: +((Number(amount) || 0) * (cfg?.promo_multiplier ?? 5)).toFixed(2),
});

export const METHODS = [
  { value: "usdt", label: "USDT", hint: "All countries · TRC20 / ERC20 / BEP20" },
  { value: "upi", label: "UPI", hint: "India · paid in INR at today's rate" },
];

export const methodLabel = (v, network) => (v === "usdt" ? `USDT${network ? ` ${network}` : ""}` : METHODS.find((m) => m.value === v)?.label || v);

export const TX_TYPES = {
  deposit: "Credit Allocation",
  bet: "Bet",
  win: "Win",
  rollback: "Bet Refund",
  referral_bonus: "Referral Income",
  share_bonus: "Share Bonus",
  sharer_reward: "Top Sharer Reward",
  contest_bonus: "Contest Prize",
  live_round: "Live Casino",
  loss_reward: "Loss Reward",
  transfer_out: "Transfer Out",
  transfer_in: "Transfer In",
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
