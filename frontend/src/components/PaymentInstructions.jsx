import { toast } from "sonner";
import { Copy } from "lucide-react";
import { Input } from "@/components/ui/input";
import { localMoney } from "@/lib/format";

const NETWORKS = ["TRC20", "ERC20", "BEP20"];

const CopyRow = ({ label, value, testId }) => (
  <div className="rounded-xl border border-purple-500/25 bg-black/40 px-4 py-3">
    <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
    <div className="mt-1 flex items-center justify-between gap-3">
      <p className="break-all font-num text-sm text-white" data-testid={testId}>{value}</p>
      <button type="button" data-testid={`${testId}-copy`} onClick={() => { navigator.clipboard.writeText(value).catch(() => {}); toast.success("Copied"); }}
        className="shrink-0 rounded-lg p-1.5 text-purple-300 transition-colors hover:bg-purple-500/15"><Copy className="h-4 w-4" /></button>
    </div>
  </div>
);

export const PaymentInstructions = ({ config, method, network, setNetwork, amount, reference, setReference }) => {
  const pay = config?.payment || { usdt: {} };
  const rate = config?.fx_rates?.INR;
  const usdtAddr = pay.usdt?.[network];
  const available = method === "usdt" ? !!usdtAddr : !!(pay.upi_id && rate);
  return (
    <div className="space-y-3" data-testid="payment-instructions">
      {method === "usdt" && (
        <div className="flex gap-2">
          {NETWORKS.map((n) => (
            <button key={n} type="button" data-testid={`deposit-network-${n}`} onClick={() => setNetwork(n)}
              className={`flex-1 rounded-full border px-3 py-1.5 font-num text-xs transition-colors ${network === n ? "border-purple-400 bg-purple-500/20 text-white" : "border-white/10 text-slate-400 hover:border-purple-500/40"}`}>
              {n}
            </button>
          ))}
        </div>
      )}
      {!available ? (
        <p data-testid="payment-unavailable" className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200">
          {method === "usdt" ? `USDT ${network}` : "UPI"} deposits are not available yet. Please choose another option.
        </p>
      ) : (
        <>
          {method === "usdt" ? (
            <>
              <CopyRow label={`Send exactly ${Number(amount || 0).toFixed(2)} USDT (${network}) to`} value={usdtAddr} testId="deposit-pay-to" />
              <p className="text-[11px] text-slate-500">Only send USDT on the {network} network. Wrong-network transfers cannot be recovered.</p>
            </>
          ) : (
            <>
              <CopyRow label={`Pay ${localMoney((Number(amount) || 0) * rate, "INR")} by UPI to`} value={pay.upi_id} testId="deposit-pay-to" />
              <p className="text-[11px] text-slate-500" data-testid="deposit-fx-rate">Today's rate: $1 = ₹{rate}. Set by the platform and may change.</p>
            </>
          )}
          <label htmlFor="deposit-reference" className="label-eyebrow block pt-1">{method === "usdt" ? "Transaction hash (TX ID)" : "UPI UTR / reference number"}</label>
          <Input id="deposit-reference" data-testid="deposit-reference-input" value={reference} onChange={(e) => setReference(e.target.value)}
            placeholder={method === "usdt" ? "Paste the transaction hash (TX ID)" : "Enter the 12-digit UPI UTR number"}
            className="h-11 border-purple-500/25 bg-black/40 font-num" />
        </>
      )}
    </div>
  );
};

export const paymentAvailable = (config, method, network) =>
  method === "usdt" ? !!config?.payment?.usdt?.[network] : !!(config?.payment?.upi_id && config?.fx_rates?.INR);
