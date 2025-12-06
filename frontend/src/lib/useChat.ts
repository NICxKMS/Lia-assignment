/**
 * useChat - A robust, optimized chat hook for SSE streaming
 * 
 * Features:
 * - Clean SSE (Server-Sent Events) parsing
 * - Proper state management with React best practices
 * - AbortController for request cancellation
 * - Automatic reconnection handling
 * - Type-safe events
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { SentimentResult } from './api'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ============ Types ============

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  thoughts?: string[]  // Model thinking process (for assistant messages)
  sentiment?: SentimentResult
  cumulativeSentiment?: SentimentResult
  timestamp: Date
  isStreaming?: boolean
}

export type ChatStatus = 'idle' | 'connecting' | 'streaming' | 'error'

export interface UseChatOptions {
  /** Called when a message is fully received */
  onFinish?: (message: ChatMessage) => void
  /** Called when an error occurs */
  onError?: (error: Error) => void
  /** Called when conversation ID changes (new conversation created) */
  onConversationIdChange?: (id: string) => void
}

export interface ModelSettings {
  temperature: number
  maxTokens: number
  topP: number
  frequencyPenalty: number
  presencePenalty: number
}

export interface SendMessageOptions {
  token: string | null
  method: string
  provider: string
  model: string
  conversationId?: string
  modelSettings?: ModelSettings
}

// ============ SSE Event Types ============

interface SSEStartEvent {
  conversation_id: string
  message_id: string
}

interface SSEChunkEvent {
  content: string
}

interface SSEThoughtEvent {
  content: string
}

interface SSESentimentEvent {
  message: SentimentResult | null
  cumulative: SentimentResult | null
}

interface SSEErrorEvent {
  message: string
}

// ============ SSE Parser ============

function parseSSEEvent(eventStr: string): { event: string; data: unknown } | null {
  const lines = eventStr.split('\n')
  let eventType = ''
  let dataStr = ''
  
  for (const line of lines) {
    if (line.startsWith('event: ')) {
      eventType = line.slice(7).trim()
    } else if (line.startsWith('data: ')) {
      dataStr = line.slice(6)
    }
  }
  
  if (!eventType || !dataStr) return null
  
  try {
    return { event: eventType, data: JSON.parse(dataStr) }
  } catch {
    return null
  }
}

