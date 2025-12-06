const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Fetch wrapper with auth token
async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = localStorage.getItem("token");
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, { ...options, headers });
}

// Helper to extract error message from API response (async - parses body)
export async function extractApiError(error: unknown): Promise<string> {
  if (error instanceof Response) {
    try {
      // Clone response in case body was already consumed
      const cloned = error.clone();
      const data = await cloned.json();

      // Try different error formats returned by the backend
      // Format 1: { "error": { "message": "..." } }
      if (data?.error?.message) {
        return data.error.message;
      }
      // Format 2: { "detail": "..." } (FastAPI default)
      if (data?.detail) {
        return typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail);
      }
      // Format 3: { "message": "..." }
      if (data?.message) {
        return data.message;
      }
    } catch {
      // Failed to parse JSON, fall through to status-based message
    }

    // Fallback to status-based messages
    switch (error.status) {
      case 401:
        return "Session expired. Please log in again.";
      case 403:
        return "You don't have permission to do this.";
      case 404:
        return "Resource not found.";
      case 429:
        return "Too many requests. Please wait a moment.";
      case 500:
        return "Server error. Please try again later.";
      default:
        return `Request failed (${error.status})`;
    }
  }
  if (error instanceof Error) {
    if (error.message.includes("fetch"))
      return "Connection lost. Check your internet.";
    return error.message;
  }
  return "An unexpected error occurred.";
}

// Synchronous version for cases where you can't await (deprecated - prefer extractApiError)
export function parseApiError(error: unknown): string {
  if (error instanceof Response) {
    switch (error.status) {
      case 401:
        return "Session expired. Please log in again.";
      case 403:
        return "You don't have permission to do this.";
      case 404:
        return "Resource not found.";
      case 429:
        return "Too many requests. Please wait a moment.";
      case 500:
        return "Server error. Please try again later.";
      default:
        return `Request failed (${error.status})`;
    }
  }
  if (error instanceof Error) {
    if (error.message.includes("fetch"))
      return "Connection lost. Check your internet.";
    return error.message;
  }
  return "An unexpected error occurred.";
}

// Auth API
export interface User {
  id: number;
  email: string;
  username: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authApi = {
  register: async (
    email: string,
    username: string,
    password: string
  ): Promise<AuthResponse> => {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/register`, {
      method: "POST",
      body: JSON.stringify({ email, username, password }),
    });
    if (!res.ok) throw res;
    return res.json();
  },

  login: async (email: string, password: string): Promise<AuthResponse> => {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw res;
    return res.json();
  },

  me: async (): Promise<User> => {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
    if (!res.ok) throw res;
    return res.json();
  },
};

// Chat API
export interface SentimentResult {
  score: number;
  label: string;
  emotion?: string; // Short description of exact emotion
  summary?: string; // Cumulative sentiment summary (for incremental analysis)
  source?: string;
  details?: Record<string, unknown>;
}

export interface DualSentiment {
  message: SentimentResult | null; // Sentiment of the current user message
  cumulative: SentimentResult | null; // Sentiment of conversation so far
}

export interface ChatResponse {
  response: string;
  sentiment?: DualSentiment; // Dual sentiment (message + cumulative)
  conversation_id: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sentiment_data?: DualSentiment; // Fixed: should be DualSentiment, not SentimentResult
  model_info?: { provider: string; model: string; thoughts?: string[] | null };
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  total_messages: number;
  limit: number;
  offset: number;
  has_more: boolean;
  messages: ConversationMessage[];
}

// SSE Event types for streaming
export interface StreamStartEvent {
  type: "start";
  conversation_id: string;
}

export interface StreamChunkEvent {
  type: "chunk";
  content: string;
}

export interface StreamSentimentEvent {
  type: "sentiment";
  sentiment: DualSentiment | null;
}

export interface StreamDoneEvent {
  type: "done";
}

export interface StreamErrorEvent {
  type: "error";
  error: string;
}

export type StreamEvent =
  | StreamStartEvent
  | StreamChunkEvent
  | StreamSentimentEvent
  | StreamDoneEvent
  | StreamErrorEvent;

export interface StreamCallbacks {
  onStart?: (conversationId: string) => void;
  onChunk?: (content: string) => void;
  onSentiment?: (sentiment: DualSentiment | null) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

export const chatApi = {
  // Streaming chat using Server-Sent Events (primary method)
  sendStream: async (
    message: string,
    callbacks: StreamCallbacks,
    sentimentMethod: string = "llm_separate",
    provider: string = "gemini",
    model: string = "gemini-2.5-flash",
    conversationId?: string
  ): Promise<void> => {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/chat/stream`, {
      method: "POST",
      body: JSON.stringify({
        message,
        sentiment_method: sentimentMethod,
        provider,
        model,
        conversation_id: conversationId,
      }),
    });

    if (!response.ok) {
      const errorMsg = await extractApiError(response);
      callbacks.onError?.(errorMsg);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError?.("No response body");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let receivedDone = false;

    const processLine = (line: string) => {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6)) as StreamEvent;

          switch (data.type) {
            case "start":
              callbacks.onStart?.(data.conversation_id);
              break;
            case "chunk":
              callbacks.onChunk?.(data.content);
              break;
            case "sentiment":
              callbacks.onSentiment?.(data.sentiment);
              break;
            case "done":
              receivedDone = true;
              callbacks.onDone?.();
              break;
            case "error":
              callbacks.onError?.(data.error);
              break;
          }
        } catch {
          // Ignore JSON parse errors
        }
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          processLine(line);
        }
      }

      // Process any remaining data in buffer
      if (buffer.trim()) {
        processLine(buffer);
      }

      // Ensure onDone is called even if server didn't send done event
      if (!receivedDone) {
        callbacks.onDone?.();
      }
    } finally {
      reader.releaseLock();
    }
  },

  getHistory: async (): Promise<ConversationSummary[]> => {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/chat/history`);
    if (!res.ok) throw res;
    return res.json();
  },

  getConversation: async (
    conversationId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<ConversationDetail> => {
    const url = new URL(
      `${API_BASE_URL}/api/v1/chat/conversation/${conversationId}`
    );
    if (params?.limit) url.searchParams.set("limit", params.limit.toString());
    if (params?.offset)
      url.searchParams.set("offset", params.offset.toString());
    const res = await fetchWithAuth(url.toString());
    if (!res.ok) throw res;
    return res.json();
  },

  deleteConversation: async (
    conversationId: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/chat/conversation/${conversationId}`,
      {
        method: "DELETE",
      }
    );
    if (!res.ok) throw res;
    return res.json();
  },

  deleteAllConversations: async (): Promise<{
    success: boolean;
    message: string;
    deleted_count?: number;
  }> => {
    const res = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/chat/conversations`,
      {
        method: "DELETE",
      }
    );
    if (!res.ok) throw res;
    return res.json();
  },

  renameConversation: async (
    conversationId: string,
    title: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/chat/conversation/${conversationId}/rename`,
      {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }
    );
    if (!res.ok) throw res;
    return res.json();
  },

  getModels: async (): Promise<Record<string, string[]>> => {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/chat/models`);
    if (!res.ok) throw res;
    return res.json();
  },

  getMethods: async (): Promise<string[]> => {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/chat/methods`);
    if (!res.ok) throw res;
    return res.json();
  },
};
