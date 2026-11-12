import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { PlayingCard, drawCard } from "@/components/demo/PlayingCard";
import { BetSpot, ChipRack, ResultText } from "@/components/demo/TableParts";
import { play } from "@/lib/sounds";
import { usd } from "@/lib/format";

const PAYOUT = { andar: 1.9, bahar: 2 };
const RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
const SUITS = ["♠", "♥", "♦", "♣"];
const STEP_MS = 320;

const shuffledDeck = () => {
  const deck = [];
  for (let r = 1; r <= 13; r++) for (let s = 0; s < 4; s++) deck.push({ rank: r, suit: s });
  for (let i = deck.length - 1; i > 0; i--) {
    const j = crypto.getRandomValues(new Uint32Array(1))[0] % (i + 1);
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
};

const dealRound = () => {
  const [joker, ...rest] = shuffledDeck();
  const seq = [];
  for (const c of rest) {
    seq.push({ ...c, side: seq.length % 2 === 0 ? "andar" : "bahar" });
    if (c.rank === joker.rank) break;
  }
  return { joker, seq, winner: seq[seq.length - 1].side };
};

const MiniCard = ({ c, hit }) => (
  <motion.span initial={{ y: -16, opacity: 0, rotate: -8 }} animate={{ y: 0, opacity: 1, rotate: 0 }}
    className={`grid h-12 w-9 shrink-0 place-items-center rounded-md bg-white text-xs font-bold shadow ${c.suit === 1 || c.suit === 2 ? "text-red-600" : "text-slate-900"} ${hit ? "ring-4 ring-emerald-400" : ""}`}>
    {RANKS[c.rank - 1]}{SUITS[c.suit]}
  </motion.span>
);

const Row = ({ label, cards, total, testId, tone }) => (
  <div className="flex items-center gap-3" data-testid={testId}>
    <span className={`w-16 shrink-0 text-xs font-bold uppercase tracking-wider ${tone}`}>{label}</span>
    <div className="flex min-h-12 flex-1 gap-1 overflow-hidden">{cards.slice(-8).map((c, i, arr) => <MiniCard key={`${c.rank}${c.suit}`} c={c} hit={c.hit && i === arr.length - 1} />)}</div>
    <span className="w-8 text-right font-num text-xs text-slate-500">{total}</span>
  </div>
);

export const AndarBaharTable = ({ free, onRound }) => {
  const [chip, setChip] = useState(50);
  const [bets, setBets] = useState({});
  const [joker, setJoker] = useState(null);
  const [dealt, setDealt] = useState([]);
  const [result, setResult] = useState(null);
  const [dealing, setDealing] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearInterval(timer.current), []);
  const staked = Object.values(bets).reduce((a, b) => a + b, 0);

  const place = (side) => {
    if (dealing) return;
    if (result) { setResult(null); setJoker(null); setDealt([]); }
    if (chip > free - staked) return toast.error("Not enough demo balance — press Reset to get $1,000 again");
    play("chip");
    setBets((b) => ({ ...b, [side]: (b[side] || 0) + chip }));
  };
  const deal = () => {
    const round = dealRound();
    const net = Math.round(((bets[round.winner] || 0) * PAYOUT[round.winner] - staked) * 100) / 100;
    setDealing(true);
    setResult(null);
    setDealt([]);
    setJoker(round.joker);
    play("flip");
    let i = 0;
    timer.current = setInterval(() => {
      const c = round.seq[i];
      play("flip");
      setDealt((d) => [...d, { ...c, hit: i === round.seq.length - 1 }]);
      i += 1;
      if (i >= round.seq.length) {
        clearInterval(timer.current);
        setTimeout(() => {
          play(net >= 0 ? "win" : "lose");
          setResult({ winner: round.winner, net });
          setBets({});
          setDealing(false);
          onRound(net);
        }, 500);
      }
    }, STEP_MS);
  };
  const andar = dealt.filter((c) => c.side === "andar");
  const bahar = dealt.filter((c) => c.side === "bahar");

  return (
    <div data-testid="demo-andar-bahar-table">
      <div className="flex flex-col gap-6 rounded-3xl bg-[radial-gradient(ellipse_at_center,#14532d_0%,#052e16_70%)] px-4 py-6 sm:flex-row sm:items-center sm:px-8">
        <div className="flex flex-col items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-amber-200">Joker</span>
          <PlayingCard card={joker} testId="demo-ab-joker" />
        </div>
        <div className="flex-1 space-y-4">
          <Row label="Andar" cards={andar} total={andar.length} testId="demo-ab-andar-row" tone="text-sky-300" />
          <Row label="Bahar" cards={bahar} total={bahar.length} testId="demo-ab-bahar-row" tone="text-fuchsia-300" />
          <ResultText result={result} label={result && `${result.winner === "andar" ? "Andar" : "Bahar"} wins on card ${dealt.length}`} />
        </div>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <BetSpot id="andar" amount={bets.andar || 0} onClick={() => place("andar")} disabled={dealing} won={result?.winner === "andar"} ring="border-sky-400/40 bg-sky-500/[0.06]">
          <span className="font-display text-xl font-bold text-sky-200">ANDAR</span><span className="text-xs text-slate-400">pays 0.9:1</span>
        </BetSpot>
        <BetSpot id="bahar" amount={bets.bahar || 0} onClick={() => place("bahar")} disabled={dealing} won={result?.winner === "bahar"} ring="border-fuchsia-400/40 bg-fuchsia-500/[0.08]">
          <span className="font-display text-xl font-bold text-fuchsia-200">BAHAR</span><span className="text-xs text-slate-400">pays 1:1</span>
        </BetSpot>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <ChipRack chip={chip} setChip={setChip} />
        <div className="flex items-center gap-2">
          {staked > 0 && <span className="font-num text-sm text-slate-300" data-testid="demo-ab-in-play">In play {usd(staked)}</span>}
          <Button variant="ghost" onClick={() => setBets({})} disabled={dealing || !staked} data-testid="demo-ab-clear-button" className="rounded-full text-slate-400">Clear bets</Button>
          <Button onClick={deal} disabled={dealing || !staked} data-testid="demo-ab-deal-button" className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 font-semibold">{dealing ? "Dealing…" : "Deal cards"}</Button>
        </div>
      </div>
      <p className="mt-4 text-xs text-slate-500">One Joker card opens. Cards then fall Andar, Bahar, Andar… The side that first gets a card with the same number as the Joker wins.</p>
    </div>
  );
};
