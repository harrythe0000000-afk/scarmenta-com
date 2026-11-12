import { useState } from "react";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { useAuth } from "@/context/AuthContext";
import { contestImg } from "@/pages/user/Contest";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const act = async (fn, msg, after) => {
  try {
    await fn();
    toast.success(msg);
    after();
  } catch (e) {
    toast.error(formatApiError(e));
  }
};

const EntryCard = ({ e, canPay, reload, onZoom }) => {
  const [amount, setAmount] = useState("10");
  return (
    <div className="card-lux overflow-hidden" data-testid={`admin-contest-entry-${e.id}`}>
      <button type="button" onClick={() => onZoom(e)} className="block w-full" data-testid={`admin-contest-zoom-${e.id}`}>
        <img src={contestImg(e.id)} alt="" className="h-48 w-full object-cover transition-transform hover:scale-[1.02]" />
      </button>
      <div className="space-y-2 p-4">
        <p className="font-semibold text-white">{e.name}</p>
        <p className="text-xs text-slate-500">{e.user_email} · {fmtDate(e.created_at)}</p>
        {e.caption && <p className="text-sm text-slate-300">“{e.caption}”</p>}
        {e.status === "winner" && <p className="text-sm text-emerald-300">Paid {usd(e.bonus)}</p>}
        {e.status === "rejected" && <p className="text-sm text-slate-400">Rejected{e.note ? `: ${e.note}` : ""}</p>}
        {e.status === "pending" && (
          <div className="flex gap-2 pt-1">
            {canPay && (
              <>
                <div className="relative w-24">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">$</span>
                  <Input type="number" min="0.01" step="0.01" value={amount} onChange={(ev) => setAmount(ev.target.value)} data-testid={`admin-contest-amount-${e.id}`} className="border-purple-500/20 bg-black/40 pl-6 font-num" />
                </div>
                <Button size="sm" data-testid={`admin-contest-win-${e.id}`} className="flex-1 rounded-full bg-emerald-600 hover:bg-emerald-500"
                  onClick={() => act(() => api.post(`/admin/contest/entries/${e.id}/win`, { amount: Number(amount) }), `Paid ${usd(Number(amount))} bonus`, reload)}>
                  <Check className="mr-1 h-4 w-4" /> Winner
                </Button>
              </>
            )}
            <Button size="sm" variant="outline" data-testid={`admin-contest-reject-${e.id}`} className="rounded-full border-red-500/30 bg-transparent text-red-300"
              onClick={() => act(() => api.post(`/admin/contest/entries/${e.id}/reject`, {}), "Entry rejected", reload)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default function AdminContest() {
  const { user } = useAuth();
  const [status, setStatus] = useState("pending");
  const [zoom, setZoom] = useState(null);
  const { data, reload } = useFetch(`/admin/contest/entries?status=${status}`);
  return (
    <>
      <PageHeader eyebrow="Growth" title="Promo contest" desc="Review players' share screenshots and pick winners for bonus credits. Credits are added to the winner's balance right away." />
      <Tabs value={status} onValueChange={setStatus}>
        <TabsList className="mb-6 bg-black/40" data-testid="admin-contest-tabs">
          {["pending", "winner", "rejected"].map((s) => (
            <TabsTrigger key={s} value={s} data-testid={`admin-contest-tab-${s}`} className="capitalize">{s === "winner" ? "Winners" : s} ({data?.counts?.[s] ?? 0})</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {data && (data.entries.length === 0 ? <EmptyState text="Nothing here yet." testId="admin-contest-empty" /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="admin-contest-grid">
          {data.entries.map((e) => <EntryCard key={e.id} e={e} canPay={user?.role === "admin"} reload={reload} onZoom={setZoom} />)}
        </div>
      ))}
      <Dialog open={!!zoom} onOpenChange={(o) => !o && setZoom(null)}>
        <DialogContent className="max-w-2xl border-purple-500/20 bg-[#0b0816]" data-testid="admin-contest-zoom-dialog">
          <DialogTitle className="text-white">{zoom?.name}</DialogTitle>
          <DialogDescription className="text-slate-400">{zoom?.caption || "No caption"}</DialogDescription>
          {zoom && <img src={contestImg(zoom.id)} alt="" className="max-h-[70vh] w-full rounded-lg object-contain" />}
        </DialogContent>
      </Dialog>
    </>
  );
}
