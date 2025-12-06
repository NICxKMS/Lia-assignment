import { useCallback, useRef, useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { chatApi } from './api'
import type { SentimentResult, ConversationDetail as ApiConversationDetail } from './api'
import type { ChatMessage as BaseChatMessage } from './useChat'
import { toast } from 'sonner'

const PAGE_SIZE = 50

// Query key factories for consistent cache management
export const queryKeys = {
  history: (userId: number | undefined) => ['history', userId] as const,
  conversation: (conversationId: string, offset = 0, limit = PAGE_SIZE) =>
    ['conversation', conversationId, offset, limit] as const,
  models: ['models'] as const,
}

export interface ConversationMeta {
  hasMore: boolean
  total: number
  offset: number
  limit: number
}

export interface UseConversationManagementOptions {
  user: { id: number } | null
  setChatMessages: React.Dispatch<React.SetStateAction<BaseChatMessage[]>>
  chatMessages: BaseChatMessage[]
  clearMessages: () => void
  setIsSidebarOpen?: (open: boolean) => void
}

export function useConversationManagement({
  user,
  setChatMessages,
  chatMessages,
  clearMessages,
  setIsSidebarOpen,
}: UseConversationManagementOptions) {
  const queryClient = useQueryClient()
  const [conversationId, setConversationId] = useState<string>()
  const [conversationMeta, setConversationMeta] = useState<ConversationMeta | null>(null)
  const [isLoadingConversation, setIsLoadingConversation] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)

  // Refs for stable callbacks
  const conversationIdRef = useRef(conversationId)
  useEffect(() => { conversationIdRef.current = conversationId }, [conversationId])

  // Load conversation with caching
  const loadConversation = useCallback(async (convId: string) => {
    setIsLoadingConversation(true)
    try {
      // Use queryClient to leverage cache - check if already cached
      const cachedData = queryClient.getQueryData<ApiConversationDetail>(
        queryKeys.conversation(convId, 0, PAGE_SIZE)
      )
      
      // Fetch with cache support
      const conv = cachedData ?? await queryClient.fetchQuery({
        queryKey: queryKeys.conversation(convId, 0, PAGE_SIZE),
        queryFn: () => chatApi.getConversation(convId, { limit: PAGE_SIZE, offset: 0 }),
        staleTime: 60 * 1000, // Consider fresh for 1 minute
      })
      
      if (!conv) {
        toast.error('Failed to load conversation')
        return
      }
      
      const loadedMessages: BaseChatMessage[] = conv.messages.map(msg => {
        const sentimentData = msg.sentiment_data as { 
          message?: SentimentResult
          cumulative?: SentimentResult | null 
        } | undefined
        
        // Extract thoughts from model_info for assistant messages
        const thoughts = msg.role === 'assistant' && msg.model_info?.thoughts
          ? msg.model_info.thoughts
          : undefined
        
        return {
          id: msg.id.toString(),
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          thoughts,
          timestamp: new Date(msg.created_at),
          sentiment: sentimentData?.message,
          cumulativeSentiment: sentimentData?.cumulative ?? undefined,
        }
      })

      setChatMessages(loadedMessages)
      setConversationId(convId)
      setConversationMeta({
        hasMore: conv.has_more,
        total: conv.total_messages,
        offset: conv.offset + conv.messages.length,
        limit: conv.limit,
      })
      setSelectedMessageId(loadedMessages.length > 0 ? loadedMessages[loadedMessages.length - 1].id : null)
      
      if (window.innerWidth < 768) setIsSidebarOpen?.(false)
    } catch (error) {
      toast.error('Error loading conversation')
      console.error('Error loading conversation:', error)
    } finally {
      setIsLoadingConversation(false)
    }
  }, [setChatMessages, queryClient, setIsSidebarOpen])

  // New conversation
  const startNewConversation = useCallback(() => {
    clearMessages()
    setConversationId(undefined)
    setConversationMeta(null)
    setSelectedMessageId(null)
    if (window.innerWidth < 768) setIsSidebarOpen?.(false)
  }, [clearMessages, setIsSidebarOpen])

  // Delete conversation
  const deleteConversation = useCallback(async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    
    try {
      await chatApi.deleteConversation(convId)
      if (conversationId === convId) startNewConversation()
      // Invalidate both history and the specific conversation cache
      queryClient.invalidateQueries({ queryKey: queryKeys.history(user?.id) })
      queryClient.removeQueries({ queryKey: ['conversation', convId] })
      toast.success('Conversation deleted')
    } catch (error) {
      toast.error('Failed to delete conversation')
      console.error('Error deleting:', error)
    }
  }, [conversationId, startNewConversation, queryClient, user?.id])

  // Delete all
  const deleteAllConversations = useCallback(async () => {
    if (!confirm('Delete ALL conversations?')) return
    
    try {
      await chatApi.deleteAllConversations()
      startNewConversation()
      // Invalidate history and remove all conversation caches
      queryClient.invalidateQueries({ queryKey: queryKeys.history(user?.id) })
      queryClient.removeQueries({ queryKey: ['conversation'] }) // Remove all conversation caches
      toast.success('All conversations deleted')
    } catch (error) {
      toast.error('Failed to delete all conversations')
      console.error('Error deleting all:', error)
    }
  }, [startNewConversation, queryClient, user?.id])

  // Load more messages
  const loadMoreMessages = useCallback(async () => {
    if (!conversationIdRef.current) return
    setIsLoadingMore(true)
    try {
      const nextOffset = chatMessages.length
      const conv = await chatApi.getConversation(conversationIdRef.current, {
        limit: PAGE_SIZE,
        offset: nextOffset,
      })

      const loadedMessages: BaseChatMessage[] = conv.messages.map(msg => {
        const sentimentData = msg.sentiment_data as { 
          message?: SentimentResult
          cumulative?: SentimentResult | null 
        } | undefined
        
        // Extract thoughts from model_info for assistant messages
        const thoughts = msg.role === 'assistant' && msg.model_info?.thoughts
          ? msg.model_info.thoughts
          : undefined
        
        return {
          id: msg.id.toString(),
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          thoughts,
          timestamp: new Date(msg.created_at),
          sentiment: sentimentData?.message,
          cumulativeSentiment: sentimentData?.cumulative ?? undefined,
        }
      })

      setChatMessages(prev => {
        const existing = new Set(prev.map(m => m.id))
        const merged = [...prev]
        loadedMessages.forEach(m => {
          if (!existing.has(m.id)) merged.push(m)
        })
        return merged
      })

      setConversationMeta({
        hasMore: conv.has_more,
        total: conv.total_messages,
        offset: conv.offset + conv.messages.length,
        limit: conv.limit,
      })
    } catch (error) {
      toast.error('Error loading more messages')
      console.error('Error loading more messages:', error)
    } finally {
      setIsLoadingMore(false)
    }
  }, [chatMessages.length, setChatMessages])

  return {
    // State
    conversationId,
    setConversationId,
    conversationMeta,
    isLoadingConversation,
    isLoadingMore,
    selectedMessageId,
    setSelectedMessageId,
    conversationIdRef,
    // Actions
    loadConversation,
    startNewConversation,
    deleteConversation,
    deleteAllConversations,
    loadMoreMessages,
  }
}
