import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const inr = (n) => (n === undefined || n === null || n === "" ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
const Badge = ({ ok, children }) => (
  <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider ${ok ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>{children}</span>
);

const Grid = ({ testid, cols, rows, render, empty = "Nothing yet" }) => (
  <div className="card-lux overflow-x-auto" data-testid={testid}>
    <Table>
      <TableHeader><TableRow className="border-purple-500/10">{cols.map((c) => <TableHead key={c} className="whitespace-nowrap">{c}</TableHead>)}</TableRow></TableHeader>
      <TableBody>
        {(!rows || rows.length === 0) && <TableRow><TableCell colSpan={cols.length} className="text-center text-sm text-slate-500">{rows ? empty : "Loading…"}</TableCell></TableRow>}
        {rows?.map(render)}
      </TableBody>
    </Table>
  </div>
);

const Filter = ({ value, onChange, testid }) => (
  <Input placeholder="Filter by player email" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} className="max-w-xs border-purple-500/20 bg-black/40" />
);

const Pills = ({ value, onChange, options, testid }) => (
  <div className="flex gap-1" data-testid={testid}>
    {options.map(([v, label]) => (
      <button key={v} type="button" onClick={() => onChange(v)} data-testid={`${testid}-${v || "all"}`}
        className={`rounded-full px-3 py-1 text-xs transition-colors ${value === v ? "bg-purple-600 text-white" : "bg-white/5 text-slate-400 hover:bg-white/10"}`}>{label}</button>
    ))}
  </div>
);

export const LaunchHistory = () => {
  const [user, setUser] = useState("");
  const [status, setStatus] = useState("");
  const { data } = useFetch(`/admin/live/sessions?user=${encodeURIComponent(user)}&status=${status}`);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3"><Filter value={user} onChange={setUser} testid="live-sessions-filter" />
        <Pills value={status} onChange={setStatus} testid="live-sessions-status" options={[["", "All"], ["launched", "Launched"], ["failed", "Failed"]]} /></div>
      <Grid testid="live-sessions-table" cols={["Time", "Player", "Game", "Wallet sent", "Status"]} rows={data}
        render={(s) => (
          <TableRow key={s.id} className="border-purple-500/10" data-testid={`live-session-${s.id}`}>
            <TableCell className="whitespace-nowrap text-xs text-slate-400">{fmtDate(s.created_at)}</TableCell>
            <TableCell className="text-sm text-white">{s.user_email}<p className="font-mono text-[10px] text-slate-500">{s.player_id || "—"}</p></TableCell>
            <TableCell className="text-sm text-slate-300">{s.game_name || "—"}<p className="font-mono text-[10px] text-slate-500">{s.game_uid}</p></TableCell>
            <TableCell className="font-num text-sm">{s.wallet_inr ? `${inr(s.wallet_inr)} (${usd(s.wallet_usd)})` : "—"}</TableCell>
            <TableCell><Badge ok={s.status === "launched"}>{s.status}</Badge>{s.reason && <p className="mt-1 text-[10px] text-slate-500">{s.reason}</p>}</TableCell>
          </TableRow>
        )} />
    </div>
  );
};

