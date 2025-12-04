import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't clear tokens on 401 - let the AuthContext handle auth state
    // This prevents race conditions during login
    return Promise.reject(error)
  }
)

// Auth API
export interface User {
  id: number
  email: string
  username: string
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export const authApi = {
  register: async (email: string, username: string, password: string): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/register', { email, username, password })
    return res.data
  },
  
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/login', { email, password })
    return res.data
  },
  
  me: async (): Promise<User> => {
    const res = await api.get<User>('/auth/me')
    return res.data
  },
}

// Chat API
export interface SentimentResult {
  score: number
  label: string
  emotion?: string  // Short description of exact emotion
  source?: string
  details?: Record<string, unknown>
}

export interface DualSentiment {
  message: SentimentResult  // Sentiment of the current user message
  cumulative: SentimentResult | null  // Sentiment of conversation so far
}

export interface ChatResponse {
  response: string
  sentiment?: DualSentiment  // Dual sentiment (message + cumulative)
  conversation_id: string
}

export interface ConversationSummary {
  id: string
  title: string | null
  created_at: string
  message_count: number
  last_message: string | null
}

export interface ConversationMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sentiment_data?: SentimentResult
  created_at: string
}

export interface ConversationDetail {
  id: string
  title: string | null
  created_at: string
  messages: ConversationMessage[]
}

// SSE Event types for streaming
export interface StreamStartEvent {
  type: 'start'
  conversation_id: string
}

export interface StreamChunkEvent {
  type: 'chunk'
  content: string
}

export interface StreamSentimentEvent {
  type: 'sentiment'
  sentiment: DualSentiment | null
}

export interface StreamDoneEvent {
  type: 'done'
}

export interface StreamErrorEvent {
  type: 'error'
  error: string
}

export type StreamEvent = StreamStartEvent | StreamChunkEvent | StreamSentimentEvent | StreamDoneEvent | StreamErrorEvent

export interface StreamCallbacks {
  onStart?: (conversationId: string) => void
  onChunk?: (content: string) => void
  onSentiment?: (sentiment: DualSentiment | null) => void
  onDone?: () => void
  onError?: (error: string) => void
}

export const chatApi = {
  send: async (
    message: string,
    sentimentMethod: string = 'nlp_api',
    provider: string = 'gemini',
    model: string = 'gemini-2.5-flash',
    conversationId?: number
  ): Promise<ChatResponse> => {
    const res = await api.post<ChatResponse>('/chat', {
      message,
      sentiment_method: sentimentMethod,
      provider,
      model,
      conversation_id: conversationId,
    })
    return res.data
  },
  
  // Streaming chat using Server-Sent Events
  sendStream: async (
    message: string,
    callbacks: StreamCallbacks,
    sentimentMethod: string = 'nlp_api',
    provider: string = 'gemini',
    model: string = 'gemini-2.5-flash',
    conversationId?: number
  ): Promise<void> => {
    const token = localStorage.getItem('token')
    
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({
        message,
        sentiment_method: sentimentMethod,
        provider,
        model,
        conversation_id: conversationId,
      }),
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }
    
    const decoder = new TextDecoder()
    let buffer = ''
    let receivedDone = false
    
    const processLine = (line: string) => {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6)) as StreamEvent
          
          switch (data.type) {
            case 'start':
              callbacks.onStart?.(data.conversation_id)
              break
            case 'chunk':
              callbacks.onChunk?.(data.content)
              break
            case 'sentiment':
              callbacks.onSentiment?.(data.sentiment)
              break
            case 'done':
              receivedDone = true
              callbacks.onDone?.()
              break
            case 'error':
              callbacks.onError?.(data.error)
              break
          }
        } catch {
          // Ignore JSON parse errors
        }
      }
    }
    
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        
        // Process complete SSE events
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer
        
        for (const line of lines) {
          processLine(line)
        }
      }
      
      // Process any remaining data in buffer
      if (buffer.trim()) {
        processLine(buffer)
      }
      
      // Ensure onDone is called even if server didn't send done event
      if (!receivedDone) {
        callbacks.onDone?.()
      }
    } finally {
      reader.releaseLock()
    }
  },
  
  getHistory: async (): Promise<ConversationSummary[]> => {
    const res = await api.get<ConversationSummary[]>('/chat/history')
    return res.data
  },
  
  getConversation: async (conversationId: string): Promise<ConversationDetail> => {
    const res = await api.get<ConversationDetail>(`/chat/conversation/${conversationId}`)
    return res.data
  },
  
  deleteConversation: async (conversationId: string): Promise<{ success: boolean; message: string }> => {
    const res = await api.delete<{ success: boolean; message: string }>(`/chat/conversation/${conversationId}`)
    return res.data
  },
  
  deleteAllConversations: async (): Promise<{ success: boolean; message: string; deleted_count?: number }> => {
    const res = await api.delete<{ success: boolean; message: string; deleted_count?: number }>('/chat/conversations')
    return res.data
  },
  
  renameConversation: async (conversationId: string, title: string): Promise<{ success: boolean; message: string }> => {
    const res = await api.patch<{ success: boolean; message: string }>(`/chat/conversation/${conversationId}/rename`, { title })
    return res.data
  },
  
  getModels: async (): Promise<Record<string, string[]>> => {
    const res = await api.get<Record<string, string[]>>('/chat/models')
    return res.data
  },
  
  getMethods: async (): Promise<string[]> => {
    const res = await api.get<string[]>('/chat/methods')
    return res.data
  },
}
