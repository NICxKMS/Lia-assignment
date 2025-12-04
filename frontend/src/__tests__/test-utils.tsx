import React from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthContext, type AuthContextType } from '../context/AuthContext'
import { vi } from 'vitest'
import type { User } from '../lib/api'

// Default mock user
export const mockUser: User = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  created_at: '2024-01-01T00:00:00Z',
}

// Default mock auth context
export const createMockAuthContext = (overrides?: Partial<AuthContextType>): AuthContextType => ({
  user: null,
  token: null,
  isLoading: false,
  isAuthenticated: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  ...overrides,
})

// Create a fresh query client for each test
export const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })

// Props for the test wrapper
interface TestProvidersProps {
  children: React.ReactNode
  authValue?: Partial<AuthContextType>
  queryClient?: QueryClient
}

// Wrapper component with all providers
export const TestProviders: React.FC<TestProvidersProps> = ({
  children,
  authValue,
  queryClient = createTestQueryClient(),
}) => {
  const authContext = createMockAuthContext(authValue)
  
  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={authContext}>
        {children}
      </AuthContext.Provider>
    </QueryClientProvider>
  )
}

// Custom render function
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  authValue?: Partial<AuthContextType>
  queryClient?: QueryClient
}

export const renderWithProviders = (
  ui: React.ReactElement,
  options: CustomRenderOptions = {}
) => {
  const { authValue, queryClient = createTestQueryClient(), ...renderOptions } = options
  
  const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <TestProviders authValue={authValue} queryClient={queryClient}>
      {children}
    </TestProviders>
  )
  
  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  }
}

// Mock localStorage
export const mockLocalStorage = () => {
  const store: Record<string, string> = {}
  
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      Object.keys(store).forEach((key) => delete store[key])
    }),
    store,
  }
}

// Mock fetch for streaming
export const createMockFetch = (events: Array<{ event: string; data: unknown }>) => {
  return vi.fn().mockResolvedValue({
    ok: true,
    body: {
      getReader: () => {
        let index = 0
        const encoder = new TextEncoder()
        
        return {
          read: vi.fn().mockImplementation(() => {
            if (index < events.length) {
              const event = events[index]
              index++
              const sseString = `event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`
              return Promise.resolve({
                done: false,
                value: encoder.encode(sseString),
              })
            }
            return Promise.resolve({ done: true, value: undefined })
          }),
          releaseLock: vi.fn(),
        }
      },
    },
  })
}

// Wait for all promises to resolve
export const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0))

// Create mock message
export const createMockMessage = (overrides?: Partial<{
  id: string
  role: 'user' | 'assistant'
  content: string
  sentiment?: { score: number; label: string; emotion?: string }
  cumulativeSentiment?: { score: number; label: string }
  timestamp: Date
  isStreaming?: boolean
}>) => ({
  id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
  role: 'user' as const,
  content: 'Test message',
  timestamp: new Date(),
  ...overrides,
})

// Export everything from testing library
export * from '@testing-library/react'
export { vi } from 'vitest'
