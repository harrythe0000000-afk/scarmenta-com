import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useFetch } from "@/lib/hooks";
import { fmtDate, signedUsd } from "@/lib/format";

const inr = (n) => `₹${Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export default function LiveHistory() {
  const { data } = useFetch("/live/my-rounds");
  return (
    <>
      <Link to="/app/live-casino" className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white" data-testid="live-history-back"><ArrowLeft className="h-4 w-4" /> Live casino</Link>
      <PageHeader eyebrow="Live casino" title="My game history" desc="Every live round you played: what you bet, what you won and how your credit balance changed." />
      {data && data.length === 0 ? (
        <EmptyState testId="live-history-empty" text="No rounds yet. Your live casino rounds will show here after you play." />
      ) : (
        <div className="card-lux overflow-x-auto" data-testid="live-history-table">
          <Table>
            <TableHeader>
              <TableRow className="border-purple-500/10">
                {["Time", "Game", "Bet", "Won", "Result", "Balance change"].map((h) => <TableHead key={h} className="whitespace-nowrap">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {!data && <TableRow><TableCell colSpan={6} className="text-center text-sm text-slate-500">Loading…</TableCell></TableRow>}
              {data?.map((r) => (
                <TableRow key={r.game_round} className="border-purple-500/10" data-testid={`live-history-row-${r.game_round}`}>
                  <TableCell className="whitespace-nowrap text-xs text-slate-400">{fmtDate(r.updated_at)}</TableCell>
                  <TableCell className="text-sm text-white">{r.game_name || r.game_uid}<p className="text-[10px] text-slate-500">{r.provider}</p></TableCell>
                  <TableCell className="font-num">{inr(r.bet_inr)}</TableCell>
                  <TableCell className="font-num">{inr(r.win_inr)}</TableCell>
                  <TableCell className={`font-num ${r.net_inr > 0 ? "text-emerald-300" : r.net_inr < 0 ? "text-red-300" : "text-slate-400"}`}>{r.net_inr > 0 ? "+" : r.net_inr < 0 ? "−" : ""}{inr(Math.abs(r.net_inr))}</TableCell>
                  <TableCell className={`font-num ${r.applied_usd >= 0 ? "text-emerald-300" : "text-red-300"}`}>{signedUsd(r.applied_usd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
