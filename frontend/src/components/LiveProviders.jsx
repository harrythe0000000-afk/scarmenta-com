import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, FlaskConical, Plus, Trash2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, formatApiError } from "@/lib/api";
import { fmtDate } from "@/lib/format";

const call = async (fn, ok, after) => {
  try {
    const r = await fn();
    if (ok) toast.success(ok);
    after?.(r?.data);
  } catch (e) {
    toast.error(formatApiError(e));
  }
};

const AddProvider = ({ onDone }) => {
  const [f, setF] = useState({ name: "", provider_id: "" });
  const submit = (e) => {
    e.preventDefault();
    call(() => api.post("/admin/live/providers", f), "Provider added", () => { setF({ name: "", provider_id: "" }); onDone(); });
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2" data-testid="live-provider-add-form">
      <Input required minLength={2} maxLength={40} placeholder="Provider name, e.g. Evolution" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="live-provider-name-input" className="max-w-xs border-purple-500/20 bg-black/40" />
      <Input maxLength={40} placeholder="Provider ID (optional)" value={f.provider_id} onChange={(e) => setF({ ...f, provider_id: e.target.value })} data-testid="live-provider-id-input" className="max-w-[200px] border-purple-500/20 bg-black/40 font-mono" />
      <Button data-testid="live-provider-add-button" className="rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-1.5 h-4 w-4" /> Add provider</Button>
    </form>
  );
};

const TestStatus = ({ t }) => {
  if (!t) return <span className="text-xs text-slate-500">Not tested</span>;
  const Icon = t.ok ? CheckCircle2 : XCircle;
  return (
    <div className="text-xs" title={t.detail}>
      <span className={`flex items-center gap-1 ${t.ok ? "text-emerald-300" : "text-red-300"}`}><Icon className="h-3.5 w-3.5" /> {t.ok ? "Passed" : `Failed (${t.status || "no reply"})`}</span>
      <p className="text-[10px] text-slate-500">{fmtDate(t.at)} · {t.game_uid}</p>
      {!t.ok && t.detail && <p className="max-w-[220px] truncate text-[10px] text-slate-600">{t.detail}</p>}
    </div>
  );
};

const ProviderRow = ({ p, canEdit, reload }) => {
  const [busy, setBusy] = useState(false);
  const test = async () => {
    setBusy(true);
    await call(() => api.post(`/admin/live/providers/${p.id}/test`, {}), null, (r) => { toast[r.ok ? "success" : "error"](r.ok ? `${p.name} test passed` : `${p.name} test failed`); reload(); });
    setBusy(false);
  };
  const tested = p.last_test?.ok;
  return (
    <TableRow className="border-purple-500/10" data-testid={`live-provider-row-${p.provider_id}`}>
      <TableCell className="font-medium text-white">{p.name}</TableCell>
      <TableCell className="font-mono text-xs text-slate-400">{p.provider_id}</TableCell>
      <TableCell className="max-w-[180px] truncate font-mono text-[11px] text-slate-500">{p.endpoint}</TableCell>
      <TableCell className="font-num">{p.games}</TableCell>
      <TableCell><TestStatus t={p.last_test} /></TableCell>
      <TableCell>
        <Switch checked={p.enabled} disabled={!canEdit || (!p.enabled && !tested)} data-testid={`live-provider-toggle-${p.provider_id}`}
          onCheckedChange={(v) => call(() => api.patch(`/admin/live/providers/${p.id}`, { enabled: v }), v ? `${p.name} is live for players` : `${p.name} hidden from players`, reload)} />
      </TableCell>
      {canEdit && (
        <TableCell className="whitespace-nowrap text-right">
          <Button size="sm" variant="outline" onClick={test} disabled={busy || !p.games} data-testid={`live-provider-test-${p.provider_id}`} className="rounded-full border-purple-500/30 bg-transparent">
            <FlaskConical className="mr-1 h-3.5 w-3.5" /> {busy ? "Testing…" : "Test"}
          </Button>
          {!p.games && (
            <button type="button" className="ml-2 align-middle" data-testid={`live-provider-delete-${p.provider_id}`}
              onClick={() => window.confirm(`Remove ${p.name}?`) && call(() => api.delete(`/admin/live/providers/${p.id}`), "Provider removed", reload)}>
              <Trash2 className="h-4 w-4 text-slate-500 hover:text-red-400" />
            </button>
          )}
        </TableCell>
      )}
    </TableRow>
  );
};

export const LiveProviders = ({ providers, canEdit, reload }) => (
  <div className="space-y-4" data-testid="live-providers">
    <p className="text-sm text-slate-400">
      All providers run through the same BULKAPI gateway and keys. BULKAPI has no provider list API, so add providers here. A provider can be turned on for players only after a test launch with one of its games passes. A failed test turns it off.
    </p>
    {canEdit && <AddProvider onDone={reload} />}
    <div className="card-lux overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="border-purple-500/10">
            {["Provider", "Provider ID", "API endpoint", "Games", "Last test", "Live for players", ...(canEdit ? [""] : [])].map((h) => <TableHead key={h}>{h}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(providers || []).map((p) => <ProviderRow key={p.id} p={p} canEdit={canEdit} reload={reload} />)}
        </TableBody>
      </Table>
    </div>
  </div>
);
