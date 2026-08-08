import { createContext, useContext } from "react";
import { useChats } from "../hooks/useChats";

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const chatState = useChats();
  return <ChatContext.Provider value={chatState}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used within ChatProvider");
  return ctx;
}
