import { Trophy } from "lucide-react";
import { useFetch } from "@/lib/hooks";

const inr = (n) => `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export const BigWinFeed = () => {
  const { data } = useFetch("/live/big-wins");
  if (!data?.length) return null;
  const items = [...data, ...data];
  return (
    <div className="mb-6 overflow-hidden rounded-full border border-amber-400/20 bg-amber-400/5 py-2" data-testid="big-win-feed">
      <div className="flex w-max animate-[marquee_40s_linear_infinite] gap-8 px-4 hover:[animation-play-state:paused]">
        {items.map((w, i) => (
          <span key={i} className="flex items-center gap-2 whitespace-nowrap text-sm text-slate-300" data-testid={i < data.length ? `big-win-${i}` : undefined}>
            <Trophy className="h-4 w-4 text-amber-300" /> <b className="text-white">{w.player}</b> won <b className="font-num text-amber-300">{inr(w.net_inr)}</b> on {w.game}
          </span>
        ))}
      </div>
    </div>
  );
};
