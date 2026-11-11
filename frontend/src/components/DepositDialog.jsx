import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CreditCalculator } from "@/components/CreditCalculator";
import { api, formatApiError } from "@/lib/api";
import { METHODS, usd } from "@/lib/format";
import { PaymentInstructions, paymentAvailable } from "@/components/PaymentInstructions";

export const DepositDialog = ({ open, onOpenChange, config, presetAmount, onDone }) => {
  const [amount, setAmount] = useState(200);
  const [method, setMethod] = useState("usdt");
  const [network, setNetwork] = useState("TRC20");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setAmount(presetAmount || 200);
      setReference("");
      setBusy(false);
    }
  }, [open, presetAmount]);

  const submit = async () => {
    setBusy(true);
    try {
      const body = { amount: Number(amount), method, payment_reference: reference.trim(), network: method === "usdt" ? network : null };
      const { data } = await api.post("/deposits", body);
      toast.success(`Deposit ${data.reference} submitted`, { description: "We'll verify your payment and add the credits once it's approved." });
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
          <DialogTitle className="font-display text-2xl text-white">Buy a credit package</DialogTitle>
          <DialogDescription className="text-slate-400">
            Pay with USDT (any country) or UPI (India). Enter your payment reference and we'll add the credits once it's verified.
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
                {usd(p)}
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
        <PaymentInstructions config={config} method={method} network={network} setNetwork={setNetwork} amount={amount} reference={reference} setReference={setReference} />
        {config && (
          <p className="text-[11px] text-slate-500">
            Limits: {usd(config.min_deposit)} – {usd(config.max_deposit)} per deposit. Prepaid credits are non-refundable and cannot be withdrawn.
          </p>
        )}
        <Button
          data-testid="deposit-submit-button"
          disabled={busy || !Number(amount) || reference.trim().length < 6 || !paymentAvailable(config, method, network)}
          onClick={submit}
          className="h-12 w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 text-base font-semibold hover:from-violet-500 hover:to-fuchsia-500"
        >
          {busy ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting…
            </>
          ) : (
            <>
              <ShieldCheck className="mr-2 h-4 w-4" /> I've paid {usd(amount)}, submit
            </>
          )}
        </Button>
      </DialogContent>
    </Dialog>
  );
};
