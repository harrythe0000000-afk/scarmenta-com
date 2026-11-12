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
import { TeenPattiTable } from "@/components/demo/TeenPattiTable";
import { Portfolio } from "@/components/demo/Portfolio";
import { LangToggle, RivalBadges } from "@/components/demo/TableParts";
import { loadLangs, saveLangs } from "@/lib/demoText";
import { STREAK_GOAL, StreakMeter } from "@/components/demo/StreakMeter";
import { toast } from "sonner";
import { setSoundOn, soundOn } from "@/lib/sounds";
import { usd } from "@/lib/format";

const START = 1000;
const EMPTY_STATS = { rounds: 0, wins: 0, losses: 0, pnl: 0, bestWin: 0 };
const GAMES = [
  ["rivals", "Scarmenta vs Rivals", RivalsTable],
  ["andar-bahar", "Andar Bahar", AndarBaharTable],
  ["teen-patti", "Teen Patti", TeenPattiTable],
  ["tutorial", "Tutorial", null],
];
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
  const [stats, setStats] = useState(EMPTY_STATS);
  const [prompt, setPrompt] = useState(false);
  const [sound, setSound] = useState(soundOn);
  const [streak, setStreak] = useState(0);
  const [best, setBest] = useState(0);
  const [game, setGame] = useState(GAMES[0][1]);
  const [langs, setLangs] = useState(loadLangs);
  const setLang = (tab) => (v) => setLangs((l) => {
    const next = { ...l, [tab]: v };
    saveLangs(next);
    return next;
  });
  const onRound = (name) => (net) => {
    setBalance((b) => Math.round((b + net) * 100) / 100);
    setGame(name);
    const next = net > 0 ? streak + 1 : 0;
    setStreak(next);
    setBest((b) => Math.max(b, next));
    if (next === STREAK_GOAL) toast.success("Hot Streak! 3 wins in a row", { position: "top-center" });
    setStats((st) => {
      const rounds = st.rounds + 1;
      if (rounds === PROMPT_AFTER) setPrompt(true);
      return { rounds, wins: st.wins + (net > 0 ? 1 : 0), losses: st.losses + (net < 0 ? 1 : 0),
        pnl: Math.round((st.pnl + net) * 100) / 100, bestWin: Math.max(st.bestWin, net) };
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
      <Portfolio stats={stats} />
      <Tabs defaultValue="rivals">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <TabsList className="bg-black/40" data-testid="demo-tabs">
            <TabsTrigger value="rivals" data-testid="demo-tab-rivals">Scarmenta vs Rivals</TabsTrigger>
            <TabsTrigger value="andar-bahar" data-testid="demo-tab-andar-bahar">Andar Bahar</TabsTrigger>
            <TabsTrigger value="teen-patti" data-testid="demo-tab-teen-patti">Teen Patti</TabsTrigger>
            <TabsTrigger value="tutorial" data-testid="demo-tab-tutorial">Tutorial</TabsTrigger>
          </TabsList>
          <div className="flex flex-wrap items-center gap-3">
            <StreakMeter streak={streak} best={best} game={game} />
            <div className="text-right">
              <p className="text-[11px] uppercase tracking-wider text-slate-500">Demo balance</p>
              <p className="font-num text-2xl font-bold text-white" data-testid="demo-balance">{usd(balance)}</p>
            </div>
            <Button size="icon" variant="outline" onClick={toggleSound} data-testid="demo-sound-toggle" aria-label={sound ? "Mute" : "Unmute"} className="rounded-full border-purple-500/30 bg-transparent">
              {sound ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </Button>
            <Button variant="outline" onClick={() => { setBalance(START); setStats(EMPTY_STATS); setStreak(0); }} data-testid="demo-reset-button" className="rounded-full border-purple-500/30 bg-transparent"><RotateCcw className="mr-2 h-4 w-4" /> Reset</Button>
          </div>
        </div>
        <div className="card-lux p-5 sm:p-8">
          {GAMES.map(([tab, name, Table]) => (
            <TabsContent key={tab} value={tab} className="mt-0">
              <div className="mb-4 flex justify-end"><LangToggle lang={langs[tab]} setLang={setLang(tab)} testId={`demo-lang-${tab}`} /></div>
              {Table ? <Table free={balance} onRound={onRound(name)} lang={langs[tab]} rivalBadges={<RivalBadges />} /> : <DemoTutorial lang={langs[tab]} />}
            </TabsContent>
          ))}
        </div>
      </Tabs>
      <p className="mt-4 text-xs text-slate-500">The demo balance resets to $1,000 every time you open this page.</p>
      <RealPlayPrompt open={prompt} onClose={() => setPrompt(false)} />
    </>
  );
}
