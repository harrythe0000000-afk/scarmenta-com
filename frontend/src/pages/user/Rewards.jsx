import { Award, TrendingDown, TrendingUp } from "lucide-react";
import { EmptyState, PageHeader, StatCard } from "@/components/StatCard";
import { TxTable } from "@/components/TxTable";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

export default function UserRewards() {
  const { data: r } = useFetch("/rewards/loss/me");
  if (!r) return null;
  return (
    <>
      <PageHeader eyebrow="Loss rewards" title="Weekly loss-back rewards"
        desc={`Every week you get ${r.percent}% of your net game loss back as credits. Net loss = bets − refunds − wins.`} />
      <div className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-900/20 to-[#05040A] p-8 fade-up" data-testid="loss-reward-current-card">
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-amber-500/10 blur-3xl" />
        <p className="relative text-xs uppercase tracking-[0.2em] text-amber-300">This week so far · since {fmtDate(r.period_start)}</p>
        <p className="relative mt-4 text-sm text-slate-400">Estimated reward</p>
        <p className="relative font-num text-5xl font-semibold text-white" data-testid="loss-reward-estimate">{usd(r.estimated_reward)}</p>
        <p className="relative mt-2 text-xs text-slate-500">Paid by the platform at the end of the week. The final amount is calculated at payout.</p>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-4">
        <StatCard label="Bets this week" value={usd(r.bets)} icon={TrendingDown} testId="loss-stat-bets" />
        <StatCard label="Wins this week" value={usd(r.wins)} icon={TrendingUp} tone="emerald" testId="loss-stat-wins" />
        <StatCard label="Net loss this week" value={usd(Math.max(r.net_loss, 0))} icon={TrendingDown} tone="red" testId="loss-stat-net" />
        <StatCard label="Total rewards received" value={usd(r.total_received)} icon={Award} tone="amber" testId="loss-stat-total" />
      </div>
      <section className="mt-10">
        <p className="label-eyebrow mb-4">Reward history</p>
        {r.history.length ? <TxTable rows={r.history} testId="loss-reward-history" /> : <EmptyState text="No loss rewards yet." testId="loss-reward-history-empty" />}
      </section>
    </>
  );
}
