import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DepositDialog } from "@/components/DepositDialog";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfig, useFetch } from "@/lib/hooks";
import { fmtDate, inr, methodLabel } from "@/lib/format";

export default function UserDeposits() {
  const config = useConfig();
  const { data, reload } = useFetch("/deposits");
  const [open, setOpen] = useState(false);
  return (
    <>
      <PageHeader eyebrow="Funding" title="Deposit history" desc="Every package purchase with the credits it allocated."
        action={<Button data-testid="deposits-new-button" onClick={() => setOpen(true)} className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6"><Plus className="mr-2 h-4 w-4" /> New deposit</Button>} />
      {!data?.length ? (
        <EmptyState text="No deposits yet. Purchase your first credit package to get started." testId="deposits-empty" />
      ) : (
        <div className="card-lux overflow-x-auto p-2" data-testid="deposits-table">
          <Table>
            <TableHeader>
              <TableRow className="border-white/5 hover:bg-transparent">
                {["Reference", "Date", "Method", "Cash paid", "Credits", "Status"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id} className="border-white/5 hover:bg-purple-500/[0.04]" data-testid={`deposit-row-${d.reference}`}>
                  <TableCell className="font-num text-xs text-purple-300">{d.reference}</TableCell>
                  <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(d.created_at)}</TableCell>
                  <TableCell className="text-xs text-slate-300">{methodLabel(d.method)}</TableCell>
                  <TableCell className="font-num text-sm font-semibold text-white">{inr(d.amount)}</TableCell>
                  <TableCell className="font-num text-sm font-semibold text-purple-300">{inr(d.promo_credit)}</TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} testId={`deposit-status-${d.reference}`} />
                    {d.reject_reason && <p className="mt-1 text-[11px] text-red-300/80">{d.reject_reason}</p>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <DepositDialog open={open} onOpenChange={setOpen} config={config} onDone={reload} />
    </>
  );
}
