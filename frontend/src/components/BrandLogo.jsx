import { Link } from "react-router-dom";

export const BrandLogo = ({ to = "/", testId = "brand-logo-link" }) => (
  <Link to={to} data-testid={testId} className="flex items-center gap-2.5 group">
    <img src="/scarmenta-logo.png" alt="Scarmenta" className="h-10 w-10 object-contain drop-shadow-[0_0_14px_rgba(192,48,216,0.45)] transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:rotate-3" />
    <span className="leading-none">
      <span className="block font-display text-lg font-bold tracking-tight text-white">Scarmenta</span>
      <span className="block text-[10px] uppercase tracking-[0.25em] text-[#F2B94B]/80">Credit OS</span>
    </span>
  </Link>
);
