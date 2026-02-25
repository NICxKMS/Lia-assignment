import DOMPurify from "dompurify";
import {
	Bot,
	Brain,
	Check,
	ChevronDown,
	ChevronUp,
	Copy,
	ExternalLink,
	Paperclip,
	User,
} from "lucide-react";
import React, {
	lazy,
	memo,
	Suspense,
	useCallback,
	useMemo,
	useState,
} from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "./ChatInterface";

// Lazy load heavy markdown component
const MarkdownMessage = lazy(() => import("../MarkdownMessage"));

// Simple markdown loading fallback
const MarkdownFallback = () => (
	<div className="animate-pulse space-y-2">
		<div className="h-4 bg-muted rounded w-3/4" />
		<div className="h-4 bg-muted rounded w-1/2" />
	</div>
);

// ============ Types ============

interface MessageListProps {
	messages: ChatMessage[];
	selectedMessageId: string | null;
	onSelectMessage: (id: string) => void;
	messagesEndRef: React.RefObject<HTMLDivElement | null>;
	onSuggestionSelect?: (text: string) => void;
}

// ============ Constants ============

const SUGGESTIONS = [
	"What are the advantages of using Next.js?",
	"Write code to demonstrate Dijkstra's algorithm",
	"Help me write an essay about Silicon Valley",
	"What is the weather in San Francisco?",
];

// ============ Hooks ============

function useCopyToClipboard() {
	const [copied, setCopied] = React.useState(false);
	const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

	const copy = useCallback(async (text: string) => {
		await navigator.clipboard.writeText(text);
		setCopied(true);
		if (timerRef.current) clearTimeout(timerRef.current);
		timerRef.current = setTimeout(() => setCopied(false), 2000);
	}, []);

	React.useEffect(
		() => () => {
			if (timerRef.current) clearTimeout(timerRef.current);
		},
		[],
	);

	return { copied, copy };
}

// ============ Components ============

// Loading dots animation - CSS only
const LoadingDots: React.FC = memo(() => (
	<div className="flex items-center gap-1 py-2">
		{[0, 1, 2].map((i) => (
			<div
				key={i}
				className="w-2 h-2 rounded-full bg-primary animate-pulse"
				style={{ animationDelay: `${i * 200}ms` }}
			/>
		))}
	</div>
));

LoadingDots.displayName = "LoadingDots";

// Sentiment indicator dot
const SentimentDot = memo<{ label: string }>(({ label }) => {
	const color =
		label === "Positive"
			? "bg-emerald-500"
			: label === "Negative"
				? "bg-rose-500"
				: "bg-blue-500";

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<div className={cn("w-1.5 h-1.5 rounded-full", color)} />
				</TooltipTrigger>
				<TooltipContent side="left">
					<p className="text-xs font-medium">{label} Sentiment</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
});

SentimentDot.displayName = "SentimentDot";

