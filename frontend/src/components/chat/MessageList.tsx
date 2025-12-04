import React, { useMemo, useCallback, memo, lazy, Suspense } from 'react'
import { User, Bot, Copy, Check, ExternalLink, Paperclip } from 'lucide-react'
import type { ChatMessage } from './ChatInterface'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

// Lazy load heavy markdown component
const MarkdownMessage = lazy(() => import('../MarkdownMessage'))

// Simple markdown loading fallback
const MarkdownFallback = () => (
  <div className="animate-pulse space-y-2">
    <div className="h-4 bg-muted rounded w-3/4" />
    <div className="h-4 bg-muted rounded w-1/2" />
  </div>
)

// ============ Types ============

interface MessageListProps {
  messages: ChatMessage[]
  selectedMessageId: string | null
  onSelectMessage: (id: string) => void
  messagesEndRef: React.RefObject<HTMLDivElement | null>
}

// ============ Constants ============

const SUGGESTIONS = [
  'What are the advantages of using Next.js?',
  "Write code to demonstrate Dijkstra's algorithm",
  'Help me write an essay about Silicon Valley',
  'What is the weather in San Francisco?'
]

// ============ Hooks ============

function useCopyToClipboard() {
  const [copied, setCopied] = React.useState(false)
  
  const copy = useCallback((text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [])
  
  return { copied, copy }
}

// ============ Components ============

// Loading dots animation - CSS only
const LoadingDots: React.FC = memo(() => (
  <div className="flex items-center gap-1 py-2">
    {[0, 1, 2].map(i => (
      <div
        key={i}
        className="w-2 h-2 rounded-full bg-primary animate-pulse"
        style={{ animationDelay: `${i * 200}ms` }}
      />
    ))}
  </div>
))

LoadingDots.displayName = 'LoadingDots'

// Sentiment indicator dot
const SentimentDot = memo<{ label: string }>(({ label }) => {
  const color = label === 'Positive' ? 'bg-emerald-500' 
    : label === 'Negative' ? 'bg-rose-500' 
    : 'bg-blue-500'
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <div className={cn('w-1.5 h-1.5 rounded-full', color)} />
        </TooltipTrigger>
        <TooltipContent side="left">
          <p className="text-xs font-medium">{label} Sentiment</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
})

SentimentDot.displayName = 'SentimentDot'

// Single message component - optimized with CSS transitions
const MessageItem = memo<{
  msg: ChatMessage
  onSelect: () => void
}>(({ msg, onSelect }) => {
  const isUser = msg.role === 'user'
  const { copied, copy } = useCopyToClipboard()
  
  // Get content from parts or fallback to content
  const content = useMemo(() => {
    const textPart = msg.parts.find(p => p.type === 'text')
    return textPart?.text || msg.content
  }, [msg.parts, msg.content])
  
  const fileParts = useMemo(() => msg.parts.filter(p => p.type === 'file'), [msg.parts])
  const sourceParts = useMemo(() => msg.parts.filter(p => p.type === 'source-url'), [msg.parts])

  const handleCopy = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    copy(content)
  }, [copy, content])

  return (
    <div
      id={`message-${msg.id}`}
      className={cn(
        'relative group py-4 animate-in fade-in slide-in-from-bottom-2 duration-300',
        isUser && 'flex justify-end'
      )}
      onClick={onSelect}
    >
      <div className={cn('flex gap-4', isUser && 'flex-row-reverse max-w-[80%]')}>
        {/* Avatar */}
        <div className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ring-1 ring-border',
          isUser ? 'bg-secondary text-foreground' : 'bg-primary text-primary-foreground'
        )}>
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>
        
        {/* Content */}
        <div className={cn('flex-1 min-w-0', isUser && 'text-right')}>
          {/* Header */}
          <div className={cn('flex items-center gap-2 mb-1', isUser && 'justify-end')}>
            <span className="text-sm font-semibold">{isUser ? 'You' : 'Assistant'}</span>
            <span className="text-xs text-muted-foreground">
              {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            {msg.isStreaming && (
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            )}
          </div>
          
          {/* Message body */}
          <div className="text-foreground leading-7">
            {content ? (
              isUser ? (
                <p className="whitespace-pre-wrap m-0">{content}</p>
              ) : (
                <Suspense fallback={<MarkdownFallback />}>
                  <MarkdownMessage content={content} />
                </Suspense>
              )
            ) : msg.isStreaming ? (
              <LoadingDots />
            ) : null}
          </div>
          
          {/* File attachments */}
          {fileParts.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {fileParts.map((file, idx) => (
                file.mediaType?.startsWith('image/') ? (
                  <img 
                    key={idx}
                    src={file.url} 
                    alt={file.filename || 'Attachment'} 
                    className="max-w-xs rounded-lg border border-border shadow-sm"
                    loading="lazy"
                  />
                ) : (
                  <a key={idx} href={file.url} target="_blank" rel="noopener noreferrer">
                    <Badge variant="outline" className="gap-2 cursor-pointer hover:bg-accent/10 py-1.5 px-3">
                      <Paperclip className="w-3 h-3" />
                      {file.filename || 'File'}
                    </Badge>
                  </a>
                )
              ))}
            </div>
          )}
          
          {/* Sources */}
          {!isUser && sourceParts.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border/30">
              {sourceParts.map((source, idx) => (
                <a key={idx} href={source.url} target="_blank" rel="noopener noreferrer">
                  <Badge variant="secondary" className="gap-1 text-xs">
                    <ExternalLink className="w-3 h-3" />
                    {source.title || `Source ${idx + 1}`}
                  </Badge>
                </a>
              ))}
            </div>
          )}
          
          {/* Copy action for assistant messages */}
          {!isUser && content && !msg.isStreaming && (
            <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={handleCopy}
              >
                {copied ? <Check className="w-3 h-3 mr-1" /> : <Copy className="w-3 h-3 mr-1" />}
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
          )}
        </div>
      </div>
      
      {/* Sentiment indicator */}
      {isUser && msg.sentiment && (
        <div className="absolute -right-3 top-6 opacity-0 group-hover:opacity-100 transition-opacity">
          <SentimentDot label={msg.sentiment.label} />
        </div>
      )}
    </div>
  )
})

