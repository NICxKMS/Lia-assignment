import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock scrollIntoView which is not available in jsdom
beforeEach(() => {
	Element.prototype.scrollIntoView = vi.fn();
});

// Mock framer-motion - render only one version by skipping mobile overlay
vi.mock("framer-motion", async () => {
	const actual = await vi.importActual("react");
	const { createElement, forwardRef } = actual as typeof import("react");
	return {
		motion: {
			div: forwardRef(
				(
					{
						className,
						...props
					}: React.HTMLAttributes<HTMLDivElement> & {
						children?: React.ReactNode;
					},
					ref: React.Ref<HTMLDivElement>,
				) => {
					// Skip mobile overlay and mobile drawer (lg:hidden elements)
					if (
						className?.includes("lg:hidden") ||
						className?.includes("fixed inset-0") ||
						className?.includes("fixed inset-y-0")
					) {
						return null;
					}
					// Always show desktop version
					const testClassName = className?.replace("hidden lg:block", "block");
					return createElement(
						"div",
						{ ref, className: testClassName, ...props },
						props.children,
					);
				},
			),
		},
		AnimatePresence: ({ children }: { children?: React.ReactNode }) => children,
	};
});

// Mock recharts
vi.mock("recharts", () => ({
	ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="responsive-container">{children}</div>
	),
	AreaChart: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="area-chart">{children}</div>
	),
	Area: () => null,
	XAxis: () => null,
	YAxis: () => null,
	Tooltip: () => null,
	ReferenceLine: () => null,
	Dot: () => null,
}));

import ChatInspector from "../components/chat/ChatInspector";
import type { ChatMessage } from "../lib/useChat";

const createMockMessage = (
	overrides: Partial<ChatMessage> = {},
): ChatMessage => ({
	id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
	role: "user",
	content: "Test message",
	timestamp: new Date(),
	...overrides,
});

