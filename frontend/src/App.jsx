import { ThemeProvider } from "./context/ThemeContext";
import { UIProvider } from "./context/UIContext";
import { ChatProvider } from "./context/ChatContext";
import { ChatLayout } from "./components/layout/ChatLayout";

export default function App() {
  return (
    <ThemeProvider>
      <UIProvider>
        <ChatProvider>
          <ChatLayout />
        </ChatProvider>
      </UIProvider>
    </ThemeProvider>
  );
}
