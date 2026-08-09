import { ThemeProvider } from "./context/ThemeContext";
import { UIProvider } from "./context/UIContext";
import { ChatProvider } from "./context/ChatContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ChatLayout } from "./components/layout/ChatLayout";
import LoginPage from "./components/auth/LoginPage";
import { Loader2 } from "lucide-react";

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[var(--bg-app)] text-[var(--text-secondary)]">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <UIProvider>
      <ChatProvider>
        <ChatLayout />
      </ChatProvider>
    </UIProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}
