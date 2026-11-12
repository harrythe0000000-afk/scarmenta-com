import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { Flame, Share2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { renderStreakImage, shareBlob } from "@/lib/shareImage";

export const STREAK_GOAL = 3;
const FILE = "scarmenta-hot-streak.png";

const ShareStreak = ({ streak, game }) => {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const share = async () => {
    const code = user?.referral_code;
    const link = `${window.location.origin}/register${code ? `?ref=${code}&src=calc` : ""}`;
    setBusy(true);
    try {
      const blob = await renderStreakImage({ streak, game, code, link });
      const how = await shareBlob(blob, FILE, `🔥 ${streak} wins in a row on Scarmenta! Join with my code ${code || ""}: ${link}`);
      if (how === "downloaded") toast.success("Image saved — attach it in WhatsApp", { position: "top-center" });
    } catch (e) {
      if (e?.name !== "AbortError") toast.error("Couldn't create the image", { position: "top-center" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" onClick={share} disabled={busy} data-testid="demo-streak-share-button"
      className="flex items-center gap-1 rounded-full bg-[#25D366] px-3 py-1 text-xs font-bold text-black transition-transform hover:scale-105 disabled:opacity-60">
      <Share2 className="h-3.5 w-3.5" /> {busy ? "…" : "Share"}
    </button>
  );
};

export const StreakMeter = ({ streak, best, game }) => {
  const hot = streak >= STREAK_GOAL;
  return (
    <div className="flex items-center gap-3" data-testid="demo-streak">
      <div className="text-right">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">Win streak</p>
        <p className="font-num text-2xl font-bold text-white"><span data-testid="demo-streak-count">{streak}</span><span className="ml-1 text-xs font-normal text-slate-500">best {best}</span></p>
      </div>
      <AnimatePresence>
        {hot && (
          <motion.div key="hot" initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} exit={{ scale: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 15 }} className="flex items-center gap-2">
            <span data-testid="demo-streak-badge" className="flex items-center gap-1 rounded-full bg-gradient-to-r from-orange-500 to-amber-400 px-3 py-1 text-xs font-bold text-black shadow-lg shadow-orange-500/40">
              <Flame className="h-4 w-4 animate-pulse" /> Hot Streak
            </span>
            <ShareStreak streak={streak} game={game} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
