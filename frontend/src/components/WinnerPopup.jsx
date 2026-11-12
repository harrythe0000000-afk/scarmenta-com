import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { PartyPopper, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { contestImg } from "@/pages/user/Contest";
import { api } from "@/lib/api";
import { usd } from "@/lib/format";
import { play } from "@/lib/sounds";

const CONFETTI = ["#f59e0b", "#d946ef", "#8b5cf6", "#10b981", "#f43f5e"];

const Confetti = () => (
  <div className="pointer-events-none absolute inset-0 overflow-hidden">
    {Array.from({ length: 24 }).map((_, i) => (
      <motion.span key={i} className="absolute top-0 h-2 w-1.5 rounded-sm" style={{ left: `${(i * 37) % 100}%`, background: CONFETTI[i % 5] }}
        initial={{ y: -20, opacity: 1, rotate: 0 }} animate={{ y: 420, opacity: 0, rotate: 360 }} transition={{ duration: 2 + (i % 4) * 0.4, delay: (i % 6) * 0.1 }} />
    ))}
  </div>
);

export const WinnerPopup = ({ onDone }) => {
  const [queue, setQueue] = useState(null);
  const navigate = useNavigate();
  useEffect(() => {
    api.get("/contest/unseen-wins").then((r) => setQueue(r.data)).catch(() => setQueue([]));
  }, []);
  const current = queue?.[0];
  useEffect(() => {
    if (queue && !current) onDone();
    if (current) play("win");
  }, [queue, current, onDone]);
  if (!current) return null;
  const close = (after) => {
    api.post(`/contest/entries/${current.id}/seen`).catch(() => {});
    setQueue((q) => q.slice(1));
    after?.();
  };
  return (
    <Dialog open onOpenChange={(o) => !o && close()}>
      <DialogContent key={current.id} data-testid="winner-popup" className="max-w-md overflow-hidden border-amber-400/30 bg-[#0b0816] text-slate-200">
        <Confetti />
        <div className="relative text-center">
          <PartyPopper className="mx-auto h-10 w-10 text-amber-300" />
          <DialogTitle className="mt-2 font-display text-2xl font-bold text-white">Congratulations, you won!</DialogTitle>
          <DialogDescription className="mt-1 text-sm text-slate-400">Your share was picked as a Promo Contest winner{current.theme_title ? ` for “${current.theme_title}”` : ""}.</DialogDescription>
          <p className="mt-4 font-num text-4xl font-bold text-emerald-300" data-testid="winner-popup-amount">+{usd(current.bonus)}</p>
          <p className="text-xs text-slate-500">bonus credits added to your balance</p>
          <img src={contestImg(current.id)} alt="Your winning screenshot" data-testid="winner-popup-image" className="mx-auto mt-4 max-h-48 rounded-xl object-contain" />
          <div className="mt-5 flex gap-2">
            <Button variant="outline" onClick={() => close()} data-testid="winner-popup-close" className="flex-1 rounded-full border-purple-500/30 bg-transparent">Close</Button>
            <Button onClick={() => close(() => navigate("/app/demo-game"))} data-testid="winner-popup-share-again" className="flex-1 rounded-full bg-[#25D366] font-semibold text-black hover:bg-[#1ebe5b]">
              <Share2 className="mr-2 h-4 w-4" /> Share again
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
