import { Link } from "react-router-dom";

export const BrandLogo = ({ to = "/", testId = "brand-logo-link" }) => (
  <Link to={to} data-testid={testId} className="flex items-center gap-2.5 group">
    <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 glow-violet transition-transform duration-300 group-hover:rotate-6">
      <span className="font-display text-lg font-extrabold text-white">A</span>
    </span>
    <span className="leading-none">
      <span className="block font-display text-lg font-bold tracking-tight text-white">Aetheria</span>
      <span className="block text-[10px] uppercase tracking-[0.25em] text-purple-300/70">Credit OS</span>
    </span>
  </Link>
);
