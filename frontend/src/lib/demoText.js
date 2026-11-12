const T = {
  en: {
    pays: "pays", clear: "Clear bets", deal: "Deal cards", dealing: "Dealing…", inPlay: "In play", lastResults: "Last results", noRounds: "No rounds yet",
    noBalance: "Not enough demo balance — press Reset to get $1,000 again",
    rivalsWin: "Rivals win", scarmentaWins: "Scarmenta wins", tie: "Tie!",
    rivalsRules: "A is lowest, K is highest. On a Tie, Rivals and Scarmenta bets get half back.",
    joker: "Joker", andarWins: (n) => `Andar wins on card ${n}`, baharWins: (n) => `Bahar wins on card ${n}`,
    abRules: "One Joker card opens. Cards then fall Andar, Bahar, Andar… The side that first gets a card with the same number as the Joker wins.",
    scanning: "Dealer scanning cards…", tpTie: "Tie — bets returned",
    tpRules: "Each side gets 3 cards. Best hand wins: Trail > Pure sequence > Sequence > Color > Pair > High card. Both sides pay 1:1; on a Tie all bets are returned.",
    hands: { 6: "Trail", 5: "Pure sequence", 4: "Sequence", 3: "Color", 2: "Pair", 1: "High card" },
  },
  hi: {
    pays: "milega", clear: "Bet hatao", deal: "Card baanto", dealing: "Baant rahe hain…", inPlay: "Lagi hui bet", lastResults: "Pichhle result", noRounds: "Abhi koi round nahi",
    noBalance: "Demo balance kam hai — Reset dabakar dobara $1,000 lein",
    rivalsWin: "Rivals jeete", scarmentaWins: "Scarmenta jeeta", tie: "Tie!",
    rivalsRules: "A sabse chhota, K sabse bada. Tie aane par Rivals aur Scarmenta ki bet ka aadha wapas milta hai.",
    joker: "Joker", andarWins: (n) => `Andar jeeta, card ${n} par`, baharWins: (n) => `Bahar jeeta, card ${n} par`,
    abRules: "Pehle ek Joker card khulta hai. Phir cards Andar, Bahar, Andar… girte hain. Jis side pehle Joker wala number aaye, wo jeetti hai.",
    scanning: "Dealer card scan kar raha hai…", tpTie: "Tie — bet wapas",
    tpRules: "Dono side ko 3-3 card milte hain. Behtar haath jeetta hai: Trail > Pure sequence > Sequence > Color > Pair > High card. Dono side 1:1 deti hain; Tie par saari bet wapas.",
    hands: { 6: "Trail", 5: "Pure sequence", 4: "Sequence", 3: "Color", 2: "Pair", 1: "High card" },
  },
};

export const t = (lang) => T[lang] || T.en;

const KEY = "scarmenta_demo_langs";
export const loadLangs = () => ({ rivals: "en", "andar-bahar": "en", "teen-patti": "en", tutorial: "en", ...JSON.parse(localStorage.getItem(KEY) || "{}") });
export const saveLangs = (langs) => localStorage.setItem(KEY, JSON.stringify(langs));
