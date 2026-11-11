import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Banknote, Clock, LifeBuoy, ShieldAlert, Sparkles, Users, Wallet } from "lucide-react";
import { PageHeader, StatCard } from "@/components/StatCard";
import { useFetch } from "@/lib/hooks";
import { inr } from "@/lib/format";

const tooltipStyle = { background: "#0d0a1a", border: "1px solid rgba(139,92,246,.3)", borderRadius: 12, fontSize: 12 };
const short = (v) => (v >= 100000 ? `${(v / 100000).toFixed(1)}L` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v);

export default function AdminOverview() {
  const { data: s } = useFetch("/admin/stats");
  const series = (s?.series || []).map((d) => ({ ...d, label: d.date.slice(5) }));
  return (
    <>
      <PageHeader eyebrow="Admin cockpit" title="Financial overview" desc="Platform-wide cash deposits, credit allocations and outstanding balances." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Cash deposits" value={inr(s?.total_deposits)} icon={Banknote} tone="emerald" testId="admin-stat-deposits" sub={`${s?.approved_count ?? 0} approved`} />
        <StatCard label="Credits issued" value={inr(s?.total_credits)} icon={Sparkles} testId="admin-stat-credits" className="d-1" />
        <StatCard label="Outstanding credits" value={inr(s?.credit_outstanding)} icon={Wallet} tone="amber" testId="admin-stat-outstanding" className="d-2" />
        <StatCard label="Pending approvals" value={s?.pending_count ?? 0} icon={Clock} tone="red" testId="admin-stat-pending" className="d-3" />
        <StatCard label="Players" value={s?.users_count ?? 0} icon={Users} testId="admin-stat-users" sub={`${s?.verified_users ?? 0} verified`} />
        <StatCard label="Open fraud alerts" value={s?.open_alerts ?? 0} icon={ShieldAlert} tone="red" testId="admin-stat-alerts" />
        <StatCard label="Open tickets" value={s?.open_tickets ?? 0} icon={LifeBuoy} tone="amber" testId="admin-stat-tickets" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="card-lux p-6" data-testid="admin-chart-deposits">
          <p className="label-eyebrow">Last 30 days</p>
          <h3 className="mt-1 font-display text-lg font-semibold text-white">Cash deposits vs credits issued</h3>
          <div className="mt-6 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="gD" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10B981" stopOpacity={0.4} /><stop offset="100%" stopColor="#10B981" stopOpacity={0} /></linearGradient>
                  <linearGradient id="gP" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#A855F7" stopOpacity={0.45} /><stop offset="100%" stopColor="#A855F7" stopOpacity={0} /></linearGradient>
                </defs>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} interval={4} />
                <YAxis tickFormatter={short} tickLine={false} axisLine={false} width={44} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => inr(v)} />
                <Area type="monotone" dataKey="credits" name="Credits issued" stroke="#A855F7" fill="url(#gP)" strokeWidth={2} />
                <Area type="monotone" dataKey="deposits" name="Cash deposits" stroke="#10B981" fill="url(#gD)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card-lux p-6" data-testid="admin-chart-daily-deposits">
          <p className="label-eyebrow">Revenue</p>
          <h3 className="mt-1 font-display text-lg font-semibold text-white">Daily cash deposits</h3>
          <div className="mt-6 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} interval={6} />
                <YAxis tickFormatter={short} tickLine={false} axisLine={false} width={40} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => inr(v)} cursor={{ fill: "rgba(139,92,246,.08)" }} />
                <Bar dataKey="deposits" name="Cash deposits" fill="#8B5CF6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      {s?.pending_count > 0 && (
        <Link to="/admin/deposits" data-testid="admin-pending-cta" className="mt-6 flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/5 px-5 py-4 text-sm text-amber-200 transition-colors hover:bg-amber-500/10">
          <span>{s.pending_count} deposit(s) waiting for review</span><span>Review queue →</span>
        </Link>
      )}
    </>
  );
}
