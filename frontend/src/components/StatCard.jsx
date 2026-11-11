export const StatCard = ({ label, value, sub, icon: Icon, tone = "violet", testId, className = "" }) => {
  const tones = {
    violet: "text-violet-300 bg-violet-500/10",
    emerald: "text-emerald-300 bg-emerald-500/10",
    amber: "text-amber-300 bg-amber-500/10",
    red: "text-red-300 bg-red-500/10",
  };
  return (
    <div className={`card-lux p-5 fade-up ${className}`} data-testid={testId}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">{label}</p>
        {Icon && (
          <span className={`grid h-8 w-8 place-items-center rounded-lg ${tones[tone]}`}>
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      <p className="mt-3 font-num text-2xl font-semibold text-white" data-testid={testId ? `${testId}-value` : undefined}>
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
};

export const PageHeader = ({ eyebrow, title, desc, action }) => (
  <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between fade-up">
    <div>
      {eyebrow && <p className="label-eyebrow mb-2">{eyebrow}</p>}
      <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h1>
      {desc && <p className="mt-2 max-w-2xl text-sm text-slate-400">{desc}</p>}
    </div>
    {action}
  </div>
);

export const EmptyState = ({ text, testId }) => (
  <div data-testid={testId} className="rounded-xl border border-dashed border-purple-500/20 px-6 py-12 text-center text-sm text-slate-500">
    {text}
  </div>
);
