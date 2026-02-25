import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock framer-motion - must be before component import
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

import AuthPage from "../components/AuthPage";
import { AuthContext, type AuthContextType } from "../context/AuthContext";

// Fast helper to fill input - uses fireEvent.change instead of userEvent.type for speed
const fillInput = (element: Element, value: string) => {
	fireEvent.change(element, { target: { value } });
};

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

const renderWithAuth = (
	authValue?: Partial<AuthContextType>,
	onSuccess?: () => void,
) => {
	const authContext = createMockAuthContext(authValue);

	return {
		...render(
			<AuthContext.Provider value={authContext}>
				<AuthPage onSuccess={onSuccess} />
			</AuthContext.Provider>,
		),
		authContext,
	};
};

describe("AuthPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	describe("Rendering", () => {
		it("renders the login form by default", () => {
			renderWithAuth();

			expect(screen.getByText("Welcome back")).toBeInTheDocument();
			expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
			expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /sign in/i }),
			).toBeInTheDocument();
		});

		it("renders the logo and branding", () => {
			renderWithAuth();

			expect(screen.getByText("Lia Console")).toBeInTheDocument();
			expect(screen.getByText(/AI-Powered Analytics/i)).toBeInTheDocument();
		});

		it("renders email input with correct attributes", () => {
			renderWithAuth();

			const emailInput = screen.getByLabelText(/email/i);
			expect(emailInput).toHaveAttribute("type", "email");
			expect(emailInput).toHaveAttribute("placeholder", "you@example.com");
			expect(emailInput).toBeRequired();
		});

		it("renders password input with correct attributes", () => {
			renderWithAuth();

			const passwordInput = screen.getByLabelText(/password/i);
			expect(passwordInput).toHaveAttribute("type", "password");
			expect(passwordInput).toBeRequired();
		});

		it("renders terms of service notice", () => {
			renderWithAuth();

			expect(
				screen.getByText(/By continuing, you agree to our Terms of Service/i),
			).toBeInTheDocument();
		});
	});

	describe("Form Toggle", () => {
		it("switches to register form when clicking sign up link", async () => {
			const user = userEvent.setup({ delay: null });
			renderWithAuth();

			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			// Multiple due to framer-motion animation - title and button both have 'Create account'
			const createAccountElements = screen.getAllByText("Create account");
			expect(createAccountElements.length).toBeGreaterThan(0);
			expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
		});

		it("switches back to login form when clicking sign in link", async () => {
			const user = userEvent.setup({ delay: null });
			renderWithAuth();

			// Switch to register
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			// Switch back to login
			const signInButton = screen.getByRole("button", {
				name: /already have an account\?/i,
			});
			await user.click(signInButton);

			expect(screen.getByText("Welcome back")).toBeInTheDocument();
			expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument();
		});

		it("clears error when switching between login and register", async () => {
			const user = userEvent.setup({ delay: null });
			const mockLogin = vi
				.fn()
				.mockRejectedValue(new Error("Invalid credentials"));
			renderWithAuth({ login: mockLogin });

			// Trigger an error - use fast fillInput since we don't test typing behavior here
			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "wrongpassword");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
			});

			// Switch forms - error should be cleared
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			expect(screen.queryByText("Invalid credentials")).not.toBeInTheDocument();
		});
	});

	describe("Login Form Submission", () => {
		it("calls login with email and password", async () => {
			const user = userEvent.setup({ delay: null });
			const mockLogin = vi.fn().mockResolvedValue(undefined);
			const { authContext } = renderWithAuth({ login: mockLogin });

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(authContext.login).toHaveBeenCalledWith(
					"test@example.com",
					"password123",
				);
			});
		});

		it("shows loading state during login", async () => {
			const user = userEvent.setup({ delay: null });
			const mockLogin = vi
				.fn()
				.mockImplementation(
					() => new Promise((resolve) => setTimeout(resolve, 100)),
				);
			renderWithAuth({ login: mockLogin });

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			// Button should be disabled and show loading
			const submitButton = screen.getByRole("button", { name: "" });
			expect(submitButton).toBeDisabled();
		});

		it("displays error message on login failure", async () => {
			const user = userEvent.setup({ delay: null });
			const mockLogin = vi
				.fn()
				.mockRejectedValue(new Error("Invalid credentials"));
			renderWithAuth({ login: mockLogin });

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "wrongpassword");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
			});
		});

		it("handles API error response", async () => {
			const user = userEvent.setup({ delay: null });
			// Create a mock Response object with error body
			const errorResponse = new Response(
				JSON.stringify({ detail: "User not found" }),
				{ status: 404, statusText: "Not Found" },
			);
			const mockLogin = vi.fn().mockRejectedValue(errorResponse);
			renderWithAuth({ login: mockLogin });

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(screen.getByText("User not found")).toBeInTheDocument();
			});
		});

		it("calls onSuccess callback after successful login", async () => {
			const user = userEvent.setup({ delay: null });
			const mockLogin = vi.fn().mockResolvedValue(undefined);
			const onSuccess = vi.fn();
			renderWithAuth({ login: mockLogin }, onSuccess);

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(onSuccess).toHaveBeenCalled();
			});
		});
	});

	describe("Register Form Submission", () => {
		it("shows username field only in register mode", async () => {
			const user = userEvent.setup({ delay: null });
			renderWithAuth();

			expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument();

			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
		});

		it("calls register with email, username, and password", async () => {
			const user = userEvent.setup({ delay: null });
			const mockRegister = vi.fn().mockResolvedValue(undefined);
			const { authContext } = renderWithAuth({ register: mockRegister });

			// Switch to register mode
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			fillInput(screen.getByLabelText(/email/i), "new@example.com");
			fillInput(screen.getByLabelText(/username/i), "newuser");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /create account/i }));

			await waitFor(() => {
				expect(authContext.register).toHaveBeenCalledWith(
					"new@example.com",
					"newuser",
					"password123",
				);
			});
		});

		it("validates username length - too short", async () => {
			const user = userEvent.setup({ delay: null });
			const mockRegister = vi.fn();
			renderWithAuth({ register: mockRegister });

			// Switch to register mode
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			fillInput(screen.getByLabelText(/email/i), "new@example.com");
			fillInput(screen.getByLabelText(/username/i), "ab");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /create account/i }));

			await waitFor(() => {
				expect(
					screen.getByText("Username must be at least 3 characters"),
				).toBeInTheDocument();
			});
			expect(mockRegister).not.toHaveBeenCalled();
		});

		it("validates password length - too short", async () => {
			const user = userEvent.setup({ delay: null });
			const mockRegister = vi.fn();
			renderWithAuth({ register: mockRegister });

			// Switch to register mode
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			fillInput(screen.getByLabelText(/email/i), "new@example.com");
			fillInput(screen.getByLabelText(/username/i), "newuser");
			fillInput(screen.getByLabelText(/password/i), "short");
			await user.click(screen.getByRole("button", { name: /create account/i }));

			await waitFor(() => {
				expect(
					screen.getByText("Password must be at least 8 characters"),
				).toBeInTheDocument();
			});
			expect(mockRegister).not.toHaveBeenCalled();
		});

		it("displays error message on register failure", async () => {
			const user = userEvent.setup({ delay: null });
			const mockRegister = vi
				.fn()
				.mockRejectedValue(new Error("Email already exists"));
			renderWithAuth({ register: mockRegister });

			// Switch to register mode
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			fillInput(screen.getByLabelText(/email/i), "existing@example.com");
			fillInput(screen.getByLabelText(/username/i), "existinguser");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /create account/i }));

			await waitFor(() => {
				expect(screen.getByText("Email already exists")).toBeInTheDocument();
			});
		});
	});

	describe("Input Handling", () => {
		it("updates email field value", async () => {
			renderWithAuth();

			const emailInput = screen.getByLabelText(/email/i);
			fillInput(emailInput, "test@example.com");

			expect(emailInput).toHaveValue("test@example.com");
		});

		it("updates password field value", async () => {
			renderWithAuth();

			const passwordInput = screen.getByLabelText(/password/i);
			fillInput(passwordInput, "mypassword");

			expect(passwordInput).toHaveValue("mypassword");
		});

		it("updates username field value in register mode", async () => {
			const user = userEvent.setup({ delay: null });
			renderWithAuth();

			// Switch to register mode
			const signUpButton = screen.getByRole("button", {
				name: /don't have an account\?/i,
			});
			await user.click(signUpButton);

			const usernameInput = screen.getByLabelText(/username/i);
			fillInput(usernameInput, "myusername");

			expect(usernameInput).toHaveValue("myusername");
		});

		it("prevents default form submission and handles it", async () => {
			const mockLogin = vi.fn().mockResolvedValue(undefined);
			renderWithAuth({ login: mockLogin });

			const form = screen.getByLabelText(/email/i).closest("form");
			expect(form).toBeInTheDocument();

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");

			// Submit via Enter key
			fireEvent.submit(form!);

			await waitFor(() => {
				expect(mockLogin).toHaveBeenCalled();
			});
		});
	});

	describe("Error Handling", () => {
		it("displays generic error for unknown error types", async () => {
			const user = userEvent.setup({ delay: null });
			const mockLogin = vi.fn().mockRejectedValue("Unknown error");
			renderWithAuth({ login: mockLogin });

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(
					screen.getByText("An unexpected error occurred."),
				).toBeInTheDocument();
			});
		});

		it("displays fallback error for axios error without detail", async () => {
			const user = userEvent.setup({ delay: null });
			const axiosError = { response: { data: {} } };
			const mockLogin = vi.fn().mockRejectedValue(axiosError);
			renderWithAuth({ login: mockLogin });

			fillInput(screen.getByLabelText(/email/i), "test@example.com");
			fillInput(screen.getByLabelText(/password/i), "password123");
			await user.click(screen.getByRole("button", { name: /sign in/i }));

			await waitFor(() => {
				expect(
					screen.getByText("An unexpected error occurred."),
				).toBeInTheDocument();
			});
		});
	});
});
