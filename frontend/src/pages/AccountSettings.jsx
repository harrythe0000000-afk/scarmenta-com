import { useState } from "react";
import { toast } from "sonner";
import { KeyRound, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/StatCard";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";

const F = ({ label, testId, ...props }) => (
  <div>
    <p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
    <Input data-testid={testId} {...props} className="h-11 border-purple-500/20 bg-black/40" />
  </div>
);

export default function AccountSettings() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ name: user?.name || "", email: user?.email || "", new_password: "", confirm: "", current_password: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async (e) => {
    e.preventDefault();
    if (form.new_password && form.new_password !== form.confirm) return toast.error("New passwords don't match");
    setBusy(true);
    try {
      const body = { current_password: form.current_password, name: form.name, email: form.email,
        new_password: form.new_password || null };
      const { data } = await api.put("/auth/account", body);
      setUser(data);
      setForm({ ...form, new_password: "", confirm: "", current_password: "" });
      toast.success("Account updated. Use your new details next time you sign in.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="My account" title="Login details" desc="Change the name, login email and password for this account. Your current password is required to save any change." />
      <form onSubmit={save} className="card-lux max-w-xl space-y-4 p-6" data-testid="account-settings-form">
        <F label="Name" testId="account-name-input" value={form.name} onChange={set("name")} minLength={2} required />
        <F label="Login email" testId="account-email-input" type="email" value={form.email} onChange={set("email")} required />
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="New password (optional)" testId="account-new-password-input" type="password" minLength={8} value={form.new_password} onChange={set("new_password")} autoComplete="new-password" />
          <F label="Confirm new password" testId="account-confirm-password-input" type="password" value={form.confirm} onChange={set("confirm")} autoComplete="new-password" />
        </div>
        <div className="border-t border-white/5 pt-4">
          <F label="Current password" testId="account-current-password-input" type="password" required value={form.current_password} onChange={set("current_password")} autoComplete="current-password" />
        </div>
        <Button data-testid="account-save-button" disabled={busy} className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6">
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />} Save changes
        </Button>
      </form>
    </>
  );
}
