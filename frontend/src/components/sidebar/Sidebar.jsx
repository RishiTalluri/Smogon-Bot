import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PanelLeft, Plus, Search, Sparkles } from "lucide-react";
import { useChatContext } from "../../context/ChatContext";
import { useUI } from "../../context/UIContext";
import { IconButton } from "../ui/IconButton";
import { Tooltip } from "../ui/Tooltip";
import { ThreadList } from "./ThreadList";

export function Sidebar() {
  const { chats, activeChatId, isLoadingChats, selectChat, startNewChat, renameChat, removeChat } =
    useChatContext();
  const { isSidebarCollapsed, toggleSidebar } = useUI();
  const [query, setQuery] = useState("");

  const filteredChats = useMemo(() => {
    if (!query.trim()) return chats;
    const q = query.toLowerCase();
    return chats.filter((c) => (c.title || "").toLowerCase().includes(q));
  }, [chats, query]);

  if (isSidebarCollapsed) return null;

  return (
    <motion.aside
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 272, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="flex h-full shrink-0 flex-col overflow-hidden border-r border-[var(--border-subtle)] bg-[var(--bg-sidebar)]"
    >
      <div className="flex w-[272px] flex-1 flex-col overflow-hidden">
        {/* Brand + collapse */}
        <div className="flex items-center justify-between px-3 pt-3">
          <div className="flex items-center gap-2 px-1">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-accent)]/10">
              <Sparkles size={13} className="text-[var(--color-accent)]" />
            </div>
            <span className="text-sm font-semibold text-[var(--text-primary)]">Smogon Bot</span>
          </div>
          <Tooltip label="Hide sidebar">
            <IconButton size="sm" onClick={toggleSidebar}>
              <PanelLeft size={15} />
            </IconButton>
          </Tooltip>
        </div>

        {/* New chat */}
        <div className="px-3 pt-3">
          <button
            onClick={startNewChat}
            className="flex w-full items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-surface-hover)]"
          >
            <Plus size={15} />
            New chat
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pt-3">
          <div className="flex items-center gap-2 rounded-lg bg-[var(--bg-surface-hover)] px-2.5 py-1.5">
            <Search size={14} className="shrink-0 text-[var(--text-tertiary)]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats"
              className="min-w-0 flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none"
            />
          </div>
        </div>

        {/* Thread list */}
        <div className="mt-3 flex-1 overflow-y-auto px-3 pb-3">
          <AnimatePresence mode="wait">
            {isLoadingChats ? (
              <div className="flex flex-col gap-2 pt-1">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-8 animate-pulse rounded-lg bg-[var(--bg-surface-hover)]" />
                ))}
              </div>
            ) : (
              <ThreadList
                chats={filteredChats}
                activeChatId={activeChatId}
                onSelect={selectChat}
                onRename={renameChat}
                onDelete={removeChat}
                emptyLabel={query ? "No chats match your search" : "No chats yet — start one above"}
              />
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.aside>
  );
}
