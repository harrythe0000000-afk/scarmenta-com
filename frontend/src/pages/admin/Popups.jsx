import { useState } from "react";
import { toast } from "sonner";
import { Eye, Plus, RefreshCcw, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { PageHeader, EmptyState } from "@/components/StatCard";
import { BannerCard, bannerImg } from "@/components/UserPopups";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

const AUD = [["user", "Players"], ["agent", "Agents"]];
const EMPTY = { title: "", text: "", button_label: "", button_url: "", image_id: null, audience: ["user"], starts_at: "", ends_at: "" };
const toIst = (v) => (v ? `${v}:00+05:30` : null);
const fmtIst = (iso) => new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const phase = (b) => {
  const now = new Date().toISOString();
  if (!b.active) return ["Off", "text-slate-500"];
  if (b.starts_at && b.starts_at > now) return ["Scheduled", "text-sky-300"];
  if (b.ends_at && b.ends_at <= now) return ["Ended", "text-slate-500"];
  return ["Live", "text-emerald-300"];
};
const inputCls = "border-purple-500/20 bg-black/40";

export const ImagePicker = ({ imageId, onChange }) => {
  const [busy, setBusy] = useState(false);
  const pick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return toast.error("Image must be 5 MB or smaller");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/admin/banners/image", fd);
      onChange(data.image_id);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2">
      {imageId && <img src={bannerImg(imageId)} alt="Popup" data-testid="popup-image-preview" className="max-h-40 w-full rounded-lg object-cover" />}
      <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-purple-500/30 py-3 text-sm text-slate-300 hover:bg-white/[0.03]">
        <Upload className="h-4 w-4" /> {busy ? "Uploading…" : imageId ? "Replace image" : "Upload image (JPG, PNG, WEBP · max 5 MB)"}
        <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={pick} disabled={busy} data-testid="popup-image-input" />
      </label>
      {imageId && <button type="button" className="text-xs text-slate-500 hover:text-red-300" onClick={() => onChange(null)} data-testid="popup-image-remove">Remove image</button>}
    </div>
  );
};

