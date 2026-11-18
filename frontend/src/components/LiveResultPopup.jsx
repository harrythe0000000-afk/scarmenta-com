import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Equal, PartyPopper, RotateCcw } from "lucide-react";
import { LiveWinShare } from "@/components/LiveWinShare";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { signedUsd } from "@/lib/format";
import { play } from "@/lib/sounds";

export const LAUNCH_KEY = "scarmenta_live_launch";
const inr = (n) => `₹${Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const fetchResult = async (since, alive, tries = 15) => {
  for (let i = 0; i < tries && alive(); i++) {
    const { data } = await api.get("/live/session-result", { params: { since } });
    if (data.events > 0) return data;
    await new Promise((r) => setTimeout(r, 3000));
  }
  return null;
};

export const LiveResultPopup = ({ onDone }) => {
  const [res, setRes] = useState(null);
  const [game, setGame] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  useEffect(() => {
    let stored;
    try { stored = JSON.parse(localStorage.getItem(LAUNCH_KEY) || "null"); } catch { stored = null; }
    if (!stored?.at) return;
    localStorage.removeItem(LAUNCH_KEY);
    setGame(stored.game || "");
    fetchResult(stored.at, () => alive.current).then((r) => {
      if (!r || !alive.current) return;
      setRes(r);
      if (r.net_inr !== 0) play(r.net_inr > 0 ? "win" : "lose");
      onDone?.();
    }).catch(() => {});
  }, [onDone]);
  if (!res) return null;
  const won = res.net_inr > 0;
  const even = res.net_inr === 0;
  const Icon = won ? PartyPopper : even ? Equal : RotateCcw;
  return (
    <Dialog open onOpenChange={(o) => !o && setRes(null)}>
      <DialogContent data-testid="live-result-popup" className="max-w-sm overflow-hidden border-purple-500/20 bg-[#0b0816] text-center text-slate-200">
        <motion.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 220, damping: 14 }}
          className={`mx-auto grid h-16 w-16 place-items-center rounded-full ${won ? "bg-amber-400/20" : "bg-slate-500/15"}`}>
          <Icon className={won ? "h-8 w-8 text-amber-300" : "h-7 w-7 text-slate-300"} />
        </motion.div>
        <DialogTitle className="font-display text-2xl text-white"><span data-testid="live-result-title">{won ? "You won!" : even ? "Break even" : "Not this time"}</span></DialogTitle>
        <DialogDescription className="text-sm text-slate-400">{game ? `${game} · ` : ""}{res.events} result{res.events > 1 ? "s" : ""} from your last session</DialogDescription>
        <p className={`font-num text-4xl font-bold ${won ? "text-amber-300" : "text-slate-300"}`} data-testid="live-result-net">{won ? "+" : res.net_inr < 0 ? "−" : ""}{inr(res.net_inr)}</p>
        <p className="text-xs text-slate-500" data-testid="live-result-detail">Bet {inr(res.bet_inr)} · Won {inr(res.win_inr)} · Balance change {signedUsd(res.net_usd)}</p>
        {even && <p className="text-xs text-slate-400" data-testid="live-result-even">You got your full bet back.</p>}
        {won && <LiveWinShare net={res.net_inr} game={game} />}
        <Button onClick={() => setRes(null)} data-testid="live-result-close" className="mt-2 w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold">{won ? "Keep playing" : "Try again"}</Button>
      </DialogContent>
    </Dialog>
  );
};
