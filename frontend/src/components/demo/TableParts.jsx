import { usd } from "@/lib/format";
import { play } from "@/lib/sounds";

export const CHIPS = [10, 50, 100, 500];

export const ChipRack = ({ chip, setChip, prefix = "$", values = CHIPS }) => (
  <div className="flex gap-2" data-testid="demo-chips">
    {values.map((c) => (
      <button key={c} type="button" onClick={() => { setChip(c); play("chip"); }} data-testid={`demo-chip-${c}`}
        className={`grid h-12 w-12 place-items-center rounded-full border-4 border-dashed font-num text-xs font-bold transition-transform ${chip === c ? "scale-110 border-white bg-purple-600 text-white" : "border-purple-300/40 bg-purple-950 text-purple-200 hover:scale-105"}`}>{prefix}{c >= 1000 ? `${c / 1000}K` : c}</button>
    ))}
  </div>
);

export const BetSpot = ({ id, amount, onClick, disabled, won, ring, children }) => (
  <button type="button" onClick={onClick} disabled={disabled} data-testid={`demo-bet-${id}`}
    className={`relative flex min-h-[110px] flex-1 flex-col items-center justify-center gap-2 rounded-2xl border-2 p-4 transition-all ${ring} ${won ? "scale-[1.03] ring-4 ring-emerald-400/70" : ""} ${disabled ? "cursor-default" : "hover:-translate-y-0.5 hover:brightness-125"}`}>
    {children}
    {amount > 0 && <span className="absolute -top-3 right-3 rounded-full bg-emerald-500 px-2.5 py-0.5 font-num text-xs font-bold text-black" data-testid={`demo-bet-amount-${id}`}>{usd(amount)}</span>}
  </button>
);

export const ResultText = ({ result, label }) => (
  <div className="h-12 text-center" data-testid="demo-result">
    {result && (
      <>
        <p className="font-semibold text-emerald-300">{label}</p>
        <p className={`font-num text-sm ${result.net >= 0 ? "text-emerald-200" : "text-red-300"}`} data-testid="demo-result-net">{result.net >= 0 ? "+" : ""}{usd(result.net)}</p>
      </>
    )}
  </div>
);

export const LangToggle = ({ lang, setLang, testId }) => (
  <div className="flex gap-1 rounded-full border border-purple-500/20 bg-black/40 p-1" data-testid={testId}>
    {[["en", "English"], ["hi", "Hinglish"]].map(([v, l]) => (
      <button key={v} type="button" onClick={() => setLang(v)} data-testid={`${testId}-${v}`}
        className={`rounded-full px-4 py-1 text-xs font-medium transition-colors ${lang === v ? "bg-purple-600 text-white" : "text-slate-400 hover:text-white"}`}>{l}</button>
    ))}
  </div>
);

export const RivalBadges = () => (
  <div className="flex flex-wrap justify-center gap-1.5">
    {["Stake", "1win", "4rabet"].map((r) => <span key={r} className="rounded-md border border-sky-300/30 bg-sky-950/60 px-2 py-0.5 text-xs font-bold tracking-wide text-sky-100">{r}</span>)}
  </div>
);
