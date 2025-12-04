import React, { useRef, useEffect, useCallback, memo, useState } from 'react'
import { Square, RotateCcw, AlertCircle, ArrowUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'
import { ModelSelector, defaultModels } from '@/components/ai-elements'

// ============ Types ============

type ChatStatus = 'ready' | 'submitted' | 'streaming' | 'error'

interface ChatInputProps {
  input: string
  setInput: (value: string) => void
  onSubmit: (e: React.FormEvent) => void
  isStreaming: boolean
  status?: ChatStatus
  onStop?: () => void
  onRegenerate?: () => void
  error?: Error | null
  model: string
  setModel: (model: string) => void
  setProvider: (provider: string) => void
}

// ============ Component ============

const ChatInput = memo<ChatInputProps>(({
  input,
  setInput,
  onSubmit,
  isStreaming,
  status = isStreaming ? 'streaming' : 'ready',
  onStop,
  onRegenerate,
  error,
  model,
  setModel,
  setProvider
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Use local state for immediate responsiveness
  const [localInput, setLocalInput] = useState(input)
  const isComposingRef = useRef(false)
  
  // Sync local state with parent when parent changes (e.g., after submit clears it)
  useEffect(() => {
    if (input !== localInput && !isComposingRef.current) {
      setLocalInput(input)
    }
  }, [input])
  
  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
  }, [])

  useEffect(() => adjustHeight(), [localInput, adjustHeight])
  useEffect(() => { if (status === 'ready') textareaRef.current?.focus() }, [status])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && localInput.trim() && status === 'ready') {
      e.preventDefault()
      // Sync to parent before submit
      setInput(localInput)
      onSubmit(e)
    }
  }, [localInput, status, onSubmit, setInput])

  const handleModelChange = useCallback((value: string) => {
    setModel(value)
    setProvider(value.includes('gpt') ? 'openai' : 'gemini')
  }, [setModel, setProvider])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    setLocalInput(value)
    // Sync to parent immediately for form state
    setInput(value)
  }, [setInput])

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    if (!localInput.trim() || status !== 'ready') return
    setInput(localInput)
    onSubmit(e)
  }, [localInput, status, setInput, onSubmit])

  const isDisabled = status !== 'ready'
  const showStop = status === 'streaming' || status === 'submitted'

  return (
    <div className="p-4 pb-6 bg-background sticky bottom-0 z-20">
      <div className="max-w-3xl mx-auto relative">
        
        {/* Error Alert */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="mb-3"
            >
              <Alert variant="destructive" className="bg-destructive/10 border-destructive/20">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription className="flex items-center justify-between">
                  <span>Something went wrong. Please try again.</span>
                  {onRegenerate && (
                    <Button variant="ghost" size="sm" onClick={onRegenerate} className="ml-2 hover:bg-destructive/20">
                      <RotateCcw className="w-3 h-3 mr-1" />
                      Retry
                    </Button>
                  )}
                </AlertDescription>
              </Alert>
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={handleSubmit}>
          <div className="relative flex flex-col bg-secondary/50 border border-border rounded-3xl shadow-sm overflow-hidden focus-within:ring-1 focus-within:ring-ring">
            
            <textarea
              ref={textareaRef}
              value={localInput}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onCompositionStart={() => { isComposingRef.current = true }}
              onCompositionEnd={() => { isComposingRef.current = false }}
              placeholder="Send a message..."
              rows={1}
              disabled={isDisabled}
              className="w-full bg-transparent border-none py-4 px-5 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-0 resize-none max-h-[200px] min-h-[56px]"
            />
            
            {/* Footer */}
            <div className="flex items-center justify-between px-3 pb-3 pt-1">
              <ModelSelector
                models={defaultModels}
                value={model}
                onValueChange={handleModelChange}
                className="h-8 text-xs border-0 bg-transparent hover:bg-secondary text-muted-foreground"
              />
              
              {showStop ? (
                <Button 
                  type="button"
                  variant="secondary"
                  size="icon"
                  onClick={onStop}
                  className="h-8 w-8 rounded-full bg-foreground text-background hover:bg-foreground/90"
                  title="Stop"
                >
                  <Square className="w-3 h-3 fill-current" />
                </Button>
              ) : (
                <Button 
                  type="submit" 
                  size="icon"
                  disabled={!localInput.trim() || isDisabled}
                  className={cn(
                    'h-8 w-8 rounded-full transition-all',
                    localInput.trim() ? 'bg-foreground text-background hover:bg-foreground/90' : 'bg-muted text-muted-foreground'
                  )}
                >
                  <ArrowUp className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </form>
        
        <p className="mt-3 text-center text-[10px] text-muted-foreground/60">
          Lia can make mistakes. Check important info.
        </p>
      </div>
    </div>
  )
})

ChatInput.displayName = 'ChatInput'

export default ChatInput
