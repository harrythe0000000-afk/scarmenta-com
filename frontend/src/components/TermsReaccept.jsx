import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { TermsAccept } from "@/components/TermsContent";
import { api, formatApiError } from "@/lib/api";
import { TERMS_VERSION } from "@/lib/terms";

export const TermsReaccept = ({ onDone }) => {
  const [scrolled, setScrolled] = useState(false);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const accept = async () => {
    setBusy(true);
    try {
      await api.post("/terms/accept", { terms_version: TERMS_VERSION });
      toast.success("Thanks — updated terms accepted.");
      onDone();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open>
      <DialogContent data-testid="terms-reaccept-dialog" onEscapeKeyDown={(e) => e.preventDefault()} onPointerDownOutside={(e) => e.preventDefault()}
        className="max-w-lg border-purple-500/20 bg-[#0b0816] text-slate-200 [&>button]:hidden">
        <DialogTitle className="font-display text-xl text-white">Our Terms have been updated</DialogTitle>
        <DialogDescription className="text-sm text-slate-400">Please read and accept the updated Terms & Conditions to keep using your account.</DialogDescription>
        <TermsAccept prefix="reaccept" scrolled={scrolled} onScrolled={() => setScrolled(true)} checked={checked} onChange={setChecked} />
        <Button data-testid="terms-reaccept-submit" disabled={!checked || busy} onClick={accept}
          className="h-11 w-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold">
          {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Accept & continue
        </Button>
      </DialogContent>
    </Dialog>
  );
};

export const useTermsRequired = (user) => {
  const [required, setRequired] = useState(null);
  const eligible = user?.role === "user" || user?.role === "agent";
  useEffect(() => {
    if (!eligible) return setRequired(false);
    api.get("/terms/status").then((r) => setRequired(r.data.required)).catch(() => setRequired(false));
  }, [eligible, user?.id]);
  return [required, setRequired];
};
