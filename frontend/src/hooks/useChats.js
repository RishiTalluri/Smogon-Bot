import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import { useLocalStorage } from "./useLocalStorage";

// The backend has no rename endpoint, so custom titles live in localStorage
// keyed by chat id and are merged over whatever title the backend reports.
const RENAME_KEY = "smogon-bot:chat-renames";

export function useChats() {
  const [renames, setRenames] = useLocalStorage(RENAME_KEY, {});
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);

  const applyRenames = useCallback(
    (list) => list.map((c) => (renames[c.id] ? { ...c, title: renames[c.id] } : c)),
    [renames]
  );

  const refreshChats = useCallback(async () => {
    setIsLoadingChats(true);
    setError(null);
    try {
      const list = await api.listChats();
      setChats(applyRenames(list));
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoadingChats(false);
    }
  }, [applyRenames]);

  useEffect(() => {
    refreshChats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-apply renames if the overlay changes without refetching from the server.
  useEffect(() => {
    setChats((prev) => applyRenames(prev));
  }, [renames, applyRenames]);

  const selectChat = useCallback(async (chatId) => {
    setActiveChatId(chatId);
    setIsLoadingMessages(true);
    setError(null);
    try {
      const data = await api.getChat(chatId);
      setMessages(data.history || []);
    } catch (e) {
      setError(e.message);
      setMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  const startNewChat = useCallback(async () => {
    setError(null);
    try {
      const created = await api.createChat();
      setChats((prev) => [{ id: created.id, title: created.title, last_msg: "", created_at: created.created_at, msg_count: 0 }, ...prev]);
      setActiveChatId(created.id);
      setMessages([]);
      return created.id;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  const removeChat = useCallback(
    async (chatId) => {
      setError(null);
      try {
        await api.deleteChat(chatId);
        setChats((prev) => prev.filter((c) => c.id !== chatId));
        setRenames((prev) => {
          const next = { ...prev };
          delete next[chatId];
          return next;
        });
        if (activeChatId === chatId) {
          setActiveChatId(null);
          setMessages([]);
        }
      } catch (e) {
        setError(e.message);
      }
    },
    [activeChatId, setRenames]
  );

  const renameChat = useCallback(
    (chatId, title) => {
      const trimmed = title.trim();
      if (!trimmed) return;
      setRenames((prev) => ({ ...prev, [chatId]: trimmed }));
      setChats((prev) => prev.map((c) => (c.id === chatId ? { ...c, title: trimmed } : c)));
    },
    [setRenames]
  );

  const clearActiveChat = useCallback(async () => {
    if (!activeChatId) return;
    setError(null);
    try {
      await api.clearChat(activeChatId);
      setMessages([]);
      setChats((prev) =>
        prev.map((c) => (c.id === activeChatId ? { ...c, title: "New Chat", last_msg: "", msg_count: 0 } : c))
      );
      setRenames((prev) => {
        const next = { ...prev };
        delete next[activeChatId];
        return next;
      });
    } catch (e) {
      setError(e.message);
    }
  }, [activeChatId, setRenames]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || !activeChatId || isSending) return;

      const isFirstMessage = messages.length === 0;
      const userTs = Date.now() / 1000;
      setMessages((prev) => [...prev, { role: "user", content: trimmed, timestamp: userTs }]);
      setIsSending(true);
      setError(null);

      try {
        const data = await api.sendMessage(activeChatId, trimmed);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.answer,
            chunksUsed: data.chunks_used,
            correctedMon: data.corrected_mon,
            timestamp: Date.now() / 1000,
          },
        ]);
        setChats((prev) =>
          prev.map((c) =>
            c.id === activeChatId
              ? {
                  ...c,
                  last_msg: trimmed.slice(0, 60),
                  msg_count: c.msg_count + 1,
                  title: isFirstMessage && !renames[activeChatId]
                    ? trimmed.slice(0, 48) + (trimmed.length > 48 ? "…" : "")
                    : c.title,
                }
              : c
          )
        );
      } catch (e) {
        setError(e.message);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `⚠️ ${e.message}`, isError: true },
        ]);
      } finally {
        setIsSending(false);
      }
    },
    [activeChatId, isSending, messages.length, renames]
  );

  const retryLastMessage = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    // Drop the trailing error/assistant message before resending.
    setMessages((prev) => {
      const idx = prev.map((m) => m.role).lastIndexOf("user");
      return idx === -1 ? prev : prev.slice(0, idx + 1);
    });
    sendMessage(lastUser.content);
  }, [messages, sendMessage]);

  return {
    chats,
    activeChatId,
    messages,
    isLoadingChats,
    isLoadingMessages,
    isSending,
    error,
    setError,
    refreshChats,
    selectChat,
    startNewChat,
    removeChat,
    renameChat,
    clearActiveChat,
    sendMessage,
    retryLastMessage,
  };
}
