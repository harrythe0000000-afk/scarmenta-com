import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/StatCard";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { calc, usd } from "@/lib/format";

const SliderField = ({ label, value, min, max, step, suffix, onChange, testId }) => (
  <div className="card-lux p-6">
    <div className="flex items-baseline justify-between">
      <p className="text-sm font-medium text-slate-300">{label}</p>
      <p className="font-num text-3xl font-semibold text-white" data-testid={`${testId}-value`}>{value}{suffix}</p>
    </div>
    <Slider data-testid={testId} className="mt-6" value={[value]} min={min} max={max} step={step} onValueChange={([v]) => onChange(v)} />
    <div className="mt-2 flex justify-between font-num text-[11px] text-slate-600"><span>{min}{suffix}</span><span>{max}{suffix}</span></div>
  </div>
);

const NumField = ({ label, value, onChange, testId }) => (
  <div>
    <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
    <Input type="number" data-testid={testId} value={value} onChange={(e) => onChange(e.target.value)} className="border-purple-500/20 bg-black/40 font-num" />
  </div>
);

const TextField = ({ label, value, onChange, testId, placeholder }) => (
  <div>
    <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
    <Input data-testid={testId} value={value || ""} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} className="border-purple-500/20 bg-black/40 font-num text-xs" />
  </div>
);

const toRows = (fx) => Object.entries(fx || {}).map(([code, rate]) => ({ code, rate }));

