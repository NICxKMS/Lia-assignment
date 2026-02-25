import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock framer-motion
vi.mock("framer-motion", async () => {
	const actual = await vi.importActual("react");
	const { createElement, forwardRef } = actual as typeof import("react");
	return {
		motion: {
			div: forwardRef(
				(
					props: React.HTMLAttributes<HTMLDivElement> & {
						children?: React.ReactNode;
					},
					ref: React.Ref<HTMLDivElement>,
				) => createElement("div", { ref, ...props }, props.children),
			),
			span: forwardRef(
				(
					props: React.HTMLAttributes<HTMLSpanElement> & {
						children?: React.ReactNode;
					},
					ref: React.Ref<HTMLSpanElement>,
				) => createElement("span", { ref, ...props }, props.children),
			),
		},
		AnimatePresence: ({ children }: { children?: React.ReactNode }) => children,
	};
});

// Mock recharts
vi.mock("recharts", () => ({
	ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
	AreaChart: ({ children }: { children: React.ReactNode }) => (
		<div>{children}</div>
	),
	Area: () => null,
	XAxis: () => null,
	YAxis: () => null,
	Tooltip: () => null,
	ReferenceLine: () => null,
}));

// Mock useChat hook
vi.mock("../lib/useChat", () => ({
	useChat: () => ({
		messages: [],
		status: "idle" as const,
		error: null,
		isStreaming: false,
		sendMessage: vi.fn(),
		setMessages: vi.fn(),
		clearMessages: vi.fn(),
		stop: vi.fn(),
		regenerate: vi.fn(),
	}),
}));

import AuthPage from "../components/AuthPage";
import ChatInterface from "../components/chat/ChatInterface";
// Import components after mocks
import { AuthContext, type AuthContextType } from "../context/AuthContext";

// Mock API
vi.mock("../lib/api", () => ({
	authApi: {
		login: vi.fn(),
		register: vi.fn(),
		me: vi.fn(),
	},
	chatApi: {
		getHistory: vi.fn().mockResolvedValue([]),
		getConversation: vi.fn(),
		send: vi.fn(),
		sendStream: vi.fn(),
		getModels: vi.fn().mockResolvedValue({
			gemini: [
				{
					id: "gemini-2.5-flash",
					name: "Gemini 2.5 Flash",
					provider: "Google",
				},
			],
		}),
		getMethods: vi.fn().mockResolvedValue(["llm_separate", "structured"]),
	},
	api: {
		get: vi.fn(),
		post: vi.fn(),
		interceptors: {
			request: { use: vi.fn() },
			response: { use: vi.fn() },
		},
	},
}));

const createMockAuthContext = (
	overrides?: Partial<AuthContextType>,
): AuthContextType => ({
	user: null,
	isLoading: false,
	isAuthenticated: false,
	login: vi.fn(),
	register: vi.fn(),
	logout: vi.fn(),
	...overrides,
});

const createTestQueryClient = () =>
	new QueryClient({
		defaultOptions: {
			queries: { retry: false, gcTime: 0 },
			mutations: { retry: false },
		},
	});

const renderWithProviders = (
	ui: React.ReactElement,
	authValue?: Partial<AuthContextType>,
) => {
	const queryClient = createTestQueryClient();
	const authContext = createMockAuthContext(authValue);

	return {
		...render(
			<QueryClientProvider client={queryClient}>
				<AuthContext.Provider value={authContext}>{ui}</AuthContext.Provider>
			</QueryClientProvider>,
		),
		authContext,
		queryClient,
	};
};

// Note: App component has its own AuthProvider, so we can't inject mock auth context into it.
// Instead, we test individual components with mock context which is more unit-test like but
// provides better isolation and testability.

describe("Component Integration", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		localStorage.clear();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	describe("AuthPage Component", () => {
		it("renders login form correctly", () => {
			render(
				<AuthContext.Provider value={createMockAuthContext()}>
					<AuthPage />
				</AuthContext.Provider>,
			);

			expect(screen.getByText("Lia Console")).toBeInTheDocument();
			expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
		});
	});

	describe("ChatInterface Component", () => {
		const mockUser = {
			id: 1,
			email: "test@example.com",
			username: "testuser",
			created_at: "2024-01-01T00:00:00Z",
		};

		it("renders chat interface when user is provided", () => {
			renderWithProviders(<ChatInterface />, {
				user: mockUser,
				isAuthenticated: true,
			});

			expect(
				screen.getByPlaceholderText("Send a message..."),
			).toBeInTheDocument();
		});

		it("shows user information", () => {
			renderWithProviders(<ChatInterface />, {
				user: mockUser,
				isAuthenticated: true,
			});

			expect(screen.getByText("testuser")).toBeInTheDocument();
		});
	});
});

describe("AuthPage Integration", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders login form with required fields", () => {
		render(
			<AuthContext.Provider value={createMockAuthContext()}>
				<AuthPage />
			</AuthContext.Provider>,
		);

		expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /sign in/i }),
		).toBeInTheDocument();
	});

	it("allows switching to register mode", async () => {
		const user = userEvent.setup({ delay: null });

		render(
			<AuthContext.Provider value={createMockAuthContext()}>
				<AuthPage />
			</AuthContext.Provider>,
		);

		await user.click(
			screen.getByRole("button", { name: /don't have an account/i }),
		);

		expect(
			screen.getByRole("button", { name: /create account/i }),
		).toBeInTheDocument();
		expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
	});
});

describe("ChatInterface Integration", () => {
	const mockUser = {
		id: 1,
		email: "test@example.com",
		username: "testuser",
		created_at: "2024-01-01T00:00:00Z",
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders all main components", () => {
		renderWithProviders(<ChatInterface />, {
			user: mockUser,
			isAuthenticated: true,
		});

		// Sidebar
		expect(screen.getByText("Conversations")).toBeInTheDocument();

		// Input
		expect(
			screen.getByPlaceholderText("Send a message..."),
		).toBeInTheDocument();

		// Inspector toggle
		const infoButton = document.querySelector(".lucide-info");
		expect(infoButton).toBeInTheDocument();
	});

	it("displays user info in sidebar", () => {
		renderWithProviders(<ChatInterface />, {
			user: mockUser,
			isAuthenticated: true,
		});

		expect(screen.getByText("testuser")).toBeInTheDocument();
	});

	it("shows empty state with suggestions", () => {
		renderWithProviders(<ChatInterface />, {
			user: mockUser,
			isAuthenticated: true,
		});

		expect(screen.getByText("Hello there!")).toBeInTheDocument();
		expect(screen.getByText("How can I help you today?")).toBeInTheDocument();
	});

	it("allows typing in input", async () => {
		const user = userEvent.setup({ delay: null });

		renderWithProviders(<ChatInterface />, {
			user: mockUser,
			isAuthenticated: true,
		});

		const input = screen.getByPlaceholderText(
			"Send a message...",
		) as HTMLTextAreaElement;
		await user.type(input, "Hello AI");

		expect(input.value).toBe("Hello AI");
	});
});
