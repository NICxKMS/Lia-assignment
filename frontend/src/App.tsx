import { lazy, Suspense } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './context'

// Lazy load heavy components
const ChatInterface = lazy(() => import('./components/chat/ChatInterface'))
const AuthPage = lazy(() => import('./components/AuthPage'))

// Loading fallback component
const LoadingFallback = () => (
  <div className="h-screen w-full bg-bg-primary flex items-center justify-center">
    <div className="animate-pulse text-text-secondary">Loading...</div>
  </div>
)

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
})

function AuthenticatedApp() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="h-screen w-full bg-bg-primary flex items-center justify-center">
        <div className="animate-pulse text-text-secondary">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <Suspense fallback={<LoadingFallback />}>
        <AuthPage />
      </Suspense>
    )
  }

  return (
    <div className="h-screen w-full bg-bg-primary flex overflow-hidden selection:bg-accent selection:text-white">
      <Suspense fallback={<LoadingFallback />}>
        <ChatInterface />
      </Suspense>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthenticatedApp />
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
