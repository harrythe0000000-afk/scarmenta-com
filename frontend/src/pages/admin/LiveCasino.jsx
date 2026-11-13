import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Copy, Plus, Trash2, Upload, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/StatCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CallbackLogs, LaunchHistory, PlayerReport, RoundHistory } from "@/components/LiveReports";
import { ImagePicker } from "@/pages/admin/Popups";
import { useAuth } from "@/context/AuthContext";
import { api, API, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

const PROVIDERS = ["Ezugi", "Evolution", "Microgaming", "Playtech", "Iconic21", "ORA Gaming", "Macro Gaming", "Other"];
const EMPTY = { name: "", provider: "Evolution", game_uid: "", image_id: null };
const inr = (n) => `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const CALLBACKS = [`${API}/bulkapi/callback`, `${API}/game_callback.php`];

const run = async (fn, msg, after) => {
  try {
    await fn();
    toast.success(msg);
    after?.();
  } catch (e) {
    toast.error(formatApiError(e));
  }
};

const Check = ({ ok, label }) => (
  <p className="flex items-center gap-2 text-sm">{ok ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <XCircle className="h-4 w-4 text-red-400" />}<span className="text-slate-300">{label}</span></p>
);

const StatusCard = ({ data }) => {
  if (!data) return null;
  return (
    <div className="card-lux space-y-2 p-6" data-testid="live-status">
      <p className="label-eyebrow mb-2">Connection</p>
      <Check ok={data.token_set} label="API token saved" />
      <p className="pl-6 text-xs text-slate-500" data-testid="live-creds-source">Keys in use from: {data.source === "admin panel" ? "Admin panel" : "Server settings"}</p>
      <Check ok={data.secret_set && data.secret_bytes === 32} label={`Secret key saved (${data.secret_bytes}/32 characters)`} />
      <Check ok={data.inr_rate > 0} label={`INR rate $1 = ₹${data.inr_rate}`} />
      <Check ok={data.rounds > 0} label={`${data.rounds} game rounds received`} />
      <Check ok={data.reachable} label={data.reachable ? `BULKAPI reachable (${data.launch_url})` : `BULKAPI not reachable (${data.launch_url})`} />
      <Check ok={data.failed_callbacks === 0} label={`${data.failed_callbacks} failed callbacks`} />
      <Check ok={data.unsettled === 0} label={`${data.unsettled} rounds waiting to settle`} />
      <div className="space-y-2 pt-2">
        <p className="text-xs text-slate-500">Callback URL to set in the BULKAPI portal (either works)</p>
        {CALLBACKS.map((u, i) => (
          <div key={u} className="flex items-center gap-2 rounded-lg border border-purple-500/20 bg-black/40 px-3 py-2">
            <code className="flex-1 truncate text-xs text-purple-200" data-testid={`live-callback-url-${i}`}>{u}</code>
            <button type="button" onClick={() => { navigator.clipboard.writeText(u); toast.success("Copied"); }} data-testid={`live-callback-copy-${i}`}><Copy className="h-4 w-4 text-slate-400" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};

const CredsCard = ({ data, reload }) => {
  const [f, setF] = useState({ api_token: "", secret_key: "" });
  const [show, setShow] = useState(false);
  if (!data) return null;
  const save = async (e) => {
    e.preventDefault();
    try {
      const { data: r } = await api.put("/admin/live/credentials", f);
      toast.success("BULKAPI keys saved");
      if (r.warning) toast.warning(r.warning);
      setF({ api_token: "", secret_key: "" });
      reload();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  const field = (k, label, mask, ph) => (
    <div className="space-y-1">
      <p className="text-xs text-slate-400">{label} <span className="font-mono text-slate-500" data-testid={`live-creds-${k}-mask`}>{mask ? `saved ${mask}` : "not saved"}</span></p>
      <Input type={show ? "text" : "password"} autoComplete="off" placeholder={ph} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`live-creds-${k}-input`} className="border-purple-500/20 bg-black/40 font-mono" />
    </div>
  );
  return (
    <form onSubmit={save} className="card-lux space-y-3 p-6" data-testid="live-creds-form">
      <p className="label-eyebrow">BULKAPI keys</p>
      <p className="text-xs text-slate-500">Copy these two fields from your BULKAPI portal. One Token + Secret Key opens every game. Leave a box empty to keep the saved value.</p>
      {field("api_token", "API Token", data.token_mask, "API Token from the portal")}
      {field("secret_key", "Secret Key", data.secret_mask, "Secret Key (usually 32 characters)")}
      {f.secret_key && <p className={`text-xs ${f.secret_key.trim().length === 32 ? "text-emerald-300" : "text-amber-300"}`} data-testid="live-creds-secret-length">{f.secret_key.trim().length}/32 characters</p>}
      <label className="flex items-center gap-2 text-xs text-slate-400"><Switch checked={show} onCheckedChange={setShow} data-testid="live-creds-show-toggle" /> Show what I type</label>
      <Button data-testid="live-creds-save" className="w-full rounded-full bg-purple-600 hover:bg-purple-500">Save keys</Button>
      {data.source === "admin panel" && (
        <button type="button" data-testid="live-creds-clear" className="w-full text-center text-xs text-slate-500 underline hover:text-red-300"
          onClick={() => window.confirm("Remove the keys saved here and use the server keys instead?") && run(() => api.delete("/admin/live/credentials"), "Saved keys removed", reload)}>Remove keys saved here</button>
      )}
    </form>
  );
};

const TEMPLATE = "name,provider,game_uid\nLightning Roulette,Evolution,PUT_GAME_UID_HERE\n";

const ImportCard = ({ onDone }) => {
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/admin/live/games/import", fd);
      setRes(data);
      toast.success(`${data.added} games added`);
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const template = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`;
  return (
    <div className="card-lux space-y-3 p-6" data-testid="live-import-card">
      <p className="label-eyebrow">Add many games (Excel / CSV)</p>
      <p className="text-xs text-slate-500">First row: <code className="text-purple-200">name, provider, game_uid</code>. Games already in the list are skipped.</p>
      <label className={`flex cursor-pointer items-center justify-center gap-2 rounded-full border border-dashed border-purple-500/40 px-4 py-3 text-sm text-purple-200 transition-colors hover:bg-purple-500/10 ${busy ? "opacity-50" : ""}`}>
        <Upload className="h-4 w-4" /> {busy ? "Uploading…" : "Choose .xlsx or .csv file"}
        <input type="file" accept=".csv,.xlsx,.xlsm" className="hidden" disabled={busy} onChange={upload} data-testid="live-import-input" />
      </label>
      <a href={template} download="bulkapi-games-template.csv" className="block text-center text-xs text-slate-400 underline hover:text-white" data-testid="live-import-template">Download sample file</a>
      {res && (
        <div className="rounded-lg border border-purple-500/20 bg-black/40 p-3 text-xs" data-testid="live-import-result">
          <p className="text-emerald-300">{res.added} added</p>
          <p className="text-slate-400">{res.skipped} already in list</p>
          {res.error_count > 0 && <p className="text-red-300">{res.error_count} rows had problems</p>}
          {res.errors.map((er) => <p key={er} className="text-[10px] text-slate-500">{er}</p>)}
        </div>
      )}
    </div>
  );
};

