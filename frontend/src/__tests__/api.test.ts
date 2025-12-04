import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, authApi, chatApi } from '../lib/api'
import type { AuthResponse, ChatResponse, ConversationSummary, ConversationDetail } from '../lib/api'

// Mock axios
vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    defaults: { headers: { common: {} } },
  }
  
  return {
    default: {
      create: () => mockAxiosInstance,
    },
  }
})

// Get the mocked api instance
const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
}

describe('API Module', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('authApi', () => {
    describe('register', () => {
      it('sends registration request with correct payload', async () => {
        const mockResponse: AuthResponse = {
          access_token: 'token123',
          token_type: 'bearer',
          user: {
            id: 1,
            email: 'new@example.com',
            username: 'newuser',
            created_at: '2024-01-01T00:00:00Z',
          },
        }
        
        mockedApi.post.mockResolvedValue({ data: mockResponse })
        
        const result = await authApi.register('new@example.com', 'newuser', 'password123')
        
        expect(mockedApi.post).toHaveBeenCalledWith('/auth/register', {
          email: 'new@example.com',
          username: 'newuser',
          password: 'password123',
        })
        expect(result).toEqual(mockResponse)
      })
    })

    describe('login', () => {
      it('sends login request with correct payload', async () => {
        const mockResponse: AuthResponse = {
          access_token: 'token123',
          token_type: 'bearer',
          user: {
            id: 1,
            email: 'test@example.com',
            username: 'testuser',
            created_at: '2024-01-01T00:00:00Z',
          },
        }
        
        mockedApi.post.mockResolvedValue({ data: mockResponse })
        
        const result = await authApi.login('test@example.com', 'password123')
        
        expect(mockedApi.post).toHaveBeenCalledWith('/auth/login', {
          email: 'test@example.com',
          password: 'password123',
        })
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
        
        mockedApi.get.mockResolvedValue({ data: mockUser })
        
        const result = await authApi.me()
        
        expect(mockedApi.get).toHaveBeenCalledWith('/auth/me')
        expect(result).toEqual(mockUser)
      })
    })
  })

  describe('chatApi', () => {
    describe('send', () => {
      it('sends chat message with default parameters', async () => {
        const mockResponse: ChatResponse = {
          response: 'Hello!',
          conversation_id: 'conv-123',
        }
        
        mockedApi.post.mockResolvedValue({ data: mockResponse })
        
        const result = await chatApi.send('Hello')
        
        expect(mockedApi.post).toHaveBeenCalledWith('/chat', {
          message: 'Hello',
          sentiment_method: 'nlp_api',
          provider: 'gemini',
          model: 'gemini-2.5-flash',
          conversation_id: undefined,
        })
        expect(result).toEqual(mockResponse)
      })

      it('sends chat message with custom parameters', async () => {
        const mockResponse: ChatResponse = {
          response: 'Response',
          conversation_id: 'conv-456',
        }
        
        mockedApi.post.mockResolvedValue({ data: mockResponse })
        
        await chatApi.send('Message', 'llm_separate', 'openai', 'gpt-4', 123)
        
        expect(mockedApi.post).toHaveBeenCalledWith('/chat', {
          message: 'Message',
          sentiment_method: 'llm_separate',
          provider: 'openai',
          model: 'gpt-4',
          conversation_id: 123,
        })
      })

      it('includes sentiment in response when available', async () => {
        const mockResponse: ChatResponse = {
          response: 'Hello!',
          conversation_id: 'conv-123',
          sentiment: {
            message: { score: 0.8, label: 'Positive' },
            cumulative: { score: 0.7, label: 'Positive' },
          },
        }
        
        mockedApi.post.mockResolvedValue({ data: mockResponse })
        
        const result = await chatApi.send('Happy message')
        
        expect(result.sentiment).toBeDefined()
        expect(result.sentiment?.message.label).toBe('Positive')
      })
    })

    describe('getHistory', () => {
      it('fetches conversation history', async () => {
        const mockHistory: ConversationSummary[] = [
          {
            id: '1',
            title: 'Chat 1',
            created_at: '2024-01-01T00:00:00Z',
            message_count: 5,
            last_message: 'Last msg',
          },
        ]
        
        mockedApi.get.mockResolvedValue({ data: mockHistory })
        
        const result = await chatApi.getHistory()
        
        expect(mockedApi.get).toHaveBeenCalledWith('/chat/history')
        expect(result).toEqual(mockHistory)
      })
    })

    describe('getConversation', () => {
      it('fetches conversation details', async () => {
        const mockConversation: ConversationDetail = {
          id: 'conv-123',
          title: 'My Chat',
          created_at: '2024-01-01T00:00:00Z',
          messages: [
            {
              id: 1,
              role: 'user',
              content: 'Hello',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              id: 2,
              role: 'assistant',
              content: 'Hi there!',
              created_at: '2024-01-01T00:00:01Z',
            },
          ],
        }
        
        mockedApi.get.mockResolvedValue({ data: mockConversation })
        
        const result = await chatApi.getConversation('conv-123')
        
        expect(mockedApi.get).toHaveBeenCalledWith('/chat/conversation/conv-123')
        expect(result).toEqual(mockConversation)
      })
    })

    describe('deleteConversation', () => {
      it('deletes a conversation', async () => {
        const mockResponse = { success: true, message: 'Deleted' }
        
        mockedApi.delete.mockResolvedValue({ data: mockResponse })
        
        const result = await chatApi.deleteConversation('conv-123')
        
        expect(mockedApi.delete).toHaveBeenCalledWith('/chat/conversation/conv-123')
        expect(result).toEqual(mockResponse)
      })
    })

    describe('deleteAllConversations', () => {
      it('deletes all conversations', async () => {
        const mockResponse = { success: true, message: 'All deleted', deleted_count: 5 }
        
        mockedApi.delete.mockResolvedValue({ data: mockResponse })
        
        const result = await chatApi.deleteAllConversations()
        
        expect(mockedApi.delete).toHaveBeenCalledWith('/chat/conversations')
        expect(result).toEqual(mockResponse)
      })
    })

    describe('renameConversation', () => {
      it('renames a conversation', async () => {
        const mockResponse = { success: true, message: 'Renamed' }
        
        mockedApi.patch.mockResolvedValue({ data: mockResponse })
        
        const result = await chatApi.renameConversation('conv-123', 'New Title')
        
        expect(mockedApi.patch).toHaveBeenCalledWith(
          '/chat/conversation/conv-123/rename',
          { title: 'New Title' }
        )
        expect(result).toEqual(mockResponse)
      })
    })

    describe('getModels', () => {
      it('fetches available models', async () => {
        const mockModels = {
          gemini: ['gemini-2.5-flash', 'gemini-2.5-pro'],
          openai: ['gpt-4', 'gpt-3.5-turbo'],
        }
        
        mockedApi.get.mockResolvedValue({ data: mockModels })
        
        const result = await chatApi.getModels()
        
        expect(mockedApi.get).toHaveBeenCalledWith('/chat/models')
        expect(result).toEqual(mockModels)
      })
    })

    describe('getMethods', () => {
      it('fetches available sentiment methods', async () => {
        const mockMethods = ['nlp_api', 'llm_separate', 'structured']
        
        mockedApi.get.mockResolvedValue({ data: mockMethods })
        
        const result = await chatApi.getMethods()
        
        expect(mockedApi.get).toHaveBeenCalledWith('/chat/methods')
        expect(result).toEqual(mockMethods)
      })
    })
  })
})

