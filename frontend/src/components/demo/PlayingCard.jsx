import { motion, AnimatePresence } from "framer-motion";

const SUITS = [["♠", "text-slate-900"], ["♥", "text-red-600"], ["♦", "text-red-600"], ["♣", "text-slate-900"]];
const RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];

const rand = (n) => crypto.getRandomValues(new Uint32Array(1))[0] % n;
export const drawCard = () => ({ rank: rand(13) + 1, suit: rand(4) });

export const PlayingCard = ({ card, testId, delay = 0 }) => (
  <div className="relative h-36 w-24 sm:h-44 sm:w-32 [perspective:800px]" data-testid={testId}>
    <AnimatePresence mode="wait">
      {card ? (
        <motion.div key={`${card.rank}-${card.suit}-${delay}`} initial={{ rotateY: 180, y: -30, opacity: 0 }} animate={{ rotateY: 0, y: 0, opacity: 1 }}
          transition={{ duration: 0.55, delay }} className="absolute inset-0 flex flex-col justify-between rounded-xl bg-white p-2 shadow-xl shadow-black/50">
          <span className={`text-lg font-bold leading-none sm:text-xl ${SUITS[card.suit][1]}`}>{RANKS[card.rank - 1]}<br />{SUITS[card.suit][0]}</span>
          <span className={`self-center text-4xl sm:text-5xl ${SUITS[card.suit][1]}`}>{SUITS[card.suit][0]}</span>
          <span className={`rotate-180 text-lg font-bold leading-none sm:text-xl ${SUITS[card.suit][1]}`}>{RANKS[card.rank - 1]}<br />{SUITS[card.suit][0]}</span>
        </motion.div>
      ) : (
        <motion.div key="back" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="absolute inset-0 rounded-xl border-2 border-purple-400/40 bg-[repeating-linear-gradient(45deg,#3b0764_0,#3b0764_6px,#581c87_6px,#581c87_12px)] shadow-xl shadow-black/50" />
      )}
    </AnimatePresence>
  </div>
);
