import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { MarkdownRenderer } from "../markdown/MarkdownRenderer";
import { MessageActions } from "./MessageActions";
import { cn, formatTime } from "../../lib/utils";

export function Message({ message, isLast, onRegenerate }) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn("group mx-auto w-full max-w-3xl px-4", isUser ? "flex justify-end" : "")}
    >
      <div className={cn("flex gap-3", isUser ? "max-w-[80%] flex-row-reverse" : "w-full")}>
        {!isUser && (
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent)]/10">
            <Sparkles size={14} className="text-[var(--color-accent)]" />
          </div>
        )}

        <div className={cn("flex min-w-0 flex-col", isUser ? "items-end" : "items-start flex-1")}>
          <div
            className={cn(
              isUser
                ? "rounded-2xl rounded-tr-sm bg-[var(--bg-bubble-user)] px-4 py-2.5 text-[var(--text-primary)]"
                : "w-full py-0.5"
            )}
          >
            {message.isError ? (
              <p className="text-sm text-red-400">{message.content}</p>
            ) : isUser ? (
              <p className="whitespace-pre-wrap text-[0.95rem] leading-relaxed">{message.content}</p>
            ) : (
              <MarkdownRenderer content={message.content} />
            )}
          </div>

          {!isUser && message.correctedMon && !message.isError && (
            <span className="mt-1 rounded-full bg-[var(--bg-surface-hover)] px-2.5 py-0.5 text-xs text-[var(--text-tertiary)]">
              Matched: {message.correctedMon}
            </span>
          )}

          <div
            className={cn(
              "mt-1 flex items-center gap-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100",
              isUser ? "flex-row-reverse" : ""
            )}
          >
            {message.timestamp && (
              <span className="text-xs text-[var(--text-tertiary)]">{formatTime(message.timestamp)}</span>
            )}
            {!message.isError && (
              <MessageActions
                content={message.content}
                onRegenerate={onRegenerate}
                showRegenerate={!isUser && isLast}
              />
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
