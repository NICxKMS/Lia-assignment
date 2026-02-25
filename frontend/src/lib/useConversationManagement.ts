import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type {
	ConversationDetail as ApiConversationDetail,
	SentimentResult,
} from "./api";
import { chatApi } from "./api";
import { queryKeys } from "./queryKeys";
import type { ChatMessage as BaseChatMessage } from "./useChat";

const PAGE_SIZE = 50;

export interface ConversationMeta {
	hasMore: boolean;
	total: number;
	offset: number;
	limit: number;
}

export interface PendingDelete {
	type: "single" | "all";
	id?: string;
}

export interface UseConversationManagementOptions {
	user: { id: number } | null;
	setChatMessages: React.Dispatch<React.SetStateAction<BaseChatMessage[]>>;
	chatMessages: BaseChatMessage[];
	clearMessages: () => void;
	setIsSidebarOpen?: (open: boolean) => void;
}

// Runtime type guard for sentiment data from API
function isSentimentData(
	data: unknown,
): data is { message?: SentimentResult; cumulative?: SentimentResult | null } {
	if (!data || typeof data !== "object") return false;
	const d = data as Record<string, unknown>;
	// Allow if it has the expected shape (message/cumulative keys, or is empty object)
	if ("message" in d || "cumulative" in d) {
		if (d.message != null && typeof d.message !== "object") return false;
		if (d.cumulative != null && typeof d.cumulative !== "object") return false;
		return true;
	}
	return false;
}