const RateCard = ({ data, reload }) => {
  const [rate, setRate] = useState("");
  if (!data) return null;
  const save = (e) => {
    e.preventDefault();
    run(() => api.put("/admin/live/rate", { inr_rate: Number(rate) }), "Live casino rate saved", () => { setRate(""); reload(); });
  };
  return (
    <form onSubmit={save} className="card-lux space-y-3 p-6" data-testid="live-rate-form">
      <p className="label-eyebrow">Live casino rate</p>
      <p className="text-sm text-slate-300">Now: <span className="font-num text-white" data-testid="live-rate-current">$1 = ₹{data.inr_rate}</span></p>
      <p className="text-xs text-slate-500">Player credits are sent to games in INR at this rate, and wins or losses come back to credits at the same rate.</p>
      <div className="flex gap-2">
        <Input required type="number" step="0.01" min="1.01" max="1000" placeholder="e.g. 95" value={rate} onChange={(e) => setRate(e.target.value)} data-testid="live-rate-input" className="border-purple-500/20 bg-black/40" />
        <Button data-testid="live-rate-save" className="rounded-full bg-purple-600 hover:bg-purple-500">Save</Button>
      </div>
    </form>
  );
};

const TestCard = () => {
  const [uid, setUid] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const test = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      setRes((await api.post("/admin/live/test", { game_uid: uid })).data);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={test} className="card-lux space-y-3 p-6" data-testid="live-test-form">
      <p className="label-eyebrow">Test connection</p>
      <div className="flex gap-2">
        <Input required placeholder="Any game_uid" value={uid} onChange={(e) => setUid(e.target.value)} data-testid="live-test-uid-input" className="border-purple-500/20 bg-black/40 font-mono" />
        <Button disabled={busy} data-testid="live-test-button" className="rounded-full bg-purple-600 hover:bg-purple-500">{busy ? "Testing…" : "Test"}</Button>
      </div>
      {res && (
        <div className="space-y-1 rounded-lg border border-purple-500/20 bg-black/40 p-3" data-testid="live-test-result">
          <Check ok={res.ok} label={res.ok ? "BULKAPI accepted the launch" : `BULKAPI rejected it (status ${res.status})`} />
          {res.redirect && <p className="truncate text-xs text-slate-400">Opens: {res.redirect}</p>}
          {res.detail && <p className="break-words text-xs text-slate-500">{res.detail}</p>}
        </div>
      )}
    </form>
  );
};