export const RoundHistory = () => {
  const [user, setUser] = useState("");
  const [result, setResult] = useState("");
  const { data } = useFetch(`/admin/live/rounds?user=${encodeURIComponent(user)}&result=${result}`);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3"><Filter value={user} onChange={setUser} testid="live-rounds-filter" />
        <Pills value={result} onChange={setResult} testid="live-rounds-result" options={[["", "All"], ["win", "Player won"], ["loss", "Player lost"]]} /></div>
      <Grid testid="live-rounds-table" cols={["Time", "Round", "Player", "Game", "Bet", "Win", "Wallet before → after", "Credit change", "Settled"]} rows={data}
        render={(r) => (
          <TableRow key={r.game_round} className="border-purple-500/10" data-testid={`live-round-${r.game_round}`}>
            <TableCell className="whitespace-nowrap text-xs text-slate-400">{fmtDate(r.updated_at)}</TableCell>
            <TableCell className="font-mono text-[11px] text-slate-400">{r.game_round}{r.callbacks > 1 && <p className="text-[10px] text-amber-300">{r.callbacks} callbacks</p>}</TableCell>
            <TableCell className="text-sm text-white">{r.user_email || r.player_id}</TableCell>
            <TableCell className="text-sm text-slate-300">{r.game_name || r.game_uid}<p className="text-[10px] text-slate-500">{r.provider}</p></TableCell>
            <TableCell className="font-num text-sm">{inr(r.bet_inr)}</TableCell>
            <TableCell className="font-num text-sm">{inr(r.win_inr)}</TableCell>
            <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{inr(r.wallet_before)} → {inr(r.wallet_after)}</TableCell>
            <TableCell className={`font-num text-sm ${r.applied_usd >= 0 ? "text-emerald-300" : "text-red-300"}`}>{usd(r.applied_usd)}</TableCell>
            <TableCell><Badge ok={r.settled !== false}>{r.settled === false ? "pending" : "done"}</Badge></TableCell>
          </TableRow>
        )} />
    </div>
  );
};

export const PlayerReport = () => {
  const { data } = useFetch("/admin/live/players");
  return (
    <Grid testid="live-players-table" cols={["Player", "Rounds", "Bets", "Wins", "House GGR", "Credit change", "Last played"]} rows={data}
      render={(p) => (
        <TableRow key={p.user_id} className="border-purple-500/10" data-testid={`live-player-${p.user_id}`}>
          <TableCell className="text-sm text-white">{p.email}<p className="font-mono text-[10px] text-slate-500">{p.player_id}</p></TableCell>
          <TableCell className="font-num">{p.rounds}</TableCell>
          <TableCell className="font-num">{inr(p.bets_inr)}</TableCell>
          <TableCell className="font-num">{inr(p.wins_inr)}</TableCell>
          <TableCell className={`font-num ${p.ggr_inr >= 0 ? "text-emerald-300" : "text-red-300"}`}>{inr(p.ggr_inr)}</TableCell>
          <TableCell className="font-num">{usd(p.net_usd)}</TableCell>
          <TableCell className="whitespace-nowrap text-xs text-slate-400">{fmtDate(p.last)}</TableCell>
        </TableRow>
      )} />
  );
};

export const CallbackLogs = () => {
  const [failed, setFailed] = useState(false);
  const { data } = useFetch(`/admin/live/callbacks?failed=${failed}`);
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm text-slate-300"><Switch checked={failed} onCheckedChange={setFailed} data-testid="live-callbacks-failed-toggle" /> Show failed only</label>
      <Grid testid="live-callbacks-table" cols={["Time", "From IP", "Round", "Player", "Data", "Result"]} rows={data}
        render={(c) => (
          <TableRow key={c.id} className="border-purple-500/10" data-testid={`live-callback-${c.id}`}>
            <TableCell className="whitespace-nowrap text-xs text-slate-400">{fmtDate(c.created_at)}</TableCell>
            <TableCell className="font-mono text-[11px] text-slate-400">{c.ip}<p className="text-[10px] text-slate-600">{c.path}</p></TableCell>
            <TableCell className="font-mono text-[11px] text-slate-400">{c.game_round || "—"}</TableCell>
            <TableCell className="font-mono text-[11px] text-slate-400">{c.mobile || "—"}</TableCell>
            <TableCell className="max-w-xs truncate font-mono text-[10px] text-slate-500" title={JSON.stringify(c.fields)}>{JSON.stringify(c.fields)}</TableCell>
            <TableCell><Badge ok={!c.failed}>{c.http_status}</Badge><p className="mt-1 text-[10px] text-slate-400">{c.result}</p></TableCell>
          </TableRow>
        )} />
    </div>
  );
};
