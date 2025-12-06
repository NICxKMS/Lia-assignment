import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat, type ChatMessage, type SendMessageOptions } from '../lib/useChat'

// Mock fetch
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

// Helper to create SSE response
const createSSEResponse = (events: Array<{ event: string; data: unknown }>) => {
  let index = 0
  const encoder = new TextEncoder()
  
  return {
    ok: true,
    body: {
      getReader: () => ({
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
      }),
    },
  }
}

const defaultOptions: SendMessageOptions = {
  token: 'test-token',
  method: 'llm_separate',
  provider: 'gemini',
  model: 'gemini-2.5-flash',
}

describe('useChat Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('returns initial state correctly', () => {
      const { result } = renderHook(() => useChat())
      
      expect(result.current.messages).toEqual([])
      expect(result.current.status).toBe('idle')
      expect(result.current.error).toBeNull()
      expect(result.current.isStreaming).toBe(false)
    })

    it('provides all required functions', () => {
      const { result } = renderHook(() => useChat())
      
      expect(typeof result.current.sendMessage).toBe('function')
      expect(typeof result.current.setMessages).toBe('function')
      expect(typeof result.current.clearMessages).toBe('function')
      expect(typeof result.current.stop).toBe('function')
      expect(typeof result.current.regenerate).toBe('function')
    })
  })

  describe('sendMessage', () => {
    it('sends message and receives streamed response', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123', message_id: 'msg-123' } },
        { event: 'chunk', data: { content: 'Hello' } },
        { event: 'chunk', data: { content: ' World' } },
        { event: 'sentiment', data: { message: { score: 0.8, label: 'Positive' }, cumulative: null } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const onFinish = vi.fn()
      const onConversationIdChange = vi.fn()
      
      const { result } = renderHook(() =>
        useChat({ onFinish, onConversationIdChange })
      )
      
      await act(async () => {
        await result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      expect(result.current.messages).toHaveLength(2)
      expect(result.current.messages[0].role).toBe('user')
      expect(result.current.messages[0].content).toBe('Hello')
      expect(result.current.messages[1].role).toBe('assistant')
      expect(result.current.messages[1].content).toBe('Hello World')
      
      expect(onConversationIdChange).toHaveBeenCalledWith('conv-123')
      expect(onFinish).toHaveBeenCalled()
    })

    it('does not send empty messages', async () => {
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('   ', defaultOptions)
      })
      
      expect(mockFetch).not.toHaveBeenCalled()
      expect(result.current.messages).toHaveLength(0)
    })

    it('trims message content before sending', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'chunk', data: { content: 'Response' } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('  Hello  ', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      expect(result.current.messages[0].content).toBe('Hello')
    })

    it('handles HTTP errors', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        text: vi.fn().mockResolvedValue('Not authorized'),
      })
      
      const onError = vi.fn()
      const { result } = renderHook(() => useChat({ onError }))
      
      await act(async () => {
        await result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('error')
      })
      
      expect(result.current.error).toBeInstanceOf(Error)
      expect(onError).toHaveBeenCalled()
    })

    it('handles SSE error events', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'error', data: { message: 'Server error' } },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const onError = vi.fn()
      const { result } = renderHook(() => useChat({ onError }))
      
      await act(async () => {
        await result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('error')
      })
      
      expect(result.current.error?.message).toBe('Server error')
    })

    it('updates sentiment on user message', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'chunk', data: { content: 'Response' } },
        { event: 'sentiment', data: { 
          message: { score: 0.9, label: 'Positive', emotion: 'happy' }, 
          cumulative: { score: 0.7, label: 'Positive' } 
        }},
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Great!', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      const userMessage = result.current.messages.find(m => m.role === 'user')
      expect(userMessage?.sentiment).toEqual({ score: 0.9, label: 'Positive', emotion: 'happy' })
      expect(userMessage?.cumulativeSentiment).toEqual({ score: 0.7, label: 'Positive' })
    })

    it('sends correct headers with token', async () => {
      mockFetch.mockResolvedValue(createSSEResponse([
        { event: 'done', data: {} },
      ]))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hello', {
          ...defaultOptions,
          token: 'my-auth-token',
        })
      })
      
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer my-auth-token',
          }),
        })
      )
    })

    it('sends without auth header when no token', async () => {
      mockFetch.mockResolvedValue(createSSEResponse([
        { event: 'done', data: {} },
      ]))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hello', {
          ...defaultOptions,
          token: null,
        })
      })
      
      const call = mockFetch.mock.calls[0]
      expect(call[1].headers).not.toHaveProperty('Authorization')
    })
  })

  describe('stop', () => {
    it('aborts ongoing request', async () => {
      // Create a response that waits
      let resolveRead: () => void
      const waitPromise = new Promise<void>(resolve => {
        resolveRead = resolve
      })
      
      mockFetch.mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn().mockImplementation(async () => {
              await waitPromise
              return { done: true, value: undefined }
            }),
            releaseLock: vi.fn(),
          }),
        },
      })
      
      const { result } = renderHook(() => useChat())
      
      // Start sending (don't await)
      act(() => {
        result.current.sendMessage('Hello', defaultOptions)
      })
      
      // Wait for streaming to start
      await waitFor(() => {
        expect(result.current.status).toBe('streaming')
      })
      
      // Stop
      act(() => {
        result.current.stop()
      })
      
      expect(result.current.status).toBe('idle')
      
      // Clean up
      resolveRead!()
    })
  })

  describe('clearMessages', () => {
    it('clears all messages', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'chunk', data: { content: 'Hello' } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hi', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.messages.length).toBeGreaterThan(0)
      })
      
      act(() => {
        result.current.clearMessages()
      })
      
      expect(result.current.messages).toEqual([])
      expect(result.current.error).toBeNull()
      expect(result.current.status).toBe('idle')
    })
  })

  describe('setMessages', () => {
    it('allows setting messages directly', () => {
      const { result } = renderHook(() => useChat())
      
      const newMessages: ChatMessage[] = [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Hello',
          timestamp: new Date(),
        },
        {
          id: 'msg-2',
          role: 'assistant',
          content: 'Hi there!',
          timestamp: new Date(),
        },
      ]
      
      act(() => {
        result.current.setMessages(newMessages)
      })
      
      expect(result.current.messages).toEqual(newMessages)
    })
  })

  describe('regenerate', () => {
    it('regenerates last assistant response', async () => {
      // First message
      mockFetch.mockResolvedValueOnce(createSSEResponse([
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'chunk', data: { content: 'First response' } },
        { event: 'done', data: {} },
      ]))
      
      // Regenerated message
      mockFetch.mockResolvedValueOnce(createSSEResponse([
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'chunk', data: { content: 'Second response' } },
        { event: 'done', data: {} },
      ]))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.messages.length).toBe(2)
      })
      
      await act(async () => {
        await result.current.regenerate(defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      expect(result.current.messages).toHaveLength(2)
      expect(result.current.messages[1].content).toBe('Second response')
    })

    it('does nothing when no user messages exist', async () => {
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.regenerate(defaultOptions)
      })
      
      expect(mockFetch).not.toHaveBeenCalled()
    })
  })

  describe('isStreaming', () => {
    it('returns true when streaming', async () => {
      let resolveRead: () => void
      const waitPromise = new Promise<void>(resolve => {
        resolveRead = resolve
      })
      
      mockFetch.mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn().mockImplementation(async () => {
              await waitPromise
              return { done: true, value: undefined }
            }),
            releaseLock: vi.fn(),
          }),
        },
      })
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        void result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.isStreaming).toBe(true)
      })
      
      resolveRead!()
    })

    it('returns false when idle', () => {
      const { result } = renderHook(() => useChat())
      expect(result.current.isStreaming).toBe(false)
    })
  })

  describe('Conversation ID', () => {
    it('includes conversation ID in subsequent requests', async () => {
      mockFetch.mockResolvedValue(createSSEResponse([
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'done', data: {} },
      ]))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hello', {
          ...defaultOptions,
          conversationId: 'existing-conv-id',
        })
      })
      
      const call = mockFetch.mock.calls[0]
      const body = JSON.parse(call[1].body)
      expect(body.conversation_id).toBe('existing-conv-id')
    })
  })

  describe('Error Recovery', () => {
    it('removes empty assistant message on error', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('error')
      })
      
      // Should have user message but no empty assistant message
      const assistantMessages = result.current.messages.filter(m => m.role === 'assistant')
      expect(assistantMessages.every(m => m.content !== '')).toBe(true)
    })
  })

  describe('Thinking/Thought Events', () => {
    it('accumulates thought events into assistant message', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'thought', data: { content: 'Step 1: Parse the question' } },
        { event: 'thought', data: { content: 'Step 2: Calculate result' } },
        { event: 'chunk', data: { content: 'The answer is 42.' } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('What is 6 times 7?', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      const assistantMessage = result.current.messages.find(m => m.role === 'assistant')
      expect(assistantMessage).toBeDefined()
      expect(assistantMessage?.thoughts).toEqual([
        'Step 1: Parse the question',
        'Step 2: Calculate result',
      ])
      expect(assistantMessage?.content).toBe('The answer is 42.')
    })

    it('handles no thought events gracefully', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'chunk', data: { content: 'Direct response' } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Hello', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      const assistantMessage = result.current.messages.find(m => m.role === 'assistant')
      expect(assistantMessage?.content).toBe('Direct response')
      // thoughts should be undefined when empty
      expect(assistantMessage?.thoughts).toBeUndefined()
    })

    it('updates thoughts array during streaming', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'thought', data: { content: 'First thought' } },
        { event: 'thought', data: { content: 'Second thought' } },
        { event: 'chunk', data: { content: 'Response' } },
        { event: 'done', data: {} },
      ]
      
      let eventIndex = 0
      const encoder = new TextEncoder()
      
      mockFetch.mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn().mockImplementation(() => {
              if (eventIndex < events.length) {
                const event = events[eventIndex]
                eventIndex++
                const sseString = `event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`
                return Promise.resolve({
                  done: false,
                  value: encoder.encode(sseString),
                })
              }
              return Promise.resolve({ done: true, value: undefined })
            }),
            releaseLock: vi.fn(),
          }),
        },
      })
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Test', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      // Final state should have both thoughts
      const assistantMessage = result.current.messages.find(m => m.role === 'assistant')
      expect(assistantMessage?.thoughts).toHaveLength(2)
    })

    it('preserves thoughts in final message', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'thought', data: { content: 'Analyzing...' } },
        { event: 'chunk', data: { content: 'Result' } },
        { event: 'sentiment', data: { message: { score: 0.8, label: 'Positive' }, cumulative: null } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const onFinish = vi.fn()
      const { result } = renderHook(() => useChat({ onFinish }))
      
      await act(async () => {
        await result.current.sendMessage('Test', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      // Final message in state should have thoughts
      const finalMessage = result.current.messages.find(m => m.role === 'assistant')
      expect(finalMessage?.thoughts).toEqual(['Analyzing...'])
      expect(finalMessage?.isStreaming).toBe(false)
    })

    it('handles interleaved thought and chunk events', async () => {
      const events = [
        { event: 'start', data: { conversation_id: 'conv-123' } },
        { event: 'thought', data: { content: 'Thinking part 1' } },
        { event: 'chunk', data: { content: 'Response ' } },
        { event: 'thought', data: { content: 'Thinking part 2' } },
        { event: 'chunk', data: { content: 'continues.' } },
        { event: 'done', data: {} },
      ]
      
      mockFetch.mockResolvedValue(createSSEResponse(events))
      
      const { result } = renderHook(() => useChat())
      
      await act(async () => {
        await result.current.sendMessage('Test', defaultOptions)
      })
      
      await waitFor(() => {
        expect(result.current.status).toBe('idle')
      })
      
      const assistantMessage = result.current.messages.find(m => m.role === 'assistant')
      expect(assistantMessage?.thoughts).toEqual(['Thinking part 1', 'Thinking part 2'])
      expect(assistantMessage?.content).toBe('Response continues.')
    })
  })
})
