import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { PlayingCard, shuffledDeck } from "@/components/demo/PlayingCard";
import { BetSpot, ChipRack, ResultText } from "@/components/demo/TableParts";
import { compareHands, evaluate } from "@/lib/teenPatti";
import { t } from "@/lib/demoText";
import { play } from "@/lib/sounds";
import { usd } from "@/lib/format";

const STEP_MS = 550;
const ORDER = [["rivals", 0], ["scarmenta", 0], ["rivals", 1], ["scarmenta", 1], ["rivals", 2], ["scarmenta", 2]];

const ScanLine = () => (
  <motion.span initial={{ top: "0%" }} animate={{ top: ["0%", "100%", "0%"] }} transition={{ duration: 0.5 }}
    className="pointer-events-none absolute inset-x-0 h-1 rounded-full bg-emerald-300 shadow-[0_0_16px_4px_rgba(110,231,183,0.8)]" />
);

const Hand = ({ title, badge, cards, scanning, handName, won, testId }) => (
  <div className={`flex flex-col items-center gap-3 rounded-2xl p-3 transition-all ${won ? "bg-emerald-400/10 ring-2 ring-emerald-400/60" : ""}`} data-testid={testId}>
    {badge || <span className="text-xs font-bold tracking-wide text-white">{title}</span>}
    <div className="flex gap-2">
      {[0, 1, 2].map((i) => (
        <PlayingCard key={i} size="sm" card={cards[i]} delay={0} testId={`${testId}-card-${i}`}>
          {scanning === i && <ScanLine />}
        </PlayingCard>
      ))}
    </div>
    <p className="h-5 text-xs font-semibold text-amber-200" data-testid={`${testId}-hand`}>{handName}</p>
  </div>
);

export const TeenPattiTable = ({ free, onRound, lang, rivalBadges }) => {
  const tx = t(lang);
  const [chip, setChip] = useState(50);
  const [bets, setBets] = useState({});
  const [hands, setHands] = useState({ rivals: [], scarmenta: [] });
  const [scan, setScan] = useState(null);
  const [result, setResult] = useState(null);
  const [dealing, setDealing] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearInterval(timer.current), []);
  const staked = Object.values(bets).reduce((a, b) => a + b, 0);

  const place = (side) => {
    if (dealing) return;
    if (result) { setResult(null); setHands({ rivals: [], scarmenta: [] }); }
    if (chip > free - staked) return toast.error(tx.noBalance, { position: "top-center" });
    play("chip");
    setBets((b) => ({ ...b, [side]: (b[side] || 0) + chip }));
  };
  const deal = () => {
    const deck = shuffledDeck();
    const full = { rivals: deck.slice(0, 3), scarmenta: deck.slice(3, 6) };
    const cmp = compareHands(full.rivals, full.scarmenta);
    const winner = cmp === 0 ? "tie" : cmp > 0 ? "rivals" : "scarmenta";
    const net = winner === "tie" ? 0 : (bets[winner] || 0) * 2 - staked;
    setDealing(true);
    setResult(null);
    setHands({ rivals: [], scarmenta: [] });
    let i = 0;
    timer.current = setInterval(() => {
      const [side, idx] = ORDER[i];
      setScan({ side, idx });
      play("flip");
      setHands((h) => ({ ...h, [side]: [...h[side], full[side][idx]] }));
      i += 1;
      if (i >= ORDER.length) {
        clearInterval(timer.current);
        setTimeout(() => {
          setScan(null);
          play(net > 0 ? "win" : net < 0 ? "lose" : "chip");
          setResult({ winner, net, names: { rivals: evaluate(full.rivals)[0], scarmenta: evaluate(full.scarmenta)[0] } });
          setBets({});
          setDealing(false);
          onRound(net);
        }, 600);
      }
    }, STEP_MS);
  };
  const label = result && (result.winner === "tie" ? tx.tpTie : result.winner === "rivals" ? tx.rivalsWin : tx.scarmentaWins);

  return (
    <div data-testid="demo-teen-patti-table">
      <div className="rounded-3xl bg-[radial-gradient(ellipse_at_center,#14532d_0%,#052e16_70%)] px-4 py-6">
        <p className="mb-3 h-5 text-center text-xs uppercase tracking-[0.3em] text-emerald-200/80" data-testid="demo-tp-status">{dealing ? tx.scanning : ""}</p>
        <div className="flex flex-col items-center justify-center gap-4 lg:flex-row lg:gap-10">
          <Hand testId="demo-tp-rivals" badge={rivalBadges} cards={hands.rivals} scanning={scan?.side === "rivals" ? scan.idx : null}
            handName={result && tx.hands[result.names.rivals]} won={result?.winner === "rivals"} />
          <ResultText result={result} label={label} />
          <Hand testId="demo-tp-scarmenta" badge={<span className="rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-0.5 text-xs font-bold tracking-wide text-white">SCARMENTA</span>}
            cards={hands.scarmenta} scanning={scan?.side === "scarmenta" ? scan.idx : null}
            handName={result && tx.hands[result.names.scarmenta]} won={result?.winner === "scarmenta"} />
        </div>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <BetSpot id="tp-rivals" amount={bets.rivals || 0} onClick={() => place("rivals")} disabled={dealing} won={result?.winner === "rivals"} ring="border-sky-400/40 bg-sky-500/[0.06]">
          {rivalBadges}<span className="text-xs text-slate-400">{tx.pays} 1:1</span>
        </BetSpot>
        <BetSpot id="tp-scarmenta" amount={bets.scarmenta || 0} onClick={() => place("scarmenta")} disabled={dealing} won={result?.winner === "scarmenta"} ring="border-fuchsia-400/40 bg-fuchsia-500/[0.08]">
          <span className="font-display text-xl font-bold text-fuchsia-200">SCARMENTA</span><span className="text-xs text-slate-400">{tx.pays} 1:1</span>
        </BetSpot>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <ChipRack chip={chip} setChip={setChip} />
        <div className="flex items-center gap-2">
          {staked > 0 && <span className="font-num text-sm text-slate-300" data-testid="demo-tp-in-play">{tx.inPlay} {usd(staked)}</span>}
          <Button variant="ghost" onClick={() => setBets({})} disabled={dealing || !staked} data-testid="demo-tp-clear-button" className="rounded-full text-slate-400">{tx.clear}</Button>
          <Button onClick={deal} disabled={dealing || !staked} data-testid="demo-tp-deal-button" className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 font-semibold">{dealing ? tx.dealing : tx.deal}</Button>
        </div>
      </div>
      <p className="mt-4 text-xs text-slate-500">{tx.tpRules}</p>
    </div>
  );
};
