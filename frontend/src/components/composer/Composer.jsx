import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { cn } from "../../lib/utils";

const MAX_HEIGHT = 200;

export function Composer({ onSend, isSending, disabled, placeholder }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!value.trim() || isSending || disabled) return;
    onSend(value);
    setValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="sticky bottom-0 w-full bg-gradient-to-t from-[var(--bg-app)] via-[var(--bg-app)] to-transparent pb-4 pt-3">
      <form
        onSubmit={handleSubmit}
        className={cn(
          "mx-auto flex w-full max-w-3xl items-end gap-2 rounded-2xl border border-[var(--border-subtle)]",
          "bg-[var(--bg-composer)] px-3 py-2.5 shadow-[var(--shadow-composer)]",
          "transition-shadow duration-150 focus-within:border-[var(--border-strong)]",
          disabled && "opacity-60"
        )}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Ask about a Pokémon, moveset, or matchup…"}
          className="max-h-[200px] flex-1 resize-none bg-transparent px-1.5 py-1 text-[0.95rem] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none"
        />
        <button
          type="submit"
          disabled={!value.trim() || isSending || disabled}
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-all duration-150",
            value.trim() && !isSending && !disabled
              ? "bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)]"
              : "bg-[var(--bg-surface-hover)] text-[var(--text-tertiary)]"
          )}
          aria-label={isSending ? "Sending" : "Send message"}
        >
          {isSending ? <Square size={13} fill="currentColor" /> : <ArrowUp size={16} />}
        </button>
      </form>
      <p className="mt-2 text-center text-xs text-[var(--text-tertiary)]">
        Smogon Bot can be wrong. Verify movesets before tournament play.
      </p>
    </div>
  );
}
