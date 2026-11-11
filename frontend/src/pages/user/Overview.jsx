import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Clock, Coins, Plus, Sparkles, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DepositDialog } from "@/components/DepositDialog";
import { PageHeader, StatCard } from "@/components/StatCard";
import { TxTable } from "@/components/TxTable";
import { useAuth } from "@/context/AuthContext";
import { useConfig, useFetch } from "@/lib/hooks";
import { calc, inr } from "@/lib/format";

const CreditBalanceCard = ({ value, mult, testId }) => (
  <div data-testid={testId} className="relative overflow-hidden rounded-2xl border border-purple-500/40 bg-gradient-to-b from-purple-900/30 to-[#05040A] p-8 glow-violet fade-up">
    <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-fuchsia-500/20 blur-3xl" />
    <div className="relative flex items-center justify-between">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-purple-300">Credit balance</p>
      <Sparkles className="h-5 w-5 text-fuchsia-300" />
    </div>
    <p className="relative mt-6 font-num text-5xl font-semibold tracking-tight text-white sm:text-6xl" data-testid={`${testId}-value`}>{value == null ? "—" : inr(value)}</p>
    <p className="relative mt-2 text-xs text-slate-500">{mult ?? 5}X of every cash deposit · No service fees · Non-withdrawable</p>
  </div>
);

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

      <CreditBalanceCard value={w?.balance} mult={config?.promo_multiplier} testId="credit-balance-card" />

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Cash deposited" value={inr(w?.total_deposited)} icon={TrendingUp} testId="stat-total-deposited" />
        <StatCard label="Credits received" value={inr(w?.total_credits)} icon={Coins} tone="amber" testId="stat-total-credits" />
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
                <p className="mt-3 text-[11px] uppercase tracking-wider text-slate-500">Get credits</p>
                <p className="font-num text-sm font-semibold text-purple-300">{inr(b.credits)}</p>
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
