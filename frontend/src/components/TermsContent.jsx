import { Link } from "react-router-dom";
import { TERMS, TERMS_EFFECTIVE } from "@/lib/terms";

const Paras = ({ items }) => items?.map((t) => <p key={t} className="mt-2">{t}</p>);

export const TermsContent = () => (
  <div className="space-y-6 text-sm leading-relaxed text-slate-300" data-testid="terms-content">
    <div>
      <p className="font-display text-lg font-bold tracking-wide text-white">SCARMENTA</p>
      <p className="text-xs uppercase tracking-wider text-slate-400">Terms & Conditions & User Agreement</p>
      <p className="mt-2 text-xs text-slate-500">Effective Date: {TERMS_EFFECTIVE} · Website: https://scarmenta.com</p>
    </div>
    {TERMS.map((s) => (
      <section key={s.h}>
        <h3 className="font-display text-base font-semibold text-white">{s.h}</h3>
        <Paras items={s.p} />
        {s.ol && <ol className="mt-2 list-decimal space-y-1 pl-5">{s.ol.map((t) => <li key={t}>{t}</li>)}</ol>}
        {s.ul && <ul className="mt-2 list-disc space-y-1 pl-5">{s.ul.map((t) => <li key={t}>{t}</li>)}</ul>}
        <Paras items={s.after} />
        {s.privacyLink && <Link to="/privacy" target="_blank" className="mt-2 inline-block text-purple-300 hover:text-purple-200" data-testid={`terms-privacy-link-${s.h.split(".")[0]}`}>Read the Privacy Policy</Link>}
      </section>
    ))}
    <div className="border-t border-purple-500/20 pt-4 text-center" data-testid="terms-end">
      <p className="font-display font-bold text-white">SCARMENTA</p>
      <p className="text-xs text-slate-400">Technology. Transparency. Trust.</p>
      <p className="mt-1 text-xs text-slate-500">End of Terms & Conditions.</p>
    </div>
  </div>
);

export const TermsAccept = ({ scrolled, onScrolled, checked, onChange, prefix = "register" }) => {
  const onScroll = (e) => {
    const el = e.currentTarget;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 12) onScrolled();
  };
  return (
    <div className="space-y-3" data-testid={`${prefix}-terms-block`}>
      <p className="text-xs uppercase tracking-wider text-slate-400">Terms & Conditions</p>
      <div onScroll={onScroll} data-testid={`${prefix}-terms-scrollbox`}
        className="h-56 overflow-y-auto rounded-xl border border-purple-500/20 bg-black/40 p-4">
        <TermsContent />
      </div>
      <p className="text-xs text-slate-500" data-testid={`${prefix}-terms-hint`}>
        {scrolled ? "Thanks for reading. You can now accept the terms." : "Scroll to the end of the terms to enable acceptance."}
        {" "}<Link to="/terms" target="_blank" className="text-purple-300 hover:text-purple-200" data-testid={`${prefix}-terms-link`}>Open full page</Link>
      </p>
      <label className={`flex items-start gap-3 text-xs ${scrolled ? "text-slate-300" : "text-slate-600"}`}>
        <input type="checkbox" disabled={!scrolled} checked={checked} onChange={(e) => onChange(e.target.checked)}
          data-testid={`${prefix}-terms-checkbox`} className="mt-0.5 h-4 w-4 accent-purple-500 disabled:cursor-not-allowed" />
        <span>I have read and agree to the Scarmenta Terms & Conditions and the{" "}
          <Link to="/privacy" target="_blank" className="text-purple-300 underline hover:text-purple-200" data-testid={`${prefix}-privacy-link`}>Privacy Policy</Link>,
          including the credit usage, non-withdrawal and refund policies, and understand no winnings or profits are guaranteed.</span>
      </label>
    </div>
  );
};
