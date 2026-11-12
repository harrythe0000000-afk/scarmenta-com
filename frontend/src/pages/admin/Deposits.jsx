import { useState } from "react";
import { Link } from "react-router-dom";
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
import { useAuth } from "@/context/AuthContext";
import { fmtDate, usd, methodLabel, localMoney } from "@/lib/format";

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
  const { user: me } = useAuth();
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
      <PageHeader eyebrow="Deposit monitoring" title="Approval queue" desc="Approving a deposit adds credits to the player's balance at the configured multiplier." />
      {me?.role === "admin" && <Link to="/admin/settings" data-testid="admin-payment-setup-link" className="mb-5 flex items-center justify-between rounded-xl border border-purple-500/25 bg-purple-500/5 px-4 py-3 text-sm text-purple-200 transition-colors hover:bg-purple-500/10">
        <span>Add or change where players pay you (UPI ID, USDT addresses, $ to ₹ rate) in Credit Config</span><span>Open →</span>
      </Link>}
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
                {["Reference", "Player", "Date", "Method / payment ref.", "Received", "Amount", "Credits", "Risk", "Status", ""].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id} className="border-white/5 hover:bg-purple-500/[0.04]" data-testid={`admin-deposit-row-${d.reference}`}>
                  <TableCell className="font-num text-xs text-purple-300">{d.reference}</TableCell>
                  <TableCell><p className="text-sm text-white">{d.user_name}</p><p className="text-xs text-slate-500">{d.user_email}</p></TableCell>
                  <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(d.created_at)}</TableCell>
                  <TableCell className="max-w-[200px]">
                    <p className="text-xs text-slate-300">{methodLabel(d.method, d.network)}</p>
                    <p className="truncate font-num text-[11px] text-purple-300/80" title={d.payment_reference} data-testid={`admin-deposit-ref-${d.reference}`}>{d.payment_reference}</p>
                  </TableCell>
                  <TableCell className="whitespace-nowrap font-num text-xs text-slate-300">{localMoney(d.local_amount, d.local_currency)}{d.local_currency === "INR" && <p className="text-[10px] text-slate-500">@ ₹{d.fx_rate}/$</p>}</TableCell>
                  <TableCell className="font-num text-sm font-semibold text-white">{usd(d.amount)}</TableCell>
                  <TableCell className="whitespace-nowrap font-num text-sm text-purple-300">{usd(d.promo_credit)}</TableCell>
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