describe('chatApi.sendStream', () => {
  const mockLocalStorage = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  }
  
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('streams chat messages using fetch', async () => {
    const callbacks = {
      onStart: vi.fn(),
      onChunk: vi.fn(),
      onSentiment: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    }
    
    mockLocalStorage.getItem.mockReturnValue('test-token')
    
    const events = [
      'data: {"type":"start","conversation_id":"conv-123"}\n\n',
      'data: {"type":"chunk","content":"Hello"}\n\n',
      'data: {"type":"chunk","content":" World"}\n\n',
      'data: {"type":"sentiment","sentiment":{"message":{"score":0.5,"label":"Neutral"},"cumulative":null}}\n\n',
      'data: {"type":"done"}\n\n',
    ]
    
    let eventIndex = 0
    const mockReader = {
      read: vi.fn().mockImplementation(() => {
        if (eventIndex < events.length) {
          const encoder = new TextEncoder()
          const value = encoder.encode(events[eventIndex])
          eventIndex++
          return Promise.resolve({ done: false, value })
        }
        return Promise.resolve({ done: true, value: undefined })
      }),
      releaseLock: vi.fn(),
    }
    
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => mockReader,
      },
    })
    
    await chatApi.sendStream('Hello', callbacks)
    
    expect(callbacks.onStart).toHaveBeenCalledWith('conv-123')
    expect(callbacks.onChunk).toHaveBeenCalledWith('Hello')
    expect(callbacks.onChunk).toHaveBeenCalledWith(' World')
    expect(callbacks.onSentiment).toHaveBeenCalled()
    expect(callbacks.onDone).toHaveBeenCalled()
    expect(callbacks.onError).not.toHaveBeenCalled()
  })

  it('handles HTTP errors', async () => {
    mockLocalStorage.getItem.mockReturnValue('test-token')
    
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    })
    
    await expect(
      chatApi.sendStream('Hello', {})
    ).rejects.toThrow('HTTP error! status: 500')
  })

  it('handles missing response body', async () => {
    mockLocalStorage.getItem.mockReturnValue('test-token')
    
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: null,
    })
    
    await expect(
      chatApi.sendStream('Hello', {})
    ).rejects.toThrow('No response body')
  })

  it('calls onError for error events', async () => {
    const onError = vi.fn()
    mockLocalStorage.getItem.mockReturnValue('test-token')
    
    const events = [
      'data: {"type":"error","error":"Server error"}\n\n',
    ]
    
    let eventIndex = 0
    const mockReader = {
      read: vi.fn().mockImplementation(() => {
        if (eventIndex < events.length) {
          const encoder = new TextEncoder()
          const value = encoder.encode(events[eventIndex])
          eventIndex++
          return Promise.resolve({ done: false, value })
        }
        return Promise.resolve({ done: true, value: undefined })
      }),
      releaseLock: vi.fn(),
    }
    
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => mockReader,
      },
    })
    
    await chatApi.sendStream('Hello', { onError })
    
    expect(onError).toHaveBeenCalledWith('Server error')
  })

  it('ensures onDone is called even if server does not send done event', async () => {
    const onDone = vi.fn()
    mockLocalStorage.getItem.mockReturnValue('test-token')
    
    const events = [
      'data: {"type":"chunk","content":"Hello"}\n\n',
    ]
    
    let eventIndex = 0
    const mockReader = {
      read: vi.fn().mockImplementation(() => {
        if (eventIndex < events.length) {
          const encoder = new TextEncoder()
          const value = encoder.encode(events[eventIndex])
          eventIndex++
          return Promise.resolve({ done: false, value })
        }
        return Promise.resolve({ done: true, value: undefined })
      }),
      releaseLock: vi.fn(),
    }
    
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => mockReader,
      },
    })
    
    await chatApi.sendStream('Hello', { onDone })
    
    expect(onDone).toHaveBeenCalled()
  })
})
