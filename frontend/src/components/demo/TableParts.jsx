import { usd } from "@/lib/format";
import { play } from "@/lib/sounds";

export const CHIPS = [10, 50, 100, 500];

export const ChipRack = ({ chip, setChip }) => (
  <div className="flex gap-2" data-testid="demo-chips">
    {CHIPS.map((c) => (
      <button key={c} type="button" onClick={() => { setChip(c); play("chip"); }} data-testid={`demo-chip-${c}`}
        className={`grid h-12 w-12 place-items-center rounded-full border-4 border-dashed font-num text-xs font-bold transition-transform ${chip === c ? "scale-110 border-white bg-purple-600 text-white" : "border-purple-300/40 bg-purple-950 text-purple-200 hover:scale-105"}`}>${c}</button>
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
