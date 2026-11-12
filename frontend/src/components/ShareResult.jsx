import { useState } from "react";
import { toast } from "sonner";
import { Download, Loader2, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { renderShareImage } from "@/lib/shareImage";

const FILE = "scarmenta-calculator.png";

const download = (blob) => {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: FILE });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

export const ShareResult = ({ amount, rate, days, res }) => {
  const { user } = useAuth();
  const [busy, setBusy] = useState("");
  const code = user?.referral_code;
  const link = `${window.location.origin}/register${code ? `?ref=${code}` : ""}`;
  const text = `I tried the Scarmenta compound calculator. Join with my code ${code || ""}: ${link}`;
  const make = () => renderShareImage({ amount, rate, days, final: res.final, chart: res.chart, code, link });

  const run = (kind, fn) => async () => {
    setBusy(kind);
    try {
      await fn(await make());
    } catch (e) {
      if (e?.name !== "AbortError") toast.error("Couldn't create the image. Please try again.");
    } finally {
      setBusy("");
    }
  };
  const share = run("share", async (blob) => {
    const file = new File([blob], FILE, { type: "image/png" });
    if (navigator.canShare?.({ files: [file] })) return navigator.share({ files: [file], text });
    download(blob);
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
    toast.success("Image saved — attach it in WhatsApp");
  });
  const save = run("save", async (blob) => {
    download(blob);
    toast.success("Image saved");
  });

  return (
    <div className="flex flex-wrap gap-2" data-testid="calc-share">
      <Button onClick={share} disabled={!!busy} data-testid="calc-share-whatsapp-button" className="rounded-full bg-[#25D366] font-semibold text-black hover:bg-[#1ebe5b]">
        {busy === "share" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Share2 className="mr-2 h-4 w-4" />} Share on WhatsApp
      </Button>
      <Button onClick={save} disabled={!!busy} variant="outline" data-testid="calc-save-image-button" className="rounded-full border-purple-500/30 bg-transparent">
        {busy === "save" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />} Save image
      </Button>
    </div>
  );
};
