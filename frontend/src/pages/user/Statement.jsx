import { useState } from "react";
import { PageHeader } from "@/components/StatCard";
import { TxTable } from "@/components/TxTable";
import { StatementActions, TotalsBar, TxFilters, buildQuery, useTotals } from "@/components/TxFilters";
import { useAuth } from "@/context/AuthContext";
import { useFetch } from "@/lib/hooks";

export default function UserStatement() {
  const { user } = useAuth();
  const [filters, setFilters] = useState({ type: "", wallet: "", start: "", end: "" });
  const { data } = useFetch(buildQuery("/transactions", filters));
  const totals = useTotals(data);
  return (
    <>
      <PageHeader eyebrow="Account statement" title="Transaction ledger" desc={`${user?.name} · ${user?.email} · Issued by Scarmenta Ltd, Cyprus`}
        action={<StatementActions rows={data} name={`scarmenta-statement-${new Date().toISOString().slice(0, 10)}.csv`} />} />
      <TxFilters filters={filters} setFilters={setFilters} />
      <TotalsBar totals={totals} count={data?.length || 0} />
      <TxTable rows={data} testId="statement-tx-table" />
    </>
  );
}
