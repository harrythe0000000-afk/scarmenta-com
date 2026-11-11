import { Input } from "@/components/ui/input";
import { calc, inr } from "@/lib/format";
import { ArrowDown, Sparkles } from "lucide-react";

export const CreditCalculator = ({ config, amount, onChange, testPrefix = "calc" }) => {
  const b = calc(amount, config);
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
      <div className="flex items-center justify-between rounded-xl border border-purple-500/40 bg-gradient-to-r from-purple-600/20 to-fuchsia-600/10 px-4 py-5 glow-violet">
        <span className="flex items-center gap-2.5 text-sm font-medium text-purple-100">
          <Sparkles className="h-4 w-4 text-fuchsia-300" />
          Your credit balance ({mult}X)
        </span>
        <span className="font-num text-2xl font-bold text-white" data-testid={`${testPrefix}-credits`}>
          {inr(b.credits)}
        </span>
      </div>
      <p className="text-center text-[11px] text-slate-500">No service fees · Credits are non-withdrawable</p>
    </div>
  );
};
