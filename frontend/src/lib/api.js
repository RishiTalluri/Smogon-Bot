// Thin client around the Flask backend in RAG/Server.py.
// Every function here maps 1:1 to a real route — nothing is invented.
// Base URL is configurable via VITE_API_BASE_URL (defaults to local dev server).

const rawBase = import.meta.env.VITE_API_BASE_URL || "";
const BASE_URL = rawBase.replace(/\/+$/, "");

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const TOKEN_KEY = 'smogon-bot:token';

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  let res;
  try {
    const headers = { "Content-Type": "application/json", ...options.headers };
    const token = getAuthToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(
      "Can't reach the Smogon Bot server. Is Server.py running on port 5000?",
      0
    );
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // some routes (e.g. DELETE) may return an empty/non-JSON body
  }

  if (res.status === 401) {
    clearAuthToken();
    window.dispatchEvent(new Event('auth:logout'));
  }

  if (!res.ok) {
    throw new ApiError(data?.error || `Request failed (${res.status})`, res.status);
  }
  return data;
}

// GET /api/health
export function getHealth() {
  return request("/api/health");
}

// POST /api/auth/register
export function register(username, email, password) {
  return request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });
}

// POST /api/auth/login
export function login(email, password) {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// GET /api/auth/me
export function getMe() {
  return request("/api/auth/me");
}

// GET /api/chats -> [{ id, title, last_msg, created_at, msg_count }]
export function listChats() {
  return request("/api/chats");
}

// POST /api/chats -> { id, title, history, created_at }
export function createChat() {
  return request("/api/chats", { method: "POST" });
}

// GET /api/chats/:id -> { id, title, history: [{role, content}], raw_history }
export function getChat(chatId) {
  return request(`/api/chats/${chatId}`);
}

// DELETE /api/chats/:id -> { deleted: id }
export function deleteChat(chatId) {
  return request(`/api/chats/${chatId}`, { method: "DELETE" });
}

// POST /api/chats/:id/messages { message } -> { answer, chunks_used, corrected_mon }
export function sendMessage(chatId, message) {
  return request(`/api/chats/${chatId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// POST /api/chats/:id/clear -> { cleared: id }
export function clearChat(chatId) {
  return request(`/api/chats/${chatId}/clear`, { method: "POST" });
}

export { ApiError };
