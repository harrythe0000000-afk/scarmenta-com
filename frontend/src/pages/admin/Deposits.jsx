import { useState } from "react";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate, inr, methodLabel } from "@/lib/format";

const Risk = ({ score, flags }) => {
  const tone = score >= 50 ? "text-red-300 bg-red-500/10" : score >= 30 ? "text-amber-300 bg-amber-500/10" : "text-emerald-300 bg-emerald-500/10";
  return (
    <div>
      <span className={`rounded-md px-2 py-0.5 font-num text-xs font-semibold ${tone}`}>{score}</span>
      {flags?.map((f) => <p key={f} className="mt-1 text-[10px] uppercase tracking-wider text-red-300/80">{f.replace("_", " ")}</p>)}
    </div>
  );
};

export default function AdminDeposits() {
  const [status, setStatus] = useState("pending");
  const { data, reload } = useFetch(`/admin/deposits?status=${status}`);
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");
  const [busyId, setBusyId] = useState(null);

  const approve = async (d) => {
    setBusyId(d.id);
    try {
      await api.post(`/admin/deposits/${d.id}/approve`);
      toast.success(`${d.reference} approved — credits allocated`);
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusyId(null);
    }
  };
  const reject = async () => {
    try {
      await api.post(`/admin/deposits/${rejecting.id}/reject`, { reason });
      toast.success(`${rejecting.reference} rejected`);
      setRejecting(null);
      setReason("");
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  return (
    <>
      <PageHeader eyebrow="Deposit monitoring" title="Approval queue" desc="Approving a deposit credits the real wallet (net of fee) and allocates promotional credits." />
      <Tabs value={status} onValueChange={setStatus} className="mb-5">
        <TabsList className="bg-white/[0.03]">
          {["pending", "approved", "rejected", "all"].map((s) => <TabsTrigger key={s} value={s} data-testid={`admin-deposits-tab-${s}`} className="capitalize data-[state=active]:bg-purple-600 data-[state=active]:text-white">{s}</TabsTrigger>)}
        </TabsList>
      </Tabs>
      {!data?.length ? <EmptyState text={`No ${status} deposits.`} testId="admin-deposits-empty" /> : (
        <div className="card-lux overflow-x-auto p-2" data-testid="admin-deposits-table">
          <Table>
            <TableHeader>
              <TableRow className="border-white/5 hover:bg-transparent">
                {["Reference", "Player", "Date", "Method", "Amount", "Fee / Real / Promo", "Risk", "Status", ""].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id} className="border-white/5 hover:bg-purple-500/[0.04]" data-testid={`admin-deposit-row-${d.reference}`}>
                  <TableCell className="font-num text-xs text-purple-300">{d.reference}</TableCell>
                  <TableCell><p className="text-sm text-white">{d.user_name}</p><p className="text-xs text-slate-500">{d.user_email}</p></TableCell>
                  <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(d.created_at)}</TableCell>
                  <TableCell className="text-xs text-slate-300">{methodLabel(d.method)}</TableCell>
                  <TableCell className="font-num text-sm font-semibold text-white">{inr(d.amount)}</TableCell>
                  <TableCell className="whitespace-nowrap font-num text-xs">
                    <span className="text-slate-400">{inr(d.service_fee)}</span> / <span className="text-emerald-300">{inr(d.net_real_credit)}</span> / <span className="text-purple-300">{inr(d.promo_credit)}</span>
                  </TableCell>
                  <TableCell><Risk score={d.risk_score} flags={d.fraud_flags} /></TableCell>
                  <TableCell><StatusBadge status={d.status} /></TableCell>
                  <TableCell>
                    {d.status === "pending" && (
                      <div className="flex gap-2">
                        <Button size="sm" disabled={busyId === d.id} onClick={() => approve(d)} data-testid={`admin-approve-deposit-btn-${d.reference}`} className="rounded-full bg-emerald-600 hover:bg-emerald-500"><Check className="h-4 w-4" /></Button>
                        <Button size="sm" variant="outline" onClick={() => setRejecting(d)} data-testid={`admin-reject-deposit-btn-${d.reference}`} className="rounded-full border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10"><X className="h-4 w-4" /></Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <Dialog open={!!rejecting} onOpenChange={(v) => !v && setRejecting(null)}>
        <DialogContent className="border-purple-500/30 bg-[#0b0817]" data-testid="reject-dialog">
          <DialogHeader><DialogTitle className="text-white">Reject {rejecting?.reference}</DialogTitle></DialogHeader>
          <Input data-testid="reject-reason-input" placeholder="Reason (shown to player)" value={reason} onChange={(e) => setReason(e.target.value)} className="border-purple-500/20 bg-black/40" />
          <DialogFooter>
            <Button data-testid="reject-confirm-button" onClick={reject} className="rounded-full bg-red-600 hover:bg-red-500">Reject deposit</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