describe("ChatInspector", () => {
	const defaultProps = {
		messages: [] as ChatMessage[],
		selectedMessage: null as ChatMessage | null | undefined,
		onSelectMessage: vi.fn(),
		chartData: [] as Array<{
			id: string;
			name: number;
			score: number;
			label?: string;
			content?: string;
		}>,
		isOpen: true,
		onClose: vi.fn(),
		method: "llm_separate",
		setMethod: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	describe("Rendering", () => {
		it("renders when isOpen is true", () => {
			render(<ChatInspector {...defaultProps} isOpen={true} />);

			expect(screen.getByText("Sentiment Analysis")).toBeInTheDocument();
		});

		it("does not render when isOpen is false", () => {
			render(<ChatInspector {...defaultProps} isOpen={false} />);

			expect(screen.queryByText("Sentiment Analysis")).not.toBeInTheDocument();
		});

		it("renders close button", () => {
			render(<ChatInspector {...defaultProps} />);

			const closeButton = screen
				.getAllByRole("button")
				.find((btn) => btn.querySelector("svg.lucide-x"));
			expect(closeButton).toBeInTheDocument();
		});

		it("calls onClose when close button is clicked", async () => {
			const onClose = vi.fn();
			render(<ChatInspector {...defaultProps} onClose={onClose} />);

			const closeButton = screen
				.getAllByRole("button")
				.find((btn) => btn.querySelector("svg.lucide-x"));
			closeButton?.click();

			expect(onClose).toHaveBeenCalled();
		});
	});

	describe("Method Selector", () => {
		it("displays the selected method", () => {
			render(<ChatInspector {...defaultProps} method="llm_separate" />);

			expect(screen.getByText("LLM Separate")).toBeInTheDocument();
		});

		it("shows Analysis Method label", () => {
			render(<ChatInspector {...defaultProps} />);

			expect(screen.getByText("Analysis Method")).toBeInTheDocument();
		});
	});

	describe("Overall Sentiment", () => {
		it("shows empty state when no cumulative sentiment", () => {
			render(<ChatInspector {...defaultProps} messages={[]} />);

			// Use getAllByText since there might be multiple empty states
			const elements = screen.getAllByText("No conversation data");
			expect(elements.length).toBeGreaterThan(0);
		});

		it("displays overall sentiment from last message with cumulative sentiment", () => {
			const messagesWithSentiment: ChatMessage[] = [
				createMockMessage({
					id: "msg1",
					role: "user",
					content: "Hello",
					sentiment: { score: 0.5, label: "Positive" },
				}),
				createMockMessage({
					id: "msg2",
					role: "assistant",
					content: "Hi there!",
					cumulativeSentiment: { score: 0.7, label: "Positive" },
				}),
			];

			render(
				<ChatInspector {...defaultProps} messages={messagesWithSentiment} />,
			);

			// Check that cumulative sentiment is displayed
			// The component displays (score * 100).toFixed(0) = "70" without %
			expect(screen.getByText("70")).toBeInTheDocument();
		});
	});

	describe("Session Trend Chart", () => {
		it("shows empty state when no chart data", () => {
			render(<ChatInspector {...defaultProps} chartData={[]} />);

			const elements = screen.getAllByText("No trend data yet");
			expect(elements.length).toBeGreaterThan(0);
		});

		it("renders chart when chart data is available", () => {
			const chartData = [
				{
					id: "msg1",
					name: 1,
					score: 0.5,
					label: "Positive",
					content: "Hello",
				},
				{
					id: "msg2",
					name: 2,
					score: -0.3,
					label: "Negative",
					content: "Goodbye",
				},
			];

			render(<ChatInspector {...defaultProps} chartData={chartData} />);

			const charts = screen.getAllByTestId("area-chart");
			expect(charts.length).toBeGreaterThan(0);
		});
	});

	describe("Statement Analysis", () => {
		it("shows empty state when no user messages", () => {
			render(<ChatInspector {...defaultProps} messages={[]} />);

			const elements = screen.getAllByText("No messages yet");
			expect(elements.length).toBeGreaterThan(0);
		});

		it("renders user message cards", () => {
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "This is a test message",
					sentiment: { score: 0.5, label: "Positive" },
				}),
			];

			render(<ChatInspector {...defaultProps} messages={messages} />);

			expect(screen.getByText(/This is a test message/)).toBeInTheDocument();
		});

		it("shows sentiment score as percentage", () => {
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "Test",
					sentiment: { score: 0.75, label: "Positive" },
				}),
			];

			render(<ChatInspector {...defaultProps} messages={messages} />);

			expect(screen.getByText("75%")).toBeInTheDocument();
		});

		it('shows "Pending..." for messages without sentiment', () => {
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "Test message",
					sentiment: undefined,
				}),
			];

			render(<ChatInspector {...defaultProps} messages={messages} />);

			expect(screen.getByText("Pending...")).toBeInTheDocument();
		});
	});

	describe("Sentiment Colors", () => {
		it("uses appropriate styling for positive sentiment", () => {
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "Great!",
					sentiment: { score: 0.8, label: "Positive" },
				}),
			];

			render(<ChatInspector {...defaultProps} messages={messages} />);

			// The label should be shown
			expect(screen.getByText("Positive")).toBeInTheDocument();
		});

		it("uses appropriate styling for negative sentiment", () => {
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "Bad!",
					sentiment: { score: -0.8, label: "Negative" },
				}),
			];

			render(<ChatInspector {...defaultProps} messages={messages} />);

			expect(screen.getByText("Negative")).toBeInTheDocument();
		});

		it("uses appropriate styling for neutral sentiment", () => {
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "Okay",
					sentiment: { score: 0, label: "Neutral" },
				}),
			];

			render(<ChatInspector {...defaultProps} messages={messages} />);

			expect(screen.getByText("Neutral")).toBeInTheDocument();
		});
	});

	describe("Section Headers", () => {
		it("displays Overall Sentiment section header", () => {
			render(<ChatInspector {...defaultProps} />);

			expect(screen.getByText("Overall Sentiment")).toBeInTheDocument();
		});

		it("displays Session Trend section header", () => {
			render(<ChatInspector {...defaultProps} />);

			expect(screen.getByText("Session Trend")).toBeInTheDocument();
		});

		it("displays Statement Analysis section header", () => {
			render(<ChatInspector {...defaultProps} />);

			expect(screen.getByText("Statement Analysis")).toBeInTheDocument();
		});
	});

	describe("Message Card Interaction", () => {
		it("calls onSelectMessage when clicking a message card", async () => {
			const onSelectMessage = vi.fn();
			const messages: ChatMessage[] = [
				createMockMessage({
					id: "user1",
					role: "user",
					content: "Clickable message",
					sentiment: { score: 0.5, label: "Positive" },
				}),
			];

			render(
				<ChatInspector
					{...defaultProps}
					messages={messages}
					onSelectMessage={onSelectMessage}
				/>,
			);

			// Find the message card and click it
			const messageText = screen.getByText(/Clickable message/);
			const card = messageText.closest('[id^="sidebar-card-"]');
			card?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

			expect(onSelectMessage).toHaveBeenCalledWith("user1");
		});
	});

	describe("Emotion Display", () => {
		it("shows emotion when available in cumulative sentiment", () => {
			const messagesWithEmotion: ChatMessage[] = [
				createMockMessage({
					id: "msg1",
					role: "assistant",
					content: "Response",
					cumulativeSentiment: {
						score: 0.8,
						label: "Positive",
						emotion: "joy",
					},
				}),
			];

			render(
				<ChatInspector {...defaultProps} messages={messagesWithEmotion} />,
			);

			expect(screen.getByText("joy")).toBeInTheDocument();
		});
	});
});