const FxRatesCard = ({ rates, setRates }) => {
  const upd = (i, k, v) => setRates(rates.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="card-lux space-y-3 p-6 lg:col-span-2" data-testid="fx-rates-card">
      <div className="flex items-center justify-between">
        <p className="label-eyebrow">Currency rates (local currency per $1)</p>
        <Button size="sm" variant="outline" data-testid="fx-add-button" onClick={() => setRates([...rates, { code: "", rate: "" }])} className="rounded-full border-purple-500/30 bg-transparent hover:bg-purple-500/10"><Plus className="mr-1 h-3.5 w-3.5" /> Add currency</Button>
      </div>
      <p className="text-xs text-slate-500">INR is used for UPI deposits: e.g. 95 means a player pays ₹95 for every $1. Update these whenever the market rate changes.</p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {rates.map((r, i) => (
          <div key={i} className="flex items-center gap-2 rounded-xl border border-white/5 bg-black/30 p-2" data-testid={`fx-row-${i}`}>
            <span className="pl-1 font-num text-xs text-slate-500">$1 =</span>
            <Input data-testid={`fx-rate-${i}`} type="number" value={r.rate} onChange={(e) => upd(i, "rate", e.target.value)} className="h-9 border-purple-500/20 bg-black/40 font-num" />
            <Input data-testid={`fx-code-${i}`} value={r.code} onChange={(e) => upd(i, "code", e.target.value.toUpperCase())} className="h-9 w-20 border-purple-500/20 bg-black/40 font-num" />
            <button type="button" data-testid={`fx-remove-${i}`} onClick={() => setRates(rates.filter((_, j) => j !== i))} className="rounded-md p-1 text-slate-500 hover:text-red-300"><X className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default function AdminSettings() {
  const { data } = useFetch("/admin/settings");
  const [s, setS] = useState(null);
  const [pkgText, setPkgText] = useState("");
  const [busy, setBusy] = useState(false);
  const [rates, setRates] = useState([]);
  useEffect(() => {
    if (data) {
      setS(data);
      setPkgText(data.packages.join(", "));
      setRates(toRows(data.fx_rates));
    }
  }, [data]);
  if (!s) return null;
  const set = (k) => (v) => setS({ ...s, [k]: v });
  const example = calc(200, s);

  const save = async () => {
    setBusy(true);
    try {
      const packages = pkgText.split(",").map((x) => Number(x.trim())).filter((x) => x > 0);
      const { fee_percent, ...rest } = s;
      const body = { ...rest, packages, min_deposit: Number(s.min_deposit), max_deposit: Number(s.max_deposit),
        fraud_amount_threshold: Number(s.fraud_amount_threshold), fraud_velocity_count: Number(s.fraud_velocity_count), referral_bonus_percent: Number(s.referral_bonus_percent),
        loss_reward_percent: Number(s.loss_reward_percent), transfer_fee_percent: Number(s.transfer_fee_percent), share_bonus_amount: Number(s.share_bonus_amount ?? 0),
        fx_rates: Object.fromEntries(rates.filter((r) => r.code.trim()).map((r) => [r.code.trim().toUpperCase(), Number(r.rate)])) };
      const { data: saved } = await api.put("/admin/settings", body);
      setS(saved);
      setPkgText(saved.packages.join(", "));
      setRates(toRows(saved.fx_rates));
      toast.success("Configuration saved — applies to new deposits");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Credit configuration" title="Credit engine settings" desc="Changes apply to deposits created after saving. Existing deposits keep the terms they were created with."
        action={<Button data-testid="settings-save-button" disabled={busy} onClick={save} className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6"><Save className="mr-2 h-4 w-4" /> Save changes</Button>} />
      <div className="grid gap-5 lg:grid-cols-2">
        <SliderField label="Credit multiplier" value={s.promo_multiplier} min={1} max={10} step={0.5} suffix="X" onChange={set("promo_multiplier")} testId="multiplier-config-slider" />
        <div className="card-lux p-6" data-testid="settings-preview">
          <p className="label-eyebrow">Live preview · $200 deposit</p>
          <p className="mt-6 text-xs text-slate-500">Player credit balance</p>
          <p className="font-num text-3xl font-semibold text-purple-300">{usd(example.credits)}</p>
          <p className="mt-2 text-xs text-slate-500">No service fee is charged.</p>
        </div>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="card-lux space-y-4 p-6">
          <p className="label-eyebrow">Deposit limits & packages</p>
          <div className="grid grid-cols-2 gap-3">
            <NumField label="Min deposit ($)" value={s.min_deposit} onChange={set("min_deposit")} testId="settings-min-deposit" />
            <NumField label="Max deposit ($)" value={s.max_deposit} onChange={set("max_deposit")} testId="settings-max-deposit" />
          </div>
          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Packages ($, comma separated)</p>
            <Input data-testid="settings-packages-input" value={pkgText} onChange={(e) => setPkgText(e.target.value)} className="border-purple-500/20 bg-black/40 font-num" />
          </div>
        </div>
        <div className="card-lux space-y-4 p-6">
          <p className="label-eyebrow">Fraud rules</p>
          <NumField label="Flag deposits at or above ($)" value={s.fraud_amount_threshold} onChange={set("fraud_amount_threshold")} testId="settings-fraud-threshold" />
          <NumField label="Flag when deposits in 24h reach" value={s.fraud_velocity_count} onChange={set("fraud_velocity_count")} testId="settings-fraud-velocity" />
        </div>
        <div className="card-lux space-y-4 p-6">
          <p className="label-eyebrow">Refer & earn · Loss rewards</p>
          <NumField label="Referral income (% of every friend's deposit)" value={s.referral_bonus_percent} onChange={set("referral_bonus_percent")} testId="settings-referral-bonus" />
          <NumField label="Weekly loss reward (% of a player's net loss)" value={s.loss_reward_percent} onChange={set("loss_reward_percent")} testId="settings-loss-reward" />
          <NumField label="Account transfer fee (%)" value={s.transfer_fee_percent} onChange={set("transfer_fee_percent")} testId="settings-transfer-fee" />
          <NumField label="Share bonus ($ credits per friend who joins from a calculator image and deposits)" value={s.share_bonus_amount ?? 0} onChange={set("share_bonus_amount")} testId="settings-share-bonus" />
          <p className="text-xs text-slate-500">Set any of these to 0 to switch it off.</p>
          <label className="flex items-center justify-between rounded-xl border border-white/10 px-4 py-3 text-sm text-slate-300">
            Email owner & staff when a new deposit is waiting
            <Switch data-testid="settings-deposit-alerts-switch" checked={!!s.deposit_alerts} onCheckedChange={(v) => setS({ ...s, deposit_alerts: v })} />
          </label>
        </div>
        <div className="card-lux space-y-4 p-6">
          <p className="label-eyebrow">Where players pay you</p>
          <TextField label="UPI ID (India)" value={s.upi_id} onChange={set("upi_id")} testId="settings-upi-id" placeholder="yourbusiness@bank" />
          <TextField label="USDT TRC20 address" value={s.usdt_trc20} onChange={set("usdt_trc20")} testId="settings-usdt-trc20" />
          <TextField label="USDT ERC20 address" value={s.usdt_erc20} onChange={set("usdt_erc20")} testId="settings-usdt-erc20" />
          <TextField label="USDT BEP20 address" value={s.usdt_bep20} onChange={set("usdt_bep20")} testId="settings-usdt-bep20" />
          <p className="text-xs text-slate-500">Leave a field empty to hide that payment option from players.</p>
        </div>
        <FxRatesCard rates={rates} setRates={setRates} />
      </div>
    </>
  );
}
