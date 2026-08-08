import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "../../lib/utils";

export function CodeBlock({ className, children, ...props }) {
  const [copied, setCopied] = useState(false);
  const language = /language-(\w+)/.exec(className || "")?.[1] || "text";
  const codeText = String(children).replace(/\n$/, "");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard permission denied — silently ignore
    }
  };

  return (
    <div className="group relative my-3 overflow-hidden rounded-xl border border-[var(--border-subtle)]">
      <div className="flex items-center justify-between bg-[#161b22] px-4 py-2 text-xs text-zinc-400">
        <span className="font-mono">{language}</span>
        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2 py-1 font-medium transition-colors",
            "hover:bg-white/10 hover:text-zinc-100"
          )}
        >
          {copied ? (
            <>
              <Check size={13} /> Copied
            </>
          ) : (
            <>
              <Copy size={13} /> Copy code
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto bg-[var(--bg-code)] p-4 text-[0.85em] leading-relaxed">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}
