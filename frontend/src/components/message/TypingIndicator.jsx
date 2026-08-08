import { motion } from "framer-motion";
import { LoadingDots } from "./LoadingDots";

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="mx-auto w-full max-w-3xl px-4"
    >
      <div className="flex items-center gap-3 py-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent)]/10">
          <span className="h-2 w-2 rounded-full bg-[var(--color-accent)]" />
        </div>
        <LoadingDots />
      </div>
    </motion.div>
  );
}
