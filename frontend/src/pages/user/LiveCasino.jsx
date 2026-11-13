import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Play, Radio } from "lucide-react";
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
      {g.image_id && <img src={bannerImg(g.image_id)} alt={g.name} className="h-full w-full object-cover" />}
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

export default function LiveCasino() {
  const { user } = useAuth();
  const { data } = useFetch("/live/games");
  const [busy, setBusy] = useState(null);
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
  const groups = (data || []).reduce((acc, g) => ({ ...acc, [g.provider]: [...(acc[g.provider] || []), g] }), {});
  return (
    <>
      <PageHeader eyebrow="Live casino" title="Live dealer games" desc={`Play with your credit balance (${usd(user?.promo_balance || 0)}). Games run in INR; your balance is converted at the current rate and results come back to your Scarmenta balance.`} />
      {data?.length === 0 && <EmptyState text="Live games are coming soon." testId="live-empty" />}
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
