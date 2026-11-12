import { useState } from "react";
import { HelpCircle, LifeBuoy, MessagesSquare, Users } from "lucide-react";
import { EmptyState, PageHeader, StatCard } from "@/components/StatCard";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useFetch } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

const RANGES = [7, 30, 90];

const RangeToggle = ({ days, setDays }) => (
  <div className="flex gap-1 rounded-full border border-purple-500/20 bg-black/40 p-1" data-testid="insights-range">
    {RANGES.map((d) => (
      <button key={d} type="button" onClick={() => setDays(d)} data-testid={`insights-range-${d}`}
        className={`rounded-full px-3 py-1 text-xs transition-colors ${days === d ? "bg-purple-600 text-white" : "text-slate-400 hover:text-white"}`}>{d} days</button>
    ))}
  </div>
);

const TopWords = ({ words }) => {
  const max = words[0]?.count || 1;
  return (
    <div className="card-lux p-6" data-testid="insights-top-words">
      <p className="label-eyebrow mb-4">Most used words</p>
      {words.length === 0 ? <p className="text-sm text-slate-500">No questions yet.</p> : (
        <div className="space-y-2">
          {words.map((w) => (
            <div key={w.word} className="flex items-center gap-3 text-sm" data-testid={`insights-word-${w.word}`}>
              <span className="w-28 truncate text-slate-300">{w.word}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                <div className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500" style={{ width: `${(w.count / max) * 100}%` }} />
              </div>
              <span className="w-8 text-right font-num text-slate-400">{w.count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Repeated = ({ items }) => (
  <div className="card-lux p-6" data-testid="insights-top-questions">
    <p className="label-eyebrow mb-4">Asked more than once</p>
    {items.length === 0 ? <p className="text-sm text-slate-500">No repeated questions yet.</p> : (
      <ul className="space-y-2 text-sm">
        {items.map((q) => (
          <li key={q.question} className="flex justify-between gap-3 border-b border-purple-500/10 pb-2 last:border-0">
            <span className="text-slate-300">{q.question}</span><span className="font-num text-purple-300">×{q.count}</span>
          </li>
        ))}
      </ul>
    )}
  </div>
);

const Recent = ({ rows }) => (
  <div className="card-lux overflow-hidden" data-testid="insights-recent">
    <p className="label-eyebrow px-6 pt-6">Latest questions</p>
    {rows.length === 0 ? <div className="p-6"><EmptyState text="No questions in this period." testId="insights-empty" /></div> : (
      <Table>
        <TableHeader><TableRow className="border-purple-500/10"><TableHead>Question</TableHead><TableHead>From</TableHead><TableHead className="text-right">When</TableHead></TableRow></TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i} className="border-purple-500/10" data-testid={`insights-recent-row-${i}`}>
              <TableCell className="max-w-md whitespace-pre-wrap text-slate-200">{r.question}</TableCell>
              <TableCell className="text-xs text-slate-400">{r.name}<span className="ml-1 text-slate-600">({r.role === "agent" ? "agent" : "player"})</span></TableCell>
              <TableCell className="text-right text-xs text-slate-500">{fmtDate(r.created_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )}
  </div>
);

export default function ChatInsights() {
  const [days, setDays] = useState(30);
  const { data } = useFetch(`/admin/assistant/insights?days=${days}`);
  return (
    <>
      <PageHeader eyebrow="AI assistant" title="Chat insights" desc="What players and agents ask the Scara help bot." action={<RangeToggle days={days} setDays={setDays} />} />
      {data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Questions" value={data.questions} icon={HelpCircle} testId="insights-questions" />
            <StatCard label="People" value={data.people} icon={Users} tone="emerald" testId="insights-people" />
            <StatCard label="Chats" value={data.chats} icon={MessagesSquare} tone="amber" testId="insights-chats" />
            <StatCard label="Tickets by bot" value={data.tickets} icon={LifeBuoy} tone="red" testId="insights-tickets" />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <TopWords words={data.top_words} />
            <Repeated items={data.top_questions} />
          </div>
          <Recent rows={data.recent} />
        </div>
      )}
    </>
  );
}
