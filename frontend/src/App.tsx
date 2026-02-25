import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { lazy, Suspense } from "react";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "./context";

// Lazy load heavy components
const ChatInterface = lazy(() => import("./components/chat/ChatInterface"));
const AuthPage = lazy(() => import("./components/AuthPage"));

// Loading fallback component
const LoadingFallback = () => (
	<div className="h-screen w-full bg-bg-primary flex items-center justify-center">
		<div className="animate-pulse text-text-secondary">Loading...</div>
	</div>
);

// Singleton QueryClient with optimized defaults
const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			staleTime: 1000 * 60 * 5, // 5 minutes
			gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
			refetchOnWindowFocus: false,
			retry: 1,
		},
	},
});

// Error boundary to catch render crashes
class ErrorBoundary extends React.Component<
	{ children: React.ReactNode },
	{ hasError: boolean; error?: Error }
> {
	state = { hasError: false, error: undefined as Error | undefined };

	static getDerivedStateFromError(error: Error) {
		return { hasError: true, error };
	}

	componentDidCatch(error: Error, info: React.ErrorInfo) {
		console.error("App crash:", error, info);
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="flex items-center justify-center h-screen">
					<div className="text-center p-8">
						<h1 className="text-2xl font-bold mb-4">Something went wrong</h1>
						<p className="text-muted-foreground mb-4">
							{this.state.error?.message}
						</p>
						<button
							onClick={() => {
								this.setState({ hasError: false });
								window.location.reload();
							}}
							className="px-4 py-2 bg-primary text-primary-foreground rounded"
						>
							Reload App
						</button>
					</div>
				</div>
			);
		}
		return this.props.children;
	}
}

function AuthenticatedApp() {
	const { user, isLoading } = useAuth();

	if (isLoading) {
		return (
			<div className="h-screen w-full bg-bg-primary flex items-center justify-center">
				<div className="animate-pulse text-text-secondary">Loading...</div>
			</div>
		);
	}

	if (!user) {
		return (
			<Suspense fallback={<LoadingFallback />}>
				<AuthPage />
			</Suspense>
		);
	}

	return (
		<div className="h-screen w-full bg-bg-primary flex overflow-hidden selection:bg-accent selection:text-white">
			<Suspense fallback={<LoadingFallback />}>
				<ChatInterface />
			</Suspense>
		</div>
	);
}

function App() {
	return (
		<QueryClientProvider client={queryClient}>
			<AuthProvider>
				<Toaster
					position="top-right"
					toastOptions={{
						style: {
							background: "var(--color-bg-secondary, #18181b)",
							color: "var(--color-text-primary, #fafafa)",
							border: "1px solid var(--color-border-subtle, #27272a)",
						},
					}}
				/>
				<ErrorBoundary>
					<AuthenticatedApp />
				</ErrorBoundary>
			</AuthProvider>
		</QueryClientProvider>
	);
}

export default App;
