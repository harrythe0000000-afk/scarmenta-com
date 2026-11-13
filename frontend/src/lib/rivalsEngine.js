import { drawCard } from "@/components/demo/PlayingCard";

const KEY = "scarmenta_demo_rivals";
export const START = { scarmenta: 5000, others: 5000 };
const BLOCK = 5;
const HEAVY_LOSES = 3;

const shuffle = (a) => {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};
const newSchedule = () => shuffle([...Array(HEAVY_LOSES).fill(true), ...Array(BLOCK - HEAVY_LOSES).fill(false)]);

export const EMPTY_TOTALS = { rounds: 0, othersWins: 0, othersProfit: 0, creditCost: 0, net: 0 };

export const loadState = () => {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || "null");
    if (s?.wallets && Array.isArray(s.schedule)) return { totals: { ...EMPTY_TOTALS }, ...s };
  } catch { /* ignore */ }
  return { wallets: { ...START }, schedule: newSchedule(), totals: { ...EMPTY_TOTALS } };
};

const r2 = (n) => Math.round(n * 100) / 100;
export const addTotals = (t, bets, winner, s) => ({
  rounds: t.rounds + 1,
  othersWins: t.othersWins + (winner === "others" && bets.others ? 1 : 0),
  othersProfit: r2(t.othersProfit + Math.max(0, s.change.others)),
  creditCost: r2(t.creditCost + s.creditCost),
  net: r2(t.net + s.net),
});
export const saveState = (s) => localStorage.setItem(KEY, JSON.stringify(s));

// In every block of 5 rounds the side with the bigger bet loses 3 times.
export const pickWinner = (bets, schedule) => {
  const sc = bets.scarmenta || 0;
  const ot = bets.others || 0;
  const queue = schedule.length ? schedule : newSchedule();
  const [heavyLoses, ...rest] = queue;
  const heavy = sc === ot ? (Math.random() < 0.5 ? "scarmenta" : "others") : sc > ot ? "scarmenta" : "others";
  const light = heavy === "scarmenta" ? "others" : "scarmenta";
  return { winner: heavyLoses ? light : heavy, schedule: rest.length ? rest : newSchedule() };
};

export const cardsFor = (winner) => {
  let a = drawCard();
  let b = drawCard();
  while (a.rank === b.rank) b = drawCard();
  const [hi, lo] = a.rank > b.rank ? [a, b] : [b, a];
  return winner === "scarmenta" ? { scarmenta: hi, others: lo } : { scarmenta: lo, others: hi };
};

// Bets pay 1:1. Scarmenta credits cost 1/mult in real money.
export const settle = (bets, winner, mult) => {
  const sc = bets.scarmenta || 0;
  const ot = bets.others || 0;
  const change = { scarmenta: winner === "scarmenta" ? sc : -sc, others: winner === "others" ? ot : -ot };
  const creditCost = Math.round((sc / mult) * 100) / 100;
  const creditValue = Math.round((change.scarmenta / mult) * 100) / 100;
  return { change, creditCost, net: Math.round((change.others + creditValue) * 100) / 100 };
};
