// NOTE (framer-motion): Complex usage — AnimatePresence mode='wait' for
// sequential transitions, layout animations, spring physics. Keep as-is.
import { AnimatePresence, motion } from "framer-motion";
import {
	ArrowRight,
	Bot,
	Loader2,
	Lock,
	Mail,
	Sparkles,
	User,
} from "lucide-react";
import type React from "react";
import { memo, useCallback, useRef, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "../context";
import { extractApiError } from "../lib/api";

interface AuthPageProps {
	onSuccess?: () => void;
}

const AuthPage = memo<AuthPageProps>(({ onSuccess }) => {
	const [isLogin, setIsLogin] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(false);

	// Use refs for input values to avoid re-renders on each keystroke
	const emailRef = useRef("");
	const usernameRef = useRef("");
	const passwordRef = useRef("");

	// Local state for controlled inputs - only updates locally
	const [localEmail, setLocalEmail] = useState("");
	const [localUsername, setLocalUsername] = useState("");
	const [localPassword, setLocalPassword] = useState("");

	const { login, register } = useAuth();

	// Stable submit handler using refs
	const handleSubmit = useCallback(
		async (e: React.FormEvent) => {
			e.preventDefault();
			setError(null);
			setIsLoading(true);

			const email = emailRef.current;
			const username = usernameRef.current;
			const password = passwordRef.current;

			try {
				if (isLogin) {
					await login(email, password);
				} else {
					if (username.length < 3) {
						throw new Error("Username must be at least 3 characters");
					}
					if (password.length < 8) {
						throw new Error("Password must be at least 8 characters");
					}
					await register(email, username, password);
				}
				onSuccess?.();
			} catch (err: unknown) {
				const errorMessage = await extractApiError(err);
				setError(errorMessage);
			} finally {
				setIsLoading(false);
			}
		},
		[isLogin, login, register, onSuccess],
	);

	const handleEmailChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			emailRef.current = e.target.value;
			setLocalEmail(e.target.value);
		},
		[],
	);

	const handleUsernameChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			usernameRef.current = e.target.value;
			setLocalUsername(e.target.value);
		},
		[],
	);

	const handlePasswordChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			passwordRef.current = e.target.value;
			setLocalPassword(e.target.value);
		},
		[],
	);

	const toggleAuthMode = useCallback(() => {
		setIsLogin((prev) => !prev);
		setError(null);
	}, []);

	return (
		<div className="min-h-screen w-full bg-bg-primary flex items-center justify-center p-4 relative overflow-hidden">
			{/* Background Effects */}
			<div className="absolute inset-0 overflow-hidden pointer-events-none">
				<div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[100px]" />
				<div className="absolute top-[40%] -right-[10%] w-[40%] h-[40%] rounded-full bg-accent/10 blur-[100px]" />
				<div className="absolute -bottom-[10%] left-[20%] w-[30%] h-[30%] rounded-full bg-purple-500/10 blur-[100px]" />
			</div>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="w-full max-w-md relative z-10"
			>
				{/* Logo */}
				<div className="flex flex-col items-center justify-center gap-4 mb-8">
					<motion.div
						initial={{ scale: 0.8, opacity: 0 }}
						animate={{ scale: 1, opacity: 1 }}
						transition={{ delay: 0.2, type: "spring" }}
						className="w-16 h-16 bg-gradient-to-br from-primary to-accent rounded-2xl flex items-center justify-center shadow-xl shadow-primary/20 ring-1 ring-white/10"
					>
						<Bot className="w-9 h-9 text-white" />
					</motion.div>
					<div className="text-center">
						<h1 className="text-3xl font-bold text-foreground tracking-tight">
							Lia Console
						</h1>
						<p className="text-muted-foreground mt-1 flex items-center justify-center gap-2">
							<Sparkles className="w-3 h-3 text-accent" />
							AI-Powered Analytics
						</p>
					</div>
				</div>

				{/* Card */}
				<Card className="border-border/50 bg-card/50 backdrop-blur-xl shadow-2xl">
					<CardHeader className="text-center pb-2">
						<CardTitle className="text-xl">
							<AnimatePresence mode="wait">
								<motion.span
									key={isLogin ? "login" : "register"}
									initial={{ opacity: 0, y: 10 }}
									animate={{ opacity: 1, y: 0 }}
									exit={{ opacity: 0, y: -10 }}
									transition={{ duration: 0.2 }}
								>
									{isLogin ? "Welcome back" : "Create account"}
								</motion.span>
							</AnimatePresence>
						</CardTitle>
						<CardDescription>
							{isLogin
								? "Sign in to continue to Lia"
								: "Sign up to get started with Lia"}
						</CardDescription>
					</CardHeader>

					<CardContent>
						<AnimatePresence mode="wait">
							{error && (
								<motion.div
									initial={{ opacity: 0, height: 0 }}
									animate={{ opacity: 1, height: "auto" }}
									exit={{ opacity: 0, height: 0 }}
									className="overflow-hidden mb-4"
								>
									<Alert variant="destructive">
										<AlertDescription>{error}</AlertDescription>
									</Alert>
								</motion.div>
							)}
						</AnimatePresence>

						<form onSubmit={handleSubmit} className="space-y-4">
							<div className="space-y-2">
								<Label htmlFor="email">Email</Label>
								<div className="relative group">
									<Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
									<Input
										id="email"
										type="email"
										value={localEmail}
										onChange={handleEmailChange}
										placeholder="you@example.com"
										required
										className="pl-10 bg-background/50 border-border/50 focus:bg-background transition-all"
									/>
								</div>
							</div>

							<AnimatePresence mode="popLayout">
								{!isLogin && (
									<motion.div
										initial={{ opacity: 0, height: 0 }}
										animate={{ opacity: 1, height: "auto" }}
										exit={{ opacity: 0, height: 0 }}
										className="overflow-hidden"
									>
										<div className="space-y-2 pb-4">
											<Label htmlFor="username">Username</Label>
											<div className="relative group">
												<User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
												<Input
													id="username"
													type="text"
													value={localUsername}
													onChange={handleUsernameChange}
													placeholder="johndoe"
													required={!isLogin}
													minLength={3}
													maxLength={50}
													className="pl-10 bg-background/50 border-border/50 focus:bg-background transition-all"
												/>
											</div>
										</div>
									</motion.div>
								)}
							</AnimatePresence>

							<div className="space-y-2">
								<Label htmlFor="password">Password</Label>
								<div className="relative group">
									<Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
									<Input
										id="password"
										type="password"
										value={localPassword}
										onChange={handlePasswordChange}
										placeholder={isLogin ? "••••••••" : "Min. 8 characters"}
										required
										minLength={8}
										className="pl-10 bg-background/50 border-border/50 focus:bg-background transition-all"
									/>
								</div>
							</div>

							<Button
								type="submit"
								disabled={isLoading}
								className="w-full gap-2 mt-6 bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 transition-all shadow-lg shadow-primary/20"
							>
								{isLoading ? (
									<Loader2 className="w-4 h-4 animate-spin" />
								) : (
									<>
										{isLogin ? "Sign in" : "Create account"}
										<ArrowRight className="w-4 h-4" />
									</>
								)}
							</Button>
						</form>
					</CardContent>

					<CardFooter className="justify-center pb-6">
						<Button
							variant="link"
							onClick={toggleAuthMode}
							className="text-muted-foreground hover:text-foreground transition-colors"
						>
							{isLogin
								? "Don't have an account? "
								: "Already have an account? "}
							<span className="text-primary font-medium ml-1 underline decoration-primary/30 underline-offset-4 hover:decoration-primary transition-all">
								{isLogin ? "Sign up" : "Sign in"}
							</span>
						</Button>
					</CardFooter>
				</Card>

				<p className="text-muted-foreground/60 text-xs text-center mt-8">
					By continuing, you agree to our Terms of Service and Privacy Policy.
				</p>
			</motion.div>
		</div>
	);
});

AuthPage.displayName = "AuthPage";

export default AuthPage;
