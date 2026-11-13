import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Coins, Share2, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";

export const inr = (n) => `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
export const cr = (n) => `${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })} cr`;

export const RivalsWallets = ({ wallets }) => (
  <div className="mb-6 grid gap-3 sm:grid-cols-2" data-testid="rivals-wallets">
    <div className="card-lux flex items-center gap-3 border-fuchsia-500/30 px-4 py-3">
      <Coins className="h-5 w-5 text-fuchsia-300" />
      <div>
        <p className="text-[11px] uppercase tracking-wider text-slate-500">Scarmenta wallet (credits)</p>
        <p className="font-num text-xl font-bold text-fuchsia-200" data-testid="rivals-wallet-scarmenta">{cr(wallets.scarmenta)}</p>
      </div>
    </div>
    <div className="card-lux flex items-center gap-3 border-sky-500/30 px-4 py-3">
      <Wallet className="h-5 w-5 text-sky-300" />
      <div>
        <p className="text-[11px] uppercase tracking-wider text-slate-500">Others wallet (real ₹)</p>
        <p className="font-num text-xl font-bold text-sky-200" data-testid="rivals-wallet-others">{inr(wallets.others)}</p>
      </div>
    </div>
  </div>
);

export const RefillDialog = ({ open, onClose, onRefill }) => {
  const navigate = useNavigate();
  const share = async () => {
    try {
      const { data: r } = await api.get("/referrals/me");
      const msg = `Join me on Scarmenta and get 5X credits on your deposit. Use my code ${r.code}: ${r.link}`;
      window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, "_blank", "noopener");
      onRefill();
      toast.success("Demo wallets refilled. Thanks for sharing!");
    } catch {
      toast.error("Could not load your referral link");
    }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="rivals-refill-dialog" className="max-w-md border-purple-500/20 bg-[#0b0816] text-slate-200">
        <DialogTitle className="font-display text-2xl text-white">Not enough demo balance</DialogTitle>
        <DialogDescription className="text-sm text-slate-400">
          Share your referral link on WhatsApp to refill both demo wallets (5,000 credits + ₹5,000), or make a real deposit to get 5X credits.
        </DialogDescription>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <Button onClick={share} data-testid="rivals-refill-share" className="flex-1 rounded-full bg-emerald-600 hover:bg-emerald-500"><Share2 className="mr-2 h-4 w-4" /> Share & refill</Button>
          <Button onClick={() => navigate("/app/deposits")} data-testid="rivals-refill-deposit" className="flex-1 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold">Deposit</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const RivalsResult = ({ result, mult }) => {
  if (!result) return <div className="h-20" data-testid="demo-result" />;
  const { winner, bets, change, creditCost, net } = result;
  const sc = bets.scarmenta || 0;
  const ot = bets.others || 0;
  return (
    <div className="min-h-20 space-y-0.5 text-center text-xs sm:text-sm" data-testid="demo-result">
      <p className="text-sm font-semibold text-emerald-300">{winner === "scarmenta" ? "Scarmenta wins" : "Others win"}</p>
      {sc > 0 && <p className={change.scarmenta >= 0 ? "text-fuchsia-200" : "text-red-300"} data-testid="rivals-result-scarmenta">Scarmenta {change.scarmenta >= 0 ? "+" : "−"}{cr(sc)}</p>}
      {ot > 0 && <p className={change.others >= 0 ? "text-sky-200" : "text-red-300"} data-testid="rivals-result-others">Others {change.others >= 0 ? "+" : "−"}{inr(ot)}{winner === "others" ? " profit" : ""}</p>}
      {winner === "others" && sc > 0 && ot > 0 && (
        <p className="text-slate-400" data-testid="rivals-result-cost">− {inr(creditCost)} paid for {cr(sc)} (1/{mult})</p>
      )}
      {sc > 0 && ot > 0 && (
        <p className={`font-num text-sm font-bold ${net >= 0 ? "text-emerald-300" : "text-red-300"}`} data-testid="demo-result-net">Net {net >= 0 ? "profit" : "loss"} {inr(Math.abs(net))}</p>
      )}
    </div>
  );
};
