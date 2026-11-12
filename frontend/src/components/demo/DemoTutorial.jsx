const GUIDES = [
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
];

export const DemoTutorial = () => (
  <div className="grid gap-6 lg:grid-cols-2" data-testid="demo-tutorial">
    {GUIDES.map((g, gi) => (
      <div key={g.title} className="card-lux p-6" data-testid={`demo-tutorial-${gi}`}>
        <p className="label-eyebrow">Tutorial</p>
        <h3 className="mt-1 font-display text-xl font-bold text-white">{g.title}</h3>
        <ol className="mt-5 space-y-4">
          {g.steps.map(([t, d], i) => (
            <li key={t} className="flex gap-4">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 font-num text-sm font-bold text-white">{i + 1}</span>
              <div><p className="font-semibold text-white">{t}</p><p className="mt-1 text-sm text-slate-400">{d}</p></div>
            </li>
          ))}
        </ol>
      </div>
    ))}
    <p className="text-xs text-slate-500 lg:col-span-2">Both tables use free demo credits only. Nothing is taken from or added to your real balance, and results are fully random.</p>
  </div>
);
