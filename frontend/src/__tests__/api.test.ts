import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { authApi, chatApi } from '../lib/api'
import type { ConversationSummary, ConversationDetail } from '../lib/api'

// Mock global fetch
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

describe('API Module', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Set token for authenticated requests
    localStorage.setItem('token', 'test-token')
  })

  afterEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('authApi', () => {
    describe('login', () => {
      it('sends login request and returns auth response', async () => {
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
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockResponse),
        })
        
        const result = await authApi.login('test@example.com', 'password123')
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/auth/login'),
          expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
              email: 'test@example.com',
              password: 'password123',
            }),
          })
        )
        expect(result).toEqual(mockResponse)
      })

      it('handles login error', async () => {
        const errorResponse = {
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Invalid credentials' }),
        }
        mockFetch.mockResolvedValueOnce(errorResponse)
        
        await expect(authApi.login('test@example.com', 'wrongpassword'))
          .rejects.toMatchObject({ ok: false, status: 401 })
      })
    })

    describe('register', () => {
      it('sends registration request', async () => {
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
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockResponse),
        })
        
        const result = await authApi.register('new@example.com', 'newuser', 'password123')
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/auth/register'),
          expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
              email: 'new@example.com',
              username: 'newuser',
              password: 'password123',
            }),
          })
        )
        expect(result).toEqual(mockResponse)
      })
    })

    describe('me', () => {
      it('fetches current user', async () => {
        const mockUser = {
          id: 1,
          email: 'test@example.com',
          username: 'testuser',
          created_at: '2024-01-01T00:00:00Z',
        }
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockUser),
        })
        
        const result = await authApi.me()
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/auth/me'),
          expect.anything()
        )
        expect(result).toEqual(mockUser)
      })
    })
  })

  describe('chatApi', () => {
    describe('getHistory', () => {
      it('fetches conversation history', async () => {
        const mockHistory: ConversationSummary[] = [
          {
            id: '1',
            title: 'Chat 1',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            message_count: 5,
          },
        ]
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockHistory),
        })
        
        const result = await chatApi.getHistory()
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/chat/history'),
          expect.anything()
        )
        expect(result).toEqual(mockHistory)
      })
    })

    describe('getConversation', () => {
      it('fetches conversation details', async () => {
        const mockConversation: ConversationDetail = {
          id: 'conv-123',
          title: 'My Chat',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          messages: [],
          total_messages: 0,
          has_more: false,
          limit: 50,
          offset: 0,
        }
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockConversation),
        })
        
        const result = await chatApi.getConversation('conv-123')
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/chat/conversation/conv-123'),
          expect.anything()
        )
        expect(result).toEqual(mockConversation)
      })

      it('fetches conversation with pagination params', async () => {
        const mockConversation: ConversationDetail = {
          id: 'conv-123',
          title: 'My Chat',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          messages: [],
          total_messages: 100,
          has_more: true,
          limit: 20,
          offset: 40,
        }
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockConversation),
        })
        
        await chatApi.getConversation('conv-123', { limit: 20, offset: 40 })
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringMatching(/\/chat\/conversation\/conv-123\?limit=20&offset=40/),
          expect.anything()
        )
      })
    })

    describe('deleteConversation', () => {
      it('deletes a conversation', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ success: true, message: 'Deleted' }),
        })
        
        await chatApi.deleteConversation('conv-123')
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/chat/conversation/conv-123'),
          expect.objectContaining({
            method: 'DELETE',
          })
        )
      })
    })

    describe('deleteAllConversations', () => {
      it('deletes all conversations', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ success: true, message: 'Deleted', deleted_count: 5 }),
        })
        
        await chatApi.deleteAllConversations()
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringMatching(/\/chat\/conversations$/),
          expect.objectContaining({
            method: 'DELETE',
          })
        )
      })
    })

    describe('getModels', () => {
      it('fetches available models', async () => {
        const mockModels = {
          gemini: [
            { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
          ],
        }
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockModels),
        })
        
        const result = await chatApi.getModels()
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/chat/models'),
          expect.anything()
        )
        expect(result).toEqual(mockModels)
      })
    })

    describe('getMethods', () => {
      it('fetches sentiment methods', async () => {
        const mockMethods = ['nlp_api', 'llm_separate', 'llm_combined']
        
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockMethods),
        })
        
        const result = await chatApi.getMethods()
        
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/chat/methods'),
          expect.anything()
        )
        expect(result).toEqual(mockMethods)
      })
    })
  })

  describe('Error Handling', () => {
    it('handles network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))
      
      await expect(chatApi.getHistory()).rejects.toThrow('Network error')
    })

    it('handles API errors by throwing response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request' }),
      })
      
      await expect(chatApi.getHistory()).rejects.toMatchObject({ ok: false, status: 400 })
    })

    it('handles 401 unauthorized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
      
      await expect(chatApi.getHistory()).rejects.toMatchObject({ ok: false, status: 401 })
    })
  })
})
