import { useQuery, useQueryClient } from "@tanstack/react-query";
// NOTE (framer-motion): Loading overlay uses AnimatePresence for exit fade.
// Could use CSS animate-in/fade-in for entry, but exit animation requires
// AnimatePresence to delay unmount. Kept for consistency across the app.
import { AnimatePresence, motion } from "framer-motion";
import { Info, Menu, Sparkles } from "lucide-react";
import type React from "react";
import {
	lazy,
	memo,
	Suspense,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { toast } from "sonner";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuth } from "../../context";
import { chatApi } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { ModelSettings } from "../../lib/types";
import { DEFAULT_MODEL_SETTINGS } from "../../lib/types";
import {
	type ChatMessage as BaseChatMessage,
	useChat,
} from "../../lib/useChat";
import { useConversationManagement } from "../../lib/useConversationManagement";
import ChatInput from "./ChatInput";
import ChatSidebar from "./ChatSidebar";
import MessageList from "./MessageList";
import ModelSettingsDialog from "./ModelSettingsDialog";

// Lazy load the heavy ChatInspector component (includes recharts)
const ChatInspector = lazy(() => import("./ChatInspector"));

// Inspector loading fallback
const InspectorFallback = () => (
	<div className="w-80 h-full bg-secondary/50 border-l border-border animate-pulse" />
);

// ============ Types ============

export interface MessagePart {
	type: "text" | "reasoning" | "source-url" | "file";
	text?: string;
	url?: string;
	title?: string;
	mediaType?: string;
	filename?: string;
}

export interface ChatMessage extends BaseChatMessage {
	parts: MessagePart[];
	error?: boolean;
}

export type { ChatMessage };

// ============ Main Component ============