MessageItem.displayName = 'MessageItem'

// Empty state with suggestions - memoized
const EmptyState = memo<{ onSuggestionSelect: (text: string) => void }>(({ onSuggestionSelect }) => (
  <div className="h-full flex flex-col items-center justify-center p-8">
    <div className="text-center mb-12">
      <h1 className="text-4xl font-semibold text-foreground mb-2 tracking-tight">Hello there!</h1>
      <p className="text-xl text-muted-foreground">How can I help you today?</p>
    </div>
    
    <div className="max-w-2xl w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
      {SUGGESTIONS.map((suggestion, idx) => (
        <button
          key={idx}
          onClick={() => onSuggestionSelect(suggestion)}
          className="text-left p-4 rounded-xl border border-border bg-card hover:bg-accent/50 transition-colors text-sm text-muted-foreground hover:text-foreground"
        >
          {suggestion}
        </button>
      ))}
    </div>
  </div>
))

EmptyState.displayName = 'EmptyState'

// ============ Main Component ============

const MessageList = memo<MessageListProps>(({ messages, selectedMessageId, onSelectMessage, messagesEndRef }) => {
  // Handle suggestion selection by setting input value
  const handleSuggestionSelect = useCallback((suggestion: string) => {
    const input = document.querySelector('textarea') as HTMLTextAreaElement
    if (input) {
      // Use native setter to trigger React's onChange
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
      setter?.call(input, suggestion)
      input.dispatchEvent(new Event('input', { bubbles: true }))
      input.focus()
    }
  }, [])

  // Scroll to selected message
  React.useEffect(() => {
    if (selectedMessageId) {
      const el = document.getElementById(`message-${selectedMessageId}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [selectedMessageId])

  if (messages.length === 0) {
    return <EmptyState onSuggestionSelect={handleSuggestionSelect} />
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 custom-scrollbar scroll-smooth">
      <div className="max-w-3xl mx-auto space-y-2">
        {messages.map(msg => (
          <MessageItem
            key={msg.id}
            msg={msg}
            onSelect={() => onSelectMessage(msg.id)}
          />
        ))}
        <div ref={messagesEndRef} className="h-4" />
      </div>
    </div>
  )
})

MessageList.displayName = 'MessageList'

export default MessageList
