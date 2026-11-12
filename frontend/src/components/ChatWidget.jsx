import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, MessageCircle, Plus, Send, X } from "lucide-react";
import { v4 as uuid } from "uuid";
import { Button } from "@/components/ui/button";
import { api, API } from "@/lib/api";

const SESSION_KEY = "scarmenta_chat_session";
const SUGGESTIONS = ["How do I deposit?", "What is my balance?", "Can I withdraw credits?", "How does Transfer work?"];

const getSession = () => {
  let s = localStorage.getItem(SESSION_KEY);
  if (!s) localStorage.setItem(SESSION_KEY, (s = uuid()));
  return s;
};

const postChat = (body) => fetch(`${API}/assistant/chat`, {
  method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

async function streamReply(body, onDelta) {
  let res = await postChat(body);
  if (res.status === 401) {
    await api.post("/auth/refresh").catch(() => {});
    res = await postChat(body);
  }
  if (!res.ok || !res.body) throw new Error("Couldn't reach the assistant. Please try again.");
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      const line = p.replace(/^data: /, "").trim();
      if (!line || line === "[DONE]") continue;
      const ev = JSON.parse(line);
      if (ev.error) throw new Error(ev.error);
      onDelta(ev.delta);
    }
  }
}

const Bubble = ({ m }) => (
  <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
    <p data-testid={`chat-msg-${m.role}`} className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${m.role === "user" ? "rounded-br-sm bg-purple-600 text-white" : "rounded-bl-sm border border-purple-500/20 bg-white/[0.04] text-slate-200"}`}>
      {m.content || <Loader2 className="h-4 w-4 animate-spin text-purple-300" />}
    </p>
  </div>
);

const ChatPanel = ({ onClose }) => {
  const [session, setSession] = useState(getSession);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => {
    api.get("/assistant/history", { params: { session_id: session } }).then((r) => setMsgs(r.data)).catch(() => {});
  }, [session]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);
  const send = async (q) => {
    const message = (q ?? text).trim();
    if (!message || busy) return;
    setText("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: message }, { role: "assistant", content: "" }]);
    const patch = (fn) => setMsgs((m) => [...m.slice(0, -1), { role: "assistant", content: fn(m[m.length - 1].content) }]);
    try {
      await streamReply({ session_id: session, message }, (d) => patch((c) => c + d));
    } catch (e) {
      patch((c) => c || e.message);
    } finally {
      setBusy(false);
    }
  };
  const newChat = () => {
    const s = uuid();
    localStorage.setItem(SESSION_KEY, s);
    setSession(s);
    setMsgs([]);
  };
  return (
    <div data-testid="chat-panel" className="fixed bottom-24 right-4 z-50 flex h-[min(560px,75vh)] w-[min(380px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-purple-500/30 bg-[#0b0816] shadow-2xl shadow-purple-900/40 fade-up">
      <div className="flex items-center justify-between border-b border-purple-500/15 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600"><Bot className="h-4 w-4 text-white" /></span>
          <div><p className="text-sm font-semibold text-white">Scara</p><p className="text-[11px] text-emerald-300">AI help assistant</p></div>
        </div>
        <div className="flex gap-1">
          <Button size="icon" variant="ghost" onClick={newChat} title="New chat" data-testid="chat-new-button" className="h-8 w-8 text-slate-400 hover:text-white"><Plus className="h-4 w-4" /></Button>
          <Button size="icon" variant="ghost" onClick={onClose} title="Close" data-testid="chat-close-button" className="h-8 w-8 text-slate-400 hover:text-white"><X className="h-4 w-4" /></Button>
        </div>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4" data-testid="chat-messages">
        {msgs.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-slate-400">Hi! I can help with deposits, credits, transfers, referrals and your account. Ask in any language.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s, i) => (
                <button key={s} type="button" onClick={() => send(s)} data-testid={`chat-suggestion-${i}`}
                  className="rounded-full border border-purple-500/25 px-3 py-1 text-xs text-slate-300 hover:border-purple-400 hover:text-white">{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => <Bubble key={i} m={m} />)}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex gap-2 border-t border-purple-500/15 p-3">
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder="Type your question…" data-testid="chat-input"
          className="h-10 flex-1 rounded-full border border-purple-500/20 bg-black/40 px-4 text-sm text-white outline-none focus:border-purple-400" />
        <Button type="submit" size="icon" disabled={busy || !text.trim()} data-testid="chat-send-button" className="h-10 w-10 rounded-full bg-purple-600 hover:bg-purple-500">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </form>
      <p className="px-4 pb-2 text-center text-[10px] text-slate-600">AI answers can be wrong. For payment issues use Support.</p>
    </div>
  );
};

export const ChatWidget = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      {open && <ChatPanel onClose={() => setOpen(false)} />}
      <button type="button" onClick={() => setOpen((o) => !o)} data-testid="chat-launcher-button" aria-label="Open help chat"
        className="fixed bottom-5 right-4 z-50 grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 text-white shadow-lg shadow-purple-900/50 transition-transform hover:scale-105">
        {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>
    </>
  );
};
