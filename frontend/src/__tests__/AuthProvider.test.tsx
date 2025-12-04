import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import React from 'react'
import { AuthProvider } from '../context/AuthProvider'
import { useAuth } from '../context/useAuth'
import { AuthContext } from '../context/AuthContext'
import * as api from '../lib/api'

// Mock the api module
vi.mock('../lib/api', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
  },
}))

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
    get store() {
      return store
    },
    set store(newStore: Record<string, string>) {
      store = newStore
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
)

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.clear()
    localStorageMock.store = {}
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('provides initial unauthenticated state', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
    })

    it('validates stored token on mount', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        username: 'testuser',
        created_at: '2024-01-01T00:00:00Z',
      }
      
      localStorageMock.setItem('token', 'valid-token')
      vi.mocked(api.authApi.me).mockResolvedValue(mockUser)
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      expect(result.current.user).toEqual(mockUser)
      expect(result.current.token).toBe('valid-token')
      expect(result.current.isAuthenticated).toBe(true)
    })

    it('clears invalid token on mount', async () => {
      localStorageMock.setItem('token', 'invalid-token')
      vi.mocked(api.authApi.me).mockRejectedValue(new Error('Invalid token'))
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('token')
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user')
    })
  })

  describe('Login', () => {
    it('logs in successfully and updates state', async () => {
      const mockResponse = {
        access_token: 'new-token',
        token_type: 'bearer',
        user: {
          id: 1,
          email: 'test@example.com',
          username: 'testuser',
          created_at: '2024-01-01T00:00:00Z',
        },
      }
      
      vi.mocked(api.authApi.login).mockResolvedValue(mockResponse)
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      await act(async () => {
        await result.current.login('test@example.com', 'password123')
      })
      
      expect(api.authApi.login).toHaveBeenCalledWith('test@example.com', 'password123')
      expect(result.current.user).toEqual(mockResponse.user)
      expect(result.current.token).toBe('new-token')
      expect(result.current.isAuthenticated).toBe(true)
      expect(localStorageMock.setItem).toHaveBeenCalledWith('token', 'new-token')
    })

    it('throws error on login failure', async () => {
      const error = new Error('Invalid credentials')
      vi.mocked(api.authApi.login).mockRejectedValue(error)
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      await expect(
        act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      ).rejects.toThrow('Invalid credentials')
      
      expect(result.current.user).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
    })
  })

  describe('Register', () => {
    it('registers successfully and updates state', async () => {
      const mockResponse = {
        access_token: 'new-token',
        token_type: 'bearer',
        user: {
          id: 2,
          email: 'new@example.com',
          username: 'newuser',
          created_at: '2024-01-01T00:00:00Z',
        },
      }
      
      vi.mocked(api.authApi.register).mockResolvedValue(mockResponse)
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      await act(async () => {
        await result.current.register('new@example.com', 'newuser', 'password123')
      })
      
      expect(api.authApi.register).toHaveBeenCalledWith('new@example.com', 'newuser', 'password123')
      expect(result.current.user).toEqual(mockResponse.user)
      expect(result.current.token).toBe('new-token')
      expect(result.current.isAuthenticated).toBe(true)
    })

    it('throws error on register failure', async () => {
      const error = new Error('Email already exists')
      vi.mocked(api.authApi.register).mockRejectedValue(error)
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
      
      await expect(
        act(async () => {
          await result.current.register('existing@example.com', 'existinguser', 'password123')
        })
      ).rejects.toThrow('Email already exists')
      
      expect(result.current.user).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
    })
  })

  describe('Logout', () => {
    it('logs out and clears state', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        username: 'testuser',
        created_at: '2024-01-01T00:00:00Z',
      }
      
      localStorageMock.setItem('token', 'valid-token')
      vi.mocked(api.authApi.me).mockResolvedValue(mockUser)
      
      const { result } = renderHook(() => useAuth(), { wrapper })
      
      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })
      
      act(() => {
        result.current.logout()
      })
      
      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('token')
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user')
    })
  })
})

describe('useAuth Hook', () => {
  it('throws error when used outside AuthProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    
    expect(() => {
      renderHook(() => useAuth())
    }).toThrow('useAuth must be used within an AuthProvider')
    
    consoleSpy.mockRestore()
  })

  it('returns context when used within AuthProvider', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    
    expect(result.current).toHaveProperty('user')
    expect(result.current).toHaveProperty('token')
    expect(result.current).toHaveProperty('isLoading')
    expect(result.current).toHaveProperty('isAuthenticated')
    expect(result.current).toHaveProperty('login')
    expect(result.current).toHaveProperty('register')
    expect(result.current).toHaveProperty('logout')
  })
})

describe('AuthContext', () => {
  it('has undefined as default value', () => {
    const { result } = renderHook(() => React.useContext(AuthContext))
    expect(result.current).toBeUndefined()
  })
})
