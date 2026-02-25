export const API_BASE_URL =
	import.meta.env.VITE_API_URL || "http://localhost:8000";

// Fetch wrapper with cookie auth and request timeout
async function fetchWithAuth(
	url: string,
	options: RequestInit = {},
): Promise<Response> {
	const headers = new Headers(options.headers);
	if (options.body && !headers.has("Content-Type")) {
		headers.set("Content-Type", "application/json");
	}

	const controller = new AbortController();
	const timeoutId = setTimeout(() => controller.abort(), 30_000);

	// Link caller's signal so external abort still works
	const callerSignal = options.signal;
	if (callerSignal) {
		if (callerSignal.aborted) {
			clearTimeout(timeoutId);
			controller.abort();
		} else {
			callerSignal.addEventListener("abort", () => controller.abort());
		}
	}

	try {
		const response = await fetch(url, {
			...options,
			headers,
			credentials: "include",
			signal: controller.signal,
		});
		clearTimeout(timeoutId);
		return response;
	} catch (error) {
		clearTimeout(timeoutId);
		throw error;
	}
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
		password: string,
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

	logout: async (): Promise<void> => {
		await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/logout`, {
			method: "POST",
		});
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

export interface ModelInfo {
	id: string;
	name: string;
	provider?: string;
	context_window?: number;
}

export const chatApi = {
	getHistory: async (): Promise<ConversationSummary[]> => {
		const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/chat/history`);
		if (!res.ok) throw res;
		return res.json();
	},

	getConversation: async (
		conversationId: string,
		params?: { limit?: number; offset?: number },
	): Promise<ConversationDetail> => {
		const url = new URL(
			`${API_BASE_URL}/api/v1/chat/conversation/${conversationId}`,
		);
		if (params?.limit) url.searchParams.set("limit", params.limit.toString());
		if (params?.offset)
			url.searchParams.set("offset", params.offset.toString());
		const res = await fetchWithAuth(url.toString());
		if (!res.ok) throw res;
		return res.json();
	},

	deleteConversation: async (
		conversationId: string,
	): Promise<{ success: boolean; message: string }> => {
		const res = await fetchWithAuth(
			`${API_BASE_URL}/api/v1/chat/conversation/${conversationId}`,
			{
				method: "DELETE",
			},
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
			},
		);
		if (!res.ok) throw res;
		return res.json();
	},

	renameConversation: async (
		conversationId: string,
		title: string,
	): Promise<{ success: boolean; message: string }> => {
		const res = await fetchWithAuth(
			`${API_BASE_URL}/api/v1/chat/conversation/${conversationId}/rename`,
			{
				method: "PATCH",
				body: JSON.stringify({ title }),
			},
		);
		if (!res.ok) throw res;
		return res.json();
	},

	getModels: async (): Promise<Record<string, ModelInfo[]>> => {
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
