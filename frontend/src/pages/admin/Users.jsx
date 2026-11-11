import { useState } from "react";
import { toast } from "sonner";
import { Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const AdjustDialog = ({ user, onClose, onDone }) => {
  const [form, setForm] = useState({ amount: "", reason: "" });
  const submit = async () => {
    try {
      await api.post(`/admin/users/${user.id}/adjust`, { ...form, amount: Number(form.amount) });
      toast.success("Balance adjusted and logged to ledger");
      onDone();
      onClose();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <Dialog open={!!user} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="border-purple-500/30 bg-[#0b0817]" data-testid="adjust-dialog">
        <DialogHeader>
          <DialogTitle className="text-white">Adjust balance · {user?.name}</DialogTitle>
          <DialogDescription>Use a negative amount to debit. Every adjustment is recorded on the user ledger.</DialogDescription>
        </DialogHeader>
        <Input data-testid="adjust-amount-input" type="number" placeholder="Amount e.g. 500 or -500" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="border-purple-500/20 bg-black/40 font-num" />
        <Input data-testid="adjust-reason-input" placeholder="Reason (required)" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="border-purple-500/20 bg-black/40" />
        <DialogFooter>
          <Button data-testid="adjust-submit-button" disabled={!Number(form.amount) || form.reason.length < 3} onClick={submit} className="rounded-full bg-purple-600 hover:bg-purple-500">Apply adjustment</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default function AdminUsers() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { data, reload } = useFetch(`/admin/users${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  const [adjusting, setAdjusting] = useState(null);

  const toggle = async (u) => {
    try {
      await api.patch(`/admin/users/${u.id}/status`, { status: u.status === "active" ? "suspended" : "active" });
      toast.success(`${u.email} ${u.status === "active" ? "suspended" : "re-activated"}`);
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  return (
    <>
      <PageHeader eyebrow="User management" title="Accounts" desc="Inspect balances, verification state and account status." />
      <form onSubmit={(e) => { e.preventDefault(); setQuery(q); }} className="mb-5 flex max-w-md gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <Input data-testid="admin-users-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or email" className="border-purple-500/20 bg-black/40 pl-9" />
        </div>
        <Button data-testid="admin-users-search-button" className="rounded-full bg-purple-600 hover:bg-purple-500">Search</Button>
      </form>
      {!data?.length ? <EmptyState text="No users found." testId="admin-users-empty" /> : (
        <div className="card-lux overflow-x-auto p-2" data-testid="admin-users-table">
          <Table>
            <TableHeader>
              <TableRow className="border-white/5 hover:bg-transparent">
                {["User", "Role", "Email", "Credit balance", "Referral income", "Loss rewards", "Joined", "Status", ""].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((u) => (
                <TableRow key={u.id} className="border-white/5 hover:bg-purple-500/[0.04]" data-testid={`admin-user-row-${u.email}`}>
                  <TableCell><p className="text-sm text-white">{u.name}</p><p className="text-xs text-slate-500">{u.email}</p></TableCell>
                  <TableCell className="text-xs uppercase tracking-wider text-slate-400">{u.role}</TableCell>
                  <TableCell><StatusBadge status={u.email_verified ? "verified" : "unverified"} /></TableCell>
                  <TableCell className="font-num text-sm text-purple-300">{usd(u.promo_balance)}</TableCell>
                  <TableCell className="font-num text-sm text-emerald-300">{usd(u.referral_earnings)}</TableCell>
                  <TableCell className="font-num text-sm text-amber-300">{usd(u.loss_rewards_total)}</TableCell>
                  <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(u.created_at)}</TableCell>
                  <TableCell><StatusBadge status={u.status} testId={`admin-user-status-${u.email}`} /></TableCell>
                  <TableCell>
                    {u.role === "user" && (
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => setAdjusting(u)} data-testid={`admin-adjust-btn-${u.email}`} className="rounded-full border-purple-500/30 bg-transparent hover:bg-purple-500/10"><SlidersHorizontal className="h-4 w-4" /></Button>
                        <Button size="sm" variant="outline" onClick={() => toggle(u)} data-testid={`admin-toggle-status-btn-${u.email}`}
                          className={`rounded-full bg-transparent ${u.status === "active" ? "border-red-500/40 text-red-300 hover:bg-red-500/10" : "border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10"}`}>
                          {u.status === "active" ? "Suspend" : "Activate"}
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <AdjustDialog user={adjusting} onClose={() => setAdjusting(null)} onDone={reload} />
    </>
  );
}
