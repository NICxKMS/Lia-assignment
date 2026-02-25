// NOTE (framer-motion): Deeply integrated — whileHover/whileTap on items,
// AnimatePresence for list, and spring physics for mobile drawer.
import { AnimatePresence, motion } from "framer-motion";
import {
	ChevronDown,
	ChevronRight,
	Loader2,
	LogOut,
	MessageSquare,
	PanelLeft,
	PanelLeftClose,
	Plus,
	Trash2,
} from "lucide-react";
import React, { memo, useCallback, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { ConversationSummary, User } from "../../lib/api";

// ============ Types ============

interface ChatSidebarProps {
	history: ConversationSummary[] | undefined;
	currentConversationId: string | undefined;
	onSelectConversation: (id: string) => void;
	onNewChat: () => void;
	onDeleteConversation: (id: string, e: React.MouseEvent) => void;
	onDeleteAll?: () => void;
	user: User | null;
	onLogout: () => void;
	isOpen: boolean;
	onClose?: () => void;
	isLoading?: boolean;
}

interface ConversationGroup {
	label: string;
	items: ConversationSummary[];
}

// ============ Helpers ============

const getDateGroup = (timestamp: string): string => {
	const date = new Date(timestamp);
	const now = new Date();
	const diffDays = Math.floor(
		(now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24),
	);

	if (diffDays === 0) return "Today";
	if (diffDays === 1) return "Yesterday";
	if (diffDays < 7) return "This Week";
	if (diffDays < 30) return "This Month";
	return "Older";
};

const groupConversations = (
	conversations: ConversationSummary[],
): ConversationGroup[] => {
	const groups = new Map<string, ConversationSummary[]>();
	const order = ["Today", "Yesterday", "This Week", "This Month", "Older"];

	for (const conv of conversations) {
		const group = getDateGroup(conv.updated_at);
		const existing = groups.get(group) || [];
		existing.push(conv);
		groups.set(group, existing);
	}

	return order
		.filter((label) => groups.has(label))
		.map((label) => ({ label, items: groups.get(label) ?? [] }));
};

// ============ Sub-components ============

const ConversationItem = memo<{
	conversation: ConversationSummary;
	isActive: boolean;
	onSelect: () => void;
	onDelete: (e: React.MouseEvent) => void;
}>(({ conversation, isActive, onSelect, onDelete }) => {
	const handleDelete = useCallback(
		(e: React.MouseEvent) => {
			e.stopPropagation();
			onDelete(e);
		},
		[onDelete],
	);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				onSelect();
			}
		},
		[onSelect],
	);

	const title = useMemo(() => {
		const t = conversation.title || "New conversation";
		return t.length > 28 ? `${t.slice(0, 28)}...` : t;
	}, [conversation.title]);

	return (
		<motion.div
			onClick={onSelect}
			onKeyDown={handleKeyDown}
			role="button"
			tabIndex={0}
			className={cn(
				"group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left cursor-pointer",
				"transition-all duration-200 relative overflow-hidden",
				isActive
					? "text-primary font-semibold"
					: "text-foreground/70 hover:text-foreground",
			)}
			whileHover={{ x: 4 }}
			whileTap={{ scale: 0.98 }}
		>
			<MessageSquare
				className={cn("w-4 h-4 flex-shrink-0", isActive && "text-primary")}
			/>

			<span className="flex-1 truncate text-sm font-medium">{title}</span>

			<button
				type="button"
				onClick={handleDelete}
				className={cn(
					"opacity-0 group-hover:opacity-100 p-1 rounded",
					"hover:bg-destructive/10 hover:text-destructive",
					"transition-all duration-200",
				)}
				aria-label="Delete conversation"
			>
				<Trash2 className="w-3.5 h-3.5" />
			</button>
		</motion.div>
	);
});

ConversationItem.displayName = "ConversationItem";

const ConversationGroupSection = memo<{
	group: ConversationGroup;
	currentId: string | undefined;
	onSelect: (id: string) => void;
	onDelete: (id: string, e: React.MouseEvent) => void;
}>(({ group, currentId, onSelect, onDelete }) => {
	const [isOpen, setIsOpen] = React.useState(true);

	return (
		<Collapsible open={isOpen} onOpenChange={setIsOpen}>
			<CollapsibleTrigger className="w-full flex items-center gap-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors">
				{isOpen ? (
					<ChevronDown className="w-3 h-3" />
				) : (
					<ChevronRight className="w-3 h-3" />
				)}
				{group.label}
				<span className="ml-auto text-[10px] font-normal opacity-60">
					{group.items.length}
				</span>
			</CollapsibleTrigger>

			<CollapsibleContent className="space-y-1 px-2">
				<AnimatePresence mode="popLayout">
					{group.items.map((conv) => (
						<ConversationItem
							key={conv.id}
							conversation={conv}
							isActive={conv.id === currentId}
							onSelect={() => onSelect(conv.id)}
							onDelete={(e) => onDelete(conv.id, e)}
						/>
					))}
				</AnimatePresence>
			</CollapsibleContent>
		</Collapsible>
	);
});

ConversationGroupSection.displayName = "ConversationGroupSection";

// ============ Main Component ============

