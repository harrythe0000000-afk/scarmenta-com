import { useEffect, useState } from "react";
import { Copy, Repeat } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlayingCard } from "@/components/demo/PlayingCard";
import { BetSpot, ChipRack } from "@/components/demo/TableParts";
import { RefillDialog, RivalsResult, RivalsWallets, cr, inr } from "@/components/demo/RivalsWallets";
import { START, addTotals, cardsFor, loadState, pickWinner, saveState, settle } from "@/lib/rivalsEngine";
import { HedgeShare } from "@/components/demo/HedgeShare";
import { useConfig } from "@/lib/hooks";
import { play } from "@/lib/sounds";
import { t } from "@/lib/demoText";

const DOT = { others: "bg-sky-400", scarmenta: "bg-fuchsia-500" };
const RULES = {
  en: "Scarmenta bets use your credit wallet, Others bets use your real ₹ wallet. Both pay 1:1. Practice table only: results here follow a practice pattern and do not predict real games.",
  hi: "Scarmenta ki bet credit wallet se, Others ki bet real ₹ wallet se lagti hai. Dono 1:1 deti hain. Sirf practice table: yahan ke result ek practice pattern par chalte hain, asli games ka andaza nahi dete.",
};

export const RivalsTable = ({ onRound, lang }) => {
  const tx = t(lang);
  const mult = useConfig()?.promo_multiplier ?? 5;
  const [state, setState] = useState(loadState);
  const [chip, setChip] = useState(100);
  const [bets, setBets] = useState({});
  const [lastBets, setLastBets] = useState(null);
  const [cards, setCards] = useState({ others: null, scarmenta: null });
  const [result, setResult] = useState(null);
  const [dealing, setDealing] = useState(false);
  const [history, setHistory] = useState([]);
  const [refill, setRefill] = useState(false);
  const { wallets } = state;
  const staked = (bets.scarmenta || 0) + (bets.others || 0);

  useEffect(() => saveState(state), [state]);

  const fits = (b) => (b.scarmenta || 0) <= wallets.scarmenta && (b.others || 0) <= wallets.others;
  const reset = () => { if (result) { setResult(null); setCards({ others: null, scarmenta: null }); } };
  const tryBets = (next) => {
    if (dealing) return;
    reset();
    if (!fits(next)) return setRefill(true);
    play("chip");
    setBets(next);
  };
  const place = (side) => tryBets({ ...bets, [side]: (bets[side] || 0) + chip });
  const repeat = () => lastBets && tryBets({ ...lastBets });
  const double = () => {
    const base = staked ? bets : lastBets;
    if (base) tryBets({ scarmenta: (base.scarmenta || 0) * 2, others: (base.others || 0) * 2 });
  };

  const deal = () => {
    const { winner, schedule } = pickWinner(bets, state.schedule);
    const s = settle(bets, winner, mult);
    const placed = { ...bets };
    setDealing(true);
    setResult(null);
    setCards(cardsFor(winner));
    play("flip");
    setTimeout(() => play("flip"), 350);
    setTimeout(() => {
      play(s.net >= 0 ? "win" : "lose");
      setState((st) => ({ schedule, totals: addTotals(st.totals, placed, winner, s),
        wallets: { scarmenta: st.wallets.scarmenta + s.change.scarmenta, others: st.wallets.others + s.change.others } }));
      setResult({ winner, bets: placed, ...s });
      setHistory((h) => [winner, ...h].slice(0, 30));
      setLastBets(placed);
      setBets({});
      setDealing(false);
      onRound(s.net, { separate: true });
    }, 1300);
  };

  const doRefill = () => {
    setState((st) => ({ ...st, wallets: { ...START } }));
    setRefill(false);
  };

  return (
    <div data-testid="demo-rivals-table">
      <RivalsWallets wallets={wallets} />
      <HedgeShare totals={state.totals} />
      <div className="flex items-center justify-center gap-6 rounded-3xl bg-[radial-gradient(ellipse_at_center,#14532d_0%,#052e16_70%)] px-4 py-8 sm:gap-16">
        <div className="flex flex-col items-center gap-3"><span className="rounded-md bg-sky-600 px-3 py-0.5 text-xs font-bold tracking-wide text-white">OTHERS</span><PlayingCard card={cards.others} testId="demo-card-rivals" /></div>
        <div className="w-40 text-center sm:w-56">
          <p className="font-display text-2xl font-bold text-white/80">VS</p>
          <RivalsResult result={result} mult={mult} />
        </div>
        <div className="flex flex-col items-center gap-3"><span className="rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-0.5 text-xs font-bold tracking-wide text-white">SCARMENTA</span><PlayingCard card={cards.scarmenta} testId="demo-card-scarmenta" delay={0.35} /></div>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <BetSpot id="others" amount={0} onClick={() => place("others")} disabled={dealing} won={result?.winner === "others"} ring="border-sky-400/40 bg-sky-500/[0.06]">
          <span className="font-display text-xl font-bold text-sky-200">OTHERS</span><span className="text-xs text-slate-400">Real ₹ wallet · {tx.pays} 1:1</span>
          {bets.others > 0 && <span className="absolute -top-3 right-3 rounded-full bg-sky-400 px-2.5 py-0.5 font-num text-xs font-bold text-black" data-testid="rivals-bet-others">{inr(bets.others)}</span>}
        </BetSpot>
        <BetSpot id="scarmenta" amount={0} onClick={() => place("scarmenta")} disabled={dealing} won={result?.winner === "scarmenta"} ring="border-fuchsia-400/40 bg-fuchsia-500/[0.08]">
          <span className="font-display text-xl font-bold text-fuchsia-200">SCARMENTA</span><span className="text-xs text-slate-400">Credit wallet · {tx.pays} 1:1</span>
          {bets.scarmenta > 0 && <span className="absolute -top-3 right-3 rounded-full bg-fuchsia-400 px-2.5 py-0.5 font-num text-xs font-bold text-black" data-testid="rivals-bet-scarmenta">{cr(bets.scarmenta)}</span>}
        </BetSpot>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <ChipRack chip={chip} setChip={setChip} prefix="" values={[50, 100, 500, 1000]} />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={repeat} disabled={dealing || !lastBets} data-testid="rivals-repeat-button" className="rounded-full border-purple-500/30 bg-transparent"><Repeat className="mr-1.5 h-4 w-4" /> Repeat bet</Button>
          <Button variant="outline" onClick={double} disabled={dealing || (!staked && !lastBets)} data-testid="rivals-double-button" className="rounded-full border-purple-500/30 bg-transparent"><Copy className="mr-1.5 h-4 w-4" /> Double bet</Button>
          <Button variant="ghost" onClick={() => setBets({})} disabled={dealing || !staked} data-testid="demo-clear-button" className="rounded-full text-slate-400">{tx.clear}</Button>
          <Button onClick={deal} disabled={dealing || !staked} data-testid="demo-deal-button" className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 font-semibold">{dealing ? tx.dealing : tx.deal}</Button>
        </div>
      </div>
      <div className="mt-6 border-t border-purple-500/10 pt-4">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">{tx.lastResults}</p>
        <div className="flex flex-wrap gap-1.5" data-testid="demo-history">
          {history.length === 0 && <span className="text-xs text-slate-500">{tx.noRounds}</span>}
          {history.map((w, i) => <span key={i} title={w === "scarmenta" ? "Scarmenta" : "Others"} className={`h-3 w-3 rounded-full ${DOT[w]}`} />)}
        </div>
      </div>
      <p className="mt-4 text-xs text-slate-500">{RULES[lang] || RULES.en}</p>
      <RefillDialog open={refill} onClose={() => setRefill(false)} onRefill={doRefill} />
    </div>
  );
};
