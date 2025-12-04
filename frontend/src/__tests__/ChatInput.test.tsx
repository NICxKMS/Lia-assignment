import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import ChatInput from '../components/chat/ChatInput'

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }: React.PropsWithChildren<React.HTMLAttributes<HTMLDivElement>>, ref: React.ForwardedRef<HTMLDivElement>) => (
      <div ref={ref} {...props}>{children}</div>
    )),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}))

// Mock model-selector
vi.mock('@/components/ai-elements', () => ({
  ModelSelector: ({ value, onValueChange }: { value: string; onValueChange: (v: string) => void }) => (
    <select
      data-testid="model-selector"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    >
      <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
      <option value="gpt-4o">GPT-4o</option>
    </select>
  ),
  defaultModels: [
    { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'Google' },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI' },
  ],
}))

describe('ChatInput', () => {
  const defaultProps = {
    input: '',
    setInput: vi.fn(),
    onSubmit: vi.fn(),
    isStreaming: false,
    model: 'gemini-2.5-flash',
    setModel: vi.fn(),
    setProvider: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders textarea with placeholder', () => {
      render(<ChatInput {...defaultProps} />)
      
      expect(screen.getByPlaceholderText('Send a message...')).toBeInTheDocument()
    })

    it('renders submit button', () => {
      render(<ChatInput {...defaultProps} />)
      
      const submitButton = screen.getByRole('button', { name: '' })
      expect(submitButton).toBeInTheDocument()
    })

    it('renders model selector', () => {
      render(<ChatInput {...defaultProps} />)
      
      expect(screen.getByTestId('model-selector')).toBeInTheDocument()
    })

    it('renders disclaimer text', () => {
      render(<ChatInput {...defaultProps} />)
      
      expect(screen.getByText(/Lia can make mistakes/i)).toBeInTheDocument()
    })

    it('displays current input value', () => {
      render(<ChatInput {...defaultProps} input="Hello there" />)
      
      const textarea = screen.getByPlaceholderText('Send a message...') as HTMLTextAreaElement
      expect(textarea.value).toBe('Hello there')
    })
  })

  describe('Input Handling', () => {
    it('calls setInput when typing', async () => {
      const user = userEvent.setup()
      const setInput = vi.fn()
      render(<ChatInput {...defaultProps} setInput={setInput} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      await user.type(textarea, 'Hello')
      
      expect(setInput).toHaveBeenCalled()
    })

    it('disables textarea when streaming', () => {
      render(<ChatInput {...defaultProps} isStreaming={true} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      expect(textarea).toBeDisabled()
    })

    it('disables textarea when status is not ready', () => {
      render(<ChatInput {...defaultProps} status="streaming" />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      expect(textarea).toBeDisabled()
    })
  })

  describe('Form Submission', () => {
    it('calls onSubmit when form is submitted', async () => {
      const onSubmit = vi.fn((e) => e.preventDefault())
      render(<ChatInput {...defaultProps} input="Hello" onSubmit={onSubmit} />)
      
      const form = screen.getByPlaceholderText('Send a message...').closest('form')
      fireEvent.submit(form!)
      
      expect(onSubmit).toHaveBeenCalled()
    })

    it('submits on Enter key without Shift', async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn((e) => e.preventDefault())
      render(<ChatInput {...defaultProps} input="Hello" onSubmit={onSubmit} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      await user.type(textarea, '{Enter}')
      
      expect(onSubmit).toHaveBeenCalled()
    })

    it('does not submit on Shift+Enter', async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ChatInput {...defaultProps} input="Hello" onSubmit={onSubmit} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      await user.type(textarea, '{Shift>}{Enter}{/Shift}')
      
      expect(onSubmit).not.toHaveBeenCalled()
    })

    it('does not submit when input is empty', async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ChatInput {...defaultProps} input="" onSubmit={onSubmit} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      await user.type(textarea, '{Enter}')
      
      expect(onSubmit).not.toHaveBeenCalled()
    })

    it('does not submit when status is not ready', async () => {
      const onSubmit = vi.fn()
      render(<ChatInput {...defaultProps} input="Hello" status="streaming" onSubmit={onSubmit} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      // Can't type when disabled, so we simulate the keydown event
      fireEvent.keyDown(textarea, { key: 'Enter' })
      
      expect(onSubmit).not.toHaveBeenCalled()
    })

    it('disables submit button when input is empty', () => {
      render(<ChatInput {...defaultProps} input="" />)
      
      const buttons = screen.getAllByRole('button')
      const submitButton = buttons.find(btn => btn.getAttribute('type') === 'submit')
      expect(submitButton).toBeDisabled()
    })

    it('enables submit button when input has content', () => {
      render(<ChatInput {...defaultProps} input="Hello" />)
      
      const buttons = screen.getAllByRole('button')
      const submitButton = buttons.find(btn => btn.getAttribute('type') === 'submit')
      expect(submitButton).toBeEnabled()
    })
  })

  describe('Stop Button', () => {
    it('shows stop button when streaming', () => {
      render(<ChatInput {...defaultProps} status="streaming" onStop={vi.fn()} />)
      
      const buttons = screen.getAllByRole('button')
      const stopButton = buttons.find(btn => btn.getAttribute('title') === 'Stop')
      expect(stopButton).toBeInTheDocument()
    })

    it('shows stop button when submitted', () => {
      render(<ChatInput {...defaultProps} status="submitted" onStop={vi.fn()} />)
      
      const buttons = screen.getAllByRole('button')
      const stopButton = buttons.find(btn => btn.getAttribute('title') === 'Stop')
      expect(stopButton).toBeInTheDocument()
    })

    it('calls onStop when stop button is clicked', async () => {
      const user = userEvent.setup()
      const onStop = vi.fn()
      render(<ChatInput {...defaultProps} status="streaming" onStop={onStop} />)
      
      const buttons = screen.getAllByRole('button')
      const stopButton = buttons.find(btn => btn.getAttribute('title') === 'Stop')
      await user.click(stopButton!)
      
      expect(onStop).toHaveBeenCalled()
    })

    it('hides stop button when ready', () => {
      render(<ChatInput {...defaultProps} status="ready" onStop={vi.fn()} />)
      
      const buttons = screen.getAllByRole('button')
      const stopButton = buttons.find(btn => btn.getAttribute('title') === 'Stop')
      expect(stopButton).toBeUndefined()
    })
  })

  describe('Error Alert', () => {
    it('shows error alert when error is present', () => {
      const error = new Error('Something went wrong')
      render(<ChatInput {...defaultProps} error={error} />)
      
      expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument()
    })

    it('shows retry button when error and onRegenerate are present', () => {
      const error = new Error('Something went wrong')
      const onRegenerate = vi.fn()
      render(<ChatInput {...defaultProps} error={error} onRegenerate={onRegenerate} />)
      
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    })

    it('calls onRegenerate when retry button is clicked', async () => {
      const user = userEvent.setup()
      const error = new Error('Something went wrong')
      const onRegenerate = vi.fn()
      render(<ChatInput {...defaultProps} error={error} onRegenerate={onRegenerate} />)
      
      await user.click(screen.getByRole('button', { name: /retry/i }))
      
      expect(onRegenerate).toHaveBeenCalled()
    })

    it('hides error alert when no error', () => {
      render(<ChatInput {...defaultProps} error={null} />)
      
      expect(screen.queryByText(/Something went wrong/i)).not.toBeInTheDocument()
    })
  })

  describe('Model Selector', () => {
    it('displays current model value', () => {
      render(<ChatInput {...defaultProps} model="gemini-2.5-flash" />)
      
      const selector = screen.getByTestId('model-selector') as HTMLSelectElement
      expect(selector.value).toBe('gemini-2.5-flash')
    })

    it('calls setModel when model changes', async () => {
      const user = userEvent.setup()
      const setModel = vi.fn()
      const setProvider = vi.fn()
      render(<ChatInput {...defaultProps} setModel={setModel} setProvider={setProvider} />)
      
      const selector = screen.getByTestId('model-selector')
      await user.selectOptions(selector, 'gpt-4o')
      
      expect(setModel).toHaveBeenCalledWith('gpt-4o')
    })

    it('sets provider to openai for GPT models', async () => {
      const user = userEvent.setup()
      const setModel = vi.fn()
      const setProvider = vi.fn()
      render(<ChatInput {...defaultProps} setModel={setModel} setProvider={setProvider} />)
      
      const selector = screen.getByTestId('model-selector')
      await user.selectOptions(selector, 'gpt-4o')
      
      expect(setProvider).toHaveBeenCalledWith('openai')
    })

    it('sets provider to gemini for non-GPT models', async () => {
      const user = userEvent.setup()
      const setModel = vi.fn()
      const setProvider = vi.fn()
      render(<ChatInput {...defaultProps} model="gpt-4o" setModel={setModel} setProvider={setProvider} />)
      
      const selector = screen.getByTestId('model-selector')
      await user.selectOptions(selector, 'gemini-2.5-flash')
      
      expect(setProvider).toHaveBeenCalledWith('gemini')
    })
  })

  describe('Status Handling', () => {
    it('uses isStreaming when status is not provided', () => {
      render(<ChatInput {...defaultProps} isStreaming={true} />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      expect(textarea).toBeDisabled()
    })

    it('prefers status over isStreaming', () => {
      render(<ChatInput {...defaultProps} isStreaming={false} status="streaming" />)
      
      const textarea = screen.getByPlaceholderText('Send a message...')
      expect(textarea).toBeDisabled()
    })
  })
})