// Simple markdown parser for thoughts - handles basic formatting
const ThoughtsMarkdown = memo<{ content: string }>(({ content }) => {
	// Parse basic markdown: **bold**, *italic*, `code`, headers
	const parseMarkdown = (text: string) => {
		const html = text
			// Code blocks with backticks
			.replace(
				/`([^`]+)`/g,
				'<code class="px-1 py-0.5 rounded bg-muted text-muted-foreground font-mono text-xs">$1</code>',
			)
			// Bold with **
			.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
			// Italic with *
			.replace(/\*([^*]+)\*/g, "<em>$1</em>")
			// Headers (simple h4 for thoughts)
			.replace(
				/^### (.+)$/gm,
				'<span class="font-semibold block mt-2 mb-1">$1</span>',
			)
			.replace(
				/^## (.+)$/gm,
				'<span class="font-semibold block mt-2 mb-1">$1</span>',
			)
			// Line breaks
			.replace(/\n/g, "<br/>");
		return DOMPurify.sanitize(html);
	};

	return (
		<div
			className="text-sm text-muted-foreground italic leading-relaxed"
			dangerouslySetInnerHTML={{ __html: parseMarkdown(content) }}
		/>
	);
});

ThoughtsMarkdown.displayName = "ThoughtsMarkdown";

// Collapsible thoughts section - shows model thinking process
// Auto-expands during streaming, collapses when done
const ThoughtsSection = memo<{ thoughts: string[]; isStreaming?: boolean }>(
	({ thoughts, isStreaming = false }) => {
		const [isExpanded, setIsExpanded] = useState(false);
		const [wasStreaming, setWasStreaming] = useState(false);
		const hasThoughts = thoughts && thoughts.length > 0;

		// Auto-expand when streaming starts, auto-collapse when streaming ends
		React.useEffect(() => {
			if (isStreaming && !wasStreaming) {
				// Streaming just started - expand
				setIsExpanded(true);
				setWasStreaming(true);
			} else if (!isStreaming && wasStreaming) {
				// Streaming just ended - collapse
				setIsExpanded(false);
				setWasStreaming(false);
			}
		}, [isStreaming, wasStreaming]);

		const combinedThoughts = hasThoughts ? thoughts.join("") : "";

		// Handle toggle without causing scroll
		const handleToggle = React.useCallback((e: React.MouseEvent) => {
			e.preventDefault();
			e.stopPropagation();
			setIsExpanded((prev) => !prev);
		}, []);

		if (!hasThoughts) return null;

		return (
			<div className="mb-3">
				<button
					type="button"
					onClick={handleToggle}
					className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors group"
				>
					<Brain
						className={cn(
							"w-4 h-4",
							isStreaming && "animate-pulse text-primary",
						)}
					/>
					<span className="font-medium">
						{isStreaming ? "Thinking..." : "Thought process"}
					</span>
					{isStreaming && (
						<span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
					)}
					{isExpanded ? (
						<ChevronUp className="w-4 h-4 opacity-60 group-hover:opacity-100" />
					) : (
						<ChevronDown className="w-4 h-4 opacity-60 group-hover:opacity-100" />
					)}
				</button>

				{isExpanded && (
					<div className="mt-2 pl-6 border-l-2 border-muted-foreground/20 animate-in slide-in-from-top-2 duration-200">
						<ThoughtsMarkdown content={combinedThoughts} />
					</div>
				)}
			</div>
		);
	},
);

ThoughtsSection.displayName = "ThoughtsSection";

// Single message component - optimized with CSS transitions
const MessageItem = memo<{
	msg: ChatMessage;
	onSelect: () => void;
}>(({ msg, onSelect }) => {
	const isUser = msg.role === "user";
	const { copied, copy } = useCopyToClipboard();

	// Get content from parts or fallback to content
	const content = useMemo(() => {
		const textPart = msg.parts.find((p) => p.type === "text");
		return textPart?.text || msg.content;
	}, [msg.parts, msg.content]);

	const fileParts = useMemo(
		() => msg.parts.filter((p) => p.type === "file"),
		[msg.parts],
	);
	const sourceParts = useMemo(
		() => msg.parts.filter((p) => p.type === "source-url"),
		[msg.parts],
	);

	const handleCopy = useCallback(
		(e: React.MouseEvent) => {
			e.stopPropagation();
			copy(content);
		},
		[copy, content],
	);

	return (
		<div
			id={`message-${msg.id}`}
			role="button"
			tabIndex={0}
			aria-label={`${isUser ? "Your" : "Assistant"} message`}
			onKeyDown={(e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					onSelect?.();
				}
			}}
			className={cn(
				"relative group py-4 animate-in fade-in slide-in-from-bottom-2 duration-300",
				isUser && "flex justify-end",
			)}
			onClick={onSelect}
		>
			<div
				className={cn("flex gap-4", isUser && "flex-row-reverse max-w-[80%]")}
			>
				{/* Avatar */}
				<div
					className={cn(
						"w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ring-1 ring-border",
						isUser
							? "bg-secondary text-foreground"
							: "bg-primary text-primary-foreground",
					)}
				>
					{isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
				</div>

				{/* Content */}
				<div className={cn("flex-1 min-w-0", isUser && "text-right")}>
					{/* Header */}
					<div
						className={cn(
							"flex items-center gap-2 mb-1",
							isUser && "justify-end",
						)}
					>
						<span className="text-sm font-semibold">
							{isUser ? "You" : "Assistant"}
						</span>
						<span className="text-xs text-muted-foreground">
							{msg.timestamp.toLocaleTimeString([], {
								hour: "2-digit",
								minute: "2-digit",
							})}
						</span>
						{msg.isStreaming && (
							<span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
						)}
					</div>

					{/* Message body */}
					<div className="text-foreground leading-7">
						{/* Thoughts section for assistant messages */}
						{!isUser && msg.thoughts && msg.thoughts.length > 0 && (
							<ThoughtsSection
								thoughts={msg.thoughts}
								isStreaming={msg.isStreaming}
							/>
						)}

						{content ? (
							isUser ? (
								<p className="whitespace-pre-wrap m-0">{content}</p>
							) : (
								<Suspense fallback={<MarkdownFallback />}>
									<MarkdownMessage content={content} />
								</Suspense>
							)
						) : msg.isStreaming ? (
							<LoadingDots />
						) : null}
					</div>

					{/* File attachments */}
					{fileParts.length > 0 && (
						<div className="flex flex-wrap gap-2 mt-3">
							{fileParts.map((file) =>
								file.mediaType?.startsWith("image/") ? (
									<img
										key={file.url || file.filename}
										src={file.url}
										alt={file.filename || "Attachment"}
										className="max-w-xs rounded-lg border border-border shadow-sm"
										loading="lazy"
									/>
								) : (
									<a
										key={file.url || file.filename}
										href={file.url}
										target="_blank"
										rel="noopener noreferrer"
									>
										<Badge
											variant="outline"
											className="gap-2 cursor-pointer hover:bg-accent/10 py-1.5 px-3"
										>
											<Paperclip className="w-3 h-3" />
											{file.filename || "File"}
										</Badge>
									</a>
								),
							)}
						</div>
					)}

					{/* Sources */}
					{!isUser && sourceParts.length > 0 && (
						<div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border/30">
							{sourceParts.map((source, idx) => (
								<a
									key={source.url}
									href={source.url}
									target="_blank"
									rel="noopener noreferrer"
								>
									<Badge variant="secondary" className="gap-1 text-xs">
										<ExternalLink className="w-3 h-3" />
										{source.title || `Source ${idx + 1}`}
									</Badge>
								</a>
							))}
						</div>
					)}

					{/* Copy action for assistant messages */}
					{!isUser && content && !msg.isStreaming && (
						<div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
							<Button
								variant="ghost"
								size="sm"
								className="h-7 px-2 text-xs"
								onClick={handleCopy}
							>
								{copied ? (
									<Check className="w-3 h-3 mr-1" />
								) : (
									<Copy className="w-3 h-3 mr-1" />
								)}
								{copied ? "Copied" : "Copy"}
							</Button>
						</div>
					)}
				</div>
			</div>

			{/* Sentiment indicator */}
			{isUser && msg.sentiment && (
				<div className="absolute -right-3 top-6 opacity-0 group-hover:opacity-100 transition-opacity">
					<SentimentDot label={msg.sentiment.label} />
				</div>
			)}
		</div>
	);
});

MessageItem.displayName = "MessageItem";

// Empty state with suggestions - memoized
const EmptyState = memo<{ onSuggestionSelect: (text: string) => void }>(
	({ onSuggestionSelect }) => (
		<div className="h-full flex flex-col items-center justify-center p-8">
			<div className="text-center mb-12">
				<h1 className="text-4xl font-semibold text-foreground mb-2 tracking-tight">
					Hello there!
				</h1>
				<p className="text-xl text-muted-foreground">
					How can I help you today?
				</p>
			</div>

			<div className="max-w-2xl w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
				{SUGGESTIONS.map((suggestion) => (
					<button
						type="button"
						key={suggestion}
						onClick={() => onSuggestionSelect(suggestion)}
						className="text-left p-4 rounded-xl border border-border bg-card hover:bg-accent/50 transition-colors text-sm text-muted-foreground hover:text-foreground"
					>
						{suggestion}
					</button>
				))}
			</div>
		</div>
	),
);

EmptyState.displayName = "EmptyState";

// ============ Main Component ============

const MessageList = memo<MessageListProps>(
	({
		messages,
		selectedMessageId,
		onSelectMessage,
		messagesEndRef,
		onSuggestionSelect,
	}) => {
		// Handle suggestion selection via callback prop
		const handleSuggestionSelect = useCallback(
			(suggestion: string) => {
				onSuggestionSelect?.(suggestion);
			},
			[onSuggestionSelect],
		);

		// Scroll to selected message
		React.useEffect(() => {
			if (selectedMessageId) {
				const el = document.getElementById(`message-${selectedMessageId}`);
				if (el) {
					el.scrollIntoView({ behavior: "smooth", block: "center" });
				}
			}
		}, [selectedMessageId]);

		if (messages.length === 0) {
			return <EmptyState onSuggestionSelect={handleSuggestionSelect} />;
		}

		return (
			<div className="flex-1 overflow-y-auto p-4 sm:p-6 custom-scrollbar">
				<div className="max-w-3xl mx-auto space-y-2">
					{messages.map((msg) => (
						<MessageItem
							key={msg.id}
							msg={msg}
							onSelect={() => onSelectMessage(msg.id)}
						/>
					))}
					<div ref={messagesEndRef} className="h-4" />
				</div>
			</div>
		);
	},
);

MessageList.displayName = "MessageList";

export default MessageList;
