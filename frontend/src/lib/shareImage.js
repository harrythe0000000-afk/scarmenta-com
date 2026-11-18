const W = 1080;
const H = 1350;

const money = (n) => (!Number.isFinite(n) ? "Too large" : n >= 1e12 ? `$${n.toExponential(2)}` : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }));

const loadImg = (src) => new Promise((res) => {
  const img = new Image();
  img.onload = () => res(img);
  img.onerror = () => res(null);
  img.src = src;
});

const wrap = (ctx, text, x, y, maxW, lh) => {
  let line = "";
  for (const w of text.split(" ")) {
    if (ctx.measureText(`${line}${w} `).width > maxW && line) {
      ctx.fillText(line.trim(), x, y);
      line = "";
      y += lh;
    }
    line += `${w} `;
  }
  ctx.fillText(line.trim(), x, y);
};

const drawChart = (ctx, points, x, y, w, h) => {
  const vals = points.map((p) => (Number.isFinite(p.balance) ? p.balance : NaN)).filter(Number.isFinite);
  if (vals.length < 2) return;
  const max = Math.max(...vals);
  const min = Math.min(...vals);
  const px = (i) => x + (i / (vals.length - 1)) * w;
  const py = (v) => y + h - ((v - min) / (max - min || 1)) * h;
  const g = ctx.createLinearGradient(0, y, 0, y + h);
  g.addColorStop(0, "rgba(168,85,247,0.55)");
  g.addColorStop(1, "rgba(168,85,247,0)");
  ctx.beginPath();
  ctx.moveTo(px(0), y + h);
  vals.forEach((v, i) => ctx.lineTo(px(i), py(v)));
  ctx.lineTo(px(vals.length - 1), y + h);
  ctx.fillStyle = g;
  ctx.fill();
  ctx.beginPath();
  vals.forEach((v, i) => (i ? ctx.lineTo(px(i), py(v)) : ctx.moveTo(px(i), py(v))));
  ctx.strokeStyle = "#c084fc";
  ctx.lineWidth = 6;
  ctx.stroke();
};

export async function renderShareImage({ amount, rate, days, final, chart, code, link }) {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#07050d";
  ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(W, 0, 50, W, 0, 900);
  glow.addColorStop(0, "rgba(192,48,216,0.35)");
  glow.addColorStop(1, "rgba(192,48,216,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);

  const logo = await loadImg("/scarmenta-logo.png");
  if (logo) ctx.drawImage(logo, 80, 70, 90, 90);
  ctx.fillStyle = "#fff";
  ctx.font = "700 52px Georgia, serif";
  ctx.fillText("Scarmenta", 190, 135);

  ctx.fillStyle = "#F2B94B";
  ctx.font = "600 26px sans-serif";
  ctx.fillText("COMPOUND CALCULATOR", 80, 250);
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "400 36px sans-serif";
  ctx.fillText(`${money(amount)} at ${rate}% daily for ${days.toLocaleString()} days`, 80, 310);

  ctx.fillStyle = "#94a3b8";
  ctx.font = "500 28px sans-serif";
  ctx.fillText("Final amount", 80, 410);
  ctx.fillStyle = "#fff";
  ctx.font = "700 96px sans-serif";
  ctx.fillText(money(final), 80, 510);
  ctx.fillStyle = "#6ee7b7";
  ctx.font = "600 38px sans-serif";
  ctx.fillText(`Profit ${money(final - amount)}`, 80, 575);

  drawChart(ctx, chart, 80, 640, W - 160, 300);

  ctx.fillStyle = "rgba(168,85,247,0.15)";
  ctx.strokeStyle = "rgba(168,85,247,0.5)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(80, 990, W - 160, 210, 28);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "500 30px sans-serif";
  ctx.fillText("Join with my referral code", 120, 1060);
  ctx.fillStyle = "#fff";
  ctx.font = "700 60px monospace";
  ctx.fillText(code || "—", 120, 1120);
  ctx.fillStyle = "#c084fc";
  ctx.font = "500 24px sans-serif";
  const shown = link.replace(/^https?:\/\//, "");
  ctx.fillText(shown.length > 70 ? `…${shown.slice(-67)}` : shown, 120, 1170);

  ctx.fillStyle = "#64748b";
  ctx.font = "400 22px sans-serif";
  wrap(ctx, "Math example only. Scarmenta does not promise or guarantee any daily return, profit or winnings. Credits cannot be withdrawn.", 80, 1255, W - 160, 32);
  return new Promise((res) => c.toBlob(res, "image/png"));
}

export const downloadBlob = (blob, name) => {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

export async function shareBlob(blob, name, text) {
  const file = new File([blob], name, { type: "image/png" });
  if (navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file], text });
    return "shared";
  }
  downloadBlob(blob, name);
  window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  return "downloaded";
}

