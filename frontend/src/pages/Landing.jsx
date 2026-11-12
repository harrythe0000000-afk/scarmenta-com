import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Building2, Lock, Scale, ShieldCheck, Sparkles, Wallet, Receipt, Globe2 } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import { CreditCalculator } from "@/components/CreditCalculator";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { useConfig } from "@/lib/hooks";
import { calc, usd } from "@/lib/format";

const HERO_IMG = "https://images.unsplash.com/photo-1689443111130-6e9c7dfd8f9e?crop=entropy&cs=srgb&fm=jpg&q=85&w=2000";

const NavBar = () => {
  const { user } = useAuth();
  const dash = user ? (user.role === "admin" ? "/admin" : "/app") : null;
  return (
    <header className="sticky top-0 z-40 border-b border-purple-500/10 glass">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
        <BrandLogo />
        <nav className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
          <a href="#how" className="transition-colors hover:text-white" data-testid="nav-how-link">How it works</a>
          <a href="#packages" className="transition-colors hover:text-white" data-testid="nav-packages-link">Packages</a>
          <a href="#trust" className="transition-colors hover:text-white" data-testid="nav-trust-link">Compliance</a>
        </nav>
        <div className="flex items-center gap-2">
          {dash ? (
            <Button asChild data-testid="nav-dashboard-button" className="rounded-full bg-purple-600 hover:bg-purple-500">
              <Link to={dash}>Open dashboard</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" data-testid="nav-login-button" className="rounded-full text-slate-300 hover:bg-white/5 hover:text-white">
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild data-testid="nav-register-button" className="rounded-full bg-purple-600 hover:bg-purple-500">
                <Link to="/register">Create account</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

const Hero = ({ config }) => {
  const [amount, setAmount] = useState(200);
  return (
    <section className="relative overflow-hidden grain">
      <img src={HERO_IMG} alt="" className="absolute inset-0 h-full w-full object-cover opacity-25" />
      <div className="absolute inset-0 bg-gradient-to-r from-[#05040A] via-[#05040A]/90 to-[#05040A]/60" />
      <div className="relative z-10 mx-auto grid max-w-7xl gap-14 px-5 py-20 sm:px-8 lg:grid-cols-[1.15fr_1fr] lg:py-28">
        <div className="flex flex-col justify-center">
          <div className="fade-up flex flex-wrap gap-2">
            {["Cyprus HQ", "South Asia", "Middle East"].map((m) => (
              <span key={m} className="rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-purple-200">{m}</span>
            ))}
          </div>
          <h1 className="fade-up d-1 mt-7 font-display text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl">
            Prepaid gaming credit,<br />
            <span className="text-gradient">accounted to the cent.</span>
          </h1>
          <p className="fade-up d-2 mt-6 max-w-xl text-base text-slate-400 sm:text-lg">
            SquareManta is the technology layer that manages prepaid credit packages, 5X credit allocation and revenue
            reporting — with fully transparent ledgers and zero service fees.
          </p>
          <div className="fade-up d-3 mt-9 flex flex-wrap gap-3">
            <Button asChild data-testid="landing-hero-cta-button" className="h-12 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-7 text-base font-semibold hover:from-violet-500 hover:to-fuchsia-500">
              <Link to="/register">Open an account <ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
            <Button asChild variant="outline" data-testid="landing-hero-secondary-button" className="h-12 rounded-full border-purple-500/30 bg-transparent px-7 text-base text-slate-200 hover:bg-purple-500/10 hover:text-white">
              <a href="#how">See the credit model</a>
            </Button>
          </div>
          <div className="fade-up d-4 mt-12 grid max-w-lg grid-cols-3 gap-6 border-t border-white/5 pt-6">
            {[[`${config?.promo_multiplier ?? 5}X`, "Credit ratio"], ["0%", "Service fees"], ["24/7", "Ledger access"]].map(([v, l]) => (
              <div key={l}>
                <p className="font-num text-2xl font-semibold text-white">{v}</p>
                <p className="text-xs uppercase tracking-wider text-slate-500">{l}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="fade-up d-2 card-lux glow-violet self-center p-6 sm:p-8" data-testid="landing-calculator-card">
          <p className="label-eyebrow">Live credit calculator</p>
          <h2 className="mt-2 font-display text-xl font-semibold text-white">See your credit balance instantly</h2>
          <div className="mt-6">
            <CreditCalculator config={config} amount={amount} onChange={setAmount} testPrefix="landing-calc" />
          </div>
        </div>
      </div>
    </section>
  );
};

const STEPS = [
  { icon: Wallet, title: "Deposit", text: "Buy a prepaid package in USDT from any country, or by UPI in India." },
  { icon: ShieldCheck, title: "Review", text: "Each deposit is checked by our compliance team before credits are issued." },
  { icon: Sparkles, title: "5X credits", text: "Your main balance is credited with 5X your deposit, in USD, with no service fees." },
  { icon: Receipt, title: "Ledger", text: "Every allocation is recorded on your downloadable account statement." },
];

const HowItWorks = () => (
  <section id="how" className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
    <p className="label-eyebrow">The credit model</p>
    <h2 className="mt-3 max-w-2xl font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">Deposit once. Get 5X credit.</h2>
    <div className="mt-14 grid gap-4 md:grid-cols-4">
      {STEPS.map((s, i) => (
        <div key={s.title} className="card-lux p-6 hover:-translate-y-1" data-testid={`how-step-${i + 1}`}>
          <div className="flex items-center justify-between">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-purple-500/15 text-purple-300"><s.icon className="h-5 w-5" /></span>
            <span className="font-num text-xs text-slate-600">0{i + 1}</span>
          </div>
          <h3 className="mt-6 font-display text-lg font-semibold text-white">{s.title}</h3>
          <p className="mt-2 text-sm text-slate-400">{s.text}</p>
        </div>
      ))}
    </div>
  </section>
);

const Packages = ({ config }) => (
  <section id="packages" className="border-y border-purple-500/10 bg-[#07050f]">
    <div className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
      <p className="label-eyebrow">Credit packages</p>
      <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">Pick a package. See the full breakdown.</h2>
      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {(config?.packages || []).map((p, i) => {
          const b = calc(p, config);
          const featured = i === 2;
          return (
            <div key={p} data-testid={`landing-package-${p}`} className={`card-lux p-6 hover:-translate-y-1 ${featured ? "border-purple-500/60 glow-violet" : ""}`}>
              {featured && <span className="absolute -top-3 left-6 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white">Most chosen</span>}
              <p className="text-xs uppercase tracking-widest text-slate-500">You pay</p>
              <p className="mt-1 font-num text-2xl font-semibold text-white">{usd(p)}</p>
              <div className="my-5 h-px bg-white/5" />
              <p className="text-xs text-slate-500">Credit balance</p>
              <p className="font-num text-lg font-semibold text-purple-300">{usd(b.credits)}</p>
              <p className="mt-3 text-xs text-slate-500">Service fee</p>
              <p className="font-num text-sm text-emerald-300">$0</p>
            </div>
          );
        })}
      </div>
    </div>
  </section>
);

const TRUST = [
  { icon: Building2, title: "Cyprus-registered entity", text: "Operated from an EU jurisdiction with documented governance." },
  { icon: Scale, title: "Transparent accounting", text: "Every deposit and credit allocation is an immutable ledger line." },
  { icon: Lock, title: "Encrypted & audited", text: "Every dollar deposited and every credit issued is traceable." },
  { icon: Globe2, title: "Authorized markets only", text: "Gaming activity is restricted to legally authorized jurisdictions." },
];

const Trust = () => (
  <section id="trust" className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
    <div className="grid gap-14 lg:grid-cols-[1fr_1.4fr]">
      <div>
        <p className="label-eyebrow">Compliance first</p>
        <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">Infrastructure, not influence.</h2>
        <p className="mt-4 text-slate-400">
          SquareManta provides credit and accounting technology only. We never alter or influence third-party game outcomes.
          Prepaid credits are for platform use only and cannot be withdrawn or refunded.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {TRUST.map((t) => (
          <div key={t.title} className="card-lux p-6">
            <t.icon className="h-5 w-5 text-purple-300" />
            <h3 className="mt-4 font-display font-semibold text-white">{t.title}</h3>
            <p className="mt-1.5 text-sm text-slate-400">{t.text}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

export default function Landing() {
  const config = useConfig();
  return (
    <div className="min-h-screen bg-[#05040A] text-slate-200">
      <NavBar />
      <Hero config={config} />
      <HowItWorks />
      <Packages config={config} />
      <Trust />
      <footer className="border-t border-purple-500/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-10 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <BrandLogo testId="footer-logo-link" />
          <p className="max-w-xl">18+ only. Play responsibly. Prepaid credits are non-withdrawable. Services are available only where legally authorized. © {new Date().getFullYear()} SquareManta Ltd, Limassol, Cyprus.</p>
        </div>
      </footer>
    </div>
  );
}
