import { Gift, MousePointerClick, UserPlus, Wallet } from "lucide-react";
import { useFetch } from "@/lib/hooks";
import { usd as fmtMoney } from "@/lib/format";

export const ShareStats = () => {
  const { data } = useFetch("/share/me");
  if (!data) return null;
  const items = [
    ["Opened your link", data.visits, MousePointerClick, "share-stat-visits"],
    ["Signed up", data.signups, UserPlus, "share-stat-signups"],
    ["Made a deposit", data.deposited, Wallet, "share-stat-deposited"],
    ["Bonus earned", fmtMoney(data.earned), Gift, "share-stat-earned"],
  ];
  return (
    <div className="card-lux p-5" data-testid="share-stats">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="label-eyebrow">Friends from your shared images</p>
        {data.bonus_amount > 0 && <p className="text-xs text-slate-400" data-testid="share-bonus-info">Get {fmtMoney(data.bonus_amount)} bonus credits for each friend who joins from your image and makes a first deposit.</p>}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map(([l, v, Icon, id]) => (
          <div key={id} className="rounded-xl border border-purple-500/15 bg-black/30 p-3">
            <Icon className="h-4 w-4 text-purple-300" />
            <p className="mt-2 font-num text-xl font-semibold text-white" data-testid={id}>{v}</p>
            <p className="text-[11px] text-slate-500">{l}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
