import { useState } from "react";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, PageHeader } from "@/components/StatCard";
import { TicketList, TicketThread } from "@/components/Tickets";
import { api, formatApiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";

export default function AdminSupport() {
  const { data, setData } = useFetch("/admin/tickets");
  const [activeId, setActiveId] = useState(null);
  const active = data?.find((t) => t.id === activeId);
  const upsert = (t) => setData((list) => list.map((x) => (x.id === t.id ? t : x)));
  const reply = async (message) => {
    try {
      const { data: t } = await api.post(`/admin/tickets/${activeId}/reply`, { message });
      upsert(t);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  const setStatus = async (status) => {
    try {
      const { data: t } = await api.patch(`/admin/tickets/${activeId}/status`, { status });
      upsert(t);
      toast.success(`Ticket marked ${status}`);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  return (
    <>
      <PageHeader eyebrow="Customer support" title="Ticket inbox" desc="Respond to player questions about deposits, wallets and accounts." />
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <div>{data?.length ? <TicketList tickets={data} activeId={activeId} onSelect={setActiveId} /> : <EmptyState text="No tickets yet." testId="admin-tickets-empty" />}</div>
        <div className="card-lux flex min-h-[400px] flex-col p-6">
          {active ? (
            <>
              <div className="mb-4 flex justify-end">
                <Select value={active.status} onValueChange={setStatus}>
                  <SelectTrigger data-testid="admin-ticket-status-select" className="w-40 border-purple-500/20 bg-black/40 capitalize"><SelectValue /></SelectTrigger>
                  <SelectContent>{["open", "resolved", "closed"].map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <TicketThread ticket={active} onReply={reply} viewerRole="admin" />
            </>
          ) : <EmptyState text="Select a ticket to respond." testId="admin-ticket-empty" />}
        </div>
      </div>
    </>
  );
}
