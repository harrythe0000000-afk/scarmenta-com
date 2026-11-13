import { useState } from "react";
import { toast } from "sonner";
import { Share2, TrendingUp } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { renderHedgeImage, shareBlob } from "@/lib/shareImage";
import { inr } from "@/components/demo/RivalsWallets";
import { useConfig } from "@/lib/hooks";
import { usd } from "@/lib/format";

const FILE = "scarmenta-demo-profit.png";

export const HedgeShare = ({ totals }) => {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const bonus = useConfig()?.demo_share_bonus_amount ?? 0;
  if (!totals?.rounds) return null;
  const share = async () => {
    const code = user?.referral_code;
    const link = `${window.location.origin}/register${code ? `?ref=${code}&src=demo` : ""}`;
    setBusy(true);
    try {
      const blob = await renderHedgeImage({ ...totals, code, link });
      const how = await shareBlob(blob, FILE, `My Scarmenta vs Others demo practice: net profit ${inr(totals.net)}. Join with my code ${code || ""}: ${link}`);
      if (how === "downloaded") toast.success("Image saved — attach it in WhatsApp", { position: "top-center" });
    } catch (e) {
      if (e?.name !== "AbortError") toast.error("Couldn't create the image", { position: "top-center" });
    } finally {
      setBusy(false);
    }
  };
  const up = totals.net > 0;
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3" data-testid="hedge-total">
      <div className="flex items-center gap-3">
        <TrendingUp className={`h-5 w-5 ${up ? "text-emerald-300" : "text-red-300"}`} />
        <div>
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Total net profit · {totals.rounds} rounds</p>
          {bonus > 0 && up && <p className="text-[11px] text-emerald-300/80" data-testid="hedge-bonus-hint">Earn {usd(bonus)} credits for every friend who joins from your image and deposits</p>}
          <p className={`font-num text-xl font-bold ${up ? "text-emerald-300" : "text-red-300"}`} data-testid="hedge-total-net">{totals.net < 0 ? "−" : "+"}{inr(Math.abs(totals.net))}</p>
        </div>
      </div>
      {up ? (
        <button type="button" onClick={share} disabled={busy} data-testid="hedge-share-button"
          className="flex items-center gap-1.5 rounded-full bg-[#25D366] px-4 py-2 text-sm font-bold text-black transition-transform hover:scale-105 disabled:opacity-60">
          <Share2 className="h-4 w-4" /> {busy ? "Creating…" : "Share on WhatsApp"}
        </button>
      ) : (
        <p className="text-xs text-slate-500" data-testid="hedge-share-hint">Get into profit to share your result</p>
      )}
    </div>
  );
};
