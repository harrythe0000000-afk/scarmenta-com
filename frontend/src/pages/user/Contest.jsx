import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ImagePlus, Loader2, Trophy, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { api, API, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";
import { ThemeBanner } from "@/components/ContestTheme";

export const contestImg = (id) => `${API}/contest/image/${id}`;
const STATUS = {
  pending: ["In review", "bg-amber-500/15 text-amber-300"],
  winner: ["Winner", "bg-emerald-500/15 text-emerald-300"],
  rejected: ["Not selected", "bg-slate-500/15 text-slate-400"],
};

const UploadBox = ({ onDone }) => {
  const [file, setFile] = useState(null);
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);
  const submit = async (e) => {
    e.preventDefault();
    if (!file) return toast.error("Choose a screenshot first");
    if (file.size > 5 * 1024 * 1024) return toast.error("Screenshot must be 5 MB or smaller");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (caption.trim()) fd.append("caption", caption.trim());
      await api.post("/contest/entries", fd);
      toast.success("Screenshot submitted — good luck!");
      setFile(null);
      setCaption("");
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card-lux space-y-4 p-6" data-testid="contest-upload-form">
      <p className="label-eyebrow">Submit your share</p>
      <ol className="space-y-1 text-sm text-slate-400">
        <li>1. Get a Hot Streak in the <Link to="/app/demo-game" className="text-purple-300 hover:text-purple-200" data-testid="contest-demo-link">Demo games</Link> and tap Share.</li>
        <li>2. Post it on WhatsApp status, a group or Instagram.</li>
        <li>3. Upload a screenshot of your post here.</li>
      </ol>
      <label className="flex cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-xl border border-dashed border-purple-500/30 p-4 text-sm text-slate-300 hover:bg-white/[0.03]">
        {preview ? <img src={preview} alt="Preview" className="max-h-56 rounded-lg object-contain" data-testid="contest-preview" /> : <><ImagePlus className="h-6 w-6 text-purple-300" /> Choose screenshot (JPG, PNG, WEBP · max 5 MB)</>}
        <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" data-testid="contest-file-input" onChange={(e) => { setFile(e.target.files?.[0] || null); e.target.value = ""; }} />
      </label>
      <Input value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={200} placeholder="Where did you post it? (optional)" data-testid="contest-caption-input" className="border-purple-500/20 bg-black/40" />
      <Button disabled={busy || !file} data-testid="contest-submit-button" className="w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold">
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />} Submit screenshot
      </Button>
    </form>
  );
};

const MyEntries = ({ items }) => (
  <div className="card-lux p-6" data-testid="contest-my-entries">
    <p className="label-eyebrow mb-4">My entries</p>
    {items.length === 0 ? <p className="text-sm text-slate-500">You haven't submitted any screenshots yet.</p> : (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((e) => (
          <div key={e.id} className="overflow-hidden rounded-xl border border-purple-500/15 bg-black/30" data-testid={`contest-entry-${e.id}`}>
            <img src={contestImg(e.id)} alt="" className="h-32 w-full object-cover" />
            <div className="space-y-1 p-2">
              <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS[e.status][1]}`} data-testid={`contest-entry-status-${e.id}`}>{STATUS[e.status][0]}{e.status === "winner" ? ` · ${usd(e.bonus)}` : ""}</span>
              <p className="text-[11px] text-slate-500">{fmtDate(e.created_at)}{e.theme_title ? ` · ${e.theme_title}` : ""}</p>
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
);

export const WinnersGallery = ({ items }) => (
  <div className="card-lux p-6" data-testid="contest-winners">
    <p className="label-eyebrow mb-4 flex items-center gap-2"><Trophy className="h-4 w-4 text-amber-300" /> Recent winners</p>
    {items.length === 0 ? <EmptyState text="No winners yet — yours could be the first!" testId="contest-winners-empty" /> : (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map((e) => (
          <div key={e.id} className="overflow-hidden rounded-xl border border-amber-400/20 bg-black/30" data-testid={`contest-winner-${e.id}`}>
            <img src={contestImg(e.id)} alt="" className="h-36 w-full object-cover" />
            <div className="p-2">
              <p className="text-sm font-semibold text-white">{e.name}</p>
              <p className="text-xs text-emerald-300">Won {usd(e.bonus)} · {fmtDate(e.decided_at)}</p>
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
);

export default function Contest() {
  const mine = useFetch("/contest/me");
  const wins = useFetch("/contest/winners");
  const theme = useFetch("/contest/theme");
  return (
    <>
      <PageHeader eyebrow="Promo contest" title="Share & win bonus credits" desc="Post your Hot Streak image, upload a screenshot, and each week our team picks winners who get bonus credits." />
      {theme.data && <ThemeBanner theme={theme.data} />}
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <UploadBox onDone={mine.reload} />
        <MyEntries items={mine.data || []} />
      </div>
      <div className="mt-6"><WinnersGallery items={wins.data || []} /></div>
    </>
  );
}