export function useConversationManagement({
	user,
	setChatMessages,
	chatMessages,
	clearMessages,
	setIsSidebarOpen,
}: UseConversationManagementOptions) {
	const queryClient = useQueryClient();
	const [conversationId, setConversationId] = useState<string>();
	const [conversationMeta, setConversationMeta] =
		useState<ConversationMeta | null>(null);
	const [isLoadingConversation, setIsLoadingConversation] = useState(false);
	const [isLoadingMore, setIsLoadingMore] = useState(false);
	const [selectedMessageId, setSelectedMessageId] = useState<string | null>(
		null,
	);
	const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(
		null,
	);

	// Refs for stable callbacks
	const conversationIdRef = useRef(conversationId);
	useEffect(() => {
		conversationIdRef.current = conversationId;
	}, [conversationId]);

	// Load conversation with caching
	const loadConversation = useCallback(
		async (convId: string) => {
			setIsLoadingConversation(true);
			try {
				// Use queryClient to leverage cache - check if already cached
				const cachedData = queryClient.getQueryData<ApiConversationDetail>(
					queryKeys.conversation(convId, 0, PAGE_SIZE),
				);

				// Fetch with cache support
				const conv =
					cachedData ??
					(await queryClient.fetchQuery({
						queryKey: queryKeys.conversation(convId, 0, PAGE_SIZE),
						queryFn: () =>
							chatApi.getConversation(convId, { limit: PAGE_SIZE, offset: 0 }),
						staleTime: 60 * 1000, // Consider fresh for 1 minute
					}));

				if (!conv) {
					toast.error("Failed to load conversation");
					return;
				}

				const loadedMessages: BaseChatMessage[] = conv.messages.map((msg) => {
					const sentimentData = isSentimentData(msg.sentiment_data)
						? msg.sentiment_data
						: undefined;

					// Extract thoughts from model_info for assistant messages
					const thoughts =
						msg.role === "assistant" && msg.model_info?.thoughts
							? msg.model_info.thoughts
							: undefined;

					return {
						id: msg.id.toString(),
						role: msg.role as "user" | "assistant",
						content: msg.content,
						thoughts,
						timestamp: new Date(msg.created_at),
						sentiment: sentimentData?.message,
						cumulativeSentiment: sentimentData?.cumulative ?? undefined,
					};
				});

				setChatMessages(loadedMessages);
				setConversationId(convId);
				setConversationMeta({
					hasMore: conv.has_more,
					total: conv.total_messages,
					offset: conv.offset + conv.messages.length,
					limit: conv.limit,
				});
				setSelectedMessageId(
					loadedMessages.length > 0
						? loadedMessages[loadedMessages.length - 1].id
						: null,
				);

				if (window.innerWidth < 768) setIsSidebarOpen?.(false);
			} catch (error) {
				toast.error("Error loading conversation");
				console.error("Error loading conversation:", error);
			} finally {
				setIsLoadingConversation(false);
			}
		},
		[setChatMessages, queryClient, setIsSidebarOpen],
	);

	// New conversation
	const startNewConversation = useCallback(() => {
		clearMessages();
		setConversationId(undefined);
		setConversationMeta(null);
		setSelectedMessageId(null);
		if (window.innerWidth < 768) setIsSidebarOpen?.(false);
	}, [clearMessages, setIsSidebarOpen]);

	// Request deletion (opens confirmation dialog)
	const deleteConversation = useCallback(
		(convId: string, e: React.MouseEvent) => {
			e.stopPropagation();
			setPendingDelete({ type: "single", id: convId });
		},
		[],
	);

	// Request delete all (opens confirmation dialog)
	const deleteAllConversations = useCallback(() => {
		setPendingDelete({ type: "all" });
	}, []);

	// Execute confirmed delete
	const confirmDelete = useCallback(async () => {
		if (!pendingDelete) return;

		try {
			if (pendingDelete.type === "single" && pendingDelete.id) {
				await chatApi.deleteConversation(pendingDelete.id);
				if (conversationId === pendingDelete.id) startNewConversation();
				queryClient.invalidateQueries({
					queryKey: queryKeys.history(user?.id),
				});
				queryClient.removeQueries({
					queryKey: ["conversation", pendingDelete.id],
				});
				toast.success("Conversation deleted");
			} else if (pendingDelete.type === "all") {
				await chatApi.deleteAllConversations();
				startNewConversation();
				queryClient.invalidateQueries({
					queryKey: queryKeys.history(user?.id),
				});
				queryClient.removeQueries({ queryKey: ["conversation"] });
				toast.success("All conversations deleted");
			}
		} catch (error) {
			const msg =
				pendingDelete.type === "all"
					? "Failed to delete all conversations"
					: "Failed to delete conversation";
			toast.error(msg);
			console.error("Error deleting:", error);
		} finally {
			setPendingDelete(null);
		}
	}, [
		pendingDelete,
		conversationId,
		startNewConversation,
		queryClient,
		user?.id,
	]);

	// Cancel pending delete
	const cancelDelete = useCallback(() => {
		setPendingDelete(null);
	}, []);

	// Load more messages
	const loadMoreMessages = useCallback(async () => {
		if (!conversationIdRef.current) return;
		setIsLoadingMore(true);
		try {
			const nextOffset = chatMessages.length;
			const conv = await chatApi.getConversation(conversationIdRef.current, {
				limit: PAGE_SIZE,
				offset: nextOffset,
			});

			const loadedMessages: BaseChatMessage[] = conv.messages.map((msg) => {
				const sentimentData = isSentimentData(msg.sentiment_data)
					? msg.sentiment_data
					: undefined;

				// Extract thoughts from model_info for assistant messages
				const thoughts =
					msg.role === "assistant" && msg.model_info?.thoughts
						? msg.model_info.thoughts
						: undefined;

				return {
					id: msg.id.toString(),
					role: msg.role as "user" | "assistant",
					content: msg.content,
					thoughts,
					timestamp: new Date(msg.created_at),
					sentiment: sentimentData?.message,
					cumulativeSentiment: sentimentData?.cumulative ?? undefined,
				};
			});

			setChatMessages((prev) => {
				const existing = new Set(prev.map((m) => m.id));
				const newOlderMessages = loadedMessages.filter(
					(m) => !existing.has(m.id),
				);
				return [...newOlderMessages, ...prev];
			});

			setConversationMeta({
				hasMore: conv.has_more,
				total: conv.total_messages,
				offset: conv.offset + conv.messages.length,
				limit: conv.limit,
			});
		} catch (error) {
			toast.error("Error loading more messages");
			console.error("Error loading more messages:", error);
		} finally {
			setIsLoadingMore(false);
		}
	}, [chatMessages.length, setChatMessages]);

	return {
		// State
		conversationId,
		setConversationId,
		conversationMeta,
		isLoadingConversation,
		isLoadingMore,
		selectedMessageId,
		setSelectedMessageId,
		conversationIdRef,
		pendingDelete,
		// Actions
		loadConversation,
		startNewConversation,
		deleteConversation,
		deleteAllConversations,
		confirmDelete,
		cancelDelete,
		loadMoreMessages,
	};
}
