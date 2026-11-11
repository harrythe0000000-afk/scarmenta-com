import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";

const AuthLayout = ({ title, subtitle, children, footer }) => (
  <div className="relative grid min-h-screen bg-[#05040A] lg:grid-cols-2">
    <div className="relative hidden overflow-hidden border-r border-purple-500/10 lg:block grain">
      <div className="absolute -left-40 top-10 h-[480px] w-[480px] rounded-full bg-purple-700/25 blur-[120px]" />
      <div className="absolute bottom-0 right-0 h-[380px] w-[380px] rounded-full bg-fuchsia-700/15 blur-[120px]" />
      <div className="relative z-10 flex h-full flex-col justify-between p-12">
        <BrandLogo />
        <div>
          <p className="label-eyebrow">Gaming credit infrastructure</p>
          <p className="mt-4 max-w-md font-display text-4xl font-bold leading-tight text-white">
            5X credits.<br />One transparent ledger.
          </p>
          <p className="mt-4 max-w-md text-slate-400">Every cash deposit and credit allocation, tracked line by line.</p>
        </div>
        <p className="text-xs text-slate-600">Limassol, Cyprus · Serving South Asia & Middle East</p>
      </div>
    </div>
    <div className="flex items-center justify-center px-5 py-12">
      <div className="w-full max-w-md fade-up">
        <div className="mb-8 lg:hidden"><BrandLogo /></div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-slate-400">{subtitle}</p>}
        <div className="mt-8">{children}</div>
        {footer && <div className="mt-6 text-sm text-slate-400">{footer}</div>}
      </div>
    </div>
  </div>
);

const Field = ({ id, label, ...props }) => (
  <div className="space-y-2">
    <Label htmlFor={id} className="text-xs uppercase tracking-wider text-slate-400">{label}</Label>
    <Input id={id} {...props} className="h-12 rounded-xl border-purple-500/20 bg-black/40 text-white focus-visible:ring-purple-500" />
  </div>
);

const SubmitBtn = ({ busy, children, testId }) => (
  <Button type="submit" disabled={busy} data-testid={testId} className="h-12 w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 text-base font-semibold hover:from-violet-500 hover:to-fuchsia-500">
    {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
    {children}
  </Button>
);

const ErrorText = ({ error, testId }) => error ? <p data-testid={testId} className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p> : null;

export const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await login(form.email, form.password);
      navigate(u.role === "admin" ? "/admin" : "/app");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your Aetheria account."
      footer={<>New here? <Link to="/register" className="text-purple-300 hover:text-purple-200" data-testid="login-to-register-link">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-5" data-testid="login-form">
        <Field id="email" label="Email" type="email" required value={form.email} data-testid="login-email-input" onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field id="password" label="Password" type="password" required value={form.password} data-testid="login-password-input" onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-xs text-slate-400 hover:text-purple-300" data-testid="forgot-password-link">Forgot password?</Link>
        </div>
        <ErrorText error={error} testId="login-error" />
        <SubmitBtn busy={busy} testId="login-submit-button">Sign in</SubmitBtn>
      </form>
    </AuthLayout>
  );
};

export const Register = () => {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ name: "", email: "", password: "", country: "", referral_code: params.get("ref") || "" });
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (!agree) return setError("Please confirm you are 18+ and in an authorized jurisdiction.");
    setBusy(true);
    setError("");
    try {
      const u = await register({ ...form, country: form.country || null, referral_code: form.referral_code || null });
      toast.success(u.verification_sent ? "Account created — check your inbox to verify your email." : "Account created. Use 'Resend email' to get your verification link.");
      navigate("/app");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <AuthLayout title="Create your account" subtitle="Email verification is required before your first deposit."
      footer={<>Already registered? <Link to="/login" className="text-purple-300 hover:text-purple-200" data-testid="register-to-login-link">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-5" data-testid="register-form">
        <Field id="name" label="Full name" required value={form.name} data-testid="register-name-input" onChange={set("name")} />
        <Field id="email" label="Email" type="email" required value={form.email} data-testid="register-email-input" onChange={set("email")} />
        <Field id="password" label="Password (min 8 chars)" type="password" minLength={8} required value={form.password} data-testid="register-password-input" onChange={set("password")} />
        <Field id="country" label="Country (optional)" value={form.country} data-testid="register-country-input" onChange={set("country")} />
        <Field id="referral" label="Referral code (optional)" value={form.referral_code} data-testid="register-referral-input" onChange={set("referral_code")} />
        <label className="flex items-start gap-3 text-xs text-slate-400">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} data-testid="register-agree-checkbox" className="mt-0.5 h-4 w-4 accent-purple-500" />
          I confirm I am 18+ and located in a jurisdiction where these services are legally authorized.
        </label>
        <ErrorText error={error} testId="register-error" />
        <SubmitBtn busy={busy} testId="register-submit-button">Create account</SubmitBtn>
      </form>
    </AuthLayout>
  );
};

export const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Reset password" subtitle="We'll email you a secure reset link."
      footer={<Link to="/login" className="text-purple-300" data-testid="forgot-back-to-login-link">Back to sign in</Link>}>
      {sent ? (
        <p data-testid="forgot-password-sent" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
          If an account exists for that email, a reset link is on its way.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <Field id="email" label="Email" type="email" required value={email} data-testid="forgot-email-input" onChange={(e) => setEmail(e.target.value)} />
          <SubmitBtn busy={busy} testId="forgot-submit-button">Send reset link</SubmitBtn>
        </form>
      )}
    </AuthLayout>
  );
};

export const ResetPassword = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/reset-password", { token: params.get("token") || "", password });
      toast.success("Password updated. Please sign in.");
      navigate("/login");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Choose a new password">
      <form onSubmit={submit} className="space-y-5">
        <Field id="password" label="New password" type="password" minLength={8} required value={password} data-testid="reset-password-input" onChange={(e) => setPassword(e.target.value)} />
        <ErrorText error={error} testId="reset-error" />
        <SubmitBtn busy={busy} testId="reset-submit-button">Update password</SubmitBtn>
      </form>
    </AuthLayout>
  );
};

export const VerifyEmail = () => {
  const [params] = useSearchParams();
  const { user, refresh } = useAuth();
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    api.post("/auth/verify-email", { token: params.get("token") || "" })
      .then(() => { setState("ok"); refresh(); })
      .catch((e) => { setError(formatApiError(e)); setState("error"); });
  }, [params, refresh]);
  return (
    <AuthLayout title="Email verification">
      <div className="card-lux p-6 text-center" data-testid="verify-email-status">
        {state === "loading" && <Loader2 className="mx-auto h-8 w-8 animate-spin text-purple-400" />}
        {state === "ok" && (<><CheckCircle2 className="mx-auto h-10 w-10 text-emerald-400" /><p className="mt-3 text-white">Your email is verified. Deposits are now unlocked.</p></>)}
        {state === "error" && (<><XCircle className="mx-auto h-10 w-10 text-red-400" /><p className="mt-3 text-red-200">{error}</p></>)}
        {state !== "loading" && (
          <Button asChild className="mt-6 rounded-full bg-purple-600 hover:bg-purple-500" data-testid="verify-continue-button">
            <Link to={user ? (user.role === "admin" ? "/admin" : "/app") : "/login"}>Continue</Link>
          </Button>
        )}
      </div>
    </AuthLayout>
  );
};
