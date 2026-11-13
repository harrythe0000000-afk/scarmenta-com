import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Play, Radio, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { defaultGameImage } from "@/lib/liveImages";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { bannerImg } from "@/components/UserPopups";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { usd } from "@/lib/format";

const GameTile = ({ g, busy, onPlay }) => (
  <button type="button" onClick={() => onPlay(g)} disabled={!!busy} data-testid={`live-game-${g.id}`}
    className="group overflow-hidden rounded-2xl border border-purple-500/20 bg-black/40 text-left transition-transform hover:-translate-y-1 disabled:opacity-60">
    <div className="relative h-36 bg-gradient-to-br from-violet-900 to-fuchsia-900">
      <img src={g.image_id ? bannerImg(g.image_id) : defaultGameImage(g)} alt={g.name} loading="lazy" data-testid={`live-game-img-${g.id}`}
        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
      <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white"><Radio className="h-3 w-3" /> LIVE</span>
      <span className="absolute inset-0 grid place-items-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
        {busy === g.id ? <Loader2 className="h-8 w-8 animate-spin text-white" /> : <Play className="h-10 w-10 text-white" />}
      </span>
    </div>
    <div className="p-3">
      <p className="truncate font-semibold text-white">{g.name}</p>
      <p className="text-xs text-slate-400">{g.provider}</p>
    </div>
  </button>
);

const ProviderBar = ({ providers, value, onChange }) => (
  <div className="flex gap-2 overflow-x-auto pb-1" data-testid="live-provider-filter">
    {["All", ...providers].map((p) => (
      <button key={p} type="button" onClick={() => onChange(p)} data-testid={`live-provider-${p.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
        className={`whitespace-nowrap rounded-full px-4 py-1.5 text-sm transition-colors ${value === p ? "bg-purple-600 text-white" : "border border-purple-500/20 bg-black/40 text-slate-300 hover:bg-purple-500/10"}`}>{p}</button>
    ))}
  </div>
);

export default function LiveCasino() {
  const { user } = useAuth();
  const { data } = useFetch("/live/games");
  const [busy, setBusy] = useState(null);
  const [provider, setProvider] = useState("All");
  const [q, setQ] = useState("");
  const play = async (g) => {
    setBusy(g.id);
    try {
      const { data: r } = await api.post("/live/launch", { game_id: g.id });
      window.location.href = r.url;
    } catch (e) {
      toast.error(formatApiError(e));
      setBusy(null);
    }
  };
  const providers = [...new Set((data || []).map((g) => g.provider))].sort();
  const term = q.trim().toLowerCase();
  const shown = (data || []).filter((g) => (provider === "All" || g.provider === provider) && (!term || g.name.toLowerCase().includes(term)));
  const groups = shown.reduce((acc, g) => ({ ...acc, [g.provider]: [...(acc[g.provider] || []), g] }), {});
  return (
    <>
      <PageHeader eyebrow="Live casino" title="Live dealer games" desc={`Play with your credit balance (${usd(user?.promo_balance || 0)}). Games run in INR; your balance is converted at the current rate and results come back to your Scarmenta balance.`} />
      {data?.length === 0 && <EmptyState text="Live games are coming soon." testId="live-empty" />}
      {data?.length > 0 && (
        <div className="mb-6 space-y-3">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search games" data-testid="live-search-input" className="rounded-full border-purple-500/20 bg-black/40 pl-9" />
          </div>
          <ProviderBar providers={providers} value={provider} onChange={setProvider} />
        </div>
      )}
      {data?.length > 0 && shown.length === 0 && <p className="text-sm text-slate-400" data-testid="live-no-results">No games match. Try another name or provider.</p>}
      <div className="space-y-8" data-testid="live-games">
        {Object.entries(groups).map(([p, games]) => (
          <section key={p}>
            <p className="label-eyebrow mb-3">{p}</p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {games.map((g) => <GameTile key={g.id} g={g} busy={busy} onPlay={play} />)}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
