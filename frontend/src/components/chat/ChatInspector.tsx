// NOTE (framer-motion): Width animation + spring physics for mobile slide.
// Cannot be replaced with CSS: AnimatePresence exit + animated width.
import { AnimatePresence, motion } from "framer-motion";
import { Activity, Hash, Info, MessageSquare, X, Zap } from "lucide-react";
import type React from "react";
import { memo, useEffect, useMemo } from "react";
import {
	Area,
	AreaChart,
	Tooltip as RechartsTooltip,
	ReferenceLine,
	ResponsiveContainer,
	XAxis,
	YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { SentimentResult } from "../../lib/api";
import type { ChatMessage } from "../../lib/useChat";

// ============ Types ============

interface ChartDataPoint {
	id: string;
	name: number;
	score: number;
	label?: string;
	content?: string;
}

interface ChatInspectorProps {
	messages: ChatMessage[];
	selectedMessage: ChatMessage | null | undefined;
	onSelectMessage: (id: string) => void;
	chartData: ChartDataPoint[];
	isOpen: boolean;
	onClose: () => void;
	method: string;
	setMethod: (method: string) => void;
}

// ============ Helper Components ============

const SENTIMENT_COLORS = {
	Positive: {
		bg: "bg-emerald-500/10",
		text: "text-emerald-400",
		border: "border-emerald-500/20",
		gradient: "from-emerald-500 to-teal-400",
	},
	Negative: {
		bg: "bg-rose-500/10",
		text: "text-rose-400",
		border: "border-rose-500/20",
		gradient: "from-rose-500 to-orange-400",
	},
	Neutral: {
		bg: "bg-blue-500/10",
		text: "text-blue-400",
		border: "border-blue-500/20",
		gradient: "from-blue-500 to-indigo-400",
	},
};

const SentimentCard = memo<{
	title: string;
	sentiment: SentimentResult | undefined | null;
	icon: React.ReactNode;
	emptyText: string;
	compact?: boolean;
}>(({ title, sentiment, icon, emptyText, compact }) => {
	const colors =
		SENTIMENT_COLORS[sentiment?.label as keyof typeof SENTIMENT_COLORS] ||
		SENTIMENT_COLORS.Neutral;

	return (
		<Card className="bg-card/50 border-border">
			<CardHeader className={cn("pb-2 px-4", compact ? "pt-3" : "pt-4")}>
				<CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
					{icon}
					{title}
				</CardTitle>
			</CardHeader>
			<CardContent className={cn("px-4 pb-4", compact && "pt-0")}>
				{sentiment ? (
					<div className="relative">
						{!compact && (
							<div
								className={cn(
									"absolute -top-2 left-0 w-full h-1 rounded-full opacity-70 bg-gradient-to-r",
									colors.gradient,
								)}
							/>
						)}

						<div className="flex items-end justify-between mb-2 pt-2">
							<span
								className={cn(
									"font-bold font-mono tracking-tighter",
									compact ? "text-2xl" : "text-4xl",
								)}
							>
								{(sentiment.score * 100).toFixed(0)}
							</span>
							<Badge
								variant="outline"
								className={cn(
									"text-[10px] font-bold uppercase",
									colors.bg,
									colors.text,
									colors.border,
								)}
							>
								{sentiment.label}
							</Badge>
						</div>

						{sentiment.emotion && (
							<p className="text-sm text-muted-foreground capitalize flex items-center gap-2">
								<span className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
								{sentiment.emotion}
							</p>
						)}
					</div>
				) : (
					<div className="h-16 rounded-xl border border-dashed border-border flex flex-col items-center justify-center text-xs text-muted-foreground bg-muted/10">
						<Info className="w-4 h-4 mb-1 opacity-50" />
						{emptyText}
					</div>
				)}
			</CardContent>
		</Card>
	);
});

SentimentCard.displayName = "SentimentCard";

// ============ Main Component ============

const ChatInspector = memo<ChatInspectorProps>(
	({
		messages,
		selectedMessage,
		onSelectMessage,
		chartData,
		isOpen,
		onClose,
		method,
		setMethod,
	}) => {
		// Calculate overall sentiment from the last message that has it
		const lastSentimentMessage = [...messages]
			.reverse()
			.find((m) => m.cumulativeSentiment);
		const overallSentiment = lastSentimentMessage?.cumulativeSentiment;

		// Filter user messages for the log
		const userMessages = useMemo(
			() => messages.filter((m) => m.role === "user"),
			[messages],
		);

		// Determine the "focused" user message based on selection
		const focusedUserMessageIndex = useMemo(() => {
			if (!selectedMessage) return userMessages.length - 1;

			// If selected is user message, find its index
			if (selectedMessage.role === "user") {
				return userMessages.findIndex((m) => m.id === selectedMessage.id);
			}

			// If selected is assistant, find the preceding user message
			const msgIndex = messages.findIndex((m) => m.id === selectedMessage.id);
			if (msgIndex > 0) {
				const precedingUserMsg = messages[msgIndex - 1];
				if (precedingUserMsg.role === "user") {
					return userMessages.findIndex((m) => m.id === precedingUserMsg.id);
				}
			}

			return userMessages.length - 1;
		}, [selectedMessage, messages, userMessages]);

		// Auto-scroll logic for the sidebar list
		useEffect(() => {
			if (focusedUserMessageIndex !== -1) {
				const msg = userMessages[focusedUserMessageIndex];
				if (msg) {
					const el = document.getElementById(`sidebar-card-${msg.id}`);
					if (el) {
						el.scrollIntoView({ behavior: "smooth", block: "center" });
					}
				}
			}
		}, [focusedUserMessageIndex, userMessages]);

		const content = (
			<div className="h-full flex flex-col bg-secondary border-l border-border w-80 shadow-xl">
				{/* Header */}
				<div className="h-14 border-b border-border flex items-center px-6 justify-between bg-secondary/95 backdrop-blur-sm">
					<span className="font-bold text-sm flex items-center gap-2">
						<Activity className="w-4 h-4 text-primary" />
						Sentiment Analysis
					</span>
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						className="h-7 w-7"
						aria-label="Close inspector"
					>
						<X className="w-4 h-4" />
					</Button>
				</div>

				<ScrollArea className="flex-1">
					<div className="p-6 space-y-6">
						{/* Method Selector */}
						<div className="space-y-2">
							<label className="text-xs font-medium text-muted-foreground flex items-center gap-2">
								<Zap className="w-3.5 h-3.5" />
								Analysis Method
							</label>
							<Select value={method} onValueChange={setMethod}>
								<SelectTrigger className="w-full h-8 text-xs">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="nlp_api">NLP API</SelectItem>
									<SelectItem value="llm_separate">LLM Separate</SelectItem>
									<SelectItem value="structured">Structured</SelectItem>
								</SelectContent>
							</Select>
						</div>

						{/* Tier 1: Overall Conversation Sentiment */}
						<SentimentCard
							title="Overall Sentiment"
							sentiment={overallSentiment}
							icon={<Hash className="w-3.5 h-3.5" />}
							emptyText="No conversation data"
						/>

						{/* Trend Chart (Moved Up) */}
						<Card className="bg-card/50 border-border">
							<CardHeader className="pb-2 pt-4 px-4">
								<CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
									<Activity className="w-3.5 h-3.5" />
									Session Trend
								</CardTitle>
							</CardHeader>
							<CardContent className="px-4 pb-4">
								{chartData.length > 0 ? (
									<div className="h-48">
										<ResponsiveContainer width="100%" height={192}>
											<AreaChart data={chartData}>
												<defs>
													<linearGradient
														id="colorScore"
														x1="0"
														y1="0"
														x2="0"
														y2="1"
													>
														<stop
															offset="5%"
															stopColor="#3b82f6"
															stopOpacity={0.3}
														/>
														<stop
															offset="95%"
															stopColor="#3b82f6"
															stopOpacity={0}
														/>
													</linearGradient>
												</defs>
												<XAxis dataKey="name" hide />
												<YAxis domain={[-1, 1]} hide />
												<RechartsTooltip
													content={({ active, payload }) => {
														if (active && payload && payload.length) {
															const data = payload[0].payload as ChartDataPoint;
															return (
																<div className="bg-popover border border-border p-2 rounded-lg shadow-lg max-w-[200px]">
																	<p className="text-xs font-bold mb-1">
																		Message {data.name}
																	</p>
																	<div className="flex items-center justify-between gap-4 mb-1">
																		<span className="text-xs text-muted-foreground">
																			{data.label}
																		</span>
																		<span className="text-xs font-mono font-bold">
																			{(data.score * 100).toFixed(0)}%
																		</span>
																	</div>
																	{data.content && (
																		<p className="text-[10px] text-muted-foreground line-clamp-2 italic border-t border-border pt-1 mt-1">
																			"{data.content}"
																		</p>
																	)}
																</div>
															);
														}
														return null;
													}}
												/>
												<ReferenceLine
													y={0}
													stroke="hsl(var(--muted-foreground))"
													strokeDasharray="3 3"
												/>
												<Area
													type="monotone"
													dataKey="score"
													stroke="#3b82f6"
													fillOpacity={1}
													fill="url(#colorScore)"
													strokeWidth={2}
													activeDot={{
														r: 6,
														fill: "#3b82f6",
														stroke: "white",
														strokeWidth: 2,
													}}
													dot={(props) => {
														const { cx, cy, payload } = props;
														const isFocused =
															userMessages[focusedUserMessageIndex]?.id ===
															payload.id;

														if (!isFocused) return <></>;

														return (
															<circle
																cx={cx}
																cy={cy}
																r={5}
																fill="#3b82f6"
																stroke="white"
																strokeWidth={2}
															/>
														);
													}}
												/>
											</AreaChart>
										</ResponsiveContainer>
									</div>
								) : (
									<div className="h-48 rounded-xl border border-dashed border-border flex flex-col items-center justify-center text-xs text-muted-foreground bg-muted/10">
										<Info className="w-4 h-4 mb-2 opacity-50" />
										No trend data yet
									</div>
								)}
							</CardContent>
						</Card>

						{/* Tier 2: Statement-Level Analysis (Log) */}
						<div className="space-y-3">
							<h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2 px-1">
								<MessageSquare className="w-3.5 h-3.5" />
								Statement Analysis
							</h3>

							<div className="space-y-2 max-h-[400px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
								{userMessages.length > 0 ? (
									userMessages.map((msg) => {
										const sentiment = msg.sentiment;
										const colors =
											SENTIMENT_COLORS[
												sentiment?.label as keyof typeof SENTIMENT_COLORS
											] || SENTIMENT_COLORS.Neutral;
										const isFocused =
											userMessages[focusedUserMessageIndex]?.id === msg.id;

										return (
											<Card
												key={msg.id}
												id={`sidebar-card-${msg.id}`}
												onClick={() => onSelectMessage(msg.id)}
												className={cn(
													"bg-card/50 border-border overflow-hidden shrink-0 transition-all duration-200 cursor-pointer hover:bg-card/80",
													isFocused &&
														"ring-2 ring-primary border-primary shadow-md scale-[1.02]",
												)}
											>
												<div
													className={cn("h-1 w-full opacity-50", colors.bg)}
												/>
												<CardContent className="p-3 space-y-2">
													<p
														className="text-xs text-muted-foreground line-clamp-3 italic"
														title={msg.content}
													>
														"{msg.content}"
													</p>

													{sentiment ? (
														<div className="flex items-center justify-between">
															<Badge
																variant="outline"
																className={cn(
																	"text-[10px] font-bold uppercase h-5",
																	colors.bg,
																	colors.text,
																	colors.border,
																)}
															>
																{sentiment.label}
															</Badge>
															<span className="text-[10px] font-mono text-muted-foreground">
																{(sentiment.score * 100).toFixed(0)}%
															</span>
														</div>
													) : (
														<div className="flex items-center gap-1 text-[10px] text-muted-foreground">
															<span className="w-1.5 h-1.5 rounded-full bg-muted" />
															Pending...
														</div>
													)}
												</CardContent>
											</Card>
										);
									})
								) : (
									<div className="h-24 rounded-xl border border-dashed border-border flex flex-col items-center justify-center text-xs text-muted-foreground bg-muted/10">
										<Info className="w-4 h-4 mb-2 opacity-50" />
										No messages yet
									</div>
								)}
							</div>
						</div>
					</div>
				</ScrollArea>
			</div>
		);

		return (
			<AnimatePresence>
				{isOpen && (
					<>
						{/* Desktop */}
						<motion.div
							initial={{ width: 0, opacity: 0 }}
							animate={{ width: 320, opacity: 1 }}
							exit={{ width: 0, opacity: 0 }}
							className="hidden lg:block h-full overflow-hidden"
						>
							<div className="w-80 h-full">{content}</div>
						</motion.div>

						{/* Mobile overlay */}
						<motion.div
							initial={{ opacity: 0 }}
							animate={{ opacity: 1 }}
							exit={{ opacity: 0 }}
							onClick={onClose}
							className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
						/>
						<motion.div
							initial={{ x: "100%" }}
							animate={{ x: 0 }}
							exit={{ x: "100%" }}
							transition={{ type: "spring", damping: 25, stiffness: 200 }}
							className="fixed inset-y-0 right-0 z-50 lg:hidden"
						>
							{content}
						</motion.div>
					</>
				)}
			</AnimatePresence>
		);
	},
);

ChatInspector.displayName = "ChatInspector";

export default ChatInspector;