const ChatInterface: React.FC = () => {
	// Input state
	const [input, setInput] = useState("");

	// Chat settings
	const [method, setMethod] = useState("llm_separate");
	const [provider, setProvider] = useState("gemini");
	const [model, setModel] = useState("gemini-2.5-flash");
	const [modelSettings, setModelSettings] = useState<ModelSettings>(
		DEFAULT_MODEL_SETTINGS,
	);
	// UI state
	const [isSidebarOpen, setIsSidebarOpen] = useState(false);
	const [isInspectorOpen, setIsInspectorOpen] = useState(true);
	const [isSettingsOpen, setIsSettingsOpen] = useState(false);

	const messagesEndRef = useRef<HTMLDivElement>(null);
	const queryClient = useQueryClient();
	const { user, logout } = useAuth();

	// Stable refs for callbacks to prevent re-renders
	const methodRef = useRef(method);
	const providerRef = useRef(provider);
	const modelRef = useRef(model);
	const modelSettingsRef = useRef(modelSettings);

	// Keep refs updated
	useEffect(() => {
		methodRef.current = method;
	}, [method]);
	useEffect(() => {
		providerRef.current = provider;
	}, [provider]);
	useEffect(() => {
		modelRef.current = model;
	}, [model]);
	useEffect(() => {
		modelSettingsRef.current = modelSettings;
	}, [modelSettings]);

	// Stable ref for conversation ID change callback (avoids circular dep between useChat and useConversationManagement)
	const convIdChangeRef = useRef<(id: string) => void>(() => {});

	// Chat hook with debounced history invalidation
	const convIdRefForFinish = useRef<string | undefined>();
	const {
		messages: chatMessages,
		status,
		error: chatError,
		isStreaming,
		sendMessage,
		setMessages: setChatMessages,
		clearMessages,
		stop,
	} = useChat({
		onFinish: useCallback(() => {
			// Invalidate history after message completes
			queryClient.invalidateQueries({ queryKey: queryKeys.history(user?.id) });
			// Also invalidate current conversation detail cache
			if (convIdRefForFinish.current) {
				queryClient.invalidateQueries({
					queryKey: queryKeys.conversation(convIdRefForFinish.current),
				});
			}
		}, [queryClient, user?.id]),
		onError: useCallback((error: Error) => {
			toast.error(error.message || "An error occurred while sending message");
		}, []),
		onConversationIdChange: useCallback(
			(id: string) => convIdChangeRef.current(id),
			[],
		),
	});

	// Conversation management hook - replaces inline load/delete/create logic
	const {
		conversationId,
		setConversationId,
		conversationMeta,
		isLoadingConversation,
		isLoadingMore,
		selectedMessageId,
		setSelectedMessageId,
		conversationIdRef,
		loadConversation,
		startNewConversation,
		deleteConversation,
		deleteAllConversations,
		confirmDelete,
		cancelDelete,
		pendingDelete,
		loadMoreMessages,
	} = useConversationManagement({
		user,
		setChatMessages,
		chatMessages,
		clearMessages,
		setIsSidebarOpen,
	});

	// Wire up refs after hook initialization
	useEffect(() => {
		convIdChangeRef.current = setConversationId;
	}, [setConversationId]);
	useEffect(() => {
		convIdRefForFinish.current = conversationId;
	}, [conversationId]);

	// Convert to message format with parts - memoized
	const messages: ChatMessage[] = useMemo(
		() =>
			chatMessages.map((msg) => ({
				...msg,
				parts: [{ type: "text" as const, text: msg.content }],
			})),
		[chatMessages],
	);

	// Fetch history with proper caching
	const { data: history, isLoading: isLoadingHistory } = useQuery({
		queryKey: queryKeys.history(user?.id),
		queryFn: chatApi.getHistory,
		enabled: !!user,
		staleTime: 30 * 1000, // Consider fresh for 30 seconds to prevent rapid refetches
	});

	// Prefetch static data once - models and methods rarely change
	// These are prefetched to warm the cache for ModelSelector component
	useQuery({
		queryKey: queryKeys.models,
		queryFn: chatApi.getModels,
		enabled: !!user, // Only fetch when user is authenticated
		staleTime: Infinity, // Static data - never refetch automatically
		gcTime: 24 * 60 * 60 * 1000, // Keep in cache for 24 hours
	});

	// Auto-scroll to bottom - use instant during streaming to prevent jumpy behavior
	const prevMessageCountRef = useRef(chatMessages.length);
	useEffect(() => {
		const isNewMessage = chatMessages.length > prevMessageCountRef.current;
		prevMessageCountRef.current = chatMessages.length;

		// Use smooth scroll only for new messages, instant for streaming updates
		const behavior = isStreaming && !isNewMessage ? "instant" : "smooth";
		messagesEndRef.current?.scrollIntoView({ behavior });
	}, [chatMessages, isStreaming]);

	// Auto-select last message
	useEffect(() => {
		if (chatMessages.length > 0 && !selectedMessageId) {
			setSelectedMessageId(chatMessages[chatMessages.length - 1].id);
		}
	}, [chatMessages, selectedMessageId]);

	// Send message - use refs for stable callback
	const handleSubmit = useCallback(
		(e: React.FormEvent) => {
			e.preventDefault();
			if (!input.trim() || isStreaming) return;

			sendMessage(input, {
				method: methodRef.current,
				provider: providerRef.current,
				model: modelRef.current,
				conversationId: conversationIdRef.current,
				modelSettings: modelSettingsRef.current,
			});
			setInput("");
		},
		[input, isStreaming, sendMessage],
	);

	// Regenerate last response - use refs for stable callback
	const handleRegenerate = useCallback(() => {
		let lastUserMsg: BaseChatMessage | undefined;
		for (let i = chatMessages.length - 1; i >= 0; i--) {
			if (chatMessages[i].role === "user") {
				lastUserMsg = chatMessages[i];
				break;
			}
		}
		if (!lastUserMsg) return;

		// Remove last assistant + user message
		setChatMessages((prev) => {
			const msgs = [...prev];
			if (msgs.length > 0 && msgs[msgs.length - 1].role === "assistant")
				msgs.pop();
			if (msgs.length > 0 && msgs[msgs.length - 1].role === "user") msgs.pop();
			return msgs;
		});

		sendMessage(lastUserMsg.content, {
			method: methodRef.current,
			provider: providerRef.current,
			model: modelRef.current,
			conversationId: conversationIdRef.current,
			modelSettings: modelSettingsRef.current,
		});
	}, [chatMessages, setChatMessages, sendMessage]);

	// Derived data - memoized
	const selectedMessage = useMemo(
		() => messages.find((m) => m.id === selectedMessageId),
		[messages, selectedMessageId],
	);

	const chartData = useMemo(
		() =>
			messages
				.filter((m) => m.role === "user" && m.sentiment)
				.map((m, i) => ({
					id: m.id,
					name: i + 1,
					score: m.sentiment?.score || 0,
					label: m.sentiment?.label,
					content: m.content,
				})),
		[messages],
	);

	const chatStatus = useMemo(
		() =>
			status === "connecting" || status === "streaming"
				? "streaming"
				: status === "error"
					? "error"
					: "ready",
		[status],
	);

	// Stable callback refs to prevent child re-renders
	const closeSidebar = useCallback(() => setIsSidebarOpen(false), []);
	const openSidebar = useCallback(() => setIsSidebarOpen(true), []);
	const closeInspector = useCallback(() => setIsInspectorOpen(false), []);
	const toggleInspector = useCallback(
		() => setIsInspectorOpen((prev) => !prev),
		[],
	);

	return (
		<div className="flex w-full h-full bg-background text-foreground font-sans overflow-hidden">
			{/* Sidebar */}
			<ChatSidebar
				history={history}
				currentConversationId={conversationId}
				onSelectConversation={loadConversation}
				onNewChat={startNewConversation}
				onDeleteConversation={deleteConversation}
				onDeleteAll={deleteAllConversations}
				user={user}
				onLogout={logout}
				isOpen={isSidebarOpen}
				onClose={closeSidebar}
				isLoading={isLoadingHistory}
			/>

			{/* Main Content */}
			<div className="flex-1 flex flex-col min-w-0 relative bg-background">
				{/* Toolbar */}
				<div className="h-14 flex items-center justify-between px-4 sm:px-6 sticky top-0 z-10">
					<div className="flex items-center gap-4">
						<Button
							variant="ghost"
							size="icon"
							onClick={openSidebar}
							className="md:hidden -ml-2"
						>
							<Menu className="w-5 h-5" />
						</Button>
						<span className="text-sm font-medium text-muted-foreground hidden sm:block">
							Lia Assistant
						</span>
					</div>

					<div className="flex items-center gap-1">
						<TooltipProvider>
							<ModelSettingsDialog
								modelSettings={modelSettings}
								setModelSettings={setModelSettings}
								open={isSettingsOpen}
								onOpenChange={setIsSettingsOpen}
							/>

							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant={isInspectorOpen ? "secondary" : "ghost"}
										size="icon"
										onClick={toggleInspector}
										className={cn(
											"transition-all duration-200 text-muted-foreground hover:text-foreground",
											isInspectorOpen && "bg-secondary text-foreground",
										)}
									>
										<Info className="w-5 h-5" />
									</Button>
								</TooltipTrigger>
								<TooltipContent>Toggle Inspector</TooltipContent>
							</Tooltip>
						</TooltipProvider>
					</div>
				</div>

				{/* Loading Overlay */}
				<AnimatePresence>
					{isLoadingConversation && (
						<motion.div
							initial={{ opacity: 0 }}
							animate={{ opacity: 1 }}
							exit={{ opacity: 0 }}
							className="absolute inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center z-20"
						>
							<div className="flex flex-col items-center gap-4 p-6 rounded-2xl bg-card border border-border shadow-2xl">
								<div className="relative">
									<div className="w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
									<div className="absolute inset-0 flex items-center justify-center">
										<Sparkles className="w-4 h-4 text-primary animate-pulse" />
									</div>
								</div>
								<span className="text-sm font-medium text-muted-foreground">
									Loading...
								</span>
							</div>
						</motion.div>
					)}
				</AnimatePresence>

				{/* Messages */}
				{conversationMeta?.hasMore && (
					<div className="flex justify-center py-2">
						<Button
							variant="outline"
							size="sm"
							onClick={loadMoreMessages}
							disabled={isLoadingMore || isLoadingConversation}
						>
							{isLoadingMore ? "Loading more..." : "Load older messages"}
						</Button>
					</div>
				)}
				<MessageList
					messages={messages}
					selectedMessageId={selectedMessageId}
					onSelectMessage={setSelectedMessageId}
					messagesEndRef={messagesEndRef}
					onSuggestionSelect={setInput}
				/>

				{/* Input */}
				<ChatInput
					input={input}
					setInput={setInput}
					onSubmit={handleSubmit}
					isStreaming={isStreaming}
					status={chatStatus}
					onStop={stop}
					onRegenerate={chatMessages.length > 0 ? handleRegenerate : undefined}
					error={chatError}
					model={model}
					setModel={setModel}
					setProvider={setProvider}
				/>
			</div>

			{/* Inspector - Lazy loaded */}
			<Suspense fallback={<InspectorFallback />}>
				<ChatInspector
					messages={messages}
					selectedMessage={selectedMessage}
					onSelectMessage={setSelectedMessageId}
					chartData={chartData}
					isOpen={isInspectorOpen}
					onClose={closeInspector}
					method={method}
					setMethod={setMethod}
				/>
			</Suspense>

			{/* Delete confirmation dialog */}
			<AlertDialog
				open={!!pendingDelete}
				onOpenChange={(open) => {
					if (!open) cancelDelete();
				}}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>
							{pendingDelete?.type === "all"
								? "Delete all conversations?"
								: "Delete this conversation?"}
						</AlertDialogTitle>
						<AlertDialogDescription>
							{pendingDelete?.type === "all"
								? "This will permanently delete all your conversations. This action cannot be undone."
								: "This will permanently delete this conversation. This action cannot be undone."}
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel onClick={cancelDelete}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={confirmDelete}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							Delete
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
};

export default memo(ChatInterface);
