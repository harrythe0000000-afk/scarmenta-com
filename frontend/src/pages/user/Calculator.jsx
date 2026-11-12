import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Info } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/StatCard";

const UNITS = [["days", "Days", 1], ["weeks", "Weeks", 7], ["months", "Months", 30], ["years", "Years", 365]];
const PRESETS = [[10, "days"], [20, "days"], [30, "days"], [6, "months"], [1, "years"], [500, "days"]];
const MAX_DAYS = 3650;
const money = (n) => (n >= 1e12 ? `$${n.toExponential(2)}` : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }));
const compact = (n) => (n >= 1e12 ? n.toExponential(1) : Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n));

const compute = (amount, rate, days) => {
  const r = rate / 100;
  const at = (d) => amount * Math.pow(1 + r, d);
  const step = Math.max(1, Math.ceil(days / 120));
  const chart = [];
  for (let d = 0; d <= days; d += step) chart.push({ day: d, balance: at(d) });
  if (chart[chart.length - 1].day !== days) chart.push({ day: days, balance: at(days) });
  const rowStep = Math.max(1, Math.ceil(days / 15));
  const rows = [];
  for (let d = rowStep; d < days; d += rowStep) rows.push(d);
  rows.push(days);
  return { final: at(days), chart, rows: rows.map((d) => ({ day: d, balance: at(d), earned: at(d) - at(d - 1) })) };
};

const Field = ({ id, label, children }) => (
  <div className="space-y-2">
    <Label htmlFor={id} className="text-xs uppercase tracking-wider text-slate-400">{label}</Label>
    {children}
  </div>
);

const Inputs = ({ f, setF }) => {
  const num = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="card-lux space-y-5 p-6" data-testid="calc-inputs">
      <Field id="calc-amount" label="Starting amount ($)">
        <Input id="calc-amount" type="number" min="1" step="any" value={f.amount} onChange={num("amount")} data-testid="calc-amount-input" className="h-12 border-purple-500/20 bg-black/40 font-num text-lg" />
      </Field>
      <Field id="calc-rate" label="Daily return (%)">
        <Input id="calc-rate" type="number" min="0" max="100" step="any" value={f.rate} onChange={num("rate")} data-testid="calc-rate-input" className="h-12 border-purple-500/20 bg-black/40 font-num text-lg" />
      </Field>
      <Field id="calc-period" label="Time period">
        <div className="flex gap-2">
          <Input id="calc-period" type="number" min="1" step="1" value={f.period} onChange={num("period")} data-testid="calc-period-input" className="h-12 w-28 border-purple-500/20 bg-black/40 font-num text-lg" />
          <div className="grid flex-1 grid-cols-4 gap-1 rounded-xl border border-purple-500/20 bg-black/40 p-1" data-testid="calc-unit-toggle">
            {UNITS.map(([v, l]) => (
              <button key={v} type="button" onClick={() => setF({ ...f, unit: v })} data-testid={`calc-unit-${v}`}
                className={`rounded-lg text-xs font-medium transition-colors ${f.unit === v ? "bg-purple-600 text-white" : "text-slate-400 hover:text-white"}`}>{l}</button>
            ))}
          </div>
        </div>
      </Field>
      <div className="flex flex-wrap gap-2" data-testid="calc-presets">
        {PRESETS.map(([p, u]) => (
          <button key={`${p}${u}`} type="button" onClick={() => setF({ ...f, period: String(p), unit: u })} data-testid={`calc-preset-${p}-${u}`}
            className="rounded-full border border-purple-500/25 px-3 py-1 text-xs text-slate-300 transition-colors hover:border-purple-400 hover:text-white">
            {p} {u === "years" ? "year" : u}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500">Months count as 30 days and years as 365 days. Returns compound every day.</p>
    </div>
  );
};

const Results = ({ amount, days, res }) => (
  <div className="grid gap-4 sm:grid-cols-3" data-testid="calc-results">
    {[["Final amount", money(res.final), "calc-final", "text-white"], ["Total profit", money(res.final - amount), "calc-profit", "text-emerald-300"],
      [`Growth in ${days.toLocaleString()} days`, `${amount ? compact(res.final / amount) : 0}x`, "calc-growth", "text-purple-300"]].map(([l, v, id, c]) => (
      <div key={id} className="card-lux p-5">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">{l}</p>
        <p className={`mt-2 break-all font-num text-2xl font-semibold ${c}`} data-testid={id}>{v}</p>
      </div>
    ))}
  </div>
);

const GrowthChart = ({ data }) => (
  <div className="card-lux h-72 p-4" data-testid="calc-chart">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ left: 8, right: 8, top: 10 }}>
        <defs>
          <linearGradient id="calcFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a855f7" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#a855f7" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#ffffff10" vertical={false} />
        <XAxis dataKey="day" stroke="#64748b" fontSize={11} tickFormatter={(d) => `D${d}`} minTickGap={24} />
        <YAxis stroke="#64748b" fontSize={11} tickFormatter={(v) => `$${compact(v)}`} width={60} />
        <Tooltip contentStyle={{ background: "#0b0816", border: "1px solid #a855f740", borderRadius: 12 }} labelFormatter={(d) => `Day ${d}`} formatter={(v) => [money(v), "Balance"]} />
        <Area type="monotone" dataKey="balance" stroke="#c084fc" strokeWidth={2} fill="url(#calcFill)" />
      </AreaChart>
    </ResponsiveContainer>
  </div>
);

const Breakdown = ({ rows }) => (
  <div className="card-lux overflow-hidden" data-testid="calc-table">
    <Table>
      <TableHeader><TableRow className="border-purple-500/10"><TableHead>Day</TableHead><TableHead className="text-right">Balance</TableHead><TableHead className="text-right">Earned that day</TableHead></TableRow></TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.day} className="border-purple-500/10" data-testid={`calc-row-${r.day}`}>
            <TableCell className="font-num">{r.day.toLocaleString()}</TableCell>
            <TableCell className="text-right font-num text-white">{money(r.balance)}</TableCell>
            <TableCell className="text-right font-num text-emerald-300">+{money(r.earned)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </div>
);

export default function CompoundCalculator() {
  const [f, setF] = useState({ amount: "100", rate: "1", period: "500", unit: "days" });
  const amount = Math.max(0, Number(f.amount) || 0);
  const rate = Math.min(100, Math.max(0, Number(f.rate) || 0));
  const rawDays = Math.round((Number(f.period) || 0) * UNITS.find((u) => u[0] === f.unit)[2]);
  const days = Math.min(MAX_DAYS, Math.max(1, rawDays));
  const res = useMemo(() => compute(amount, rate, days), [amount, rate, days]);
  return (
    <>
      <PageHeader eyebrow="Tools" title="Compound calculator" desc="See how a daily percentage grows when every day's gain is added back to the balance." />
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200" data-testid="calc-disclaimer">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        This is only a math example. Scarmenta does not promise or guarantee any daily return, profit or winnings, and credits cannot be withdrawn.
      </div>
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Inputs f={f} setF={setF} />
        <div className="space-y-6">
          {rawDays > MAX_DAYS && <p className="text-xs text-amber-300" data-testid="calc-cap-note">Capped at {MAX_DAYS.toLocaleString()} days (10 years).</p>}
          <Results amount={amount} days={days} res={res} />
          <GrowthChart data={res.chart} />
          <Breakdown rows={res.rows} />
        </div>
      </div>
    </>
  );
}
