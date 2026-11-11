const STYLES = {
  pending: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  approved: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  completed: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  rejected: "bg-red-500/10 text-red-300 border-red-500/30",
  active: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  suspended: "bg-red-500/10 text-red-300 border-red-500/30",
  open: "bg-violet-500/10 text-violet-300 border-violet-500/30",
  resolved: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  closed: "bg-slate-500/10 text-slate-300 border-slate-500/30",
  high: "bg-red-500/10 text-red-300 border-red-500/30",
  medium: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  low: "bg-slate-500/10 text-slate-300 border-slate-500/30",
  verified: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  earning: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  inactive: "bg-slate-500/10 text-slate-300 border-slate-500/30",
  unverified: "bg-amber-500/10 text-amber-300 border-amber-500/30",
};

export const StatusBadge = ({ status, testId }) => (
  <span
    data-testid={testId}
    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${
      STYLES[status] || STYLES.closed
    }`}
  >
    <span className="h-1.5 w-1.5 rounded-full bg-current" />
    {status?.replace("_", " ")}
  </span>
);
