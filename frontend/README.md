# Smogon Bot — Frontend

A React (JS, Vite, Tailwind) chat UI for the existing Flask RAG backend in `RAG/Server.py`,
built in the visual/interaction style of [assistant-ui](https://github.com/assistant-ui/assistant-ui)
(centered welcome screen, rounded message bubbles, sticky composer, markdown + code
blocks with copy, message actions, ChatGPT-style sidebar) — without depending on the
`assistant-ui` package itself.

## Running it

1. Start the Flask backend first (from the existing `RAG/` folder):
   ```bash
   cd RAG
   python Server.py
   # -> http://localhost:5000
   ```
2. In a separate terminal, run the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   # -> http://localhost:5173
   ```
3. Optional: copy `.env.example` to `.env` if your Flask server isn't on
   `http://localhost:5000`:
   ```
   VITE_API_BASE_URL=http://your-host:port
   ```

## Architecture

```
src/
├── lib/
│   ├── api.js          # Thin wrapper around every real Flask route — nothing invented
│   └── utils.js         # cn(), date/time formatting, id generation
├── hooks/
│   ├── useChats.js      # Core chat state machine: list/select/create/delete/rename/send
│   ├── useAutoScroll.js # Pins scroll to bottom unless the user scrolls up
│   ├── useLocalStorage.js
│   └── useClickOutside.js
├── context/
│   ├── ChatContext.jsx  # Exposes useChats() to the tree
│   ├── ThemeContext.jsx # Light/dark mode, persisted, respects system preference
│   └── UIContext.jsx    # Sidebar collapsed state
├── components/
│   ├── layout/           ChatLayout, ChatHeader
│   ├── sidebar/           Sidebar, ThreadList, ThreadListItem (rename/delete/search)
│   ├── chat/              ChatArea, WelcomeScreen, MessageList
│   ├── message/           Message, MessageActions, TypingIndicator, LoadingDots
│   ├── markdown/          MarkdownRenderer, CodeBlock (syntax highlight + copy button)
│   ├── composer/          Composer (auto-resizing sticky input)
│   └── ui/                IconButton, Tooltip
├── App.jsx / main.jsx
└── index.css              Design tokens (CSS vars) for light/dark theme + prose styles
```

## Notes on the API contract

Matched exactly against the real `RAG/Server.py` routes:

| Route | Method | Notes |
|---|---|---|
| `/api/chats` | GET | List chat summaries, sorted newest-first |
| `/api/chats` | POST | Create an empty chat |
| `/api/chats/:id` | GET | Full message history for a chat |
| `/api/chats/:id` | DELETE | Delete a chat |
| `/api/chats/:id/messages` | POST | Body `{ message }` → `{ answer, chunks_used, corrected_mon }` |
| `/api/chats/:id/clear` | POST | Clears history, resets title to "New Chat" |
| `/api/health` | GET | Health check |

Two things the backend does **not** support, handled client-side instead:

- **Rename**: no backend route exists, so custom titles are stored in
  `localStorage` (`smogon-bot:chat-renames`) and merged over whatever title the
  server reports. Deleting a chat clears its rename entry too.
- **Streaming**: `/messages` is a single synchronous JSON response, so the
  composer shows a "thinking" typing indicator while waiting rather than a
  fake token-by-token stream.

If you ever add real streaming or a rename endpoint to `Server.py`, the only
files that need to change are `src/lib/api.js` and `src/hooks/useChats.js` —
nothing in the component layer assumes the current shape.
