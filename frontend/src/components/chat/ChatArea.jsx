import { useChatContext } from "../../context/ChatContext";
import { WelcomeScreen } from "./WelcomeScreen";
import { MessageList } from "./MessageList";
import { Composer } from "../composer/Composer";
import { ChatHeader } from "../layout/ChatHeader";

export function ChatArea() {
  const {
    activeChatId,
    messages,
    isLoadingMessages,
    isSending,
    sendMessage,
    retryLastMessage,
    startNewChat,
  } = useChatContext();

  const handleSend = async (text) => {
    let chatId = activeChatId;
    if (!chatId) {
      chatId = await startNewChat();
      if (!chatId) return;
    }
    sendMessage(text);
  };

  const showWelcome = !isLoadingMessages && messages.length === 0;

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <ChatHeader />

      <div className="flex min-h-0 flex-1 flex-col">
        {isLoadingMessages ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--color-accent)]" />
          </div>
        ) : showWelcome ? (
          <WelcomeScreen onSuggestionClick={handleSend} />
        ) : (
          <MessageList messages={messages} isSending={isSending} onRegenerate={retryLastMessage} />
        )}
      </div>

      <div className="mx-auto w-full max-w-3xl px-4">
        <Composer onSend={handleSend} isSending={isSending} />
      </div>
    </div>
  );
}
