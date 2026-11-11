import { useState } from "react";
import { Coins, Dices, TrendingDown, TrendingUp } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader, StatCard } from "@/components/StatCard";
import { useFetch } from "@/lib/hooks";
import { TX_TYPES, fmtDate, usd } from "@/lib/format";

export default function AdminGameActivity() {
  const { data: stats } = useFetch("/admin/game-stats");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const { data: rows } = useFetch(`/admin/game-transactions?${new URLSearchParams(Object.entries({ type, q }).filter(([, v]) => v))}`);
  const t = stats?.totals || {};
  return (
    <>
      <PageHeader eyebrow="Game activity" title="Bets & wins" desc="Every bet, win and refund reported by providers through the wallet API. GGR = bets − refunds − wins." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total bets" value={usd(t.bets)} icon={TrendingDown} testId="game-stat-bets" />
        <StatCard label="Total wins paid" value={usd(t.wins)} icon={TrendingUp} tone="emerald" testId="game-stat-wins" />
        <StatCard label="Gross gaming revenue" value={usd(t.ggr)} icon={Coins} tone="amber" testId="game-stat-ggr" />
        <StatCard label="Active sessions" value={stats?.active_sessions ?? 0} icon={Dices} tone="red" testId="game-stat-sessions" />
      </div>
      {stats?.providers?.length > 0 && (
        <div className="mt-6 card-lux overflow-x-auto p-2" data-testid="game-provider-stats-table">
          <Table>
            <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{["Provider", "Bets", "Bet count", "Wins", "Refunds", "GGR"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {stats.providers.map((p) => (
                <TableRow key={p.provider_id} className="border-white/5">
                  <TableCell className="text-sm text-white">{p.provider_name}</TableCell>
                  <TableCell className="font-num text-sm">{usd(p.bets)}</TableCell>
                  <TableCell className="font-num text-sm text-slate-400">{p.bet_count}</TableCell>
                  <TableCell className="font-num text-sm text-emerald-300">{usd(p.wins)}</TableCell>
                  <TableCell className="font-num text-sm text-slate-400">{usd(p.rollbacks)}</TableCell>
                  <TableCell className="font-num text-sm text-amber-300">{usd(p.ggr)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <div className="mt-8 mb-4 flex flex-wrap gap-3">
        <Input data-testid="game-tx-search-input" placeholder="Player email, round or tx id" value={q} onChange={(e) => setQ(e.target.value)} className="w-64 border-purple-500/20 bg-black/40" />
        <Select value={type || "all"} onValueChange={(v) => setType(v === "all" ? "" : v)}>
          <SelectTrigger data-testid="game-tx-type-filter" className="w-40 border-purple-500/20 bg-black/40"><SelectValue /></SelectTrigger>
          <SelectContent>{[["all", "All types"], ["bet", "Bets"], ["win", "Wins"], ["rollback", "Refunds"]].map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {!rows?.length ? <EmptyState text="No game transactions yet." testId="game-tx-empty" /> : (
        <div className="card-lux overflow-x-auto p-2" data-testid="game-tx-table">
          <Table>
            <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{["Date", "Player", "Provider", "Round / Tx", "Type", "Amount", "Status", "Balance"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {rows.map((g) => (
                <TableRow key={g.id} className="border-white/5">
                  <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(g.created_at)}</TableCell>
                  <TableCell className="text-xs text-slate-300">{g.user_email}</TableCell>
                  <TableCell className="text-xs text-slate-300">{g.provider_name}</TableCell>
                  <TableCell className="font-num text-[11px] text-purple-300">{g.round_id} / {g.external_tx_id}</TableCell>
                  <TableCell className="text-xs text-white">{TX_TYPES[g.type] || g.type}</TableCell>
                  <TableCell className="font-num text-sm">{usd(g.amount)}</TableCell>
                  <TableCell className={`text-xs ${g.status === "ok" ? "text-emerald-300" : "text-red-300"}`}>{g.status.replace("_", " ")}</TableCell>
                  <TableCell className="font-num text-xs text-slate-400">{usd(g.balance_after)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
