import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

const KIND = { high_amount: "High-value deposit", velocity: "Deposit velocity", login_lockout: "Login lockout" };

export default function AdminFraud() {
  const [status, setStatus] = useState("open");
  const { data, reload } = useFetch(`/admin/fraud?status=${status}`);
  const resolve = async (a) => {
    try {
      await api.post(`/admin/fraud/${a.id}/resolve`);
      toast.success("Alert resolved");
      reload();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <>
      <PageHeader eyebrow="Fraud monitoring" title="Risk alerts" desc="Automatic rules flag high-value deposits, deposit velocity and repeated failed logins. Thresholds are set in Fee Config." />
      <Tabs value={status} onValueChange={setStatus} className="mb-5">
        <TabsList className="bg-white/[0.03]">
          {["open", "resolved", "all"].map((s) => <TabsTrigger key={s} value={s} data-testid={`admin-fraud-tab-${s}`} className="capitalize data-[state=active]:bg-purple-600 data-[state=active]:text-white">{s}</TabsTrigger>)}
        </TabsList>
      </Tabs>
      {!data?.length ? <EmptyState text="No alerts. All clear." testId="admin-fraud-empty" /> : (
        <div className="space-y-3" data-testid="admin-fraud-list">
          {data.map((a) => (
            <div key={a.id} className="card-lux flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between" data-testid={`fraud-alert-${a.id}`}>
              <div className="flex gap-4">
                <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${a.severity === "high" ? "bg-red-500/15 text-red-300" : "bg-amber-500/15 text-amber-300"}`}>
                  <AlertTriangle className="h-5 w-5" />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-white">{KIND[a.kind] || a.kind}</p>
                    <StatusBadge status={a.severity} />
                    <StatusBadge status={a.status} />
                  </div>
                  <p className="mt-1 text-sm text-slate-400">{a.message}</p>
                  <p className="mt-1 font-num text-[11px] text-slate-500">{fmtDate(a.created_at)} {a.reference && `· ${a.reference}`}</p>
                </div>
              </div>
              {a.status === "open" && (
                <Button size="sm" onClick={() => resolve(a)} data-testid={`fraud-resolve-btn-${a.id}`} className="rounded-full bg-emerald-600 hover:bg-emerald-500">
                  <CheckCircle2 className="mr-2 h-4 w-4" /> Mark resolved
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
