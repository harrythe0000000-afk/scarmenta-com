const KEY = "scarmenta_demo_sound";
let ctx;

export const soundOn = () => localStorage.getItem(KEY) !== "off";
export const setSoundOn = (on) => localStorage.setItem(KEY, on ? "on" : "off");

const audio = () => {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
};

const tone = (freq, start, dur, type = "sine", vol = 0.15) => {
  const a = audio();
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.value = freq;
  g.gain.setValueAtTime(vol, a.currentTime + start);
  g.gain.exponentialRampToValueAtTime(0.001, a.currentTime + start + dur);
  o.connect(g).connect(a.destination);
  o.start(a.currentTime + start);
  o.stop(a.currentTime + start + dur);
};

const flip = () => {
  const a = audio();
  const len = Math.floor(a.sampleRate * 0.12);
  const buf = a.createBuffer(1, len, a.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len) ** 3;
  const src = a.createBufferSource();
  const f = a.createBiquadFilter();
  const g = a.createGain();
  f.type = "bandpass";
  f.frequency.value = 2500;
  g.gain.value = 0.5;
  src.buffer = buf;
  src.connect(f).connect(g).connect(a.destination);
  src.start();
};

const SOUNDS = {
  flip,
  chip: () => { tone(1800, 0, 0.05, "triangle", 0.12); tone(2600, 0.03, 0.06, "triangle", 0.08); },
  win: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.09, 0.25, "sine", 0.12)),
  lose: () => { tone(330, 0, 0.2, "sine", 0.1); tone(247, 0.15, 0.3, "sine", 0.1); },
};

export const play = (name) => {
  if (!soundOn()) return;
  try {
    SOUNDS[name]();
  } catch {
    /* audio not available */
  }
};
