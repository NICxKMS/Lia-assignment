import type React from "react";
import { useCallback, useEffect, useState } from "react";
import type { User } from "../lib/api";
import { authApi } from "../lib/api";
import { AuthContext } from "./AuthContext";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
	children,
}) => {
	const [user, setUser] = useState<User | null>(null);
	const [isLoading, setIsLoading] = useState(true);

	// Validate stored auth on mount
	useEffect(() => {
		const validateAuth = async () => {
			const storedUser = localStorage.getItem("user");

			try {
				// Try to validate via cookie (sent automatically with credentials: 'include')
				const userData = await authApi.me();
				if (userData) {
					setUser(userData);
					localStorage.setItem("user", JSON.stringify(userData));
				}
			} catch (error) {
				// Only clear on explicit 401 Unauthorized
				const is401 = error instanceof Response && error.status === 401;

				if (is401) {
					// Cookie is invalid or missing, clear local user data
					localStorage.removeItem("user");
				} else if (storedUser) {
					// Transient error - keep cached user for display
					try {
						const cachedUser = JSON.parse(storedUser) as User;
						setUser(cachedUser);
					} catch {
						localStorage.removeItem("user");
					}
				}
			}
			setIsLoading(false);
		};

		validateAuth();
	}, []);

	const login = useCallback(async (email: string, password: string) => {
		const response = await authApi.login(email, password);

		localStorage.setItem("user", JSON.stringify(response.user));

		setUser(response.user);
	}, []);

	const register = useCallback(
		async (email: string, username: string, password: string) => {
			const response = await authApi.register(email, username, password);

			localStorage.setItem("user", JSON.stringify(response.user));

			setUser(response.user);
		},
		[],
	);

	const logout = useCallback(async () => {
		try {
			await authApi.logout();
		} catch {
			// Even if the API call fails, clear local state
		}
		localStorage.removeItem("user");
		setUser(null);
	}, []);

	const value = {
		user,
		isLoading,
		isAuthenticated: !!user,
		login,
		register,
		logout,
	};

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
