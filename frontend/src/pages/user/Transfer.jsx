import { useState } from "react";
import { toast } from "sonner";
import { ArrowLeftRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { useConfig, useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

export default function UserTransfer() {
  const { user } = useAuth();
  const config = useConfig();
  const { data: wallet, reload: reloadWallet } = useFetch("/wallet");
  const { data: history, reload } = useFetch("/transfers");
  const [f, setF] = useState({ to_email: "", to_password: "", amount: "" });
  const [busy, setBusy] = useState(false);
  const pct = config?.transfer_fee_percent ?? 5;
  const amt = Number(f.amount) || 0;
  const fee = +(amt * pct / 100).toFixed(2);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!window.confirm(`Move ${usd(amt)} to ${f.to_email}? They receive ${usd(amt - fee)} after the ${pct}% fee.`)) return;
    setBusy(true);
    try {
      const { data } = await api.post("/transfers", { ...f, amount: amt });
      toast.success(`Transfer ${data.reference} complete: ${usd(data.net)} sent`);
      setF({ to_email: "", to_password: "", amount: "" });
      reload();
      reloadWallet();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const cls = "h-11 border-purple-500/20 bg-black/40";
  return (
    <>
      <PageHeader eyebrow="Account transfer" title="Move balance to your other account"
        desc={`Transfer credit balance from this account to another Scarmenta player account you own. A ${pct}% transfer fee is deducted.`} />
      <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
        <form onSubmit={submit} className="card-lux space-y-4 p-6" data-testid="transfer-form">
          <p className="text-sm text-slate-400">Available balance: <span className="font-num text-white" data-testid="transfer-available">{usd(wallet?.balance)}</span></p>
          <div><p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Receiving account email</p>
            <Input data-testid="transfer-to-email-input" type="email" required value={f.to_email} onChange={set("to_email")} className={cls} /></div>
          <div><p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Receiving account password (to confirm it's yours)</p>
            <Input data-testid="transfer-to-password-input" type="password" required value={f.to_password} onChange={set("to_password")} className={cls} autoComplete="off" /></div>
          <div><p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Amount ($)</p>
            <Input data-testid="transfer-amount-input" type="number" min="1" step="0.01" required value={f.amount} onChange={set("amount")} className={`${cls} font-num`} /></div>
          <div className="space-y-1.5 rounded-xl border border-white/5 bg-black/30 p-4 font-num text-sm" data-testid="transfer-breakdown">
            <div className="flex justify-between text-slate-400"><span>Transfer fee ({pct}%)</span><span>−{usd(fee)}</span></div>
            <div className="flex justify-between text-white"><span>They receive</span><span className="text-emerald-300" data-testid="transfer-net">{usd(Math.max(amt - fee, 0))}</span></div>
          </div>
          <Button data-testid="transfer-submit-button" disabled={busy || amt <= 0 || amt > (wallet?.balance || 0)} className="w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600">
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowLeftRight className="mr-2 h-4 w-4" />} Transfer
          </Button>
        </form>
        <div>
          <p className="label-eyebrow mb-4">Transfer history</p>
          {!history?.length ? <EmptyState text="No transfers yet." testId="transfer-history-empty" /> : (
            <div className="card-lux overflow-x-auto p-2" data-testid="transfer-history-table">
              <Table>
                <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{["Date", "Reference", "Direction", "Amount", "Fee", "Received"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
                <TableBody>
                  {history.map((t) => {
                    const out = t.from_user_id === user?.id;
                    return (
                      <TableRow key={t.id} className="border-white/5">
                        <TableCell className="font-num text-xs text-slate-400">{fmtDate(t.created_at)}</TableCell>
                        <TableCell className="font-num text-xs text-purple-300">{t.reference}</TableCell>
                        <TableCell className="text-xs text-slate-300">{out ? `To ${t.to_email}` : `From ${t.from_email}`}</TableCell>
                        <TableCell className={`font-num text-sm ${out ? "text-red-300" : "text-emerald-300"}`}>{out ? `−${usd(t.amount)}` : `+${usd(t.net)}`}</TableCell>
                        <TableCell className="font-num text-xs text-slate-400">{usd(t.fee)}</TableCell>
                        <TableCell className="font-num text-xs text-slate-300">{usd(t.net)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
