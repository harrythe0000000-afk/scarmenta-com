import { AnimatePresence, motion } from "framer-motion";
import { Flame } from "lucide-react";

export const STREAK_GOAL = 3;

export const StreakMeter = ({ streak, best }) => {
  const hot = streak >= STREAK_GOAL;
  return (
    <div className="flex items-center gap-3" data-testid="demo-streak">
      <div className="text-right">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">Win streak</p>
        <p className="font-num text-2xl font-bold text-white"><span data-testid="demo-streak-count">{streak}</span><span className="ml-1 text-xs font-normal text-slate-500">best {best}</span></p>
      </div>
      <AnimatePresence>
        {hot && (
          <motion.span key="hot" initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} exit={{ scale: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 15 }} data-testid="demo-streak-badge"
            className="flex items-center gap-1 rounded-full bg-gradient-to-r from-orange-500 to-amber-400 px-3 py-1 text-xs font-bold text-black shadow-lg shadow-orange-500/40">
            <Flame className="h-4 w-4 animate-pulse" /> Hot Streak
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
};