const NewPopup = ({ onDone }) => {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const toggleAud = (a) => setF({ ...f, audience: f.audience.includes(a) ? f.audience.filter((x) => x !== a) : [...f.audience, a] });
  const submit = async (e) => {
    e.preventDefault();
    if (!f.audience.length) return toast.error("Choose who should see this popup");
    setBusy(true);
    try {
      await api.post("/admin/banners", { ...f, button_label: f.button_label || null, button_url: f.button_url || null, starts_at: toIst(f.starts_at), ends_at: toIst(f.ends_at) });
      toast.success("Popup published");
      setF(EMPTY);
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card-lux space-y-3 p-6" data-testid="new-popup-form">
      <p className="label-eyebrow">New popup</p>
      <ImagePicker imageId={f.image_id} onChange={(id) => setF({ ...f, image_id: id })} />
      <Input data-testid="popup-title-input" required minLength={2} placeholder="Title" value={f.title} onChange={set("title")} className={inputCls} />
      <Textarea data-testid="popup-text-input" placeholder="Message (optional)" value={f.text} onChange={set("text")} className={inputCls} rows={3} />
      <div className="grid grid-cols-2 gap-2">
        <Input data-testid="popup-button-label-input" placeholder="Button text (optional)" value={f.button_label} onChange={set("button_label")} className={inputCls} />
        <Input data-testid="popup-button-url-input" placeholder="/app/deposits or https://…" value={f.button_url} onChange={set("button_url")} className={inputCls} />
      </div>
      <div className="grid grid-cols-2 gap-2" data-testid="popup-schedule">
        <label className="space-y-1 text-xs text-slate-400">Start (IST, optional)
          <Input type="datetime-local" data-testid="popup-start-input" value={f.starts_at} onChange={set("starts_at")} className={inputCls} />
        </label>
        <label className="space-y-1 text-xs text-slate-400">End (IST, optional)
          <Input type="datetime-local" data-testid="popup-end-input" value={f.ends_at} onChange={set("ends_at")} className={inputCls} />
        </label>
      </div>
      <p className="text-xs text-slate-500">Leave empty to show right away and keep it on until you turn it off.</p>
      <div className="flex gap-4 text-sm" data-testid="popup-audience">
        <span className="text-slate-400">Show to:</span>
        {AUD.map(([v, l]) => (
          <label key={v} className="flex items-center gap-2 text-slate-300">
            <input type="checkbox" checked={f.audience.includes(v)} onChange={() => toggleAud(v)} data-testid={`popup-audience-${v}`} className="h-4 w-4 accent-purple-500" /> {l}
          </label>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button type="button" variant="outline" onClick={() => setPreview(true)} disabled={!f.title} data-testid="popup-preview-button" className="rounded-full border-purple-500/30 bg-transparent"><Eye className="mr-2 h-4 w-4" /> Preview</Button>
        <Button data-testid="popup-create-button" disabled={busy} className="rounded-full bg-purple-600 hover:bg-purple-500"><Plus className="mr-2 h-4 w-4" /> Publish</Button>
      </div>
      <Dialog open={preview} onOpenChange={setPreview}>
        <DialogContent data-testid="popup-preview-dialog" className="max-w-md border-purple-500/20 bg-[#0b0816] text-slate-200">
          <DialogTitle className="sr-only">Preview</DialogTitle>
          <DialogDescription className="sr-only">How players will see this popup</DialogDescription>
          <BannerCard b={f} onButton={() => setPreview(false)} />
        </DialogContent>
      </Dialog>
    </form>
  );
};

const PopupRow = ({ b, reload }) => {
  const act = async (fn, msg) => {
    try {
      await fn();
      toast.success(msg);
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <div className="card-lux flex gap-4 p-4" data-testid={`popup-row-${b.id}`}>
      {b.image_id ? <img src={bannerImg(b.image_id)} alt="" className="h-20 w-28 shrink-0 rounded-lg object-cover" /> : <div className="h-20 w-28 shrink-0 rounded-lg bg-purple-500/10" />}
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-white">{b.title}</p>
        <p className="truncate text-xs text-slate-400">{b.text}</p>
        <p className="mt-1 text-xs text-slate-500">{b.audience.map((a) => (a === "user" ? "Players" : "Agents")).join(" + ")} · created {fmtIst(b.created_at)} IST</p>
        {(b.starts_at || b.ends_at) && (
          <p className="mt-1 text-xs text-slate-400" data-testid={`popup-schedule-${b.id}`}>
            {b.starts_at ? fmtIst(b.starts_at) : "Now"} → {b.ends_at ? fmtIst(b.ends_at) : "No end"} IST
          </p>
        )}
        <div className="mt-2 flex gap-4 text-xs" data-testid={`popup-stats-${b.id}`}>
          <span className="text-slate-300"><span className="font-num text-white" data-testid={`popup-views-${b.id}`}>{b.views}</span> saw it</span>
          {b.button_label && <span className="text-slate-300"><span className="font-num text-white" data-testid={`popup-clicks-${b.id}`}>{b.clicks}</span> tapped button{b.views ? ` (${Math.round((b.clicks / b.views) * 100)}%)` : ""}</span>}
        </div>
      </div>
      <div className="flex flex-col items-end gap-2">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className={phase(b)[1]} data-testid={`popup-phase-${b.id}`}>{phase(b)[0]}</span>
          <Switch checked={b.active} data-testid={`popup-toggle-${b.id}`}
            onCheckedChange={(v) => act(() => api.patch(`/admin/banners/${b.id}`, { active: v }), v ? "Popup is live" : "Popup turned off")} />
        </label>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="sm" variant="ghost" className="text-slate-500 hover:text-red-300" data-testid={`popup-delete-${b.id}`}><Trash2 className="h-4 w-4" /></Button>
          </AlertDialogTrigger>
          <AlertDialogContent className="border-purple-500/20 bg-[#0b0816] text-slate-200">
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this popup?</AlertDialogTitle>
              <AlertDialogDescription>It will stop showing to users right away.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="bg-transparent">Cancel</AlertDialogCancel>
              <AlertDialogAction data-testid={`popup-delete-confirm-${b.id}`} className="bg-red-600 hover:bg-red-500"
                onClick={() => act(() => api.delete(`/admin/banners/${b.id}`), "Popup deleted")}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
};

const TermsPanel = () => {
  const { data, reload } = useFetch("/admin/terms");
  const push = async () => {
    try {
      await api.post("/admin/terms/require-reaccept");
      toast.success("All players and agents will be asked to accept the terms again");
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <div className="card-lux space-y-3 p-6" data-testid="terms-reaccept-panel">
      <p className="label-eyebrow">Terms & Conditions</p>
      <p className="text-sm text-slate-400">After you update the terms, ask everyone to accept them again. They'll see a popup they must accept before using their account.</p>
      {data && (
        <p className="text-sm text-slate-300" data-testid="terms-reaccept-stats">
          {data.reaccept_at ? <>Last requested {fmtDate(data.reaccept_at)} · <span className="text-emerald-300">{data.accepted}</span> accepted · <span className="text-amber-300">{data.pending}</span> pending</> : "No re-acceptance requested yet."}
        </p>
      )}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="outline" data-testid="terms-reaccept-button" className="w-full rounded-full border-purple-500/30 bg-transparent"><RefreshCcw className="mr-2 h-4 w-4" /> Ask all users to re-accept</Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="border-purple-500/20 bg-[#0b0816] text-slate-200">
          <AlertDialogHeader>
            <AlertDialogTitle>Ask everyone to accept the terms again?</AlertDialogTitle>
            <AlertDialogDescription>Every player and agent will have to accept the current terms the next time they open their account.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-transparent">Cancel</AlertDialogCancel>
            <AlertDialogAction data-testid="terms-reaccept-confirm" className="bg-purple-600 hover:bg-purple-500" onClick={push}>Yes, ask everyone</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default function AdminPopups() {
  const { data, reload } = useFetch("/admin/banners");
  return (
    <>
      <PageHeader eyebrow="Announcements" title="Popups & Terms" desc="Show offers or announcements as a popup when players and agents log in." />
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <div className="space-y-6">
          <NewPopup onDone={reload} />
          <TermsPanel />
        </div>
        <div className="space-y-3" data-testid="popup-list">
          {data?.length === 0 && <EmptyState text="No popups yet. Create one to show it on next login." testId="popup-empty" />}
          {data?.map((b) => <PopupRow key={b.id} b={b} reload={reload} />)}
        </div>
      </div>
    </>
  );
}
