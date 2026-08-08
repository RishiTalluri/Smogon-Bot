import { useEffect, useRef, useState } from "react";

// Keeps a scroll container pinned to the bottom as content grows, unless the
// user has deliberately scrolled up to read earlier messages.
export function useAutoScroll(deps = []) {
  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setIsPinnedToBottom(distanceFromBottom < 80);
  };

  const scrollToBottom = (behavior = "smooth") => {
    bottomRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    if (isPinnedToBottom) {
      scrollToBottom("smooth");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { containerRef, bottomRef, handleScroll, isPinnedToBottom, scrollToBottom };
}
