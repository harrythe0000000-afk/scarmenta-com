import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FlaskConical, RotateCcw, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { PageHeader } from "@/components/StatCard";
import { RivalsTable } from "@/components/demo/RivalsTable";
import { AndarBaharTable } from "@/components/demo/AndarBaharTable";
import { DemoTutorial } from "@/components/demo/DemoTutorial";
import { setSoundOn, soundOn } from "@/lib/sounds";
import { usd } from "@/lib/format";

const START = 1000;
const PROMPT_AFTER = 5;

const RealPlayPrompt = ({ open, onClose }) => {
  const navigate = useNavigate();
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="demo-real-play-dialog" className="max-w-md border-purple-500/20 bg-[#0b0816] text-slate-200">
        <DialogTitle className="font-display text-2xl text-white">Ready for real play?</DialogTitle>
        <DialogDescription className="text-sm text-slate-400">
          You've played {PROMPT_AFTER} practice rounds. Every approved deposit gets 5X credits to use on our partner game platforms. Play responsibly; winnings are never guaranteed.
        </DialogDescription>
        <div className="mt-2 flex gap-2">
          <Button variant="outline" onClick={onClose} data-testid="demo-keep-practicing" className="flex-1 rounded-full border-purple-500/30 bg-transparent">Keep practicing</Button>
          <Button onClick={() => navigate("/app/deposits")} data-testid="demo-go-deposit" className="flex-1 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold">Go to Deposits</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default function DemoGame() {
  const [balance, setBalance] = useState(START);
  const [rounds, setRounds] = useState(0);
  const [prompt, setPrompt] = useState(false);
  const [sound, setSound] = useState(soundOn);
  const onRound = (net) => {
    setBalance((b) => Math.round((b + net) * 100) / 100);
    setRounds((r) => {
      if (r + 1 === PROMPT_AFTER) setPrompt(true);
      return r + 1;
    });
  };
  const toggleSound = () => {
    setSoundOn(!sound);
    setSound(!sound);
  };

  return (
    <>
      <PageHeader eyebrow="Practice tables" title="Demo games" desc="Free card games to learn how betting works before you play for real." />
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200" data-testid="demo-disclaimer">
        <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
        Practice only. You play with free demo credits, your real Scarmenta balance is never used, and nothing won here can be kept. Results are fully random.
      </div>
      <Tabs defaultValue="rivals">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <TabsList className="bg-black/40" data-testid="demo-tabs">
            <TabsTrigger value="rivals" data-testid="demo-tab-rivals">Scarmenta vs Rivals</TabsTrigger>
            <TabsTrigger value="andar-bahar" data-testid="demo-tab-andar-bahar">Andar Bahar</TabsTrigger>
            <TabsTrigger value="tutorial" data-testid="demo-tab-tutorial">Tutorial</TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-[11px] uppercase tracking-wider text-slate-500">Demo balance</p>
              <p className="font-num text-2xl font-bold text-white" data-testid="demo-balance">{usd(balance)}</p>
            </div>
            <Button size="icon" variant="outline" onClick={toggleSound} data-testid="demo-sound-toggle" aria-label={sound ? "Mute" : "Unmute"} className="rounded-full border-purple-500/30 bg-transparent">
              {sound ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </Button>
            <Button variant="outline" onClick={() => setBalance(START)} data-testid="demo-reset-button" className="rounded-full border-purple-500/30 bg-transparent"><RotateCcw className="mr-2 h-4 w-4" /> Reset</Button>
          </div>
        </div>
        <div className="card-lux p-5 sm:p-8">
          <TabsContent value="rivals" className="mt-0"><RivalsTable free={balance} onRound={onRound} /></TabsContent>
          <TabsContent value="andar-bahar" className="mt-0"><AndarBaharTable free={balance} onRound={onRound} /></TabsContent>
          <TabsContent value="tutorial" className="mt-0"><DemoTutorial /></TabsContent>
        </div>
      </Tabs>
      <p className="mt-4 text-xs text-slate-500">The demo balance resets to $1,000 every time you open this page.</p>
      <RealPlayPrompt open={prompt} onClose={() => setPrompt(false)} />
    </>
  );
}
