import { toast } from "sonner";
import { Copy, Gift, Share2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, PageHeader, StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { useFetch } from "@/lib/hooks";
import { fmtDate, usd } from "@/lib/format";

const copy = async (text, label) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(`${label} copied`);
  } catch {
    toast.error("Could not copy — please copy manually");
  }
};

export default function UserRefer() {
  const { data: r } = useFetch("/referrals/me");
  if (!r) return null;
  const msg = `Join me on Scarmenta and get 5X credits on your deposit. Use my code ${r.code}: ${r.link}`;
  return (
    <>
      <PageHeader eyebrow="Refer & earn" title="Invite friends, earn credits" desc={`Earn ${r.bonus_percent}% referral income on every deposit your friends make, added straight to your balance.`} />
      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="relative overflow-hidden rounded-2xl border border-purple-500/40 bg-gradient-to-br from-purple-900/40 to-[#05040A] p-8 glow-violet fade-up" data-testid="referral-code-card">
          <div className="absolute -right-20 -top-20 h-60 w-60 rounded-full bg-fuchsia-500/20 blur-3xl" />
          <Gift className="relative h-6 w-6 text-fuchsia-300" />
          <p className="relative mt-5 text-xs uppercase tracking-[0.2em] text-purple-300">Your referral code</p>
          <p className="relative mt-2 font-num text-4xl font-bold tracking-widest text-white" data-testid="referral-code-value">{r.code}</p>
          <p className="relative mt-4 truncate rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-num text-xs text-slate-400" data-testid="referral-link-value">{r.link}</p>
          <div className="relative mt-5 flex flex-wrap gap-2">
            <Button data-testid="referral-copy-code-button" onClick={() => copy(r.code, "Code")} variant="outline" className="rounded-full border-purple-500/40 bg-transparent hover:bg-purple-500/10"><Copy className="mr-2 h-4 w-4" /> Copy code</Button>
            <Button data-testid="referral-copy-link-button" onClick={() => copy(r.link, "Link")} variant="outline" className="rounded-full border-purple-500/40 bg-transparent hover:bg-purple-500/10"><Copy className="mr-2 h-4 w-4" /> Copy link</Button>
            <Button asChild data-testid="referral-whatsapp-button" className="rounded-full bg-emerald-600 hover:bg-emerald-500">
              <a href={`https://wa.me/?text=${encodeURIComponent(msg)}`} target="_blank" rel="noreferrer"><Share2 className="mr-2 h-4 w-4" /> WhatsApp</a>
            </Button>
          </div>
        </div>
        <div className="grid gap-4">
          <StatCard label="Friends referred" value={r.total_referred} icon={Users} testId="referral-stat-count" />
          <StatCard label="Credits earned" value={usd(r.total_earned)} icon={Gift} tone="emerald" testId="referral-stat-earned" />
        </div>
      </div>
      <section className="mt-10">
        <p className="label-eyebrow mb-4">Your referrals</p>
        {!r.referrals.length ? <EmptyState text="No referrals yet. Share your code to start earning." testId="referrals-empty" /> : (
          <div className="card-lux overflow-x-auto p-2" data-testid="referrals-table">
            <Table>
              <TableHeader><TableRow className="border-white/5 hover:bg-transparent">{["Friend", "Joined", "Status", "Reward"].map((h) => <TableHead key={h} className="text-slate-500">{h}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {r.referrals.map((x, i) => (
                  <TableRow key={i} className="border-white/5">
                    <TableCell className="text-sm text-white">{x.name}</TableCell>
                    <TableCell className="font-num text-xs text-slate-400">{fmtDate(x.joined_at)}</TableCell>
                    <TableCell><StatusBadge status={x.status} /></TableCell>
                    <TableCell className="font-num text-sm text-emerald-300">{usd(x.reward)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </>
  );
}
