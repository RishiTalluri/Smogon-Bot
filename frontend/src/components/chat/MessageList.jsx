import { AnimatePresence } from "framer-motion";
import { Message } from "../message/Message";
import { TypingIndicator } from "../message/TypingIndicator";
import { useAutoScroll } from "../../hooks/useAutoScroll";

export function MessageList({ messages, isSending, onRegenerate }) {
  const { containerRef, bottomRef, handleScroll } = useAutoScroll([messages.length, isSending]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto"
    >
      <div className="flex flex-col gap-6 py-6">
        <AnimatePresence initial={false}>
          {messages.map((message, i) => (
            <Message
              key={i}
              message={message}
              isLast={i === messages.length - 1 && message.role === "assistant"}
              onRegenerate={onRegenerate}
            />
          ))}
          {isSending && <TypingIndicator key="typing" />}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
