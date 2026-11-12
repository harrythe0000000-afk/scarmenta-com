const val = (c) => (c.rank === 1 ? 14 : c.rank);

const seqHigh = (v) => {
  if (v[0] === 14 && v[1] === 13 && v[2] === 12) return 16;
  if (v[0] === 14 && v[1] === 3 && v[2] === 2) return 15;
  return v[0] - v[1] === 1 && v[1] - v[2] === 1 ? v[0] : 0;
};

export const evaluate = (cards) => {
  const v = cards.map(val).sort((a, b) => b - a);
  const flush = cards.every((c) => c.suit === cards[0].suit);
  const seq = seqHigh(v);
  if (v[0] === v[2]) return [6, v[0]];
  if (seq && flush) return [5, seq];
  if (seq) return [4, seq];
  if (flush) return [3, ...v];
  if (v[0] === v[1] || v[1] === v[2]) {
    const pair = v[1];
    return [2, pair, v[0] === v[1] ? v[2] : v[0]];
  }
  return [1, ...v];
};

export const compareHands = (a, b) => {
  const x = evaluate(a);
  const y = evaluate(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0) ? 1 : -1;
  }
  return 0;
};
