import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/StatusBadge";
import { fmtDate } from "@/lib/format";

export const TicketThread = ({ ticket, onReply, viewerRole }) => {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!msg.trim()) return;
    setBusy(true);
    try {
      await onReply(msg.trim());
      setMsg("");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex h-full flex-col" data-testid="ticket-thread">
      <div className="flex items-start justify-between gap-3 border-b border-white/5 pb-4">
        <div>
          <p className="font-num text-xs text-purple-300">{ticket.reference} · {ticket.category}</p>
          <h3 className="mt-1 font-display text-lg font-semibold text-white">{ticket.subject}</h3>
          {viewerRole === "admin" && <p className="text-xs text-slate-500">{ticket.user_name} · {ticket.user_email}</p>}
        </div>
        <StatusBadge status={ticket.status} testId="ticket-thread-status" />
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto py-4 max-h-[380px]">
        {ticket.messages.map((m, i) => {
          const mine = m.author_role === viewerRole;
          return (
            <div key={i} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`ticket-message-${i}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${mine ? "bg-purple-600/25 text-purple-50 border border-purple-500/30" : "bg-white/[0.04] text-slate-200 border border-white/5"}`}>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {m.author_role === "admin" ? "Aetheria Support" : m.author_name} · {fmtDate(m.created_at)}
                </p>
                <p className="whitespace-pre-wrap">{m.message}</p>
              </div>
            </div>
          );
        })}
      </div>
      {ticket.status !== "closed" && (
        <div className="flex gap-2 border-t border-white/5 pt-4">
          <Textarea data-testid="ticket-reply-input" value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Write a reply…"
            className="min-h-[44px] resize-none border-purple-500/20 bg-black/40" rows={2} />
          <Button data-testid="ticket-reply-send-button" onClick={send} disabled={busy || !msg.trim()} className="h-auto rounded-xl bg-purple-600 hover:bg-purple-500">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
};

export const TicketList = ({ tickets, activeId, onSelect }) => (
  <div className="space-y-2" data-testid="ticket-list">
    {tickets.map((t) => (
      <button key={t.id} type="button" data-testid={`ticket-item-${t.reference}`} onClick={() => onSelect(t.id)}
        className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${activeId === t.id ? "border-purple-500/50 bg-purple-500/10" : "border-white/5 bg-white/[0.02] hover:border-purple-500/30"}`}>
        <div className="flex items-center justify-between gap-2">
          <span className="font-num text-[11px] text-purple-300">{t.reference}</span>
          <StatusBadge status={t.status} />
        </div>
        <p className="mt-1 truncate text-sm font-medium text-white">{t.subject}</p>
        <p className="text-[11px] text-slate-500">{fmtDate(t.updated_at)}</p>
      </button>
    ))}
  </div>
);
