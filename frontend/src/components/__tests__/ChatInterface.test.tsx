import { render, screen, fireEvent } from '@testing-library/react';
import ChatInterface from '../chat/ChatInterface';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../../context';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Polyfill TextEncoder/TextDecoder
class TextEncoder {
  encoding = "utf-8";
  encode(input?: string): Uint8Array {
    const utf8 = unescape(encodeURIComponent(input || ""));
    const result = new Uint8Array(utf8.length);
    for (let i = 0; i < utf8.length; i++) {
      result[i] = utf8.charCodeAt(i);
    }
    return result;
  }
}

class TextDecoder {
  encoding = "utf-8";
  decode(input?: Uint8Array): string {
    if (!input) return "";
    let str = "";
    for (let i = 0; i < input.length; i++) {
      str += String.fromCharCode(input[i]);
    }
    return decodeURIComponent(escape(str));
  }
}
Object.assign(globalThis, { TextEncoder, TextDecoder });

// Mock the useChat hook
vi.mock('../../lib/useChat', () => ({
    useChat: () => ({
        messages: [],
        status: 'idle' as const,
        error: null,
        isStreaming: false,
        sendMessage: vi.fn(),
        setMessages: vi.fn(),
        clearMessages: vi.fn(),
        stop: vi.fn(),
        regenerate: vi.fn(),
    }),
}));

// Mock Recharts ResponsiveContainer
vi.mock('recharts', async () => {
    const OriginalModule = await vi.importActual('recharts');
    return {
        ...OriginalModule,
        ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div style={{ width: 500, height: 300 }}>{children}</div>,
    };
});

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: false,
        },
    },
});

const renderWithProviders = (ui: React.ReactNode) => {
    return render(
        <QueryClientProvider client={queryClient}>
            <AuthProvider>
                {ui}
            </AuthProvider>
        </QueryClientProvider>
    );
};

describe('ChatInterface', () => {
    beforeEach(() => {
        queryClient.clear();
    });

    it('renders the chat interface with input', () => {
        renderWithProviders(<ChatInterface />);
        // Check for input placeholder
        expect(screen.getByPlaceholderText(/Send a message.../i)).toBeInTheDocument();
    });

    it('renders sidebar with Conversations header', () => {
        renderWithProviders(<ChatInterface />);
        // Use getAllByText since there may be multiple elements matching
        const conversationsElements = screen.getAllByText(/Conversations/i);
        expect(conversationsElements.length).toBeGreaterThan(0);
    });

    it('allows typing in the input field', () => {
        renderWithProviders(<ChatInterface />);
        const input = screen.getByPlaceholderText(/Send a message.../i) as HTMLTextAreaElement;
        fireEvent.change(input, { target: { value: 'Hello' } });
        expect(input.value).toBe('Hello');
    });

    it('renders model selector', async () => {
        renderWithProviders(<ChatInterface />);
        
        // Find combobox triggers (Select components render as comboboxes)
        const selectTriggers = screen.getAllByRole('combobox');
        
        // Should have at least 1 select for model
        expect(selectTriggers.length).toBeGreaterThanOrEqual(1);
    });
});
