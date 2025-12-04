import React, { useState, useRef, useEffect, useCallback, useMemo, memo, lazy, Suspense } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Menu, Info, Sparkles } from 'lucide-react'
import { chatApi } from '../../lib/api'
import type { SentimentResult, ConversationDetail as ApiConversationDetail } from '../../lib/api'
import { useAuth } from '../../context'
import { useChat, type ChatMessage as BaseChatMessage } from '../../lib/useChat'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { motion, AnimatePresence } from 'framer-motion'

import ChatSidebar from './ChatSidebar'
import MessageList from './MessageList'
import ChatInput from './ChatInput'

// Lazy load the heavy ChatInspector component (includes recharts)
const ChatInspector = lazy(() => import('./ChatInspector'))

// Query key factories for consistent cache management
// Note: 'methods' key is defined but fetched on-demand in ChatInspector
const queryKeys = {
  history: (userId: number | undefined) => ['history', userId] as const,
  conversation: (conversationId: string) => ['conversation', conversationId] as const,
  models: ['models'] as const,
}

// Inspector loading fallback
const InspectorFallback = () => (
  <div className="w-80 h-full bg-secondary/50 border-l border-border animate-pulse" />
)

// ============ Types ============

export interface MessagePart {
  type: 'text' | 'reasoning' | 'source-url' | 'file'
  text?: string
  url?: string
  title?: string
  mediaType?: string
  filename?: string
}

export interface ChatMessage extends BaseChatMessage {
  parts: MessagePart[]
  error?: boolean
}

// ============ Main Component ============

