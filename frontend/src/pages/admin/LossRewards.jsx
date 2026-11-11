import { useState } from "react";
import { toast } from "sonner";
import { Award, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const H = ({ cols }) => (
  <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{cols.map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
);

export default function AdminLossRewards() {
  const { data: p, reload } = useFetch("/admin/loss-rewards/preview");
  const { data: runs, reload: reloadRuns } = useFetch("/admin/loss-rewards/runs");
  const [busy, setBusy] = useState(false);
  const pay = async () => {
    if (!window.confirm(`Pay ${usd(p.total_reward)} in loss rewards to ${p.rows.length} player(s)?`)) return;
    setBusy(true);
    try {
      const { data } = await api.post("/admin/loss-rewards/run", { start: p.start, end: p.end });
      toast.success(`Paid ${usd(data.total_reward)} to ${data.players} player(s)`);
      reload();
      reloadRuns();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader eyebrow="Weekly loss rewards" title="Loss-back payouts"
        desc="Each week, give players a % of their net game loss (bets − refunds − wins) back as credits. The period starts where the last payout ended, so nobody is paid twice."
        action={<Button data-testid="loss-reward-pay-button" disabled={busy || !p?.rows?.length} onClick={pay} className="rounded-full bg-gradient-to-r from-amber-500 to-fuchsia-600 px-6">
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Award className="mr-2 h-4 w-4" />} Pay rewards now</Button>} />
      {p && (
        <div className="card-lux mb-6 grid gap-4 p-6 sm:grid-cols-4" data-testid="loss-reward-preview-summary">
          <div><p className="text-xs text-slate-500">Period</p><p className="font-num text-xs text-white">{fmtDate(p.start)} → {fmtDate(p.end)}</p></div>
          <div><p className="text-xs text-slate-500">Reward rate</p><p className="font-num text-xl text-white">{p.percent}%</p></div>
          <div><p className="text-xs text-slate-500">Players eligible</p><p className="font-num text-xl text-white">{p.rows.length}</p></div>
          <div><p className="text-xs text-slate-500">Total to pay</p><p className="font-num text-xl text-amber-300" data-testid="loss-reward-preview-total">{usd(p.total_reward)}</p></div>
        </div>
      )}
      {!p?.rows?.length ? <EmptyState text="No player has a net loss in this period yet." testId="loss-reward-preview-empty" /> : (
        <div className="card-lux overflow-x-auto p-2" data-testid="loss-reward-preview-table">
          <Table>
            <H cols={["Player", "Bets", "Wins", "Refunds", "Net loss", "Reward"]} />
            <TableBody>
              {p.rows.map((r) => (
                <TableRow key={r.user_id} className="border-white/5">
                  <TableCell><p className="text-sm text-white">{r.name}</p><p className="text-xs text-slate-500">{r.email}</p></TableCell>
                  <TableCell className="font-num text-sm">{usd(r.bets)}</TableCell>
                  <TableCell className="font-num text-sm text-emerald-300">{usd(r.wins)}</TableCell>
                  <TableCell className="font-num text-sm text-slate-400">{usd(r.rollbacks)}</TableCell>
                  <TableCell className="font-num text-sm text-red-300">{usd(r.net_loss)}</TableCell>
                  <TableCell className="font-num text-sm font-semibold text-amber-300">{usd(r.reward)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <section className="mt-10">
        <p className="label-eyebrow mb-4">Past payouts</p>
        {!runs?.length ? <EmptyState text="No payouts yet." testId="loss-reward-runs-empty" /> : (
          <div className="card-lux overflow-x-auto p-2" data-testid="loss-reward-runs-table">
            <Table>
              <H cols={["Paid on", "Period", "Rate", "Players", "Total paid", "By"]} />
              <TableBody>
                {runs.map((r) => (
                  <TableRow key={r.id} className="border-white/5">
                    <TableCell className="font-num text-xs text-slate-400">{fmtDate(r.created_at)}</TableCell>
                    <TableCell className="font-num text-xs text-slate-300">{fmtDate(r.period_start)} → {fmtDate(r.period_end)}</TableCell>
                    <TableCell className="font-num text-sm">{r.percent}%</TableCell>
                    <TableCell className="font-num text-sm">{r.players}</TableCell>
                    <TableCell className="font-num text-sm text-amber-300">{usd(r.total_reward)}</TableCell>
                    <TableCell className="text-xs text-slate-400">{r.paid_by}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </>
  );
}
