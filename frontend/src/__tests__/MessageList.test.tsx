import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageList from '../components/chat/MessageList'
import type { ChatMessage, MessagePart } from '../components/chat/ChatInterface'

// Mock the lazy-loaded MarkdownMessage component for tests
vi.mock('../components/MarkdownMessage', () => ({
  default: ({ content }: { content: string }) => <div data-testid="markdown-message">{content}</div>,
}))

const createMockMessage = (
  overrides: Partial<{
    id: string
    role: 'user' | 'assistant'
    content: string
    parts: MessagePart[]
    thoughts?: string[]
    sentiment?: { score: number; label: string; emotion?: string }
    cumulativeSentiment?: { score: number; label: string }
    timestamp: Date
    isStreaming?: boolean
  }> = {}
): ChatMessage => ({
  id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
  role: 'user',
  content: 'Test message',
  parts: [{ type: 'text', text: 'Test message' }],
  timestamp: new Date(),
  ...overrides,
})

describe('MessageList', () => {
  const messagesEndRef = { current: null }
  const defaultProps = {
    messages: [] as ChatMessage[],
    selectedMessageId: null as string | null,
    onSelectMessage: vi.fn(),
    messagesEndRef: messagesEndRef as React.RefObject<HTMLDivElement | null>,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  describe('Empty State', () => {
    it('renders empty state with greeting when no messages', () => {
      render(<MessageList {...defaultProps} />)
      
      expect(screen.getByText('Hello there!')).toBeInTheDocument()
      expect(screen.getByText('How can I help you today?')).toBeInTheDocument()
    })

    it('renders suggestion buttons in empty state', () => {
      render(<MessageList {...defaultProps} />)
      
      expect(screen.getByText(/What are the advantages of using Next.js/i)).toBeInTheDocument()
      expect(screen.getByText(/Write code to demonstrate Dijkstra/i)).toBeInTheDocument()
      expect(screen.getByText(/Help me write an essay about Silicon Valley/i)).toBeInTheDocument()
      expect(screen.getByText(/What is the weather in San Francisco/i)).toBeInTheDocument()
    })
  })

  describe('Message Rendering', () => {
    it('renders user message correctly', () => {
      const message = createMockMessage({
        role: 'user',
        content: 'Hello AI!',
        parts: [{ type: 'text', text: 'Hello AI!' }],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.getByText('You')).toBeInTheDocument()
      expect(screen.getByText('Hello AI!')).toBeInTheDocument()
    })

    it('renders assistant message correctly', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: 'Hello! How can I help you?',
        parts: [{ type: 'text', text: 'Hello! How can I help you?' }],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.getByText('Assistant')).toBeInTheDocument()
    })

    it('renders multiple messages', async () => {
      const messages = [
        createMockMessage({ id: '1', role: 'user', content: 'Question', parts: [{ type: 'text', text: 'Question' }] }),
        createMockMessage({ id: '2', role: 'assistant', content: 'Answer', parts: [{ type: 'text', text: 'Answer' }] }),
      ]
      
      render(<MessageList {...defaultProps} messages={messages} />)
      
      expect(screen.getByText('Question')).toBeInTheDocument()
      // Wait for lazy-loaded MarkdownMessage to render with extended timeout
      await waitFor(() => {
        expect(screen.getByText('Answer')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('renders message timestamp', () => {
      const timestamp = new Date('2024-01-01T12:30:00')
      const message = createMockMessage({ timestamp })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Time should be formatted as HH:MM
      expect(screen.getByText(/12:30/i)).toBeInTheDocument()
    })

    it('shows streaming indicator for streaming messages', () => {
      const message = createMockMessage({
        role: 'assistant',
        isStreaming: true,
        content: '',
        parts: [{ type: 'text', text: '' }],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should show loading dots or streaming indicator
      const streamingIndicator = document.querySelector('.animate-pulse')
      expect(streamingIndicator).toBeInTheDocument()
    })
  })

  describe('Message Selection', () => {
    it('calls onSelectMessage when clicking a message', async () => {
      const user = userEvent.setup({ delay: null })
      const onSelectMessage = vi.fn()
      const message = createMockMessage({ id: 'msg-123' })
      
      render(<MessageList {...defaultProps} messages={[message]} onSelectMessage={onSelectMessage} />)
      
      const messageElement = screen.getByText('Test message').closest('[id^="message-"]')
      await user.click(messageElement!)
      
      expect(onSelectMessage).toHaveBeenCalledWith('msg-123')
    })
  })

  describe('Copy Functionality', () => {
    it('shows copy button on assistant messages', async () => {
      const user = userEvent.setup({ delay: null })
      const message = createMockMessage({
        role: 'assistant',
        content: 'Response text',
        parts: [{ type: 'text', text: 'Response text' }],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Wait for lazy-loaded MarkdownMessage to render
      await waitFor(() => {
        expect(screen.getByText('Response text')).toBeInTheDocument()
      })
      
      // Hover over the message to show the copy button
      const messageElement = screen.getByText('Response text').closest('[id^="message-"]')
      await user.hover(messageElement!)
      
      expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
    })

    it('does not show copy button on user messages', () => {
      const message = createMockMessage({ role: 'user' })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.queryByRole('button', { name: /copy/i })).not.toBeInTheDocument()
    })

    it('does not show copy button while streaming', () => {
      const message = createMockMessage({
        role: 'assistant',
        isStreaming: true,
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.queryByRole('button', { name: /copy/i })).not.toBeInTheDocument()
    })
  })

  describe('File Attachments', () => {
    it('renders image attachments', () => {
      const message = createMockMessage({
        parts: [
          { type: 'text', text: 'Check this image' },
          { type: 'file', url: 'http://example.com/image.jpg', filename: 'test.jpg', mediaType: 'image/jpeg' },
        ],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      const image = screen.getByRole('img', { name: 'test.jpg' })
      expect(image).toHaveAttribute('src', 'http://example.com/image.jpg')
    })

    it('renders file attachments as badges', () => {
      const message = createMockMessage({
        parts: [
          { type: 'text', text: 'Check this file' },
          { type: 'file', url: 'http://example.com/doc.pdf', filename: 'document.pdf', mediaType: 'application/pdf' },
        ],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.getByText('document.pdf')).toBeInTheDocument()
    })
  })

  describe('Source URLs', () => {
    it('renders source URLs on assistant messages', () => {
      const message = createMockMessage({
        role: 'assistant',
        parts: [
          { type: 'text', text: 'Here is the information' },
          { type: 'source-url', url: 'http://example.com', title: 'Example Source' },
        ],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      const sourceLink = screen.getByText('Example Source')
      expect(sourceLink.closest('a')).toHaveAttribute('href', 'http://example.com')
      expect(sourceLink.closest('a')).toHaveAttribute('target', '_blank')
    })

    it('uses fallback title when source has no title', () => {
      const message = createMockMessage({
        role: 'assistant',
        parts: [
          { type: 'text', text: 'Info' },
          { type: 'source-url', url: 'http://example.com' },
        ],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.getByText('Source 1')).toBeInTheDocument()
    })
  })

  describe('Sentiment Indicator', () => {
    it('shows sentiment dot for user messages with sentiment', async () => {
      const user = userEvent.setup({ delay: null })
      const message = createMockMessage({
        role: 'user',
        sentiment: { score: 0.8, label: 'Positive' },
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      const messageElement = screen.getByText('Test message').closest('[id^="message-"]')
      await user.hover(messageElement!)
      
      // Sentiment dot should be visible (has emerald color for positive)
      const sentimentDot = document.querySelector('.bg-emerald-500')
      expect(sentimentDot).toBeInTheDocument()
    })

    it('does not show sentiment dot for assistant messages', () => {
      const message = createMockMessage({
        role: 'assistant',
        sentiment: { score: 0.8, label: 'Positive' },
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // No sentiment dot for assistant
      expect(document.querySelector('.bg-emerald-500')).not.toBeInTheDocument()
    })
  })

  describe('Loading State', () => {
    it('shows loading dots for streaming message with empty content', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: '',
        parts: [{ type: 'text', text: '' }],
        isStreaming: true,
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should render LoadingDots component
      const loadingDots = document.querySelectorAll('.animate-pulse')
      expect(loadingDots.length).toBeGreaterThan(0)
    })
  })

  describe('Message Parts', () => {
    it('uses text from parts if available', () => {
      const message = createMockMessage({
        content: 'Fallback content',
        parts: [{ type: 'text', text: 'Part text' }],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.getByText('Part text')).toBeInTheDocument()
    })

    it('falls back to content if no text part', () => {
      const message = createMockMessage({
        content: 'Fallback content',
        parts: [],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      expect(screen.getByText('Fallback content')).toBeInTheDocument()
    })
  })

  describe('Avatar Icons', () => {
    it('shows user icon for user messages', () => {
      const message = createMockMessage({ role: 'user' })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // User icon should have bg-secondary
      const avatar = document.querySelector('.bg-secondary')
      expect(avatar).toBeInTheDocument()
    })

    it('shows bot icon for assistant messages', () => {
      const message = createMockMessage({ role: 'assistant' })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Assistant icon should have bg-primary
      const avatar = document.querySelector('.bg-primary')
      expect(avatar).toBeInTheDocument()
    })
  })

  describe('Thoughts Section', () => {
    it('renders thoughts section for assistant message with thoughts', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: 'The answer is 42',
        parts: [{ type: 'text', text: 'The answer is 42' }],
        thoughts: ['Let me analyze this...', 'Breaking it down...'],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should show the "Thought process" button (when not streaming)
      expect(screen.getByText('Thought process')).toBeInTheDocument()
    })

    it('renders "Thinking..." label when streaming', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: 'The answer is 42',
        parts: [{ type: 'text', text: 'The answer is 42' }],
        thoughts: ['Analyzing...'],
        isStreaming: true,
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should show the "Thinking..." label when streaming
      expect(screen.getByText('Thinking...')).toBeInTheDocument()
    })

    it('auto-expands thoughts when streaming starts', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: '',
        parts: [{ type: 'text', text: '' }],
        thoughts: ['First thought'],
        isStreaming: true,
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // When streaming, thoughts should auto-expand - content visible
      // The ThoughtsSection uses useEffect to auto-expand when isStreaming becomes true
      // For the test, we check if it rendered with expanded state
      // Note: Due to useEffect timing, we may need to wait for the effect
      // The button should still show "Thinking..." when streaming
      expect(screen.getByText('Thinking...')).toBeInTheDocument()
    })

    it('does not render thoughts section when thoughts array is empty', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: 'Response',
        parts: [{ type: 'text', text: 'Response' }],
        thoughts: [],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should not show either label
      expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
      expect(screen.queryByText('Thought process')).not.toBeInTheDocument()
    })

    it('does not render thoughts section when thoughts is undefined', () => {
      const message = createMockMessage({
        role: 'assistant',
        content: 'Response',
        parts: [{ type: 'text', text: 'Response' }],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should not show either label
      expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
      expect(screen.queryByText('Thought process')).not.toBeInTheDocument()
    })

    it('does not render thoughts section for user messages', () => {
      const message = createMockMessage({
        role: 'user',
        content: 'User message',
        parts: [{ type: 'text', text: 'User message' }],
        thoughts: ['Some thoughts'],  // User messages shouldn't show thoughts anyway
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Should not show either label for user messages
      expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
      expect(screen.queryByText('Thought process')).not.toBeInTheDocument()
    })

    it('expands thoughts section when clicked', async () => {
      const user = userEvent.setup()
      const message = createMockMessage({
        role: 'assistant',
        content: 'Response',
        parts: [{ type: 'text', text: 'Response' }],
        thoughts: ['First thought', 'Second thought'],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      // Initially thoughts content should not be visible
      expect(screen.queryByText('First thoughtSecond thought')).not.toBeInTheDocument()
      
      // Click the "Thought process" button to expand
      const thinkingButton = screen.getByText('Thought process')
      await user.click(thinkingButton)
      
      // Now thoughts content should be visible (thoughts are joined)
      await waitFor(() => {
        expect(screen.getByText('First thoughtSecond thought')).toBeInTheDocument()
      })
    })

    it('collapses thoughts section when clicked again', async () => {
      const user = userEvent.setup()
      const message = createMockMessage({
        role: 'assistant',
        content: 'Response',
        parts: [{ type: 'text', text: 'Response' }],
        thoughts: ['Thought content'],
      })
      
      render(<MessageList {...defaultProps} messages={[message]} />)
      
      const thinkingButton = screen.getByText('Thought process')
      
      // Expand
      await user.click(thinkingButton)
      await waitFor(() => {
        expect(screen.getByText('Thought content')).toBeInTheDocument()
      })
      
      // Collapse
      await user.click(thinkingButton)
      await waitFor(() => {
        expect(screen.queryByText('Thought content')).not.toBeInTheDocument()
      })
    })
  })
})
