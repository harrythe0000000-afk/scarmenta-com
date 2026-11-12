import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PlayingCard, drawCard } from "@/components/demo/PlayingCard";
import { BetSpot, ChipRack, ResultText, RivalBadges } from "@/components/demo/TableParts";
import { play } from "@/lib/sounds";
import { t } from "@/lib/demoText";
import { usd } from "@/lib/format";

const PAYOUT = { rivals: 2, scarmenta: 2, tie: 9 };
const LABEL_KEY = { rivals: "rivalsWin", scarmenta: "scarmentaWins", tie: "tie" };
const DOT = { rivals: "bg-sky-400", tie: "bg-amber-400", scarmenta: "bg-fuchsia-500" };

const settle = (bets, winner) => Object.entries(bets).reduce((sum, [side, amt]) => {
  if (side === winner) return sum + amt * PAYOUT[side];
  if (winner === "tie" && side !== "tie") return sum + amt / 2;
  return sum;
}, 0);

export const RivalsTable = ({ free, onRound, lang }) => {
  const tx = t(lang);
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
    if (chip > free - staked) return toast.error(tx.noBalance, { position: "top-center" });
    play("chip");
    setBets((b) => ({ ...b, [side]: (b[side] || 0) + chip }));
  };
  const deal = () => {
    const r = drawCard();
    const s = drawCard();
    const winner = r.rank === s.rank ? "tie" : r.rank > s.rank ? "rivals" : "scarmenta";
    const net = settle(bets, winner) - staked;
    setDealing(true);
    setResult(null);
    setCards({ rivals: r, scarmenta: s });
    play("flip");
    setTimeout(() => play("flip"), 350);
    setTimeout(() => {
      play(net >= 0 ? "win" : "lose");
      setResult({ winner, net });
      setHistory((h) => [winner, ...h].slice(0, 30));
      setBets({});
      setDealing(false);
      onRound(net);
    }, 1300);
  };

  return (
    <div data-testid="demo-rivals-table">
      <div className="flex items-center justify-center gap-6 rounded-3xl bg-[radial-gradient(ellipse_at_center,#14532d_0%,#052e16_70%)] px-4 py-8 sm:gap-16">
        <div className="flex flex-col items-center gap-3"><RivalBadges /><PlayingCard card={cards.rivals} testId="demo-card-rivals" /></div>
        <div className="text-center">
          <p className="font-display text-2xl font-bold text-white/80">VS</p>
          <ResultText result={result} label={result && tx[LABEL_KEY[result.winner]]} />
        </div>
        <div className="flex flex-col items-center gap-3"><span className="rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-0.5 text-xs font-bold tracking-wide text-white">SCARMENTA</span><PlayingCard card={cards.scarmenta} testId="demo-card-scarmenta" delay={0.35} /></div>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <BetSpot id="rivals" amount={bets.rivals || 0} onClick={() => place("rivals")} disabled={dealing} won={result?.winner === "rivals"} ring="border-sky-400/40 bg-sky-500/[0.06]">
          <RivalBadges /><span className="text-xs text-slate-400">{tx.pays} 1:1</span>
        </BetSpot>
        <BetSpot id="tie" amount={bets.tie || 0} onClick={() => place("tie")} disabled={dealing} won={result?.winner === "tie"} ring="border-amber-400/40 bg-amber-500/[0.06]">
          <span className="font-display text-xl font-bold text-amber-200">TIE</span><span className="text-xs text-slate-400">{tx.pays} 8:1</span>
        </BetSpot>
        <BetSpot id="scarmenta" amount={bets.scarmenta || 0} onClick={() => place("scarmenta")} disabled={dealing} won={result?.winner === "scarmenta"} ring="border-fuchsia-400/40 bg-fuchsia-500/[0.08]">
          <span className="font-display text-xl font-bold text-fuchsia-200">SCARMENTA</span><span className="text-xs text-slate-400">{tx.pays} 1:1</span>
        </BetSpot>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <ChipRack chip={chip} setChip={setChip} />
        <div className="flex items-center gap-2">
          {staked > 0 && <span className="font-num text-sm text-slate-300" data-testid="demo-in-play">{tx.inPlay} {usd(staked)}</span>}
          <Button variant="ghost" onClick={() => setBets({})} disabled={dealing || !staked} data-testid="demo-clear-button" className="rounded-full text-slate-400">{tx.clear}</Button>
          <Button onClick={deal} disabled={dealing || !staked} data-testid="demo-deal-button" className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 font-semibold">{dealing ? tx.dealing : tx.deal}</Button>
        </div>
      </div>
      <div className="mt-6 border-t border-purple-500/10 pt-4">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">{tx.lastResults}</p>
        <div className="flex flex-wrap gap-1.5" data-testid="demo-history">
          {history.length === 0 && <span className="text-xs text-slate-500">{tx.noRounds}</span>}
          {history.map((w, i) => <span key={i} title={tx[LABEL_KEY[w]]} className={`h-3 w-3 rounded-full ${DOT[w]}`} />)}
        </div>
      </div>
      <p className="mt-4 text-xs text-slate-500">{tx.rivalsRules}</p>
    </div>
  );
};