const AddGame = ({ onDone }) => {
  const [f, setF] = useState(EMPTY);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    run(() => api.post("/admin/live/games", f), "Game added", () => { setF(EMPTY); onDone(); });
  };
  return (
    <form onSubmit={submit} className="card-lux space-y-3 p-6" data-testid="live-add-game-form">
      <p className="label-eyebrow">Add live game</p>
      <ImagePicker imageId={f.image_id} onChange={(id) => setF({ ...f, image_id: id })} />
      <Input required minLength={2} placeholder="Game name, e.g. Lightning Roulette" value={f.name} onChange={set("name")} data-testid="live-game-name-input" className="border-purple-500/20 bg-black/40" />
      <select value={f.provider} onChange={set("provider")} data-testid="live-game-provider-select" className="h-10 w-full rounded-md border border-purple-500/20 bg-black/40 px-3 text-sm text-white">
        {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <Input required placeholder="game_uid from BULKAPI" value={f.game_uid} onChange={set("game_uid")} data-testid="live-game-uid-input" className="border-purple-500/20 bg-black/40 font-mono" />
      <Button data-testid="live-add-game-button" className="w-full rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-2 h-4 w-4" /> Add game</Button>
    </form>
  );
};

const Games = ({ games, canEdit, reload }) => (
  <div className="card-lux overflow-hidden" data-testid="live-games-table">
    <Table>
      <TableHeader><TableRow className="border-purple-500/10"><TableHead>Game</TableHead><TableHead>Provider</TableHead><TableHead>game_uid</TableHead><TableHead className="text-right">Live</TableHead></TableRow></TableHeader>
      <TableBody>
        {games.length === 0 && <TableRow><TableCell colSpan={4} className="text-center text-sm text-slate-500">No games yet</TableCell></TableRow>}
        {games.map((g) => (
          <TableRow key={g.id} className="border-purple-500/10" data-testid={`live-game-row-${g.id}`}>
            <TableCell className="text-white">{g.name}</TableCell>
            <TableCell className="text-slate-400">{g.provider}</TableCell>
            <TableCell className="font-mono text-xs text-slate-400">{g.game_uid}</TableCell>
            <TableCell className="text-right">
              {canEdit && (
                <div className="flex items-center justify-end gap-2">
                  <Switch checked={g.active} data-testid={`live-game-toggle-${g.id}`} onCheckedChange={(v) => run(() => api.patch(`/admin/live/games/${g.id}`, { active: v }), v ? "Game on" : "Game off", reload)} />
                  <Button size="sm" variant="ghost" data-testid={`live-game-delete-${g.id}`} className="text-slate-500 hover:text-red-300" onClick={() => run(() => api.delete(`/admin/live/games/${g.id}`), "Game removed", reload)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </div>
);

const Ggr = () => {
  const { data } = useFetch("/admin/live/ggr");
  if (!data) return null;
  return (
    <div className="card-lux overflow-hidden" data-testid="live-ggr">
      <p className="label-eyebrow px-6 pt-6">GGR by provider (INR)</p>
      <Table>
        <TableHeader><TableRow className="border-purple-500/10"><TableHead>Provider</TableHead><TableHead className="text-right">Rounds</TableHead><TableHead className="text-right">Players</TableHead><TableHead className="text-right">Bets</TableHead><TableHead className="text-right">Wins</TableHead><TableHead className="text-right">GGR</TableHead></TableRow></TableHeader>
        <TableBody>
          {data.providers.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-sm text-slate-500">No rounds yet</TableCell></TableRow>}
          {data.providers.map((p) => (
            <TableRow key={p.provider} className="border-purple-500/10" data-testid={`live-ggr-row-${p.provider}`}>
              <TableCell className="text-white">{p.provider}</TableCell>
              <TableCell className="text-right font-num">{p.rounds}</TableCell>
              <TableCell className="text-right font-num">{p.players}</TableCell>
              <TableCell className="text-right font-num">{inr(p.bets_inr)}</TableCell>
              <TableCell className="text-right font-num">{inr(p.wins_inr)}</TableCell>
              <TableCell className={`text-right font-num ${p.ggr_inr >= 0 ? "text-emerald-300" : "text-red-300"}`}>{inr(p.ggr_inr)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data.recent.length > 0 && <p className="px-6 pb-4 text-xs text-slate-500">Last round {fmtDate(data.recent[0].updated_at)}</p>}
    </div>
  );
};

export default function AdminLiveCasino() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin";
  const { data, reload } = useFetch("/admin/live/games");
  const status = useFetch("/admin/live/status");
  return (
    <>
      <PageHeader eyebrow="BULKAPI" title="Live casino" desc="Manage live dealer games, check the BULKAPI connection and see GGR by provider." />
      <Tabs defaultValue="setup" data-testid="live-tabs">
        <TabsList className="mb-6 flex-wrap bg-black/40">
          <TabsTrigger value="setup" data-testid="live-tab-setup">Setup & games</TabsTrigger>
          <TabsTrigger value="launches" data-testid="live-tab-launches">Launch history</TabsTrigger>
          <TabsTrigger value="rounds" data-testid="live-tab-rounds">Bets & wins</TabsTrigger>
          <TabsTrigger value="players" data-testid="live-tab-players">Player report</TabsTrigger>
          <TabsTrigger value="callbacks" data-testid="live-tab-callbacks">Callback logs</TabsTrigger>
        </TabsList>
        <TabsContent value="setup">
          <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
            <div className="space-y-6">
              <StatusCard data={status.data} />
              {canEdit && <CredsCard data={status.data} reload={status.reload} />}
              {canEdit && <RateCard data={status.data} reload={status.reload} />}
              {canEdit && <TestCard />}
              {canEdit && <ImportCard onDone={reload} />}
              {canEdit && <AddGame onDone={reload} />}
            </div>
            <div className="space-y-6">
              <Games games={data || []} canEdit={canEdit} reload={reload} />
              <Ggr />
            </div>
          </div>
        </TabsContent>
        <TabsContent value="launches"><LaunchHistory /></TabsContent>
        <TabsContent value="rounds"><RoundHistory /></TabsContent>
        <TabsContent value="players"><PlayerReport /></TabsContent>
        <TabsContent value="callbacks"><CallbackLogs /></TabsContent>
      </Tabs>
    </>
  );
}
