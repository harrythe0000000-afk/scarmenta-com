import { useState } from "react";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/StatCard";
import { TxTable } from "@/components/TxTable";
import { StatementActions, TotalsBar, TxFilters, buildQuery, useTotals } from "@/components/TxFilters";
import { useFetch } from "@/lib/hooks";

export default function AdminTransactions() {
  const [filters, setFilters] = useState({ q: "", type: "", wallet: "", start: "", end: "" });
  const { data } = useFetch(buildQuery("/admin/transactions", filters));
  const totals = useTotals(data);
  return (
    <>
      <PageHeader eyebrow="Transaction monitoring" title="Platform ledger" desc="Every deposit, fee, promotional allocation and manual adjustment across all accounts."
        action={<StatementActions rows={data} name={`aetheria-ledger-${new Date().toISOString().slice(0, 10)}.csv`} />} />
      <TxFilters filters={filters} setFilters={setFilters}
        extra={
          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">Search</p>
            <Input data-testid="admin-tx-search-input" placeholder="Email, reference…" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} className="w-56 border-purple-500/20 bg-black/40" />
          </div>
        } />
      <TotalsBar totals={totals} count={data?.length || 0} />
      <TxTable rows={data} showUser testId="admin-tx-table" />
    </>
  );
}
