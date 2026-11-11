import { useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { useFetch } from "@/lib/hooks";
import { fmtDate, inr } from "@/lib/format";

export default function AdminReferrals() {
  const [status, setStatus] = useState("all");
  const { data } = useFetch(`/admin/referrals?status=${status}`);
  return (
    <>
      <PageHeader eyebrow="Refer & earn" title="Referrals" desc="Referrers earn bonus credits automatically when a referred friend's first deposit is approved. Bonus % is set in Credit Config." />
      <Tabs value={status} onValueChange={setStatus} className="mb-5">
        <TabsList className="bg-white/[0.03]">
          {["all", "pending", "rewarded"].map((s) => <TabsTrigger key={s} value={s} data-testid={`admin-referrals-tab-${s}`} className="capitalize data-[state=active]:bg-purple-600 data-[state=active]:text-white">{s}</TabsTrigger>)}
        </TabsList>
      </Tabs>
      {!data?.length ? <EmptyState text="No referrals yet." testId="admin-referrals-empty" /> : (
        <div className="card-lux overflow-x-auto p-2" data-testid="admin-referrals-table">
          <Table>
            <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{["Referred player", "Referred by", "Joined", "Status", "Reward paid"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {data.map((r) => (
                <TableRow key={r.id} className="border-white/5" data-testid={`admin-referral-row-${r.email}`}>
                  <TableCell><p className="text-sm text-white">{r.name}</p><p className="text-xs text-slate-500">{r.email}</p></TableCell>
                  <TableCell className="text-xs text-slate-300">{r.referred_by_email}</TableCell>
                  <TableCell className="font-num text-xs text-slate-400">{fmtDate(r.created_at)}</TableCell>
                  <TableCell><StatusBadge status={r.status === "rewarded" ? "approved" : "pending"} /></TableCell>
                  <TableCell className="font-num text-sm text-emerald-300">{inr(r.reward)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
