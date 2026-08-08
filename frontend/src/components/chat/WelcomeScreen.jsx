import { motion } from "framer-motion";
import { Sparkles, Swords, ShieldQuestion, TrendingUp } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: Swords,
    title: "Best Gholdengo moveset",
    prompt: "What's the best Gholdengo moveset in SV OU?",
  },
  {
    icon: ShieldQuestion,
    title: "Why was it banned?",
    prompt: "Why was Iron Bundle banned from OU?",
  },
  {
    icon: TrendingUp,
    title: "Tier list check",
    prompt: "What Pokémon are S-tier in SV UU?",
  },
  {
    icon: Sparkles,
    title: "Counter strategy",
    prompt: "What are good counters to Great Tusk in SV OU?",
  },
];

export function WelcomeScreen({ onSuggestionClick }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="mx-auto flex w-full max-w-2xl flex-col items-center text-center"
      >
        <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--color-accent)]/10">
          <Sparkles size={22} className="text-[var(--color-accent)]" />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-[var(--text-primary)]">
          Smogon Bot
        </h1>
        <p className="mt-2 max-w-md text-[var(--text-secondary)]">
          Ask about movesets, tiering, viability, or matchups — grounded in real Smogon forum
          analysis.
        </p>

        <div className="mt-8 grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2">
          {SUGGESTIONS.map((s, i) => (
            <motion.button
              key={s.title}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.05 * i, ease: "easeOut" }}
              onClick={() => onSuggestionClick(s.prompt)}
              className="group flex flex-col items-start gap-2 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 text-left transition-all duration-150 hover:-translate-y-0.5 hover:border-[var(--border-strong)] hover:shadow-[var(--shadow-composer)]"
            >
              <s.icon size={16} className="text-[var(--color-accent)]" />
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)]">{s.title}</p>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)] line-clamp-1">{s.prompt}</p>
              </div>
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
