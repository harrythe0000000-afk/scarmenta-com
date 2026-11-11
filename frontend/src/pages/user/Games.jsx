import { useState } from "react";
import { toast } from "sonner";
import { Gamepad2, Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { TX_TYPES, fmtDate, usd, signedUsd } from "@/lib/format";

const ProviderCard = ({ p }) => {
  const [busy, setBusy] = useState(false);
  const play = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/games/launch", { provider_id: p.id });
      if (data.launch_url) window.open(data.launch_url, "_blank", "noopener");
      else toast.info(`${p.name} is being connected`, { description: "Your game session is ready. Games will open here once the provider goes live." });
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card-lux flex flex-col p-6 hover:-translate-y-0.5" data-testid={`game-provider-card-${p.code}`}>
      <div className="flex items-center justify-between">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-violet-600/40 to-fuchsia-600/30 text-purple-100"><Gamepad2 className="h-5 w-5" /></span>
        <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${p.connected ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"}`}>
          {p.connected ? "Live" : "Coming soon"}
        </span>
      </div>
      <h3 className="mt-5 font-display text-lg font-semibold text-white">{p.name}</h3>
      <p className="mt-1 flex-1 text-sm text-slate-400">{p.description || "Authorized gaming provider"}</p>
      <Button data-testid={`game-play-btn-${p.code}`} disabled={busy} onClick={play} className="mt-5 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500">
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />} Play
      </Button>
    </div>
  );
};

export default function UserGames() {
  const { data: providers } = useFetch("/games/providers");
  const { data: history } = useFetch("/games/history");
  return (
    <>
      <PageHeader eyebrow="Games lobby" title="Play with your credits" desc="Bets are deducted from your credit balance and wins are added back, as reported by the game provider." />
      {!providers?.length ? <EmptyState text="No game providers are live yet. Check back soon." testId="games-empty" /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="games-provider-grid">
          {providers.map((p) => <ProviderCard key={p.id} p={p} />)}
        </div>
      )}
      <section className="mt-12">
        <p className="label-eyebrow mb-4">Game history</p>
        {!history?.length ? <EmptyState text="No bets yet." testId="game-history-empty" /> : (
          <div className="card-lux overflow-x-auto p-2" data-testid="game-history-table">
            <Table>
              <TableHeader>
                <TableRow className="border-white/5 hover:bg-transparent">
                  {["Date", "Provider", "Round", "Type", "Amount", "Balance"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((g) => (
                  <TableRow key={g.id} className="border-white/5">
                    <TableCell className="whitespace-nowrap font-num text-xs text-slate-400">{fmtDate(g.created_at)}</TableCell>
                    <TableCell className="text-xs text-slate-300">{g.provider_name}</TableCell>
                    <TableCell className="font-num text-xs text-purple-300">{g.round_id}</TableCell>
                    <TableCell className="text-xs text-slate-200">{TX_TYPES[g.type] || g.type}{g.status !== "ok" && <span className="ml-1 text-red-300">({g.status.replace("_", " ")})</span>}</TableCell>
                    <TableCell className={`font-num text-sm ${g.type === "bet" ? "text-red-300" : "text-emerald-300"}`}>{signedUsd(g.type === "bet" ? -g.amount : g.amount)}</TableCell>
                    <TableCell className="font-num text-xs text-slate-400">{usd(g.balance_after)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </>
  );
}
