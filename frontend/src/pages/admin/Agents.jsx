import { useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { usd } from "@/lib/format";

const NewAgent = ({ onDone }) => {
  const [f, setF] = useState({ name: "", email: "", password: "", commission_percent: 5 });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/admin/agents", { name: f.name, email: f.email, password: f.password });
      toast.success(`Agent created with code ${data.agent_code}. Share the login with them securely.`);
      setF({ name: "", email: "", password: "", commission_percent: 5 });
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const cls = "border-purple-500/20 bg-black/40";
  return (
    <form onSubmit={submit} className="card-lux space-y-3 p-6" data-testid="new-agent-form">
      <p className="label-eyebrow">Add an agent</p>
      <Input data-testid="agent-name-input" required minLength={2} placeholder="Full name" value={f.name} onChange={set("name")} className={cls} />
      <Input data-testid="agent-email-input" required type="email" placeholder="Login email" value={f.email} onChange={set("email")} className={cls} />
      <Input data-testid="agent-password-input" required minLength={8} placeholder="Temporary password (min 8)" value={f.password} onChange={set("password")} className={`${cls} font-num`} />
      <p className="rounded-lg border border-white/5 bg-black/30 px-3 py-2 text-xs text-slate-400">Commission is automatic by number of players: 1–10 → 5%, 11–50 → 7%, 51+ → 10% of each deposit.</p>
      <Button data-testid="agent-create-button" disabled={busy} className="w-full rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-2 h-4 w-4" /> Create agent</Button>
      <p className="text-xs text-slate-500">Agents sign in on the normal login page and see their own portal with their sign-up link.</p>
    </form>
  );
};

export default function AdminAgents() {
  const { user: me } = useAuth();
  const owner = me?.role === "admin";
  const { data, reload } = useFetch("/admin/agents");
  const act = async (fn, msg) => {
    try {
      await fn();
      toast.success(msg);
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  const pay = (a) => {
    if (!window.confirm(`Mark ${usd(a.unpaid)} as paid to ${a.name}? Pay them outside the platform first.`)) return;
    const note = window.prompt("Payout note (e.g. USDT TX hash)", "") || "";
    act(() => api.post(`/admin/agents/${a.id}/payout`, { note }), "Payout recorded");
  };
  return (
    <>
      <PageHeader eyebrow="Agents" title="Agent accounts & commission" desc="Agents bring players with their own sign-up link and earn commission on every approved deposit: 1–10 players 5%, 11–50 players 7%, 51+ players 10%." />
      <div className={`grid gap-6 ${owner ? "lg:grid-cols-[340px_1fr]" : ""}`}>
        {owner && <NewAgent onDone={reload} />}
        {!data?.length ? <EmptyState text="No agents yet." testId="agents-empty" /> : (
          <div className="card-lux overflow-x-auto p-2" data-testid="agents-table">
            <Table>
              <TableHeader><TableRow className="border-white/5 hover:bg-transparent">
                {["Agent", "Code", "Rate", "Players", "Volume", "Earned", "Unpaid", "Paid", "Status", ""].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}
              </TableRow></TableHeader>
              <TableBody>
                {data.map((a) => (
                  <TableRow key={a.id} className="border-white/5" data-testid={`agent-row-${a.email}`}>
                    <TableCell><p className="text-sm text-white">{a.name}</p><p className="text-xs text-slate-500">{a.email}</p></TableCell>
                    <TableCell className="font-num text-xs text-[#F2B94B]">{a.agent_code}</TableCell>
                    <TableCell className="font-num text-sm" data-testid={`agent-rate-${a.email}`}>{a.current_rate}%</TableCell>
                    <TableCell className="font-num text-sm">{a.players}</TableCell>
                    <TableCell className="font-num text-sm text-emerald-300">{usd(a.volume)}</TableCell>
                    <TableCell className="font-num text-sm">{usd(a.earned)}</TableCell>
                    <TableCell className="font-num text-sm text-amber-300" data-testid={`agent-unpaid-${a.email}`}>{usd(a.unpaid)}</TableCell>
                    <TableCell className="font-num text-sm text-slate-400">{usd(a.paid)}</TableCell>
                    <TableCell><StatusBadge status={a.status} /></TableCell>
                    <TableCell>
                      {owner && (
                        <div className="flex gap-1.5">
                          <Button size="sm" disabled={!a.unpaid} data-testid={`agent-pay-btn-${a.email}`} onClick={() => pay(a)} className="rounded-full bg-emerald-600 px-2.5 text-xs hover:bg-emerald-500">Pay</Button>
                          <Button size="sm" variant="outline" data-testid={`agent-toggle-btn-${a.email}`} onClick={() => act(() => api.patch(`/admin/agents/${a.id}`, { status: a.status === "active" ? "suspended" : "active" }), "Status updated")}
                            className="rounded-full border-red-500/30 bg-transparent px-2.5 text-xs text-red-300 hover:bg-red-500/10">{a.status === "active" ? "Disable" : "Enable"}</Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}
