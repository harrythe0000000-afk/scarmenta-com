import { useState } from "react";
import { toast } from "sonner";
import { FlaskConical, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/StatCard";
import { PlayingCard, drawCard } from "@/components/demo/PlayingCard";
import { usd } from "@/lib/format";

const START = 1000;
const CHIPS = [10, 50, 100, 500];
const PAYOUT = { rivals: 2, scarmenta: 2, tie: 9 };
const SIDES = {
  rivals: { label: "Rivals", ring: "border-sky-400/40 bg-sky-500/[0.06]", dot: "bg-sky-400" },
  tie: { label: "Tie 8:1", ring: "border-amber-400/40 bg-amber-500/[0.06]", dot: "bg-amber-400" },
  scarmenta: { label: "Scarmenta", ring: "border-fuchsia-400/40 bg-fuchsia-500/[0.08]", dot: "bg-fuchsia-500" },
};
const RIVALS = ["Stake", "1win", "4rabet"];

const settle = (bets, winner) => Object.entries(bets).reduce((sum, [side, amt]) => {
  if (side === winner) return sum + amt * PAYOUT[side];
  if (winner === "tie" && side !== "tie") return sum + amt / 2;
  return sum;
}, 0);

const BetSpot = ({ side, amount, onClick, disabled, winner, children }) => (
  <button type="button" onClick={onClick} disabled={disabled} data-testid={`demo-bet-${side}`}
    className={`relative flex min-h-[110px] flex-1 flex-col items-center justify-center gap-2 rounded-2xl border-2 p-4 transition-all ${SIDES[side].ring} ${winner === side ? "scale-[1.03] ring-4 ring-emerald-400/70" : ""} ${disabled ? "cursor-default" : "hover:-translate-y-0.5 hover:brightness-125"}`}>
    {children}
    {amount > 0 && <span className="absolute -top-3 right-3 rounded-full bg-emerald-500 px-2.5 py-0.5 font-num text-xs font-bold text-black" data-testid={`demo-bet-amount-${side}`}>{usd(amount)}</span>}
  </button>
);

const RivalBadges = () => (
  <div className="flex flex-wrap justify-center gap-1.5">
    {RIVALS.map((r) => <span key={r} className="rounded-md border border-sky-300/30 bg-sky-950/60 px-2 py-0.5 text-xs font-bold tracking-wide text-sky-100">{r}</span>)}
  </div>
);

const History = ({ items }) => (
  <div className="flex flex-wrap gap-1.5" data-testid="demo-history">
    {items.length === 0 && <span className="text-xs text-slate-500">No rounds yet</span>}
    {items.map((w, i) => <span key={i} title={SIDES[w].label} className={`h-3 w-3 rounded-full ${SIDES[w].dot}`} />)}
  </div>
);

export default function DemoGame() {
  const [balance, setBalance] = useState(START);
  const [chip, setChip] = useState(50);
  const [bets, setBets] = useState({});
  const [cards, setCards] = useState({ rivals: null, scarmenta: null });
  const [result, setResult] = useState(null);
  const [dealing, setDealing] = useState(false);
  const [history, setHistory] = useState([]);
  const staked = Object.values(bets).reduce((a, b) => a + b, 0);

  const place = (side) => {
    if (dealing) return;
    if (result) { setResult(null); setCards({ rivals: null, scarmenta: null }); }
    if (chip > balance - staked) return toast.error("Not enough demo balance — press Reset to get $1,000 again");
    setBets((b) => ({ ...b, [side]: (b[side] || 0) + chip }));
  };
  const deal = () => {
    if (!staked) return toast.error("Place a bet first");
    const r = drawCard();
    const s = drawCard();
    const winner = r.rank === s.rank ? "tie" : r.rank > s.rank ? "rivals" : "scarmenta";
    const ret = settle(bets, winner);
    setDealing(true);
    setResult(null);
    setCards({ rivals: r, scarmenta: s });
    setTimeout(() => {
      setBalance((b) => b - staked + ret);
      setResult({ winner, net: ret - staked });
      setHistory((h) => [winner, ...h].slice(0, 30));
      setBets({});
      setDealing(false);
    }, 1300);
  };
  const reset = () => {
    setBalance(START);
    setBets({});
    setResult(null);
    setCards({ rivals: null, scarmenta: null });
  };

  return (
    <>
      <PageHeader eyebrow="Practice table" title="Scarmenta vs Rivals" desc="A free demo card game to learn how betting works. Higher card wins; same number on both cards is a Tie." />
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200" data-testid="demo-disclaimer">
        <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
        Practice only. You play with free demo credits, your real Scarmenta balance is never used, and nothing won here can be kept. Results are fully random.
      </div>

      <div className="card-lux overflow-hidden p-5 sm:p-8" data-testid="demo-table">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-slate-500">Demo balance</p>
            <p className="font-num text-3xl font-bold text-white" data-testid="demo-balance">{usd(balance - staked)}</p>
          </div>
          <Button variant="outline" onClick={reset} disabled={dealing} data-testid="demo-reset-button" className="rounded-full border-purple-500/30 bg-transparent"><RotateCcw className="mr-2 h-4 w-4" /> Reset to $1,000</Button>
        </div>

        <div className="flex items-center justify-center gap-6 rounded-3xl bg-[radial-gradient(ellipse_at_center,#14532d_0%,#052e16_70%)] px-4 py-8 sm:gap-16">
          <div className="flex flex-col items-center gap-3"><RivalBadges /><PlayingCard card={cards.rivals} testId="demo-card-rivals" /></div>
          <div className="text-center">
            <p className="font-display text-2xl font-bold text-white/80">VS</p>
            <div className="mt-2 h-12" data-testid="demo-result">
              {result && (
                <>
                  <p className="font-semibold text-emerald-300">{result.winner === "tie" ? "Tie!" : `${SIDES[result.winner].label} win`}</p>
                  <p className={`font-num text-sm ${result.net >= 0 ? "text-emerald-200" : "text-red-300"}`} data-testid="demo-result-net">{result.net >= 0 ? "+" : ""}{usd(result.net)}</p>
                </>
              )}
            </div>
          </div>
          <div className="flex flex-col items-center gap-3"><span className="rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-0.5 text-xs font-bold tracking-wide text-white">SCARMENTA</span><PlayingCard card={cards.scarmenta} testId="demo-card-scarmenta" delay={0.35} /></div>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <BetSpot side="rivals" amount={bets.rivals || 0} onClick={() => place("rivals")} disabled={dealing} winner={result?.winner}>
            <RivalBadges /><span className="text-xs text-slate-400">pays 1:1</span>
          </BetSpot>
          <BetSpot side="tie" amount={bets.tie || 0} onClick={() => place("tie")} disabled={dealing} winner={result?.winner}>
            <span className="font-display text-xl font-bold text-amber-200">TIE</span><span className="text-xs text-slate-400">pays 8:1</span>
          </BetSpot>
          <BetSpot side="scarmenta" amount={bets.scarmenta || 0} onClick={() => place("scarmenta")} disabled={dealing} winner={result?.winner}>
            <span className="font-display text-xl font-bold text-fuchsia-200">SCARMENTA</span><span className="text-xs text-slate-400">pays 1:1</span>
          </BetSpot>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex gap-2" data-testid="demo-chips">
            {CHIPS.map((c) => (
              <button key={c} type="button" onClick={() => setChip(c)} data-testid={`demo-chip-${c}`}
                className={`grid h-12 w-12 place-items-center rounded-full border-4 border-dashed font-num text-xs font-bold transition-transform ${chip === c ? "scale-110 border-white bg-purple-600 text-white" : "border-purple-300/40 bg-purple-950 text-purple-200 hover:scale-105"}`}>${c}</button>
            ))}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setBets({})} disabled={dealing || !staked} data-testid="demo-clear-button" className="rounded-full text-slate-400">Clear bets</Button>
            <Button onClick={deal} disabled={dealing || !staked} data-testid="demo-deal-button" className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 font-semibold">{dealing ? "Dealing…" : "Deal cards"}</Button>
          </div>
        </div>

        <div className="mt-6 border-t border-purple-500/10 pt-4">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Last results</p>
          <History items={history} />
        </div>
      </div>
      <p className="mt-4 text-xs text-slate-500">Rules: A is lowest, K is highest. On a Tie, Rivals and Scarmenta bets get half back. The demo balance resets to $1,000 every time you open this page.</p>
    </>
  );
}
