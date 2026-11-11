import { ArrowDown, Award, Banknote, Dices, Gift, Sparkles, Trophy, Wallet } from "lucide-react";
import { PageHeader } from "@/components/StatCard";
import { useAuth } from "@/context/AuthContext";
import { useFetch } from "@/lib/hooks";
import { localMoney, usd } from "@/lib/format";

const Step = ({ icon: Icon, title, text, value, tone = "text-purple-300", testId }) => (
  <div className="card-lux flex items-start gap-4 p-5" data-testid={testId}>
    <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/[0.04] ${tone}`}><Icon className="h-5 w-5" /></span>
    <div className="flex-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-display font-semibold text-white">{title}</p>
        {value != null && <p className={`font-num text-lg font-semibold ${tone}`}>{value}</p>}
      </div>
      <p className="mt-1 text-sm text-slate-400">{text}</p>
    </div>
  </div>
);

const Arrow = () => <div className="flex justify-center py-1 text-purple-500/50"><ArrowDown className="h-4 w-4" /></div>;

export default function AdminMoneyFlow() {
  const { user } = useAuth();
  const { data: f } = useFetch("/admin/money-flow");
  if (!f) return null;
  return (
    <>
      <PageHeader eyebrow="How the platform works" title="Money flow"
        desc="Where money comes in, how the main balance is built, and where every bet, win and reward is taken from or added to. All figures are live, in USD." />
      <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <Step testId="flow-cash-in" icon={Banknote} tone="text-emerald-300" title="1 · Cash comes in (to you)" value={usd(f.cash_in)}
            text={`Players pay to your USDT addresses (${usd(f.cash_in_usdt)}) or your UPI ID (${usd(f.cash_in_upi)} = ${localMoney(f.cash_in_upi_inr, "INR")} at your rates). You check the payment reference in Deposits and approve it.`} />
          <Arrow />
          <Step testId="flow-credits" icon={Sparkles} title="2 · 5X credits go into the player's main balance" value={usd(f.credits_issued)}
            text="On approval the main balance is credited with 5X the deposit (e.g. $200 → $1,000). This one balance is used for everything. It can't be withdrawn." />
          <Arrow />
          <Step testId="flow-bets" icon={Dices} tone="text-red-300" title="3 · Bets are deducted from the main balance" value={usd(f.bets)}
            text="When a player plays Evolution, Ezugi or Pragmatic Play, the provider calls our wallet API (/provider/v1/bet) and the stake is deducted from the main balance instantly." />
          <Arrow />
          <Step testId="flow-wins" icon={Trophy} tone="text-emerald-300" title="4 · Wins and refunds are added back" value={usd(f.wins + f.refunds)}
            text={`The provider reports wins (/win: ${usd(f.wins)}) and cancelled bets (/rollback: ${usd(f.refunds)}). These are added back to the main balance. Outcomes are decided only by the provider.`} />
          <Arrow />
          <Step testId="flow-rewards" icon={Gift} tone="text-amber-300" title="5 · Referral income and loss rewards" value={usd(f.referral_paid + f.loss_rewards_paid)}
            text={`Referral income: 10% of every friend's deposit (${usd(f.referral_paid)} paid). Weekly loss rewards: % of net loss, paid from Loss Rewards (${usd(f.loss_rewards_paid)} paid). Both go into the main balance.`} />
        </div>
        <div className="space-y-4">
          <div className="card-lux p-6" data-testid="flow-summary">
            <p className="label-eyebrow">Platform summary</p>
            {[["Cash received", f.cash_in, "text-emerald-300"], ["Gross gaming revenue (bets − refunds − wins)", f.ggr, "text-amber-300"],
              ["Player balances outstanding", f.outstanding, "text-purple-300"], ["Manual adjustments", f.adjustments, "text-slate-300"]].map(([l, v, t]) => (
              <div key={l} className="flex items-center justify-between border-b border-white/5 py-3 last:border-0">
                <span className="text-sm text-slate-400">{l}</span><span className={`font-num font-semibold ${t}`}>{usd(v)}</span>
              </div>
            ))}
          </div>
          <div className="card-lux p-6" data-testid="flow-admin-access">
            <p className="label-eyebrow flex items-center gap-2"><Wallet className="h-3.5 w-3.5" /> Admin access</p>
            <p className="mt-3 text-sm text-slate-400">You're signed in as <span className="font-num text-white">{user?.email}</span>. Admins sign in at <span className="font-num text-purple-300">/login</span> with their email and password and land on this cockpit.</p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li>· Deposits: verify payment references and approve</li>
              <li>· Credit Config: multiplier, UPI ID, USDT addresses, currency rates, referral % and loss reward %</li>
              <li>· Game Providers: connect Evolution / Ezugi / Pragmatic and hand them the wallet API key</li>
              <li>· Loss Rewards: pay the weekly loss-back</li>
            </ul>
          </div>
          <div className="card-lux p-6"><p className="label-eyebrow flex items-center gap-2"><Award className="h-3.5 w-3.5" /> No withdrawals</p>
            <p className="mt-2 text-sm text-slate-400">Credits stay on the platform for play only. There is no withdrawal option for players.</p></div>
        </div>
      </div>
    </>
  );
}
