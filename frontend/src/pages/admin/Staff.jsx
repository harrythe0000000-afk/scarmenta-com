import { useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

const CAN = ["Approve or reject deposits", "View users, transactions and game activity", "Handle support tickets and fraud alerts", "View referrals and money flow"];
const CANNOT = ["Credit Config (rates, UPI/USDT addresses, %)", "Game providers and API keys", "Adjust balances or suspend players", "Pay loss rewards or manage staff"];

const NewStaff = ({ onDone }) => {
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/admin/staff", f);
      toast.success(`Staff account created for ${f.email}. Share the password with them securely.`);
      setF({ name: "", email: "", password: "" });
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <form onSubmit={submit} className="card-lux space-y-3 p-6" data-testid="new-staff-form">
      <p className="label-eyebrow">Add a staff admin</p>
      <Input data-testid="staff-name-input" required minLength={2} placeholder="Full name" value={f.name} onChange={set("name")} className="border-purple-500/20 bg-black/40" />
      <Input data-testid="staff-email-input" required type="email" placeholder="Login email" value={f.email} onChange={set("email")} className="border-purple-500/20 bg-black/40" />
      <Input data-testid="staff-password-input" required minLength={8} type="text" placeholder="Temporary password (min 8)" value={f.password} onChange={set("password")} className="border-purple-500/20 bg-black/40 font-num" />
      <p className="text-xs text-slate-500">They can change it later from My Account.</p>
      <Button data-testid="staff-create-button" disabled={busy} className="w-full rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-2 h-4 w-4" /> Create staff account</Button>
    </form>
  );
};

export default function AdminStaff() {
  const { data, reload } = useFetch("/admin/staff");
  const toggle = async (s) => {
    try {
      await api.patch(`/admin/staff/${s.id}/status`, { status: s.status === "active" ? "suspended" : "active" });
      toast.success(`${s.email} ${s.status === "active" ? "disabled" : "re-enabled"}`);
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <>
      <PageHeader eyebrow="Team" title="Staff admins" desc="Staff can run day-to-day work but can't change money settings." />
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <NewStaff onDone={reload} />
          <div className="card-lux p-5 text-sm" data-testid="staff-permissions">
            <p className="font-semibold text-emerald-300">Staff can</p>
            <ul className="mt-2 space-y-1 text-slate-400">{CAN.map((c) => <li key={c}>· {c}</li>)}</ul>
            <p className="mt-4 font-semibold text-red-300">Only you (owner) can</p>
            <ul className="mt-2 space-y-1 text-slate-400">{CANNOT.map((c) => <li key={c}>· {c}</li>)}</ul>
          </div>
        </div>
        <div className="card-lux overflow-x-auto p-2" data-testid="staff-table">
          <Table>
            <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{["Name", "Role", "Added", "Status", ""].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {(data || []).map((s) => (
                <TableRow key={s.id} className="border-white/5" data-testid={`staff-row-${s.email}`}>
                  <TableCell><p className="text-sm text-white">{s.name}</p><p className="text-xs text-slate-500">{s.email}</p></TableCell>
                  <TableCell className="text-xs uppercase tracking-wider text-slate-300">{s.role === "admin" ? "Owner" : "Staff"}</TableCell>
                  <TableCell className="font-num text-xs text-slate-400">{fmtDate(s.created_at)}</TableCell>
                  <TableCell><StatusBadge status={s.status} /></TableCell>
                  <TableCell>
                    {s.role === "staff" && (
                      <Button size="sm" variant="outline" data-testid={`staff-toggle-btn-${s.email}`} onClick={() => toggle(s)}
                        className={`rounded-full bg-transparent ${s.status === "active" ? "border-red-500/40 text-red-300 hover:bg-red-500/10" : "border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10"}`}>
                        {s.status === "active" ? "Disable" : "Enable"}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </>
  );
}
