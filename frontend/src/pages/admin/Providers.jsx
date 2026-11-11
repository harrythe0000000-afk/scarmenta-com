import { useState } from "react";
import { toast } from "sonner";
import { Copy, KeyRound, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { API, api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";

const EMPTY = { name: "", code: "", launch_url: "", description: "", status: "inactive" };

const ProviderForm = ({ initial, onClose, onSaved }) => {
  const [f, setF] = useState(initial || EMPTY);
  const editing = !!initial?.id;
  const save = async () => {
    try {
      const body = { name: f.name, code: f.code, launch_url: f.launch_url || null, description: f.description || null, status: f.status };
      const { data } = editing ? await api.put(`/admin/providers/${f.id}`, body) : await api.post("/admin/providers", body);
      toast.success(editing ? "Provider updated" : "Provider created");
      onSaved(data);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="border-purple-500/30 bg-[#0b0817]" data-testid="provider-form-dialog">
        <DialogHeader>
          <DialogTitle className="text-white">{editing ? "Edit provider" : "Add game provider"}</DialogTitle>
          <DialogDescription>Fill in the details from your provider agreement. Leave the launch URL empty until the provider is ready.</DialogDescription>
        </DialogHeader>
        <Input data-testid="provider-name-input" placeholder="Name e.g. Evolution" value={f.name} onChange={set("name")} className="border-purple-500/20 bg-black/40" />
        <Input data-testid="provider-code-input" placeholder="Code e.g. evolution (lowercase)" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toLowerCase() })} className="border-purple-500/20 bg-black/40 font-num" />
        <Input data-testid="provider-launch-url-input" placeholder="Game launch URL (https://…)" value={f.launch_url || ""} onChange={set("launch_url")} className="border-purple-500/20 bg-black/40 font-num" />
        <Input data-testid="provider-description-input" placeholder="Short description shown to players" value={f.description || ""} onChange={set("description")} className="border-purple-500/20 bg-black/40" />
        <label className="flex items-center justify-between rounded-xl border border-white/10 px-4 py-3 text-sm text-slate-300">
          Visible to players (active)
          <Switch data-testid="provider-status-switch" checked={f.status === "active"} onCheckedChange={(v) => setF({ ...f, status: v ? "active" : "inactive" })} />
        </label>
        <DialogFooter><Button data-testid="provider-save-button" onClick={save} className="rounded-full bg-purple-600 hover:bg-purple-500">Save</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const KeyDialog = ({ data, onClose }) => (
  <Dialog open={!!data} onOpenChange={(v) => !v && onClose()}>
    <DialogContent className="border-purple-500/30 bg-[#0b0817]" data-testid="provider-key-dialog">
      <DialogHeader>
        <DialogTitle className="text-white">Wallet API key · {data?.name}</DialogTitle>
        <DialogDescription>Give this key to the provider. It is shown only once — rotate it if lost.</DialogDescription>
      </DialogHeader>
      <p className="break-all rounded-lg border border-purple-500/30 bg-black/50 p-3 font-num text-xs text-purple-200" data-testid="provider-api-key-value">{data?.api_key}</p>
      <DialogFooter>
        <Button data-testid="provider-key-copy-button" onClick={() => { navigator.clipboard.writeText(data.api_key).catch(() => {}); toast.success("Key copied"); }} className="rounded-full bg-purple-600 hover:bg-purple-500"><Copy className="mr-2 h-4 w-4" /> Copy key</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

const ENDPOINTS = [
  ["POST", "/provider/v1/balance", "{ session_token }", "Player balance"],
  ["POST", "/provider/v1/bet", "{ session_token, transaction_id, round_id, amount, game_code? }", "Deducts the bet from the balance (402 if insufficient)"],
  ["POST", "/provider/v1/win", "{ session_token, transaction_id, round_id, amount, game_code? }", "Adds the win (needs a bet in the same round)"],
  ["POST", "/provider/v1/rollback", "{ session_token, transaction_id, ref_transaction_id }", "Refunds a bet"],
];

const IntegrationGuide = () => (
  <div className="card-lux p-6" data-testid="provider-integration-guide">
    <p className="label-eyebrow">How the integration works</p>
    <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm text-slate-400">
      <li>Add a provider here and share its wallet API key with the provider.</li>
      <li>When a player taps Play, we create a 4-hour session token and open <span className="font-num text-purple-300">launch_url?token=…&currency=USD</span>.</li>
      <li>The provider calls the wallet API below with header <span className="font-num text-purple-300">X-Provider-Key</span>. Every call is idempotent on <span className="font-num">transaction_id</span>.</li>
      <li>Every bet, win and refund is written to the player's ledger and appears in Game Activity.</li>
    </ol>
    <div className="mt-5 space-y-2">
      {ENDPOINTS.map(([m, path, body, desc]) => (
        <div key={path} className="rounded-xl border border-white/5 bg-black/30 px-4 py-3">
          <p className="font-num text-xs"><span className="text-emerald-300">{m}</span> <span className="text-white">{API}{path}</span></p>
          <p className="mt-1 font-num text-[11px] text-slate-500">{body}</p>
          <p className="mt-1 text-xs text-slate-400">{desc}</p>
        </div>
      ))}
    </div>
  </div>
);

export default function AdminProviders() {
  const { data, reload } = useFetch("/admin/providers");
  const [editing, setEditing] = useState(null);
  const [keyData, setKeyData] = useState(null);
  const rotate = async (p) => {
    try {
      const { data: d } = await api.post(`/admin/providers/${p.id}/rotate-key`);
      setKeyData(d);
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  const onSaved = (d) => {
    setEditing(null);
    if (d.api_key) setKeyData(d);
    reload();
  };
  return (
    <>
      <PageHeader eyebrow="Provider management" title="Game providers" desc="Connect authorized game providers (e.g. Evolution, Ezugi, Pragmatic Play). Players' bets are deducted from their credit balance via the wallet API."
        action={<Button data-testid="provider-add-button" onClick={() => setEditing(EMPTY)} className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6"><Plus className="mr-2 h-4 w-4" /> Add provider</Button>} />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-3">
          {!data?.length ? <EmptyState text="No providers yet. Add one to open a game slot." testId="providers-empty" /> : data.map((p) => (
            <div key={p.id} className="card-lux p-5" data-testid={`provider-row-${p.code}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-display text-lg font-semibold text-white">{p.name}</p>
                  <p className="font-num text-xs text-purple-300">{p.code} · key …{p.api_key_last4}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">{p.launch_url || "Launch URL not set — shows as Coming soon"}</p>
                </div>
                <StatusBadge status={p.status} testId={`provider-status-${p.code}`} />
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="outline" data-testid={`provider-edit-btn-${p.code}`} onClick={() => setEditing(p)} className="rounded-full border-purple-500/30 bg-transparent hover:bg-purple-500/10"><Pencil className="mr-1.5 h-3.5 w-3.5" /> Edit</Button>
                <Button size="sm" variant="outline" data-testid={`provider-rotate-btn-${p.code}`} onClick={() => window.confirm(`Rotate the key for ${p.name}? The old key stops working immediately.`) && rotate(p)} className="rounded-full border-amber-500/30 bg-transparent text-amber-200 hover:bg-amber-500/10"><KeyRound className="mr-1.5 h-3.5 w-3.5" /> Rotate key</Button>
              </div>
            </div>
          ))}
        </div>
        <IntegrationGuide />
      </div>
      {editing && <ProviderForm initial={editing.id ? editing : null} onClose={() => setEditing(null)} onSaved={onSaved} />}
      <KeyDialog data={keyData} onClose={() => setKeyData(null)} />
    </>
  );
}
