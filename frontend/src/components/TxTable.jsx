import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TX_TYPES, fmtDate, inr, signedInr } from "@/lib/format";
import { EmptyState } from "@/components/StatCard";

export const TxTable = ({ rows, showUser = false, testId = "tx-table" }) => {
  if (!rows?.length) return <EmptyState text="No transactions found." testId={`${testId}-empty`} />;
  return (
    <div className="overflow-x-auto rounded-xl border border-white/5" data-testid={testId}>
      <Table>
        <TableHeader>
          <TableRow className="border-white/5 hover:bg-transparent">
            <TableHead className="text-slate-500">Date</TableHead>
            {showUser && <TableHead className="text-slate-500">User</TableHead>}
            <TableHead className="text-slate-500">Type</TableHead>
            <TableHead className="text-slate-500">Description</TableHead>
            <TableHead className="text-right text-slate-500">Credits</TableHead>
            <TableHead className="text-right text-slate-500">Balance</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((t) => (
            <TableRow key={t.id} className="border-white/5 hover:bg-purple-500/[0.04]" data-testid={`tx-row-${t.id}`}>
              <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(t.created_at)}</TableCell>
              {showUser && <TableCell className="text-xs text-slate-300">{t.user_email}</TableCell>}
              <TableCell className="text-xs font-semibold text-slate-200">{TX_TYPES[t.type] || t.type}</TableCell>
              <TableCell className="max-w-[280px] truncate text-xs text-slate-400" title={t.description}>
                {t.description} <span className="font-num text-purple-300/70">· {t.reference}</span>
              </TableCell>
              <TableCell className={`text-right font-num text-sm font-semibold ${t.amount < 0 ? "text-red-300" : "text-emerald-300"}`}>
                {signedInr(t.amount)}
              </TableCell>
              <TableCell className="text-right font-num text-xs text-slate-400">{inr(t.balance_after)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
