import { useState } from "react";
import { toast } from "sonner";
import { Share2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { renderLiveWinImage, shareBlob } from "@/lib/shareImage";

const inr = (n) => `₹${Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export const LiveWinShare = ({ net, game }) => {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const share = async () => {
    const code = user?.referral_code;
    const link = `${window.location.origin}/register${code ? `?ref=${code}` : ""}`;
    setBusy(true);
    try {
      const blob = await renderLiveWinImage({ net, game, code, link });
      const how = await shareBlob(blob, "scarmenta-live-win.png", `I just won ${inr(net)} on ${game || "Scarmenta live casino"}! Join with my code ${code || ""}: ${link}`);
      if (how === "downloaded") toast.success("Image saved — attach it in WhatsApp", { position: "top-center" });
    } catch (e) {
      if (e?.name !== "AbortError") toast.error("Couldn't create the image", { position: "top-center" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" onClick={share} disabled={busy} data-testid="live-win-share-button"
      className="mx-auto flex items-center gap-1.5 rounded-full bg-[#25D366] px-5 py-2 text-sm font-bold text-black transition-transform hover:scale-105 disabled:opacity-60">
      <Share2 className="h-4 w-4" /> {busy ? "Creating…" : "Share win on WhatsApp"}
    </button>
  );
};
