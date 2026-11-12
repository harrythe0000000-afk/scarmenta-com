import { usd } from "@/lib/format";

export const Portfolio = ({ stats }) => {
  const rate = stats.rounds ? Math.round((stats.wins / stats.rounds) * 100) : 0;
  const items = [
    ["Profit / Loss", `${stats.pnl >= 0 ? "+" : "−"}${usd(Math.abs(stats.pnl))}`, stats.pnl >= 0 ? "text-emerald-300" : "text-red-300", "demo-portfolio-pnl"],
    ["Rounds", stats.rounds, "text-white", "demo-portfolio-rounds"],
    ["Wins", stats.wins, "text-emerald-300", "demo-portfolio-wins"],
    ["Losses", stats.losses, "text-red-300", "demo-portfolio-losses"],
    ["Win rate", `${rate}%`, "text-purple-300", "demo-portfolio-rate"],
    ["Biggest win", usd(stats.bestWin), "text-amber-300", "demo-portfolio-best"],
  ];
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="demo-portfolio">
      {items.map(([l, v, c, id]) => (
        <div key={id} className="card-lux px-4 py-3">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">{l}</p>
          <p className={`mt-1 font-num text-xl font-bold ${c}`} data-testid={id}>{v}</p>
        </div>
      ))}
    </div>
  );
};
