import { Crown, Medal, Trophy } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { useFetch } from "@/lib/hooks";
import { usd } from "@/lib/format";

const RANK_STYLE = {
  1: "border-amber-400/40 bg-amber-400/[0.07] text-amber-300",
  2: "border-slate-300/30 bg-slate-300/[0.05] text-slate-200",
  3: "border-orange-500/30 bg-orange-500/[0.05] text-orange-300",
};
const fmtDay = (iso) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });

const RankIcon = ({ rank }) => {
  if (rank === 1) return <Crown className="h-5 w-5" />;
  if (rank <= 3) return <Medal className="h-5 w-5" />;
  return <span className="font-num text-sm">{rank}</span>;
};

const Row = ({ r }) => (
  <div data-testid={`leaderboard-row-${r.rank}`}
    className={`flex items-center gap-4 rounded-2xl border px-5 py-4 transition-transform hover:-translate-y-0.5 ${RANK_STYLE[r.rank] || "border-purple-500/15 bg-white/[0.02] text-slate-400"} ${r.is_me ? "ring-2 ring-purple-500/60" : ""}`}>
    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-black/40"><RankIcon rank={r.rank} /></div>
    <p className="flex-1 font-semibold text-white">{r.name}{r.is_me && <span className="ml-2 rounded-full bg-purple-600 px-2 py-0.5 text-[10px] uppercase tracking-wider">You</span>}</p>
    <p className="font-num text-lg font-semibold text-white" data-testid={`leaderboard-loss-${r.rank}`}>{usd(r.net_loss)}</p>
  </div>
);

const MyRank = ({ me, pct }) => (
  <div className="card-lux p-6" data-testid="leaderboard-my-rank">
    <p className="label-eyebrow">Your week</p>
    {me ? (
      <>
        <p className="mt-3 font-num text-4xl font-bold text-white" data-testid="leaderboard-my-position">#{me.rank}</p>
        <p className="mt-1 text-sm text-slate-400">Net game loss <span className="font-num text-white">{usd(me.net_loss)}</span></p>
        <p className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-200" data-testid="leaderboard-my-reward">
          Estimated loss reward at {pct}%: <span className="font-num font-semibold">{usd(me.reward)}</span>
        </p>
      </>
    ) : <p className="mt-3 text-sm text-slate-400" data-testid="leaderboard-not-ranked">No game losses in the last 7 days, so you're not on the board yet.</p>}
  </div>
);

export default function Leaderboard() {
  const { data } = useFetch("/leaderboard/weekly");
  return (
    <>
      <PageHeader eyebrow="Weekly leaderboard" title="Top 10 this week" desc="Players with the highest net game loss over the last 7 days, across all of Scarmenta. Names are partly hidden for privacy." />
      {data && (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-3" data-testid="leaderboard-list">
            <p className="text-xs text-slate-500" data-testid="leaderboard-period">{fmtDay(data.start)} – {fmtDay(data.end)} · {data.players} {data.players === 1 ? "player" : "players"} ranked · updates live</p>
            {data.top.length === 0 ? <EmptyState text="No game activity in the last 7 days yet." testId="leaderboard-empty" /> : data.top.map((r) => <Row key={r.rank} r={r} />)}
          </div>
          <div className="space-y-4">
            <MyRank me={data.me} pct={data.loss_reward_percent} />
            <div className="card-lux flex gap-3 p-5 text-xs text-slate-400">
              <Trophy className="h-4 w-4 shrink-0 text-amber-300" />
              Net loss = bets − wins − refunded bets on partner games. Loss rewards are paid weekly by Scarmenta. Please play responsibly.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
