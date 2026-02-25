// Shared query key factories for consistent React Query cache management

const PAGE_SIZE = 50;

export const queryKeys = {
	history: (userId: number | undefined) => ["history", userId] as const,
	conversation: (conversationId: string, offset = 0, limit = PAGE_SIZE) =>
		["conversation", conversationId, offset, limit] as const,
	models: ["models"] as const,
};
