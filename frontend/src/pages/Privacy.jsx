import { Link } from "react-router-dom";
import { BrandLogo } from "@/components/BrandLogo";
import { PRIVACY, PRIVACY_EFFECTIVE } from "@/lib/privacy";

export default function Privacy() {
  return (
    <div className="min-h-screen bg-[#05040A] px-5 py-10" data-testid="privacy-page">
      <div className="mx-auto max-w-3xl">
        <div className="mb-10 flex items-center justify-between">
          <Link to="/" data-testid="privacy-home-link"><BrandLogo /></Link>
          <Link to="/terms" className="text-sm text-purple-300 hover:text-purple-200" data-testid="privacy-terms-link">Terms & Conditions</Link>
        </div>
        <div className="card-lux space-y-6 p-6 text-sm leading-relaxed text-slate-300 sm:p-10" data-testid="privacy-content">
          <div>
            <p className="font-display text-lg font-bold tracking-wide text-white">SCARMENTA</p>
            <p className="text-xs uppercase tracking-wider text-slate-400">Privacy Policy</p>
            <p className="mt-2 text-xs text-slate-500">Effective Date: {PRIVACY_EFFECTIVE} · Website: https://scarmenta.com</p>
          </div>
          {PRIVACY.map((s) => (
            <section key={s.h}>
              <h3 className="font-display text-base font-semibold text-white">{s.h}</h3>
              {s.p?.map((t) => <p key={t} className="mt-2">{t}</p>)}
              {s.ul && <ul className="mt-2 list-disc space-y-1 pl-5">{s.ul.map((t) => <li key={t}>{t}</li>)}</ul>}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
