import { useMemo, useState } from "react";
import { Download, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TX_TYPES, downloadCSV, inr } from "@/lib/format";

export const TxFilters = ({ filters, setFilters, extra }) => {
  const set = (k) => (v) => setFilters({ ...filters, [k]: v });
  return (
    <div className="mb-5 flex flex-wrap items-end gap-3 no-print" data-testid="tx-filters">
      {extra}
      <div>
        <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Type</p>
        <Select value={filters.type || "all"} onValueChange={(v) => set("type")(v === "all" ? "" : v)}>
          <SelectTrigger data-testid="tx-filter-type" className="w-40 border-purple-500/20 bg-black/40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {Object.entries(TX_TYPES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div>
        <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">From</p>
        <Input type="date" data-testid="tx-filter-start" value={filters.start} onChange={(e) => set("start")(e.target.value)} className="w-40 border-purple-500/20 bg-black/40 [color-scheme:dark]" />
      </div>
      <div>
        <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">To</p>
        <Input type="date" data-testid="tx-filter-end" value={filters.end} onChange={(e) => set("end")(e.target.value)} className="w-40 border-purple-500/20 bg-black/40 [color-scheme:dark]" />
      </div>
    </div>
  );
};

export const buildQuery = (base, filters) => {
  const p = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
  const s = p.toString();
  return s ? `${base}?${s}` : base;
};

export const exportTx = (rows, name) =>
  downloadCSV(name, [
    ["Date", "User", "Type", "Description", "Reference", "Credits (INR)", "Balance after (INR)"],
    ...rows.map((t) => [t.created_at, t.user_email, TX_TYPES[t.type] || t.type, t.description, t.reference, t.amount, t.balance_after]),
  ]);

export const useTotals = (rows) =>
  useMemo(() => {
    const r = { credits: 0, debits: 0 };
    (rows || []).forEach((t) => (t.amount >= 0 ? (r.credits += t.amount) : (r.debits += t.amount)));
    return r;
  }, [rows]);

export const StatementActions = ({ rows, name }) => (
  <div className="flex gap-2 no-print">
    <Button data-testid="statement-export-csv-button" variant="outline" disabled={!rows?.length} onClick={() => exportTx(rows, name)} className="rounded-full border-purple-500/30 bg-transparent hover:bg-purple-500/10">
      <Download className="mr-2 h-4 w-4" /> Export CSV
    </Button>
    <Button data-testid="statement-print-button" variant="outline" onClick={() => window.print()} className="rounded-full border-purple-500/30 bg-transparent hover:bg-purple-500/10">
      <Printer className="mr-2 h-4 w-4" /> Print
    </Button>
  </div>
);

export const TotalsBar = ({ totals, count }) => (
  <div className="mb-5 flex flex-wrap gap-6 text-sm" data-testid="statement-totals">
    <span className="text-slate-400">Entries: <b className="font-num text-white">{count}</b></span>
    <span className="text-slate-400">Credited: <b className="font-num text-emerald-300">{inr(totals.credits)}</b></span>
    <span className="text-slate-400">Debited: <b className="font-num text-red-300">{inr(Math.abs(totals.debits))}</b></span>
  </div>
);