export async function renderStreakImage({ streak, game, code, link }) {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#07050d";
  ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(W / 2, 520, 40, W / 2, 520, 700);
  glow.addColorStop(0, "rgba(249,115,22,0.55)");
  glow.addColorStop(1, "rgba(249,115,22,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);
  const logo = await loadImg("/scarmenta-logo.png");
  if (logo) ctx.drawImage(logo, 80, 70, 90, 90);
  ctx.fillStyle = "#fff";
  ctx.font = "700 52px Georgia, serif";
  ctx.fillText("Scarmenta", 190, 135);
  ctx.textAlign = "center";
  ctx.font = "260px serif";
  ctx.fillText("🔥", W / 2, 560);
  ctx.fillStyle = "#fbbf24";
  ctx.font = "800 110px sans-serif";
  ctx.fillText("HOT STREAK", W / 2, 720);
  ctx.fillStyle = "#fff";
  ctx.font = "700 64px sans-serif";
  ctx.fillText(`${streak} wins in a row`, W / 2, 810);
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "500 36px sans-serif";
  ctx.fillText(game, W / 2, 870);
  ctx.textAlign = "left";
  ctx.fillStyle = "rgba(249,115,22,0.12)";
  ctx.strokeStyle = "rgba(249,115,22,0.5)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(80, 990, W - 160, 210, 28);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "500 30px sans-serif";
  ctx.fillText("Join with my referral code", 120, 1060);
  ctx.fillStyle = "#fff";
  ctx.font = "700 60px monospace";
  ctx.fillText(code || "—", 120, 1120);
  ctx.fillStyle = "#fdba74";
  ctx.font = "500 24px sans-serif";
  const shown = link.replace(/^https?:\/\//, "");
  ctx.fillText(shown.length > 70 ? `…${shown.slice(-67)}` : shown, 120, 1170);
  return new Promise((res) => c.toBlob(res, "image/png"));
}

const inrFmt = (n) => `₹${Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export async function renderHedgeImage({ net, othersProfit, creditCost, rounds, othersWins, code, link }) {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#07050d";
  ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(W / 2, 460, 40, W / 2, 460, 720);
  glow.addColorStop(0, "rgba(16,185,129,0.35)");
  glow.addColorStop(1, "rgba(16,185,129,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);
  const logo = await loadImg("/scarmenta-logo.png");
  if (logo) ctx.drawImage(logo, 80, 70, 90, 90);
  ctx.fillStyle = "#fff";
  ctx.font = "700 52px Georgia, serif";
  ctx.fillText("Scarmenta", 190, 135);
  ctx.fillStyle = "#F2B94B";
  ctx.font = "600 26px sans-serif";
  ctx.fillText("SCARMENTA VS OTHERS · DEMO PRACTICE", 80, 250);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "500 30px sans-serif";
  ctx.fillText("My total net profit", 80, 340);
  ctx.fillStyle = "#6ee7b7";
  ctx.font = "800 130px sans-serif";
  ctx.fillText(`${net < 0 ? "−" : "+"}${inrFmt(net)}`, 80, 480);
  const rows = [["Profit on Others", `+${inrFmt(othersProfit)}`, "#7dd3fc"], ["Scarmenta credits cost", `−${inrFmt(creditCost)}`, "#f0abfc"],
    ["Rounds won / played", `${othersWins} / ${rounds}`, "#fff"]];
  rows.forEach(([l, v, col], i) => {
    const y = 590 + i * 95;
    ctx.fillStyle = "rgba(255,255,255,0.05)";
    ctx.beginPath();
    ctx.roundRect(80, y - 58, W - 160, 80, 20);
    ctx.fill();
    ctx.fillStyle = "#cbd5e1";
    ctx.font = "500 32px sans-serif";
    ctx.fillText(l, 115, y);
    ctx.fillStyle = col;
    ctx.font = "700 40px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(v, W - 115, y);
    ctx.textAlign = "left";
  });
  ctx.fillStyle = "rgba(16,185,129,0.12)";
  ctx.strokeStyle = "rgba(16,185,129,0.5)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(80, 940, W - 160, 210, 28);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "500 30px sans-serif";
  ctx.fillText("Join with my referral code", 120, 1010);
  ctx.fillStyle = "#fff";
  ctx.font = "700 60px monospace";
  ctx.fillText(code || "—", 120, 1070);
  ctx.fillStyle = "#6ee7b7";
  ctx.font = "500 24px sans-serif";
  const shown = link.replace(/^https?:\/\//, "");
  ctx.fillText(shown.length > 70 ? `…${shown.slice(-67)}` : shown, 120, 1120);
  ctx.fillStyle = "#64748b";
  ctx.font = "400 22px sans-serif";
  wrap(ctx, "Demo practice with free play money. Not real winnings. Real game results are never guaranteed. Credits cannot be withdrawn.", 80, 1220, W - 160, 32);
  return new Promise((res) => c.toBlob(res, "image/png"));
}

export async function renderLiveWinImage({ net, game, code, link }) {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#07050d";
  ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(W / 2, 520, 40, W / 2, 520, 720);
  glow.addColorStop(0, "rgba(251,191,36,0.45)");
  glow.addColorStop(1, "rgba(251,191,36,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);
  const logo = await loadImg("/scarmenta-logo.png");
  if (logo) ctx.drawImage(logo, 80, 70, 90, 90);
  ctx.fillStyle = "#fff";
  ctx.font = "700 52px Georgia, serif";
  ctx.fillText("Scarmenta", 190, 135);
  ctx.textAlign = "center";
  ctx.fillStyle = "#F2B94B";
  ctx.font = "600 30px sans-serif";
  ctx.fillText("LIVE CASINO WIN", W / 2, 360);
  ctx.fillStyle = "#fcd34d";
  ctx.font = "800 150px sans-serif";
  ctx.fillText(`+${inrFmt(net)}`, W / 2, 560);
  ctx.fillStyle = "#fff";
  ctx.font = "600 44px sans-serif";
  wrap(ctx, game || "Live dealer table", W / 2, 680, W - 200, 56);
  ctx.textAlign = "left";
  ctx.fillStyle = "rgba(251,191,36,0.12)";
  ctx.strokeStyle = "rgba(251,191,36,0.5)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(80, 990, W - 160, 210, 28);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "500 30px sans-serif";
  ctx.fillText("Join with my referral code", 120, 1060);
  ctx.fillStyle = "#fff";
  ctx.font = "700 60px monospace";
  ctx.fillText(code || "—", 120, 1120);
  ctx.fillStyle = "#fcd34d";
  ctx.font = "500 24px sans-serif";
  const shown = link.replace(/^https?:\/\//, "");
  ctx.fillText(shown.length > 70 ? `…${shown.slice(-67)}` : shown, 120, 1170);
  return new Promise((res) => c.toBlob(res, "image/png"));
}
