import { toast } from "sonner";
import { Banknote, Copy, Handshake, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader, StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const T = ({ cols, children, testId }) => (
  <div className="card-lux overflow-x-auto p-2" data-testid={testId}>
    <Table>
      <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{cols.map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
      <TableBody>{children}</TableBody>
    </Table>
  </div>
);

export default function AgentDashboard() {
  const { data: a } = useFetch("/agent/me");
  if (!a) return null;
  const copy = (v) => { navigator.clipboard.writeText(v).catch(() => {}); toast.success("Copied"); };
  return (
    <>
      <PageHeader eyebrow="Agent portal" title={`Welcome, ${a.name.split(" ")[0]}`} desc={`You earn ${a.commission_percent}% commission on every approved deposit by players who sign up with your link.`} />
      <div className="relative overflow-hidden rounded-2xl border border-purple-500/40 bg-gradient-to-br from-purple-900/40 to-[#05040A] p-8 glow-violet" data-testid="agent-link-card">
        <p className="text-xs uppercase tracking-[0.2em] text-[#F2B94B]">Your agent code</p>
        <p className="mt-2 font-num text-4xl font-bold tracking-widest text-white" data-testid="agent-code-value">{a.code}</p>
        <p className="mt-4 truncate rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-num text-xs text-slate-400" data-testid="agent-link-value">{a.link}</p>
        <div className="mt-4 flex gap-2">
          <Button data-testid="agent-copy-link-button" onClick={() => copy(a.link)} variant="outline" className="rounded-full border-purple-500/40 bg-transparent hover:bg-purple-500/10"><Copy className="mr-2 h-4 w-4" /> Copy sign-up link</Button>
          <Button data-testid="agent-copy-code-button" onClick={() => copy(a.code)} variant="outline" className="rounded-full border-purple-500/40 bg-transparent hover:bg-purple-500/10"><Copy className="mr-2 h-4 w-4" /> Copy code</Button>
        </div>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Players" value={a.players} icon={Users} testId="agent-stat-players" />
        <StatCard label="Deposit volume" value={usd(a.volume)} icon={Banknote} tone="emerald" testId="agent-stat-volume" />
        <StatCard label="Commission earned" value={usd(a.earned)} icon={Handshake} testId="agent-stat-earned" />
        <StatCard label="Unpaid" value={usd(a.unpaid)} icon={Wallet} tone="amber" testId="agent-stat-unpaid" />
        <StatCard label="Paid out" value={usd(a.paid)} icon={Wallet} tone="emerald" testId="agent-stat-paid" />
      </div>
      <section className="mt-10 grid gap-6 lg:grid-cols-2">
        <div>
          <p className="label-eyebrow mb-4">Your players</p>
          {!a.players_list.length ? <EmptyState text="No players yet. Share your link to get started." testId="agent-players-empty" /> : (
            <T cols={["Player", "Joined", "Deposited"]} testId="agent-players-table">
              {a.players_list.map((p, i) => (
                <TableRow key={i} className="border-white/5"><TableCell className="text-sm text-white">{p.name}</TableCell>
                  <TableCell className="font-num text-xs text-slate-400">{fmtDate(p.joined_at)}</TableCell>
                  <TableCell className="font-num text-sm text-emerald-300">{usd(p.deposited)}</TableCell></TableRow>
              ))}
            </T>
          )}
        </div>
        <div>
          <p className="label-eyebrow mb-4">Payouts</p>
          {!a.payouts.length ? <EmptyState text="No payouts yet." testId="agent-payouts-empty" /> : (
            <T cols={["Date", "Commissions", "Amount", "Note"]} testId="agent-payouts-table">
              {a.payouts.map((p) => (
                <TableRow key={p.id} className="border-white/5"><TableCell className="font-num text-xs text-slate-400">{fmtDate(p.created_at)}</TableCell>
                  <TableCell className="font-num text-sm">{p.count}</TableCell>
                  <TableCell className="font-num text-sm text-emerald-300">{usd(p.amount)}</TableCell>
                  <TableCell className="text-xs text-slate-400">{p.note || "—"}</TableCell></TableRow>
              ))}
            </T>
          )}
        </div>
      </section>
      <section className="mt-10">
        <p className="label-eyebrow mb-4">Commission history</p>
        {!a.commissions.length ? <EmptyState text="No commission yet." testId="agent-commissions-empty" /> : (
          <T cols={["Date", "Player", "Deposit", "Rate", "Commission", "Status"]} testId="agent-commissions-table">
            {a.commissions.map((c) => (
              <TableRow key={c.id} className="border-white/5"><TableCell className="font-num text-xs text-slate-400">{fmtDate(c.created_at)}</TableCell>
                <TableCell className="text-sm text-white">{c.player_name}</TableCell>
                <TableCell className="font-num text-sm">{usd(c.deposit_amount)} <span className="text-[11px] text-purple-300/70">{c.deposit_ref}</span></TableCell>
                <TableCell className="font-num text-sm">{c.percent}%</TableCell>
                <TableCell className="font-num text-sm font-semibold text-[#F2B94B]">{usd(c.amount)}</TableCell>
                <TableCell><StatusBadge status={c.status === "paid" ? "approved" : "pending"} /></TableCell></TableRow>
            ))}
          </T>
        )}
      </section>
    </>
  );
}
