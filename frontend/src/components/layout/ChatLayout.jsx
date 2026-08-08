import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { Sidebar } from "../sidebar/Sidebar";
import { ChatArea } from "../chat/ChatArea";
import { useChatContext } from "../../context/ChatContext";

export function ChatLayout() {
  const { error, setError } = useChatContext();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[var(--bg-app)]">
      <AnimatePresence initial={false}>
        <Sidebar key="sidebar" />
      </AnimatePresence>

      <div className="relative flex min-w-0 flex-1 flex-col">
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute left-1/2 top-3 z-30 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400 shadow-[var(--shadow-popover)]"
            >
              <AlertTriangle size={14} />
              <span>{error}</span>
              <button onClick={() => setError(null)} className="ml-1 opacity-70 hover:opacity-100">
                <X size={13} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <ChatArea />
      </div>
    </div>
  );
}
