import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import ChatSidebar from '../components/chat/ChatSidebar'
import type { ConversationSummary, User } from '../lib/api'

// Motion props to filter out
const motionProps = ['whileHover', 'whileTap', 'whileFocus', 'whileDrag', 'whileInView', 
  'initial', 'animate', 'exit', 'variants', 'transition', 'layout', 'layoutId', 'drag'] as const

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>, ref: React.ForwardedRef<HTMLDivElement>) => {
      // Filter out framer-motion specific props
      const filtered = Object.fromEntries(
        Object.entries(props).filter(([key]) => !motionProps.includes(key as typeof motionProps[number]))
      ) as React.HTMLAttributes<HTMLDivElement>
      return <div ref={ref} {...filtered}>{children}</div>
    }),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}))

const mockUser: User = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  created_at: '2024-01-01T00:00:00Z',
}

const createMockConversation = (
  id: string,
  title: string | null,
  daysAgo: number = 0
): ConversationSummary => {
  const date = new Date()
  date.setDate(date.getDate() - daysAgo)
  return {
    id,
    title,
    created_at: date.toISOString(),
    updated_at: date.toISOString(),
    message_count: 5,
  }
}

describe('ChatSidebar', () => {
  const defaultProps = {
    history: undefined as ConversationSummary[] | undefined,
    currentConversationId: undefined as string | undefined,
    onSelectConversation: vi.fn(),
    onNewChat: vi.fn(),
    onDeleteConversation: vi.fn(),
    onDeleteAll: vi.fn(),
    user: mockUser,
    onLogout: vi.fn(),
    isOpen: true,
    onClose: vi.fn(),
    isLoading: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders the sidebar with header', () => {
      render(<ChatSidebar {...defaultProps} />)
      
      // Multiple due to desktop/mobile views
      const headers = screen.getAllByText('Conversations')
      expect(headers.length).toBeGreaterThan(0)
    })

    it('renders new chat button', () => {
      render(<ChatSidebar {...defaultProps} />)
      
      const newChatButtons = screen.getAllByRole('button', { name: /new conversation/i })
      expect(newChatButtons.length).toBeGreaterThan(0)
    })

    it('renders empty state when no history', () => {
      render(<ChatSidebar {...defaultProps} history={[]} />)
      
      // Multiple due to desktop/mobile views
      const emptyStates = screen.getAllByText(/No conversations yet/i)
      expect(emptyStates.length).toBeGreaterThan(0)
    })

    it('renders user info when user is provided', () => {
      render(<ChatSidebar {...defaultProps} />)
      
      // Multiple due to desktop/mobile views
      const usernames = screen.getAllByText('testuser')
      expect(usernames.length).toBeGreaterThan(0)
    })

    it('renders user avatar with first letter of username', () => {
      render(<ChatSidebar {...defaultProps} />)
      
      // Multiple due to desktop/mobile views
      const avatars = screen.getAllByText('T')
      expect(avatars.length).toBeGreaterThan(0)
    })

    it('renders loading indicator when isLoading is true', () => {
      render(<ChatSidebar {...defaultProps} isLoading={true} />)
      
      // Multiple due to desktop/mobile views
      const loadingIndicators = screen.getAllByText(/Loading.../i)
      expect(loadingIndicators.length).toBeGreaterThan(0)
    })
  })

  describe('Conversation List', () => {
    it('renders conversations grouped by date', () => {
      const history = [
        createMockConversation('1', 'Today Chat', 0),
        createMockConversation('2', 'Yesterday Chat', 1),
        createMockConversation('3', 'Last Week Chat', 5),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Multiple due to desktop/mobile views
      expect(screen.getAllByText('Today').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Yesterday').length).toBeGreaterThan(0)
      expect(screen.getAllByText('This Week').length).toBeGreaterThan(0)
    })

    it('renders conversation titles', () => {
      const history = [
        createMockConversation('1', 'My First Chat', 0),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Multiple due to desktop/mobile views
      expect(screen.getAllByText('My First Chat').length).toBeGreaterThan(0)
    })

    it('truncates long conversation titles', () => {
      const longTitle = 'A'.repeat(50)
      const history = [
        createMockConversation('1', longTitle, 0),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Title should be truncated to 28 chars + '...' - multiple due to desktop/mobile views
      const truncatedElements = screen.getAllByText('A'.repeat(28) + '...')
      expect(truncatedElements.length).toBeGreaterThan(0)
    })

    it('shows "New conversation" for null titles', () => {
      const history = [
        createMockConversation('1', null, 0),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Multiple due to desktop/mobile views
      const elements = screen.getAllByText('New conversation')
      expect(elements.length).toBeGreaterThan(0)
    })

    it('highlights current conversation', () => {
      const history = [
        createMockConversation('1', 'Chat 1', 0),
        createMockConversation('2', 'Chat 2', 0),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} currentConversationId="1" />)
      
      // Multiple due to desktop/mobile views
      const chat1Elements = screen.getAllByText('Chat 1')
      expect(chat1Elements[0].closest('[role="button"]')).toHaveClass('text-primary')
    })
  })

  describe('Interactions', () => {
    it('calls onSelectConversation when clicking a conversation', async () => {
      const user = userEvent.setup({ delay: null })
      const onSelectConversation = vi.fn()
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} onSelectConversation={onSelectConversation} />)
      
      // Multiple due to desktop/mobile views
      const chatElements = screen.getAllByText('My Chat')
      await user.click(chatElements[0])
      
      expect(onSelectConversation).toHaveBeenCalledWith('1')
    })

    it('calls onSelectConversation on Enter key', () => {
      const onSelectConversation = vi.fn()
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} onSelectConversation={onSelectConversation} />)
      
      // Multiple due to desktop/mobile views
      const chatElements = screen.getAllByText('My Chat')
      const chatItem = chatElements[0].closest('[role="button"]')
      fireEvent.keyDown(chatItem!, { key: 'Enter' })
      
      expect(onSelectConversation).toHaveBeenCalledWith('1')
    })

    it('calls onSelectConversation on Space key', () => {
      const onSelectConversation = vi.fn()
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} onSelectConversation={onSelectConversation} />)
      
      // Multiple due to desktop/mobile views
      const chatElements = screen.getAllByText('My Chat')
      const chatItem = chatElements[0].closest('[role="button"]')
      fireEvent.keyDown(chatItem!, { key: ' ' })
      
      expect(onSelectConversation).toHaveBeenCalledWith('1')
    })

    it('calls onNewChat when clicking new chat button', async () => {
      const user = userEvent.setup({ delay: null })
      const onNewChat = vi.fn()
      
      render(<ChatSidebar {...defaultProps} onNewChat={onNewChat} />)
      
      const newChatButtons = screen.getAllByRole('button', { name: /new conversation/i })
      await user.click(newChatButtons[0])
      
      expect(onNewChat).toHaveBeenCalled()
    })

    it('calls onDeleteConversation when clicking delete button', async () => {
      const user = userEvent.setup({ delay: null })
      const onDeleteConversation = vi.fn()
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} onDeleteConversation={onDeleteConversation} />)
      
      // Multiple delete buttons due to desktop/mobile views
      const deleteButtons = screen.getAllByRole('button', { name: /delete conversation/i })
      await user.click(deleteButtons[0])
      
      expect(onDeleteConversation).toHaveBeenCalledWith('1', expect.any(Object))
    })

    it('stops propagation when clicking delete button', async () => {
      const user = userEvent.setup({ delay: null })
      const onSelectConversation = vi.fn()
      const onDeleteConversation = vi.fn()
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(
        <ChatSidebar 
          {...defaultProps} 
          history={history} 
          onSelectConversation={onSelectConversation}
          onDeleteConversation={onDeleteConversation} 
        />
      )
      
      // Multiple delete buttons due to desktop/mobile views
      const deleteButtons = screen.getAllByRole('button', { name: /delete conversation/i })
      await user.click(deleteButtons[0])
      
      // Delete was called
      expect(onDeleteConversation).toHaveBeenCalled()
      // Select was NOT called (propagation stopped)
      expect(onSelectConversation).not.toHaveBeenCalled()
    })

    it('calls onLogout when clicking logout button', async () => {
      const user = userEvent.setup({ delay: null })
      const onLogout = vi.fn()
      
      render(<ChatSidebar {...defaultProps} onLogout={onLogout} />)
      
      const logoutButton = screen.getAllByRole('button').find(
        btn => btn.querySelector('svg.lucide-log-out')
      )
      await user.click(logoutButton!)
      
      expect(onLogout).toHaveBeenCalled()
    })
  })

  describe('Delete All', () => {
    it('renders delete all button when history has items', () => {
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Multiple buttons due to desktop/mobile views
      const deleteAllButtons = screen.getAllByRole('button', { name: /delete all/i })
      expect(deleteAllButtons.length).toBeGreaterThan(0)
    })

    it('hides delete all button when history is empty', () => {
      render(<ChatSidebar {...defaultProps} history={[]} />)
      
      expect(screen.queryByRole('button', { name: /delete all/i })).not.toBeInTheDocument()
    })

    it('hides delete all button when onDeleteAll is not provided', () => {
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} onDeleteAll={undefined} />)
      
      expect(screen.queryByRole('button', { name: /delete all/i })).not.toBeInTheDocument()
    })

    it('calls onDeleteAll when clicking delete all button', async () => {
      const user = userEvent.setup({ delay: null })
      const onDeleteAll = vi.fn()
      const history = [createMockConversation('1', 'My Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} onDeleteAll={onDeleteAll} />)
      
      // Multiple buttons due to desktop/mobile views
      const deleteAllButtons = screen.getAllByRole('button', { name: /delete all/i })
      await user.click(deleteAllButtons[0])
      
      expect(onDeleteAll).toHaveBeenCalled()
    })
  })

  describe('Collapsible Groups', () => {
    it('renders collapsible triggers for date groups', () => {
      const history = [createMockConversation('1', 'Today Chat', 0)]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Multiple elements due to desktop/mobile views
      const todayElements = screen.getAllByText('Today')
      expect(todayElements.length).toBeGreaterThan(0)
    })

    it('shows conversation count in group header', () => {
      const history = [
        createMockConversation('1', 'Chat 1', 0),
        createMockConversation('2', 'Chat 2', 0),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Multiple elements due to desktop/mobile views
      const countElements = screen.getAllByText('2')
      expect(countElements.length).toBeGreaterThan(0)
    })
  })

  describe('Date Grouping', () => {
    it('groups conversations correctly by date', () => {
      const history = [
        createMockConversation('1', 'Today', 0),
        createMockConversation('2', 'Yesterday', 1),
        createMockConversation('3', 'Week', 3),
        createMockConversation('4', 'Month', 15),
        createMockConversation('5', 'Old', 60),
      ]
      
      render(<ChatSidebar {...defaultProps} history={history} />)
      
      // Use getAllByText for elements that appear in both desktop/mobile views
      expect(screen.getAllByText(/^Today$/)[0]).toBeInTheDocument()
      expect(screen.getAllByText('Yesterday')[0]).toBeInTheDocument()
      expect(screen.getAllByText('This Week')[0]).toBeInTheDocument()
      expect(screen.getAllByText('This Month')[0]).toBeInTheDocument()
      expect(screen.getAllByText('Older')[0]).toBeInTheDocument()
    })
  })

  describe('Sidebar Collapse', () => {
    it('shows collapse button in full sidebar', () => {
      render(<ChatSidebar {...defaultProps} />)
      
      const collapseButtons = screen.getAllByRole('button', { name: /collapse sidebar/i })
      expect(collapseButtons.length).toBeGreaterThan(0)
    })
  })

  describe('Mobile View', () => {
    it('renders mobile overlay when isOpen is true', () => {
      render(<ChatSidebar {...defaultProps} isOpen={true} />)
      
      // The mobile drawer should be rendered
      const conversations = screen.getAllByText('Conversations')
      expect(conversations.length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('User Info', () => {
    it('does not render user section when user is null', () => {
      render(<ChatSidebar {...defaultProps} user={null} />)
      
      expect(screen.queryByText('testuser')).not.toBeInTheDocument()
    })

    it('renders user section when user is provided', () => {
      render(<ChatSidebar {...defaultProps} user={mockUser} />)
      
      // Multiple elements due to desktop/mobile views
      const userElements = screen.getAllByText('testuser')
      expect(userElements.length).toBeGreaterThan(0)
    })
  })
})
