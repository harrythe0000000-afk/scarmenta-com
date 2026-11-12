import { Link } from "react-router-dom";
import { BrandLogo } from "@/components/BrandLogo";
import { TermsContent } from "@/components/TermsContent";

export default function Terms() {
  return (
    <div className="min-h-screen bg-[#05040A] px-5 py-10" data-testid="terms-page">
      <div className="mx-auto max-w-3xl">
        <div className="mb-10 flex items-center justify-between">
          <Link to="/" data-testid="terms-home-link"><BrandLogo /></Link>
          <Link to="/register" className="text-sm text-purple-300 hover:text-purple-200" data-testid="terms-register-link">Create account</Link>
        </div>
        <div className="card-lux p-6 sm:p-10"><TermsContent /></div>
      </div>
    </div>
  );
}
