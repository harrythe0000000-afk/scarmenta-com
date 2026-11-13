const BASE = "https://static.prod-images.emergentagent.com/jobs/b2a2a694-b6d0-4927-b2a6-e421a0415564/images/";
const IMG = {
  roulette: "c3b6be14f495b2b861fc1ba51629112ee775a890ae6d68a2c9e9d1fc1d2fb3c1.jpeg",
  blackjack: "d1926c65145920f5dc8f4f5117313ae59bb8fccf1250dd1f3c9ffa6a38c9aadc.jpeg",
  baccarat: "b08aebc4cb5e7b7b4279500b3582baabc39cdf7a67b3eabdbef2e67b21105b74.jpeg",
  teenpatti: "a3c384a7a431b9bc7370af24d3998924486c7389ef9d15bdf37f2403c2ade403.jpeg",
  andarbahar: "f2302fdae935fc06ea36c9b3c2911552d8eb42e6eada1aff2e032a9380219d17.jpeg",
  dragontiger: "b022969335a099368b7504480dab4553c247db139bfe84713aad80eb048a5279.jpeg",
  dice: "d1d16d2f69b1bb1681592950fa565d311f6bce94e1506de2317881c5c8af5594.jpeg",
  dealer: "f5efc6c3ef4dceedf188745f9a7306a46ffba1386a9ad0ac75ae9f9adb071204.jpeg",
};
const RULES = [
  [/roulette|wheel|lightning/i, "roulette"],
  [/black ?jack|21/i, "blackjack"],
  [/baccarat|punto/i, "baccarat"],
  [/teen ?patti|poker|hold.?em|card/i, "teenpatti"],
  [/andar|bahar/i, "andarbahar"],
  [/dragon|tiger/i, "dragontiger"],
  [/sic ?bo|dice|craps/i, "dice"],
];
const ROTATE = Object.keys(IMG);

export const defaultGameImage = (g) => {
  const hit = RULES.find(([re]) => re.test(g.name || ""));
  if (hit) return BASE + IMG[hit[1]];
  const seed = [...(g.provider || "")].reduce((a, c) => a + c.charCodeAt(0), 0);
  return BASE + IMG[ROTATE[seed % ROTATE.length]];
};
