import { Input } from "@/components/ui/input";
import { calc, inr } from "@/lib/format";
import { ArrowDown, Sparkles, Wallet, Receipt } from "lucide-react";

const Row = ({ icon: Icon, label, value, tone, testId }) => (
  <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3">
    <span className="flex items-center gap-2.5 text-sm text-slate-300">
      <Icon className={`h-4 w-4 ${tone}`} />
      {label}
    </span>
    <span className={`font-num text-sm font-semibold ${tone}`} data-testid={testId}>
      {value}
    </span>
  </div>
);

export const CreditCalculator = ({ config, amount, onChange, testPrefix = "calc" }) => {
  const b = calc(amount, config);
  const fee = config?.fee_percent ?? 20;
  const mult = config?.promo_multiplier ?? 5;
  return (
    <div className="space-y-3">
      <label className="label-eyebrow" htmlFor={`${testPrefix}-amount`}>
        Package amount (INR)
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 font-num text-xl text-purple-300">₹</span>
        <Input
          id={`${testPrefix}-amount`}
          data-testid={`${testPrefix}-amount-input`}
          type="number"
          min={0}
          value={amount}
          onChange={(e) => onChange(e.target.value)}
          className="h-14 rounded-xl border-purple-500/30 bg-black/50 pl-10 font-num text-2xl font-semibold text-white focus-visible:ring-purple-500"
        />
      </div>
      <div className="flex justify-center py-1 text-purple-400/60">
        <ArrowDown className="h-4 w-4" />
      </div>
      <Row icon={Receipt} label={`Tech service fee (${fee}%)`} value={`− ${inr(b.fee)}`} tone="text-slate-400" testId={`${testPrefix}-fee`} />
      <Row icon={Wallet} label="Real money wallet" value={inr(b.real)} tone="text-emerald-300" testId={`${testPrefix}-real`} />
      <div className="flex items-center justify-between rounded-xl border border-purple-500/40 bg-gradient-to-r from-purple-600/20 to-fuchsia-600/10 px-4 py-4 glow-violet">
        <span className="flex items-center gap-2.5 text-sm font-medium text-purple-100">
          <Sparkles className="h-4 w-4 text-fuchsia-300" />
          Promotional credits ({mult}X)
        </span>
        <span className="font-num text-xl font-bold text-white" data-testid={`${testPrefix}-promo`}>
          {inr(b.promo)}
        </span>
      </div>
    </div>
  );
};
