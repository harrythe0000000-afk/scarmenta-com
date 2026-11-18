import { AlertTriangle } from "lucide-react";
import { useFetch } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

export const GgrAlert = () => {
  const { data } = useFetch("/admin/live/ggr-alert");
  if (!data?.at) return null;
  const ip = data.kind === "ip";
  return (
    <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 px-5 py-4" data-testid="ggr-alert">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
      <div className="text-sm">
        <p className="font-semibold text-red-200" data-testid="ggr-alert-title">{ip ? "InfinityAPI is blocking this server's IP — players cannot open live games" : "InfinityAPI GGR wallet is empty — players cannot open live games"}</p>
        {ip
          ? <p className="mt-1 text-red-200/70" data-testid="ggr-alert-message">Blocked IP: <span className="font-num font-bold text-white" data-testid="ggr-alert-ip">{data.ip || "see Launch history"}</span> · since {fmtDate(data.at)}. Add exactly this IP to the whitelist in the InfinityAPI panel (keep the old ones). This warning clears on the next successful launch or provider test.</p>
          : <p className="mt-1 text-red-200/70" data-testid="ggr-alert-message">"{data.message}" · since {fmtDate(data.at)}. Recharge your GGR balance in the InfinityAPI panel. This warning clears on the next successful launch or provider test.</p>}
      </div>
    </div>
  );
};
