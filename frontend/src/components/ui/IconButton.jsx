import { forwardRef } from "react";
import { cn } from "../../lib/utils";

const SIZES = {
  sm: "h-7 w-7",
  md: "h-8 w-8",
  lg: "h-9 w-9",
};

export const IconButton = forwardRef(function IconButton(
  { children, size = "md", active = false, className, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      type="button"
      className={cn(
        "inline-flex items-center justify-center rounded-lg transition-colors duration-150",
        "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
        "hover:bg-[var(--bg-surface-hover)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]/40",
        "disabled:opacity-40 disabled:pointer-events-none",
        active && "bg-[var(--bg-surface-hover)] text-[var(--text-primary)]",
        SIZES[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
});
