import { useState } from "react";
import { Check, Copy, RotateCcw } from "lucide-react";
import { IconButton } from "../ui/IconButton";
import { Tooltip } from "../ui/Tooltip";

export function MessageActions({ content, onRegenerate, showRegenerate }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  };

  return (
    <div className="flex items-center gap-1">
      <Tooltip label={copied ? "Copied!" : "Copy"}>
        <IconButton size="sm" onClick={handleCopy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </IconButton>
      </Tooltip>
      {showRegenerate && (
        <Tooltip label="Regenerate">
          <IconButton size="sm" onClick={onRegenerate}>
            <RotateCcw size={14} />
          </IconButton>
        </Tooltip>
      )}
    </div>
  );
}
