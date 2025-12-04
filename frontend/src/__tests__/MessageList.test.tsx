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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
      const user = userEvent.setup()
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
})
