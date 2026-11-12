import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { LogOut, MailWarning } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { TermsReaccept, useTermsRequired } from "@/components/TermsReaccept";
import { UserPopups } from "@/components/UserPopups";

const VerifyBanner = () => {
  const [busy, setBusy] = useState(false);
  const resend = async () => {
    setBusy(true);
    try {
      await api.post("/auth/resend-verification");
      toast.success("Verification email sent. Check your inbox.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div data-testid="verify-email-banner" className="mb-6 flex flex-col gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="flex items-center gap-2 text-sm text-amber-200">
        <MailWarning className="h-4 w-4 shrink-0" /> Verify your email to unlock deposits and credit packages.
      </p>
      <Button data-testid="resend-verification-button" size="sm" variant="outline" disabled={busy} onClick={resend}
        className="rounded-full border-amber-500/40 bg-transparent text-amber-200 hover:bg-amber-500/10">
        Resend email
      </Button>
    </div>
  );
};

export default function DashboardShell({ nav: allNav, area }) {
  const { user, logout } = useAuth();
  const [termsRequired, setTermsRequired] = useTermsRequired(user);
  const nav = allNav.filter((n) => !n.adminOnly || user?.role === "admin");
  if (user?.role === "staff") area = "Staff Console";
  const navigate = useNavigate();
  const doLogout = async () => {
    await logout();
    navigate("/login");
  };
  const linkCls = ({ isActive }) =>
    `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
      isActive ? "bg-purple-500/15 text-white border border-purple-500/30" : "text-slate-400 border border-transparent hover:text-white hover:bg-white/[0.03]"
    }`;

  return (
    <div className="min-h-screen bg-[#05040A] text-slate-200">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-purple-500/10 bg-[#07050f] p-5 lg:flex">
        <BrandLogo to={nav[0].to} />
        <p className="label-eyebrow mt-8 mb-3 px-3">{area}</p>
        <nav className="flex flex-col gap-1">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={linkCls} data-testid={`nav-${n.id}`}>
              <n.icon className="h-4 w-4" /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-xl border border-purple-500/15 bg-white/[0.02] p-3">
          <p className="truncate text-sm font-semibold text-white" data-testid="shell-user-name">{user?.name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <Button data-testid="logout-button" onClick={doLogout} variant="ghost" size="sm" className="mt-2 w-full justify-start px-2 text-slate-400 hover:bg-white/5 hover:text-white">
            <LogOut className="mr-2 h-4 w-4" /> Sign out
          </Button>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-purple-500/10 glass lg:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <BrandLogo to={nav[0].to} testId="brand-logo-mobile" />
          <Button data-testid="logout-button-mobile" onClick={doLogout} variant="ghost" size="icon" className="text-slate-400">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={linkCls} data-testid={`nav-mobile-${n.id}`}>
              <n.icon className="h-4 w-4" /> {n.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8 lg:py-12">
          {user?.role === "user" && !user.email_verified && <VerifyBanner />}
          {termsRequired && <TermsReaccept onDone={() => setTermsRequired(false)} />}
          {termsRequired === false && (user?.role === "user" || user?.role === "agent") && <UserPopups />}
          <Outlet />
        </div>
      </main>
    </div>
  );
}
