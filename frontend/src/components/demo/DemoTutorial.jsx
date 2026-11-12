import { useState } from "react";

const LANG_KEY = "scarmenta_tutorial_lang";

const GUIDES = {
  en: [
    { title: "Scarmenta vs Rivals", steps: [
      ["Pick a chip", "Tap $10, $50, $100 or $500 to choose how much each tap bets."],
      ["Choose a side", "Tap Rivals (Stake · 1win · 4rabet), Scarmenta or Tie. Tap again to add more. You can bet on more than one."],
      ["Deal and see the result", "One card opens for each side and the higher card wins (A low, K high). Sides pay 1:1, Tie pays 8:1, and on a Tie side bets get half back."],
    ] },
    { title: "Andar Bahar", steps: [
      ["Pick a chip", "Choose your chip amount, same as the other table."],
      ["Bet Andar or Bahar", "Andar pays 0.9:1 and Bahar pays 1:1, like in real casinos."],
      ["Watch the deal", "A Joker opens, then cards fall Andar, Bahar, Andar… The first side to get the Joker's number wins."],
    ] },
  ],
  hi: [
    { title: "Scarmenta vs Rivals", steps: [
      ["Chip chuniye", "$10, $50, $100 ya $500 par tap karein — har tap par utni bet lagegi."],
      ["Side chuniye", "Rivals (Stake · 1win · 4rabet), Scarmenta ya Tie par tap karein. Dobara tap karne se bet badhegi. Ek se zyada side par bhi laga sakte hain."],
      ["Deal karein aur result dekhein", "Dono side ek-ek card khulta hai, bada card jeetta hai (A sabse chhota, K sabse bada). Side 1:1 deti hai, Tie 8:1 deta hai, aur Tie aane par side wali bet ka aadha wapas milta hai."],
    ] },
    { title: "Andar Bahar", steps: [
      ["Chip chuniye", "Doosri table ki tarah apni chip amount chuniye."],
      ["Andar ya Bahar par bet", "Andar 0.9:1 deta hai aur Bahar 1:1, bilkul asli casino jaisa."],
      ["Deal dekhiye", "Pehle Joker card khulta hai, phir cards Andar, Bahar, Andar… girte hain. Jis side pehle Joker wala number aaye, wo jeetti hai."],
    ] },
  ],
};

const NOTE = {
  en: "Both tables use free demo credits only. Nothing is taken from or added to your real balance, and results are fully random.",
  hi: "Dono tables sirf free demo credits se chalti hain. Aapke asli balance se na kuch katta hai na judta hai, aur result poori tarah random hai.",
};

const LangToggle = ({ lang, setLang }) => (
  <div className="flex gap-1 rounded-full border border-purple-500/20 bg-black/40 p-1" data-testid="tutorial-lang-toggle">
    {[["en", "English"], ["hi", "Hinglish"]].map(([v, l]) => (
      <button key={v} type="button" onClick={() => setLang(v)} data-testid={`tutorial-lang-${v}`}
        className={`rounded-full px-4 py-1 text-xs font-medium transition-colors ${lang === v ? "bg-purple-600 text-white" : "text-slate-400 hover:text-white"}`}>{l}</button>
    ))}
  </div>
);

export const DemoTutorial = () => {
  const [lang, setLangState] = useState(() => localStorage.getItem(LANG_KEY) || "en");
  const setLang = (v) => {
    localStorage.setItem(LANG_KEY, v);
    setLangState(v);
  };
  return (
    <div className="space-y-6" data-testid="demo-tutorial">
      <div className="flex justify-end"><LangToggle lang={lang} setLang={setLang} /></div>
      <div className="grid gap-6 lg:grid-cols-2">
        {GUIDES[lang].map((g, gi) => (
          <div key={g.title} className="card-lux p-6" data-testid={`demo-tutorial-${gi}`}>
            <p className="label-eyebrow">Tutorial</p>
            <h3 className="mt-1 font-display text-xl font-bold text-white">{g.title}</h3>
            <ol className="mt-5 space-y-4">
              {g.steps.map(([t, d], i) => (
                <li key={t} className="flex gap-4">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 font-num text-sm font-bold text-white">{i + 1}</span>
                  <div><p className="font-semibold text-white" data-testid={`demo-tutorial-${gi}-step-${i}`}>{t}</p><p className="mt-1 text-sm text-slate-400">{d}</p></div>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500">{NOTE[lang]}</p>
    </div>
  );
};