// ============ Hook ============

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<Error | null>(null)
  
  // Refs for stable references
  const abortControllerRef = useRef<AbortController | null>(null)
  const optionsRef = useRef(options)
  const messagesRef = useRef(messages)
  
  // Keep refs updated
  useEffect(() => {
    optionsRef.current = options
  }, [options])
  
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  // Generate unique message ID
  const generateId = useCallback(() => {
    return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
  }, [])

  // Stop current streaming
  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setStatus('idle')
  }, [])

  // Send a message
  const sendMessage = useCallback(async (content: string, opts: SendMessageOptions) => {
    const trimmedContent = content.trim()
    if (!trimmedContent) return

    // Abort any existing request
    stop()
    
    setError(null)
    setStatus('connecting')

    // Create user message
    const userMessageId = generateId()
    const userMessage: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: trimmedContent,
      timestamp: new Date(),
    }

    // Create assistant message placeholder
    const assistantId = generateId()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      thoughts: [],  // Track thinking content
      timestamp: new Date(),
      isStreaming: true,
    }

    // Add messages to state
    setMessages(prev => [...prev, userMessage, assistantMessage])

    // Create abort controller
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...(opts.token ? { 'Authorization': `Bearer ${opts.token}` } : {}),
        },
        body: JSON.stringify({
          message: trimmedContent,
          sentiment_method: opts.method,
          provider: opts.provider,
          model: opts.model,
          conversation_id: opts.conversationId,
          model_settings: opts.modelSettings ? {
            temperature: opts.modelSettings.temperature,
            max_tokens: opts.modelSettings.maxTokens,
            top_p: opts.modelSettings.topP,
            frequency_penalty: opts.modelSettings.frequencyPenalty,
            presence_penalty: opts.modelSettings.presencePenalty,
          } : undefined,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body available')
      }

      setStatus('streaming')

      const decoder = new TextDecoder()
      let buffer = ''
      let accumulatedContent = ''
      const accumulatedThoughts: string[] = []  // Track thinking content
      let sentiment: SSESentimentEvent | null = null

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          
          // SSE events are separated by double newlines
          const events = buffer.split('\n\n')
          buffer = events.pop() || '' // Keep incomplete event in buffer

          for (const eventStr of events) {
            if (!eventStr.trim()) continue

            const parsed = parseSSEEvent(eventStr)
            if (!parsed) continue

            switch (parsed.event) {
              case 'start': {
                const data = parsed.data as SSEStartEvent
                if (data.conversation_id) {
                  optionsRef.current.onConversationIdChange?.(data.conversation_id)
                }
                break
              }

              case 'chunk': {
                const data = parsed.data as SSEChunkEvent
                if (data.content) {
                  accumulatedContent += data.content
                  // Update assistant message
                  setMessages(prev => prev.map(msg => 
                    msg.id === assistantId 
                      ? { ...msg, content: accumulatedContent }
                      : msg
                  ))
                }
                break
              }

              case 'thought': {
                const data = parsed.data as SSEThoughtEvent
                if (data.content) {
                  accumulatedThoughts.push(data.content)
                  // Update assistant message with thoughts
                  setMessages(prev => prev.map(msg => 
                    msg.id === assistantId 
                      ? { ...msg, thoughts: [...accumulatedThoughts] }
                      : msg
                  ))
                }
                break
              }

              case 'sentiment': {
                sentiment = parsed.data as SSESentimentEvent
                break
              }

              case 'done': {
                // Stream complete
                break
              }

              case 'error': {
                const data = parsed.data as SSEErrorEvent
                throw new Error(data.message || 'Unknown error')
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }

      // Finalize messages
      const finalAssistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: accumulatedContent,
        thoughts: accumulatedThoughts.length > 0 ? accumulatedThoughts : undefined,
        timestamp: new Date(),
        isStreaming: false,
      }

      setMessages(prev => prev.map(msg => {
        // Update user message with sentiment
        if (msg.id === userMessageId && sentiment) {
          return {
            ...msg,
            sentiment: sentiment.message ?? undefined,
            cumulativeSentiment: sentiment.cumulative ?? undefined,
          }
        }
        // Finalize assistant message
        if (msg.id === assistantId) {
          return finalAssistantMessage
        }
        return msg
      }))

      setStatus('idle')
      optionsRef.current.onFinish?.(finalAssistantMessage)

    } catch (err) {
      // Handle abort
      if (err instanceof Error && err.name === 'AbortError') {
        setStatus('idle')
        return
      }

      const error = err instanceof Error ? err : new Error(String(err))
      console.error('[useChat] Error:', error)
      setError(error)
      setStatus('error')
      optionsRef.current.onError?.(error)

      // Remove empty assistant message on error
      setMessages(prev => prev.filter(msg => 
        !(msg.id === assistantId && msg.content === '')
      ))
    } finally {
      abortControllerRef.current = null
    }
  }, [generateId, stop])

  // Regenerate last response - now uses ref for messages
  const regenerate = useCallback(async (opts: SendMessageOptions) => {
    // Find the last user message using ref
    const currentMessages = messagesRef.current
    let lastUserMessage: ChatMessage | undefined
    for (let i = currentMessages.length - 1; i >= 0; i--) {
      if (currentMessages[i].role === 'user') {
        lastUserMessage = currentMessages[i]
        break
      }
    }
    
    if (!lastUserMessage) return

    // Remove the last assistant message and the user message
    setMessages(prev => {
      const newMessages = [...prev]
      
      // Remove last assistant message if exists
      if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
        newMessages.pop()
      }
      
      // Remove last user message
      if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'user') {
        newMessages.pop()
      }
      
      return newMessages
    })

    // Resend
    await sendMessage(lastUserMessage.content, opts)
  }, [sendMessage])

  // Clear all messages
  const clearMessages = useCallback(() => {
    stop()
    setMessages([])
    setError(null)
    setStatus('idle')
  }, [stop])

  return {
    messages,
    status,
    error,
    isStreaming: status === 'streaming' || status === 'connecting',
    sendMessage,
    setMessages,
    clearMessages,
    stop,
    regenerate,
  }
}

export type UseChatReturn = ReturnType<typeof useChat>
