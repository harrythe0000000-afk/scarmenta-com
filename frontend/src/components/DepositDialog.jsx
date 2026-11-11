import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CreditCalculator } from "@/components/CreditCalculator";
import { api, formatApiError } from "@/lib/api";
import { METHODS, inr } from "@/lib/format";

export const DepositDialog = ({ open, onOpenChange, config, presetAmount, onDone }) => {
  const [amount, setAmount] = useState(20000);
  const [method, setMethod] = useState("upi");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setAmount(presetAmount || 20000);
      setBusy(false);
    }
  }, [open, presetAmount]);

  const submit = async () => {
    setBusy(true);
    await new Promise((r) => setTimeout(r, 1200));
    try {
      const { data } = await api.post("/deposits", { amount: Number(amount), method });
      toast.success(`Deposit ${data.reference} submitted`, { description: "Awaiting compliance approval before credits are allocated." });
      onOpenChange(false);
      onDone?.();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !busy && onOpenChange(v)}>
      <DialogContent data-testid="deposit-dialog" className="max-h-[92vh] overflow-y-auto border-purple-500/30 bg-[#0b0817] sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl text-white">Purchase credit package</DialogTitle>
          <DialogDescription className="text-slate-400">
            Simulated payment gateway — no real money moves. Deposits are reviewed before allocation.
          </DialogDescription>
        </DialogHeader>
        {config && (
          <div className="flex flex-wrap gap-2">
            {config.packages.map((p) => (
              <button
                key={p}
                type="button"
                data-testid={`deposit-preset-${p}`}
                onClick={() => setAmount(p)}
                className={`rounded-full border px-3 py-1.5 font-num text-xs transition-colors ${
                  Number(amount) === p ? "border-purple-400 bg-purple-500/20 text-white" : "border-white/10 text-slate-400 hover:border-purple-500/40"
                }`}
              >
                {inr(p)}
              </button>
            ))}
          </div>
        )}
        <CreditCalculator config={config} amount={amount} onChange={setAmount} testPrefix="deposit" />
        <div className="space-y-2">
          <p className="label-eyebrow">Payment method</p>
          <div className="grid grid-cols-2 gap-2">
            {METHODS.map((m) => (
              <button
                key={m.value}
                type="button"
                data-testid={`deposit-method-${m.value}`}
                onClick={() => setMethod(m.value)}
                className={`rounded-xl border px-3 py-2.5 text-left transition-colors ${
                  method === m.value ? "border-purple-400 bg-purple-500/15" : "border-white/10 bg-white/[0.02] hover:border-purple-500/40"
                }`}
              >
                <span className="block text-sm font-semibold text-white">{m.label}</span>
                <span className="block text-[11px] text-slate-500">{m.hint}</span>
              </button>
            ))}
          </div>
        </div>
        {config && (
          <p className="text-[11px] text-slate-500">
            Limits: {inr(config.min_deposit)} – {inr(config.max_deposit)} per deposit. Prepaid credits are non-refundable and cannot be withdrawn.
          </p>
        )}
        <Button
          data-testid="deposit-submit-button"
          disabled={busy || !Number(amount)}
          onClick={submit}
          className="h-12 w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 text-base font-semibold hover:from-violet-500 hover:to-fuchsia-500"
        >
          {busy ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Processing via gateway…
            </>
          ) : (
            <>
              <ShieldCheck className="mr-2 h-4 w-4" /> Pay {inr(amount)}
            </>
          )}
        </Button>
      </DialogContent>
    </Dialog>
  );
};