const ChatSidebar = memo<ChatSidebarProps>(
	({
		history,
		currentConversationId,
		onSelectConversation,
		onNewChat,
		onDeleteConversation,
		onDeleteAll,
		user,
		onLogout,
		isOpen,
		onClose,
		isLoading,
	}) => {
		const [isCollapsed, setIsCollapsed] = useState(false);

		// Store callbacks in refs for stable references
		const onSelectRef = useRef(onSelectConversation);
		const onDeleteRef = useRef(onDeleteConversation);

		// Keep refs updated
		React.useEffect(() => {
			onSelectRef.current = onSelectConversation;
			onDeleteRef.current = onDeleteConversation;
		}, [onSelectConversation, onDeleteConversation]);

		// Stable callbacks that use refs
		const handleSelectConversation = useCallback((id: string) => {
			onSelectRef.current(id);
		}, []);

		const handleDeleteConversation = useCallback(
			(id: string, e: React.MouseEvent) => {
				onDeleteRef.current(id, e);
			},
			[],
		);

		const groupedConversations = useMemo(
			() => groupConversations(history || []),
			[history],
		);

		// Collapsed sidebar view
		const collapsedSidebar = (
			<div className="h-full flex flex-col border-r border-border w-14 items-center py-4 gap-2 bg-secondary/50">
				<Button
					onClick={() => setIsCollapsed(false)}
					variant="ghost"
					size="icon"
					className="h-8 w-8 hover:bg-muted"
					aria-label="Expand sidebar"
				>
					<PanelLeft className="w-4 h-4" />
				</Button>
				<Button
					onClick={onNewChat}
					variant="ghost"
					size="icon"
					className="h-8 w-8 hover:bg-primary/10 hover:text-primary"
					aria-label="New conversation"
				>
					<Plus className="w-4 h-4" />
				</Button>

				{/* Spacer to push user icon to bottom */}
				<div className="flex-1" />

				{/* User icon at the bottom */}
				{user && (
					<div
						className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium cursor-pointer hover:bg-primary/30 transition-colors"
						title={user.username}
					>
						{user.username.charAt(0).toUpperCase()}
					</div>
				)}

				<Button
					onClick={onLogout}
					variant="ghost"
					size="icon"
					className="h-8 w-8 hover:bg-destructive/10 hover:text-destructive"
					aria-label="Logout"
				>
					<LogOut className="w-4 h-4" />
				</Button>
			</div>
		);

		// Full sidebar with collapse button
		const fullSidebar = (
			<div className="h-full flex flex-col border-r border-border w-72 bg-secondary/50">
				{/* Header */}
				<div className="h-14 border-b border-border flex items-center px-4 justify-between bg-secondary/50">
					<span className="font-bold text-sm">Conversations</span>
					<div className="flex items-center gap-1">
						<Button
							onClick={onNewChat}
							variant="ghost"
							size="icon"
							className="h-8 w-8 hover:bg-primary/10 hover:text-primary"
							aria-label="New conversation"
						>
							<Plus className="w-4 h-4" />
						</Button>
						<Button
							onClick={() => setIsCollapsed(true)}
							variant="ghost"
							size="icon"
							className="h-8 w-8 hover:bg-muted"
							aria-label="Collapse sidebar"
						>
							<PanelLeftClose className="w-4 h-4" />
						</Button>
					</div>
				</div>

				{/* Conversation List */}
				<ScrollArea className="flex-1 py-2">
					{!history || history.length === 0 ? (
						<div className="flex flex-col items-center justify-center h-40 text-muted-foreground text-sm">
							<MessageSquare className="w-8 h-8 mb-2 opacity-50" />
							No conversations yet
						</div>
					) : (
						<div className="space-y-4">
							{groupedConversations.map((group) => (
								<ConversationGroupSection
									key={group.label}
									group={group}
									currentId={currentConversationId}
									onSelect={handleSelectConversation}
									onDelete={handleDeleteConversation}
								/>
							))}
						</div>
					)}
				</ScrollArea>

				{/* Footer */}
				<div className="border-t border-border p-4 space-y-3">
					{onDeleteAll && history && history.length > 0 && (
						<Button
							onClick={onDeleteAll}
							variant="ghost"
							size="sm"
							className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
						>
							<Trash2 className="w-4 h-4 mr-2" />
							Delete All
						</Button>
					)}

					{user && (
						<div className="flex items-center justify-between">
							<div className="flex items-center gap-2 text-sm text-muted-foreground truncate">
								<div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium">
									{user.username.charAt(0).toUpperCase()}
								</div>
								<span className="truncate">{user.username}</span>
							</div>
							<Button
								onClick={onLogout}
								variant="ghost"
								size="icon"
								className="h-8 w-8"
							>
								<LogOut className="w-4 h-4" />
							</Button>
						</div>
					)}

					{isLoading && (
						<div className="flex items-center justify-center text-muted-foreground">
							<Loader2 className="w-4 h-4 animate-spin mr-2" />
							<span className="text-xs">Loading...</span>
						</div>
					)}
				</div>
			</div>
		);

		return (
			<>
				{/* Desktop sidebar - collapsible */}
				<div className="hidden md:block h-full flex-shrink-0">
					{isCollapsed ? collapsedSidebar : fullSidebar}
				</div>

				{/* Mobile drawer */}
				<AnimatePresence>
					{isOpen && (
						<>
							<motion.div
								initial={{ opacity: 0 }}
								animate={{ opacity: 1 }}
								exit={{ opacity: 0 }}
								onClick={onClose}
								className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
							/>
							<motion.div
								initial={{ x: "-100%" }}
								animate={{ x: 0 }}
								exit={{ x: "-100%" }}
								transition={{ type: "spring", damping: 25, stiffness: 200 }}
								className="fixed inset-y-0 left-0 z-50 md:hidden"
							>
								{fullSidebar}
							</motion.div>
						</>
					)}
				</AnimatePresence>
			</>
		);
	},
);

ChatSidebar.displayName = "ChatSidebar";

export default ChatSidebar;
