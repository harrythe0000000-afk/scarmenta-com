import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { PageHeader } from "@/components/StatCard";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { calc, inr } from "@/lib/format";

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

export default function AdminSettings() {
  const { data } = useFetch("/admin/settings");
  const [s, setS] = useState(null);
  const [pkgText, setPkgText] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (data) {
      setS(data);
      setPkgText(data.packages.join(", "));
    }
  }, [data]);
  if (!s) return null;
  const set = (k) => (v) => setS({ ...s, [k]: v });
  const example = calc(20000, s);

  const save = async () => {
    setBusy(true);
    try {
      const packages = pkgText.split(",").map((x) => Number(x.trim())).filter((x) => x > 0);
      const { fee_percent, ...rest } = s;
      const body = { ...rest, packages, min_deposit: Number(s.min_deposit), max_deposit: Number(s.max_deposit),
        fraud_amount_threshold: Number(s.fraud_amount_threshold), fraud_velocity_count: Number(s.fraud_velocity_count) };
      const { data: saved } = await api.put("/admin/settings", body);
      setS(saved);
      setPkgText(saved.packages.join(", "));
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
          <p className="label-eyebrow">Live preview · ₹20,000 deposit</p>
          <p className="mt-6 text-xs text-slate-500">Player credit balance</p>
          <p className="font-num text-3xl font-semibold text-purple-300">{inr(example.credits)}</p>
          <p className="mt-2 text-xs text-slate-500">No service fee is charged.</p>
        </div>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="card-lux space-y-4 p-6">
          <p className="label-eyebrow">Deposit limits & packages</p>
          <div className="grid grid-cols-2 gap-3">
            <NumField label="Min deposit (₹)" value={s.min_deposit} onChange={set("min_deposit")} testId="settings-min-deposit" />
            <NumField label="Max deposit (₹)" value={s.max_deposit} onChange={set("max_deposit")} testId="settings-max-deposit" />
          </div>
          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Packages (₹, comma separated)</p>
            <Input data-testid="settings-packages-input" value={pkgText} onChange={(e) => setPkgText(e.target.value)} className="border-purple-500/20 bg-black/40 font-num" />
          </div>
        </div>
        <div className="card-lux space-y-4 p-6">
          <p className="label-eyebrow">Fraud rules</p>
          <NumField label="Flag deposits at or above (₹)" value={s.fraud_amount_threshold} onChange={set("fraud_amount_threshold")} testId="settings-fraud-threshold" />
          <NumField label="Flag when deposits in 24h reach" value={s.fraud_velocity_count} onChange={set("fraud_velocity_count")} testId="settings-fraud-velocity" />
        </div>
      </div>
    </>
  );
}
