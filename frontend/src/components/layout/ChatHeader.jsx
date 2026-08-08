import { useState } from "react";
import { Moon, PanelLeft, Sun, Trash2 } from "lucide-react";
import { useChatContext } from "../../context/ChatContext";
import { useTheme } from "../../context/ThemeContext";
import { useUI } from "../../context/UIContext";
import { IconButton } from "../ui/IconButton";
import { Tooltip } from "../ui/Tooltip";

export function ChatHeader() {
  const { chats, activeChatId, messages, clearActiveChat } = useChatContext();
  const { theme, toggleTheme } = useTheme();
  const { isSidebarCollapsed, toggleSidebar } = useUI();
  const [confirmClear, setConfirmClear] = useState(false);

  const activeChat = chats.find((c) => c.id === activeChatId);
  const title = activeChat?.title || "New Chat";

  const handleClear = () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 2500);
      return;
    }
    clearActiveChat();
    setConfirmClear(false);
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] px-4">
      <div className="flex min-w-0 items-center gap-2">
        {isSidebarCollapsed && (
          <Tooltip label="Show sidebar">
            <IconButton onClick={toggleSidebar}>
              <PanelLeft size={17} />
            </IconButton>
          </Tooltip>
        )}
        <h2 className="truncate text-sm font-medium text-[var(--text-primary)]">{title}</h2>
      </div>

      <div className="flex items-center gap-1">
        {activeChatId && messages.length > 0 && (
          <Tooltip label={confirmClear ? "Click again to confirm" : "Clear conversation"}>
            <IconButton onClick={handleClear} className={confirmClear ? "text-red-500" : ""}>
              <Trash2 size={16} />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip label={theme === "dark" ? "Light mode" : "Dark mode"}>
          <IconButton onClick={toggleTheme}>
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </IconButton>
        </Tooltip>
      </div>
    </header>
  );
}
