import { useState } from "react";
import { toast } from "sonner";
import { Gift } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const DemoShareStats = () => {
  const { data } = useFetch("/admin/demo-shares");
  if (!data) return null;
  const items = [["Link opens", data.visits, "demo-shares-visits"], ["Joined", data.signups, "demo-shares-signups"],
    ["Deposited", data.deposited, "demo-shares-deposited"], ["Deposits total", usd(data.deposit_total), "demo-shares-total"]];
  return (
    <div className="card-lux mb-6 p-6" data-testid="demo-shares-card">
      <p className="label-eyebrow">Demo profit images (all time)</p>
      <p className="mt-1 text-xs text-slate-500">People who opened a link from a Scarmenta vs Others profit image shared on WhatsApp.</p>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {items.map(([l, v, id]) => (
          <div key={id}>
            <p className="text-[11px] uppercase tracking-wider text-slate-500">{l}</p>
            <p className="mt-1 font-num text-2xl font-bold text-white" data-testid={id}>{v}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const RewardBox = ({ top, lastRun, onDone }) => {
  const next = lastRun ? new Date(new Date(lastRun.created_at).getTime() + 7 * 864e5) : null;
  const locked = next && next > new Date();
  const [amounts, setAmounts] = useState(["25", "15", "10"]);
  const winners = top.slice(0, 3);
  const pay = async () => {
    try {
      const { data } = await api.post("/admin/sharers/reward", { amounts: winners.map((_, i) => Number(amounts[i]) || 0) });
      toast.success(`Paid ${usd(data.total)} to ${data.winners.length} top sharers`);
      onDone();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <div className="card-lux space-y-4 p-6" data-testid="sharers-reward-box">
      <p className="label-eyebrow">Reward top 3</p>
      {winners.length === 0 ? <p className="text-sm text-slate-500">No sharers to reward yet.</p> : winners.map((w, i) => (
        <div key={w.user_id} className="flex items-center gap-3">
          <span className="w-8 font-num text-purple-300">#{w.rank}</span>
          <span className="min-w-0 flex-1 truncate text-sm text-white">{w.name}</span>
          <div className="relative w-28">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">$</span>
            <Input type="number" min="0" step="0.01" value={amounts[i]} data-testid={`sharers-amount-${i + 1}`}
              onChange={(e) => setAmounts(amounts.map((a, j) => (j === i ? e.target.value : a)))} className="border-purple-500/20 bg-black/40 pl-6 font-num" />
          </div>
        </div>
      ))}
      {locked && <p className="text-xs text-amber-300" data-testid="sharers-next-reward">Next reward available on {fmtDate(next.toISOString())}</p>}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button disabled={!winners.length || locked} data-testid="sharers-reward-button" className="w-full rounded-full bg-purple-600 hover:bg-purple-500"><Gift className="mr-2 h-4 w-4" /> Send bonus credits</Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="border-purple-500/20 bg-[#0b0816] text-slate-200">
          <AlertDialogHeader>
            <AlertDialogTitle>Send bonus credits to the top {winners.length}?</AlertDialogTitle>
            <AlertDialogDescription>Credits are added to their balances right away. You can do this once every 7 days.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-transparent">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={pay} data-testid="sharers-reward-confirm" className="bg-purple-600 hover:bg-purple-500">Yes, send</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

const Runs = ({ runs }) => (
  <div className="card-lux p-6" data-testid="sharers-runs">
    <p className="label-eyebrow mb-3">Past rewards</p>
    {runs.length === 0 ? <p className="text-sm text-slate-500">No rewards sent yet.</p> : runs.map((r) => (
      <div key={r.id} className="border-b border-purple-500/10 py-2 text-sm last:border-0">
        <p className="text-slate-300">{fmtDate(r.created_at)} · <span className="font-num text-white">{usd(r.total)}</span></p>
        <p className="text-xs text-slate-500">{r.winners.map((w) => `#${w.rank} ${w.name} ${usd(w.amount)}`).join(" · ")}</p>
      </div>
    ))}
  </div>
);

export default function TopSharers() {
  const { data, reload } = useFetch("/admin/sharers");
  return (
    <>
      <PageHeader eyebrow="Growth" title="Top sharers" desc="Players whose shared calculator images brought the most friend signups in the last 7 days." />
      <DemoShareStats />
      {data && (
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="card-lux overflow-hidden" data-testid="sharers-admin-table">
            {data.top.length === 0 ? <div className="p-6"><EmptyState text="No friend signups from shared images in the last 7 days." testId="sharers-admin-empty" /></div> : (
              <Table>
                <TableHeader><TableRow className="border-purple-500/10"><TableHead>Rank</TableHead><TableHead>Player</TableHead><TableHead className="text-right">Friends joined</TableHead></TableRow></TableHeader>
                <TableBody>
                  {data.top.map((r) => (
                    <TableRow key={r.user_id} className="border-purple-500/10" data-testid={`sharers-admin-row-${r.rank}`}>
                      <TableCell className="font-num text-purple-300">#{r.rank}</TableCell>
                      <TableCell><p className="text-white">{r.name}</p><p className="text-xs text-slate-500">{r.email}</p></TableCell>
                      <TableCell className="text-right font-num text-white">{r.friends}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
          <div className="space-y-6">
            <RewardBox top={data.top} lastRun={data.runs[0]} onDone={reload} />
            <Runs runs={data.runs} />
          </div>
        </div>
      )}
    </>
  );
}
