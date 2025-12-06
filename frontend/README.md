# Lia Chatbot Frontend

**Author: Nikhil Kumar**

A modern, responsive React application for the Lia AI Chatbot with real-time streaming, sentiment visualization, and a professional dashboard interface.

<p align="center">
  <img src="https://img.shields.io/badge/React-19.2-61DAFB?style=for-the-badge&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?style=for-the-badge&logo=typescript" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Vite-Rolldown-646CFF?style=for-the-badge&logo=vite" alt="Vite" />
  <img src="https://img.shields.io/badge/TailwindCSS-4.1-06B6D4?style=for-the-badge&logo=tailwindcss" alt="TailwindCSS" />
</p>

---

## Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [Testing](#-testing)
- [Architecture](#-architecture)
- [Styling](#-styling)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Real-time Streaming** | SSE-based token-by-token response display |
| **Sentiment Dashboard** | Visual sentiment analysis with charts |
| **Multi-Model Support** | Switch between Gemini and OpenAI models |
| **Conversation Management** | Create, rename, delete conversations |
| **Markdown Rendering** | Full markdown support with syntax highlighting |
| **Dark Mode** | Professional dark theme design |
| **Responsive Design** | Works on desktop, tablet, and mobile |
| **Authentication** | JWT-based login and registration |

---

## 🛠 Tech Stack

### Core

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2 | UI framework |
| TypeScript | 5.9 | Type safety |
| Vite | (Rolldown) | Build tool & dev server |

### Styling & UI

| Technology | Purpose |
|------------|---------|
| TailwindCSS 4.1 | Utility-first CSS |
| Radix UI | Accessible primitives |
| Framer Motion | Animations |
| Lucide React | Icon library |

### State & Data

| Technology | Purpose |
|------------|---------|
| TanStack Query 5.90 | Server state management |
| Axios | HTTP client |
| React Context | Auth state |

### Visualization

| Technology | Purpose |
|------------|---------|
| Recharts | Sentiment charts |
| react-markdown | Markdown rendering |
| rehype-highlight | Syntax highlighting |

### Testing

| Technology | Purpose |
|------------|---------|
| Vitest | Test runner |
| React Testing Library | Component testing |
| Happy DOM | DOM environment |

---

## 📁 Project Structure

```
frontend/
├── src/
│   ├── main.tsx                 # Application entry point
│   ├── App.tsx                  # Root component with providers
│   ├── App.css                  # Global styles
│   ├── index.css                # Tailwind imports
│   │
│   ├── components/
│   │   ├── chat/                # Chat UI components
│   │   │   ├── ChatInterface.tsx    # Main chat container
│   │   │   ├── ChatInput.tsx        # Message input with model selector
│   │   │   ├── ChatSidebar.tsx      # Conversation list sidebar
│   │   │   ├── ChatInspector.tsx    # Sentiment analysis panel
│   │   │   └── MessageList.tsx      # Message display list
│   │   │
│   │   ├── ui/                  # Reusable UI primitives (Radix-based)
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── select.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── alert.tsx
│   │   │   ├── label.tsx
│   │   │   ├── separator.tsx
│   │   │   └── collapsible.tsx
│   │   │
│   │   ├── ai-elements/         # AI-specific UI components
│   │   ├── AuthPage.tsx         # Login/Register page
│   │   └── MarkdownMessage.tsx  # Markdown renderer
│   │
│   ├── context/                 # React Context
│   │   ├── AuthContext.ts       # Auth context definition
│   │   ├── AuthProvider.tsx     # Auth state provider
│   │   ├── useAuth.ts           # Auth hook
│   │   └── index.ts             # Exports
│   │
│   ├── lib/                     # Utilities
│   │   ├── api.ts               # Axios API client
│   │   ├── useChat.ts           # Chat hook with SSE
│   │   └── utils.ts             # Helper functions (cn, etc.)
│   │
│   └── __tests__/               # Test files
│       ├── test-utils.tsx       # Test utilities
│       ├── AuthPage.test.tsx
│       ├── AuthProvider.test.tsx
│       ├── ChatInput.test.tsx
│       ├── ChatInspector.test.tsx
│       ├── ChatSidebar.test.tsx
│       ├── MessageList.test.tsx
│       ├── MarkdownMessage.test.tsx
│       ├── ModelSelector.test.tsx
│       ├── UIComponents.test.tsx
│       ├── useChat.test.ts
│       ├── api.test.ts
│       ├── utils.test.ts
│       └── Integration.test.tsx
│
├── public/                      # Static assets
├── index.html                   # HTML template
├── package.json                 # Dependencies
├── pnpm-lock.yaml               # Lock file
├── vite.config.ts               # Vite configuration
├── vitest.config.ts             # Vitest configuration
├── tailwind.config.js           # Tailwind configuration
├── tsconfig.json                # TypeScript config
├── tsconfig.app.json            # App-specific TS config
├── tsconfig.node.json           # Node-specific TS config
├── eslint.config.js             # ESLint configuration
├── components.json              # shadcn/ui configuration
└── README.md                    # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js 20+**
- **pnpm** (recommended) or npm

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
pnpm install

# Create environment file
echo "VITE_API_URL=http://localhost:8000" > .env

# Start development server
pnpm dev
```

### Access

Open **http://localhost:5173** in your browser.

---

## 💻 Development

### Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start development server with HMR |
| `pnpm build` | Build for production |
| `pnpm preview` | Preview production build |
| `pnpm test` | Run test suite |
| `pnpm lint` | Run ESLint |

### Environment Variables

| Variable | Description | Required |
|----------|-------------|:--------:|
| `VITE_API_URL` | Backend API URL | ✅ |

### Development Server

The development server runs on **http://localhost:5173** with:
- Hot Module Replacement (HMR)
- Fast refresh for React components
- TypeScript type checking

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests (300 tests, ~6s)
pnpm test

# Run with UI
pnpm test -- --ui

# Run with coverage
pnpm test -- --coverage

# Run specific file
pnpm test -- src/__tests__/ChatInput.test.tsx

# Watch mode
pnpm test -- --watch
```

### Test Stats

- **300 tests** across 14 test files
- **~6 seconds** total runtime
- Optimized with `userEvent.setup({ delay: null })`
- Fast form filling with `fillInput()` helper

### Test Structure

| File | Tests | Coverage |
|------|-------|----------|
| `AuthPage.test.tsx` | 24 | Login/Register forms |
| `AuthProvider.test.tsx` | 11 | Auth context behavior |
| `ChatInput.test.tsx` | 29 | Message input component |
| `ChatInspector.test.tsx` | 22 | Sentiment panel |
| `ChatSidebar.test.tsx` | 29 | Conversation list |
| `MessageList.test.tsx` | 22 | Message display |
| `MarkdownMessage.test.tsx` | 27 | Markdown rendering |
| `ModelSelector.test.tsx` | 21 | Model dropdown |
| `UIComponents.test.tsx` | 51 | UI primitives |
| `useChat.test.ts` | 19 | Chat hook logic |
| `api.test.ts` | 14 | API client |
| `utils.test.ts` | 18 | Utility functions |
| `Integration.test.tsx` | 9 | Full flow tests |
| `ChatInterface.test.tsx` | 4 | Main container |

### Test Utilities

```typescript
// src/__tests__/test-utils.tsx
import { render } from './test-utils'

// Renders with all providers (Auth, Query, etc.)
render(<MyComponent />)
```

---

## 🏗 Architecture

### Component Hierarchy

```
App
├── QueryClientProvider (TanStack Query)
└── AuthProvider (Context)
    ├── AuthPage (when not authenticated)
    │   ├── LoginForm
    │   └── RegisterForm
    │
    └── ChatInterface (when authenticated)
        ├── ChatSidebar
        │   ├── NewChatButton
        │   └── ConversationList
        │       └── ConversationItem (×n)
        │
        ├── MessageList
        │   └── MarkdownMessage (×n)
        │
        ├── ChatInput
        │   ├── ModelSelector
        │   ├── SentimentMethodSelector
        │   └── SendButton
        │
        └── ChatInspector
            ├── SentimentGauge
            ├── SentimentChart (Recharts)
            └── MessageMetadata
```

### State Management

| State Type | Solution | Usage |
|------------|----------|-------|
| **Server State** | TanStack Query | Conversations, messages, models |
| **Auth State** | React Context | User, token, login/logout |
| **UI State** | useState/useReducer | Input, selections, UI toggles |

### Data Flow

```
User Action
    │
    ▼
Component (ChatInput)
    │
    ▼
Custom Hook (useChat)
    │
    ▼
API Client (axios)
    │
    ▼
Backend (FastAPI)
    │
    ▼
SSE Stream
    │
    ▼
State Update
    │
    ▼
UI Re-render (MessageList)
```

### SSE Streaming

```typescript
// lib/useChat.ts
const eventSource = new EventSource(url);

eventSource.addEventListener('chunk', (e) => {
  const data = JSON.parse(e.data);
  appendToken(data.content);
});

eventSource.addEventListener('sentiment', (e) => {
  const data = JSON.parse(e.data);
  setSentiment(data);
});

eventSource.addEventListener('done', () => {
  eventSource.close();
});
```

---

## 🎨 Styling

### Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Custom color palette
      }
    }
  },
  plugins: [
    require('tailwindcss-animate')
  ]
}
```

### CSS Utilities

```typescript
// lib/utils.ts
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Theme

The application uses a **dark-first** design:

| Element | Color |
|---------|-------|
| Background | Zinc 950 (`#09090b`) |
| Surface | Zinc 900 (`#18181b`) |
| Border | Zinc 800 (`#27272a`) |
| Text | Zinc 100 (`#f4f4f5`) |
| Accent | Blue 500 (`#3b82f6`) |

### Component Variants

Using `class-variance-authority` for component variants:

```typescript
// ui/button.tsx
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md...",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground...",
        destructive: "bg-destructive text-destructive-foreground...",
        outline: "border border-input bg-background...",
        ghost: "hover:bg-accent hover:text-accent-foreground...",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)
```

---

## 📦 Key Dependencies

### Production

```json
{
  "react": "^19.2.0",
  "react-dom": "^19.2.0",
  "@tanstack/react-query": "^5.90.11",
  "axios": "^1.13.2",
  "tailwindcss": "^4.1.17",
  "@radix-ui/react-*": "latest",
  "framer-motion": "^12.23.25",
  "recharts": "^3.5.1",
  "react-markdown": "^9.0.1",
  "lucide-react": "^0.555.0"
}
```

### Development

```json
{
  "typescript": "~5.9.3",
  "vite": "npm:rolldown-vite@7.2.5",
  "vitest": "^4.0.15",
  "@testing-library/react": "^16.3.0",
  "@testing-library/jest-dom": "^6.9.1",
  "eslint": "^9.39.1"
}
```

---

## 🚀 Build & Deployment

### Production Build

```bash
pnpm build
```

Output is in `dist/` directory.

### Deployment (Vercel)

1. Connect your GitHub repository to Vercel
2. Configure environment variables:
   - `VITE_API_URL`: Your backend API URL
3. Deploy automatically on push

### Preview

```bash
pnpm preview
```

Serves the production build locally at **http://localhost:4173**.

---

## 📖 Related Documentation

| Document | Description |
|----------|-------------|
| [../README.md](../README.md) | Project overview |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | System architecture |
| [../backend/README.md](../backend/README.md) | Backend documentation |

---

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details.
