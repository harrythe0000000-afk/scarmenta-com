import { useState } from "react";
import { toast } from "sonner";
import { CalendarDays, Plus, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ImagePicker } from "@/pages/admin/Popups";
import { bannerImg } from "@/components/UserPopups";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";

const toIst = (v) => `${v}:00+05:30`;
export const fmtIst = (iso) => new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const EMPTY = { title: "", message: "", image_id: null, starts_at: "", ends_at: "" };
const inputCls = "border-purple-500/20 bg-black/40";

export const ThemeBanner = ({ theme }) => (
  <div className="relative mb-6 overflow-hidden rounded-2xl border border-amber-400/30 bg-gradient-to-r from-amber-500/10 via-fuchsia-500/10 to-violet-600/10" data-testid="contest-theme-banner">
    {theme.image_id && <img src={bannerImg(theme.image_id)} alt="" className="h-40 w-full object-cover sm:h-52" data-testid="contest-theme-image" />}
    <div className="p-5 sm:p-6">
      <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-300"><Sparkles className="h-4 w-4" /> Theme of the week</p>
      <h2 className="mt-1 font-display text-2xl font-bold text-white sm:text-3xl" data-testid="contest-theme-title">{theme.title}</h2>
      {theme.message && <p className="mt-2 whitespace-pre-line text-sm text-slate-300" data-testid="contest-theme-message">{theme.message}</p>}
      <p className="mt-3 flex items-center gap-1 text-xs text-slate-400"><CalendarDays className="h-3.5 w-3.5" /> Ends {fmtIst(theme.ends_at)} IST</p>
    </div>
  </div>
);

const phase = (t) => {
  const now = new Date().toISOString();
  if (t.starts_at > now) return ["Scheduled", "text-sky-300"];
  if (t.ends_at <= now) return ["Ended", "text-slate-500"];
  return ["Live", "text-emerald-300"];
};

export const ThemeManager = ({ canEdit }) => {
  const { data, reload } = useFetch("/admin/contest/themes");
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/admin/contest/themes", { ...f, starts_at: toIst(f.starts_at), ends_at: toIst(f.ends_at) });
      toast.success("Theme saved");
      setF(EMPTY);
      reload();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id) => {
    try {
      await api.delete(`/admin/contest/themes/${id}`);
      toast.success("Theme removed");
      reload();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  return (
    <div className="mb-8 grid gap-6 lg:grid-cols-[380px_1fr]" data-testid="contest-theme-manager">
      {canEdit && (
        <form onSubmit={submit} className="card-lux space-y-3 p-6" data-testid="contest-theme-form">
          <p className="label-eyebrow">Theme of the week</p>
          <ImagePicker imageId={f.image_id} onChange={(id) => setF({ ...f, image_id: id })} />
          <Input required minLength={2} maxLength={80} placeholder="Title, e.g. Diwali Streak" value={f.title} onChange={set("title")} data-testid="contest-theme-title-input" className={inputCls} />
          <Textarea maxLength={500} rows={3} placeholder="Message for players (optional)" value={f.message} onChange={set("message")} data-testid="contest-theme-message-input" className={inputCls} />
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1 text-xs text-slate-400">Start (IST)
              <Input required type="datetime-local" value={f.starts_at} onChange={set("starts_at")} data-testid="contest-theme-start-input" className={inputCls} />
            </label>
            <label className="space-y-1 text-xs text-slate-400">End (IST)
              <Input required type="datetime-local" value={f.ends_at} onChange={set("ends_at")} data-testid="contest-theme-end-input" className={inputCls} />
            </label>
          </div>
          <Button disabled={busy} data-testid="contest-theme-save-button" className="w-full rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-2 h-4 w-4" /> Save theme</Button>
        </form>
      )}
      <div className="space-y-3" data-testid="contest-theme-list">
        {data?.length === 0 && <p className="text-sm text-slate-500">No themes yet.</p>}
        {data?.map((t) => (
          <div key={t.id} className="card-lux flex gap-4 p-4" data-testid={`contest-theme-row-${t.id}`}>
            {t.image_id ? <img src={bannerImg(t.image_id)} alt="" className="h-16 w-24 shrink-0 rounded-lg object-cover" /> : <div className="h-16 w-24 shrink-0 rounded-lg bg-amber-500/10" />}
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-white">{t.title}</p>
              <p className="text-xs text-slate-400">{fmtIst(t.starts_at)} → {fmtIst(t.ends_at)} IST</p>
              <p className={`text-xs ${phase(t)[1]}`} data-testid={`contest-theme-phase-${t.id}`}>{phase(t)[0]}</p>
            </div>
            {canEdit && <Button size="sm" variant="ghost" onClick={() => remove(t.id)} data-testid={`contest-theme-delete-${t.id}`} className="text-slate-500 hover:text-red-300"><Trash2 className="h-4 w-4" /></Button>}
          </div>
        ))}
      </div>
    </div>
  );
};
