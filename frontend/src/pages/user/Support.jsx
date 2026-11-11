import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { TicketList, TicketThread } from "@/components/Tickets";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";

const NewTicket = ({ onCreated }) => {
  const [form, setForm] = useState({ subject: "", category: "deposit", message: "" });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/support/tickets", form);
      toast.success(`Ticket ${data.reference} opened`);
      setForm({ subject: "", category: "deposit", message: "" });
      onCreated(data);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card-lux space-y-3 p-5" data-testid="new-ticket-form">
      <p className="label-eyebrow">Open a ticket</p>
      <Input data-testid="ticket-subject-input" required minLength={3} placeholder="Subject" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="border-purple-500/20 bg-black/40" />
      <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
        <SelectTrigger data-testid="ticket-category-select" className="border-purple-500/20 bg-black/40"><SelectValue /></SelectTrigger>
        <SelectContent>
          {["deposit", "wallet", "account", "technical", "other"].map((c) => <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>)}
        </SelectContent>
      </Select>
      <Textarea data-testid="ticket-message-input" required minLength={5} placeholder="Describe your issue…" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="min-h-[100px] border-purple-500/20 bg-black/40" />
      <Button data-testid="ticket-submit-button" disabled={busy} className="w-full rounded-full bg-purple-600 hover:bg-purple-500">Submit ticket</Button>
    </form>
  );
};

export default function UserSupport() {
  const { data, reload, setData } = useFetch("/support/tickets");
  const [activeId, setActiveId] = useState(null);
  const active = data?.find((t) => t.id === activeId);
  const reply = async (message) => {
    try {
      const { data: t } = await api.post(`/support/tickets/${activeId}/reply`, { message });
      setData((list) => list.map((x) => (x.id === t.id ? t : x)));
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <>
      <PageHeader eyebrow="Customer support" title="Help desk" desc="Our compliance and payments team typically replies within a few hours." />
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-6">
          <NewTicket onCreated={(t) => { reload(); setActiveId(t.id); }} />
          {data?.length ? <TicketList tickets={data} activeId={activeId} onSelect={setActiveId} /> : null}
        </div>
        <div className="card-lux min-h-[400px] p-6">
          {active ? <TicketThread ticket={active} onReply={reply} viewerRole="user" /> : <EmptyState text="Select a ticket to view the conversation." testId="ticket-empty" />}
        </div>
      </div>
    </>
  );
}