const ChatInterface: React.FC = () => {
  // Input state
  const [input, setInput] = useState('')
  
  // Chat settings
  const [method, setMethod] = useState('llm_separate')
  const [provider, setProvider] = useState('gemini')
  const [model, setModel] = useState('gemini-2.5-flash')
  const [conversationId, setConversationId] = useState<string>()
  
  // UI state
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const [isLoadingConversation, setIsLoadingConversation] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isInspectorOpen, setIsInspectorOpen] = useState(true)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const { user, token, logout } = useAuth()
  
  // Stable refs for callbacks to prevent re-renders
  const tokenRef = useRef(token)
  const methodRef = useRef(method)
  const providerRef = useRef(provider)
  const modelRef = useRef(model)
  const conversationIdRef = useRef(conversationId)
  
  // Keep refs updated
  useEffect(() => { tokenRef.current = token }, [token])
  useEffect(() => { methodRef.current = method }, [method])
  useEffect(() => { providerRef.current = provider }, [provider])
  useEffect(() => { modelRef.current = model }, [model])
  useEffect(() => { conversationIdRef.current = conversationId }, [conversationId])

  // Chat hook with debounced history invalidation
  const {
    messages: chatMessages,
    status,
    error: chatError,
    isStreaming,
    sendMessage,
    setMessages: setChatMessages,
    clearMessages,
    stop,
  } = useChat({
    onFinish: useCallback(() => {
      // Invalidate history after message completes
      queryClient.invalidateQueries({ queryKey: queryKeys.history(user?.id) })
      // Also invalidate current conversation detail cache
      if (conversationIdRef.current) {
        queryClient.invalidateQueries({ queryKey: queryKeys.conversation(conversationIdRef.current) })
      }
    }, [queryClient, user?.id]),
    onError: console.error,
    onConversationIdChange: setConversationId,
  })

  // Convert to message format with parts - memoized
  const messages: ChatMessage[] = useMemo(() => 
    chatMessages.map(msg => ({
      ...msg,
      parts: [{ type: 'text' as const, text: msg.content }],
    })),
    [chatMessages]
  )

  // Fetch history with proper caching
  const { data: history, isLoading: isLoadingHistory } = useQuery({
    queryKey: queryKeys.history(user?.id),
    queryFn: chatApi.getHistory,
    enabled: !!user,
    staleTime: 30 * 1000, // Consider fresh for 30 seconds to prevent rapid refetches
  })

  // Prefetch static data once - models and methods rarely change
  // These are prefetched to warm the cache for ModelSelector component
  useQuery({
    queryKey: queryKeys.models,
    queryFn: chatApi.getModels,
    enabled: !!user, // Only fetch when user is authenticated
    staleTime: Infinity, // Static data - never refetch automatically
    gcTime: 24 * 60 * 60 * 1000, // Keep in cache for 24 hours
  })

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // Auto-select last message
  useEffect(() => {
    if (chatMessages.length > 0 && !selectedMessageId) {
      setSelectedMessageId(chatMessages[chatMessages.length - 1].id)
    }
  }, [chatMessages, selectedMessageId])

  // Send message - use refs for stable callback
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isStreaming) return
    
    sendMessage(input, { 
      token: tokenRef.current, 
      method: methodRef.current, 
      provider: providerRef.current, 
      model: modelRef.current, 
      conversationId: conversationIdRef.current 
    })
    setInput('')
  }, [input, isStreaming, sendMessage])

  // Regenerate last response - use refs for stable callback
  const handleRegenerate = useCallback(() => {
    let lastUserMsg: BaseChatMessage | undefined
    for (let i = chatMessages.length - 1; i >= 0; i--) {
      if (chatMessages[i].role === 'user') {
        lastUserMsg = chatMessages[i]
        break
      }
    }
    if (!lastUserMsg) return
    
    // Remove last assistant + user message
    setChatMessages(prev => {
      const msgs = [...prev]
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') msgs.pop()
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'user') msgs.pop()
      return msgs
    })
    
    sendMessage(lastUserMsg.content, { 
      token: tokenRef.current, 
      method: methodRef.current, 
      provider: providerRef.current, 
      model: modelRef.current, 
      conversationId: conversationIdRef.current 
    })
  }, [chatMessages, setChatMessages, sendMessage])

  // Load conversation with caching
  const loadConversation = useCallback(async (convId: string) => {
    setIsLoadingConversation(true)
    try {
      // Use queryClient to leverage cache - check if already cached
      const cachedData = queryClient.getQueryData<ApiConversationDetail>(queryKeys.conversation(convId))
      
      // Fetch with cache support
      const conv = cachedData ?? await queryClient.fetchQuery({
        queryKey: queryKeys.conversation(convId),
        queryFn: () => chatApi.getConversation(convId),
        staleTime: 60 * 1000, // Consider fresh for 1 minute
      })
      
      const loadedMessages: BaseChatMessage[] = conv.messages.map(msg => {
        const sentimentData = msg.sentiment_data as { 
          message?: SentimentResult
          cumulative?: SentimentResult | null 
        } | undefined
        
        return {
          id: msg.id.toString(),
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: new Date(msg.created_at),
          sentiment: sentimentData?.message,
          cumulativeSentiment: sentimentData?.cumulative ?? undefined,
        }
      })

      setChatMessages(loadedMessages)
      setConversationId(convId)
      setSelectedMessageId(loadedMessages.length > 0 ? loadedMessages[loadedMessages.length - 1].id : null)
      
      if (window.innerWidth < 768) setIsSidebarOpen(false)
    } catch (error) {
      console.error('Error loading conversation:', error)
    } finally {
      setIsLoadingConversation(false)
    }
  }, [setChatMessages, queryClient])

  // New conversation
  const startNewConversation = useCallback(() => {
    clearMessages()
    setConversationId(undefined)
    setSelectedMessageId(null)
    if (window.innerWidth < 768) setIsSidebarOpen(false)
  }, [clearMessages])

  // Delete conversation
  const deleteConversation = useCallback(async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    
    try {
      await chatApi.deleteConversation(convId)
      if (conversationId === convId) startNewConversation()
      // Invalidate both history and the specific conversation cache
      queryClient.invalidateQueries({ queryKey: queryKeys.history(user?.id) })
      queryClient.removeQueries({ queryKey: queryKeys.conversation(convId) })
    } catch (error) {
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
    } catch (error) {
      console.error('Error deleting all:', error)
    }
  }, [startNewConversation, queryClient, user?.id])

  // Derived data - memoized
  const selectedMessage = useMemo(() => 
    messages.find(m => m.id === selectedMessageId),
    [messages, selectedMessageId]
  )
  
  const chartData = useMemo(() => 
    messages
      .filter(m => m.role === 'user' && m.sentiment)
      .map((m, i) => ({ 
        id: m.id,
        name: i + 1, 
        score: m.sentiment?.score || 0, 
        label: m.sentiment?.label,
        content: m.content 
      })),
    [messages]
  )

  const chatStatus = useMemo(() => 
    status === 'connecting' || status === 'streaming' ? 'streaming' 
      : status === 'error' ? 'error' : 'ready',
    [status]
  )

  // Stable callback refs to prevent child re-renders
  const closeSidebar = useCallback(() => setIsSidebarOpen(false), [])
  const openSidebar = useCallback(() => setIsSidebarOpen(true), [])
  const closeInspector = useCallback(() => setIsInspectorOpen(false), [])
  const toggleInspector = useCallback(() => setIsInspectorOpen(prev => !prev), [])

  return (
    <div className="flex w-full h-full bg-background text-foreground font-sans overflow-hidden">
      
      {/* Sidebar */}
      <ChatSidebar 
        history={history}
        currentConversationId={conversationId}
        onSelectConversation={loadConversation}
        onNewChat={startNewConversation}
        onDeleteConversation={deleteConversation}
        onDeleteAll={deleteAllConversations}
        user={user}
        onLogout={logout}
        isOpen={isSidebarOpen}
        onClose={closeSidebar}
        isLoading={isLoadingHistory}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 relative bg-background">
        
        {/* Toolbar */}
        <div className="h-14 flex items-center justify-between px-4 sm:px-6 sticky top-0 z-10">
          <div className="flex items-center gap-4">
            <Button 
              variant="ghost"
              size="icon"
              onClick={openSidebar}
              className="md:hidden -ml-2"
            >
              <Menu className="w-5 h-5" />
            </Button>
            <span className="text-sm font-medium text-muted-foreground hidden sm:block">
              Assistant
            </span>
          </div>
          
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={isInspectorOpen ? 'secondary' : 'ghost'}
                  size="icon"
                  onClick={toggleInspector}
                  className={cn(
                    'transition-all duration-200',
                    isInspectorOpen && 'bg-secondary text-foreground'
                  )}
                >
                  <Info className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Toggle Inspector</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Loading Overlay */}
        <AnimatePresence>
          {isLoadingConversation && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center z-20"
            >
              <div className="flex flex-col items-center gap-4 p-6 rounded-2xl bg-card border border-border shadow-2xl">
                <div className="relative">
                  <div className="w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Sparkles className="w-4 h-4 text-primary animate-pulse" />
                  </div>
                </div>
                <span className="text-sm font-medium text-muted-foreground">Loading...</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <MessageList 
          messages={messages}
          selectedMessageId={selectedMessageId}
          onSelectMessage={setSelectedMessageId}
          messagesEndRef={messagesEndRef}
        />

        {/* Input */}
        <ChatInput 
          input={input}
          setInput={setInput}
          onSubmit={handleSubmit}
          isStreaming={isStreaming}
          status={chatStatus}
          onStop={stop}
          onRegenerate={chatMessages.length > 0 ? handleRegenerate : undefined}
          error={chatError}
          model={model}
          setModel={setModel}
          setProvider={setProvider}
        />
      </div>

      {/* Inspector - Lazy loaded */}
      <Suspense fallback={<InspectorFallback />}>
        <ChatInspector 
          messages={messages}
          selectedMessage={selectedMessage}
          onSelectMessage={setSelectedMessageId}
          chartData={chartData}
          isOpen={isInspectorOpen}
          onClose={closeInspector}
          method={method}
          setMethod={setMethod}
        />
      </Suspense>
    </div>
  )
}

export default memo(ChatInterface)
