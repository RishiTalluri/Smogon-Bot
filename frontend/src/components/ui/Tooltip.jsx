import { useState } from "react";
import { cn } from "../../lib/utils";

export function Tooltip({ label, children, side = "bottom", className }) {
  const [show, setShow] = useState(false);

  const sideClasses = {
    bottom: "top-full mt-1.5 left-1/2 -translate-x-1/2",
    top: "bottom-full mb-1.5 left-1/2 -translate-x-1/2",
    right: "left-full ml-1.5 top-1/2 -translate-y-1/2",
  };

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium",
            "bg-[var(--text-primary)] text-[var(--bg-app)] shadow-lg",
            "animate-[fadeIn_0.1s_ease-out]",
            sideClasses[side],
            className
          )}
        >
          {label}
        </span>
      )}
    </span>
  );
}
