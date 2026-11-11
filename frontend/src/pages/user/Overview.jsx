import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Clock, Plus, Receipt, Sparkles, TrendingUp, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DepositDialog } from "@/components/DepositDialog";
import { PageHeader, StatCard } from "@/components/StatCard";
import { TxTable } from "@/components/TxTable";
import { useAuth } from "@/context/AuthContext";
import { useConfig, useFetch } from "@/lib/hooks";
import { calc, inr } from "@/lib/format";

const WalletCard = ({ kind, value, testId }) => {
  const real = kind === "real";
  return (
    <div data-testid={testId} className={`relative overflow-hidden rounded-2xl border p-7 fade-up ${real ? "border-emerald-500/30 bg-gradient-to-b from-emerald-950/30 to-[#05040A]" : "border-purple-500/40 bg-gradient-to-b from-purple-900/30 to-[#05040A] glow-violet d-1"}`}>
      <div className={`absolute -right-16 -top-16 h-48 w-48 rounded-full blur-3xl ${real ? "bg-emerald-500/10" : "bg-fuchsia-500/20"}`} />
      <div className="relative flex items-center justify-between">
        <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${real ? "text-emerald-300" : "text-purple-300"}`}>
          {real ? "Real money wallet" : "Promotional credit wallet"}
        </p>
        {real ? <Wallet className="h-5 w-5 text-emerald-300" /> : <Sparkles className="h-5 w-5 text-fuchsia-300" />}
      </div>
      <p className="relative mt-6 font-num text-4xl font-semibold tracking-tight text-white sm:text-5xl" data-testid={`${testId}-value`}>{inr(value)}</p>
      <p className="relative mt-2 text-xs text-slate-500">{real ? "Net of technology service fees · Non-withdrawable" : "Allocated at the published promo multiplier · Non-withdrawable"}</p>
    </div>
  );
};

export default function UserOverview() {
  const { user } = useAuth();
  const config = useConfig();
  const { data: w, reload } = useFetch("/wallet");
  const { data: txs, reload: reloadTx } = useFetch("/transactions");
  const [open, setOpen] = useState(false);
  const [preset, setPreset] = useState(null);
  const buy = (p) => { setPreset(p); setOpen(true); };

  return (
    <>
      <PageHeader eyebrow="Player account" title={`Hello, ${user?.name?.split(" ")[0] || ""}`} desc="Your balances, credit packages and latest ledger activity."
        action={<Button data-testid="deposit-modal-open-button" onClick={() => buy(null)} className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 hover:from-violet-500 hover:to-fuchsia-500"><Plus className="mr-2 h-4 w-4" /> New deposit</Button>} />

      <div className="grid gap-5 md:grid-cols-2">
        <WalletCard kind="real" value={w?.real_balance} testId="real-wallet-balance-card" />
        <WalletCard kind="promo" value={w?.promo_balance} testId="promo-credit-balance-card" />
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Total deposited" value={inr(w?.total_deposited)} icon={TrendingUp} testId="stat-total-deposited" />
        <StatCard label="Service fees paid" value={inr(w?.total_fees)} icon={Receipt} tone="amber" testId="stat-total-fees" />
        <StatCard label="Pending deposits" value={w?.pending_count ?? 0} icon={Clock} tone="emerald" testId="stat-pending-deposits" sub="Awaiting compliance review" />
      </div>

      <section className="mt-12">
        <p className="label-eyebrow">Credit packages</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {(config?.packages || []).map((p) => {
            const b = calc(p, config);
            return (
              <button key={p} type="button" onClick={() => buy(p)} data-testid={`buy-package-${p}`}
                className="card-lux group p-5 text-left hover:-translate-y-0.5">
                <p className="font-num text-xl font-semibold text-white">{inr(p)}</p>
                <p className="mt-3 text-[11px] uppercase tracking-wider text-slate-500">Get promo</p>
                <p className="font-num text-sm font-semibold text-purple-300">{inr(b.promo)}</p>
                <span className="mt-4 flex items-center gap-1 text-xs text-slate-400 transition-colors group-hover:text-white">Purchase <ArrowRight className="h-3 w-3" /></span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mt-12">
        <div className="mb-4 flex items-center justify-between">
          <p className="label-eyebrow">Recent activity</p>
          <Link to="/app/statement" className="text-xs text-purple-300 hover:text-purple-200" data-testid="view-statement-link">Full statement →</Link>
        </div>
        <TxTable rows={txs?.slice(0, 6)} testId="recent-tx-table" />
      </section>

      <DepositDialog open={open} onOpenChange={setOpen} config={config} presetAmount={preset} onDone={() => { reload(); reloadTx(); }} />
    </>
  );
}
