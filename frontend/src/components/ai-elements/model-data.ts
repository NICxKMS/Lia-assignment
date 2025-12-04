// Model type definition
export interface AIModel {
  id: string
  name: string
  provider: string
  description?: string
  capabilities?: ('reasoning' | 'vision' | 'code' | 'fast')[]
  icon?: React.ReactNode
  badge?: string
}

// Pre-configured model lists
export const defaultModels: AIModel[] = [
  { 
    id: 'gemini-2.5-flash', 
    name: 'Gemini 2.5 Flash', 
    provider: 'Google',
    capabilities: ['fast', 'reasoning'],
    badge: 'New'
  },
  { 
    id: 'gemini-2.5-pro', 
    name: 'Gemini 2.5 Pro', 
    provider: 'Google',
    capabilities: ['reasoning', 'code'],
  },
  { 
    id: 'gemini-2.5-flash-lite', 
    name: 'Gemini 2.5 Flash Lite', 
    provider: 'Google',
    capabilities: ['fast'],
  },
  { 
    id: 'gpt-4o', 
    name: 'GPT-4o', 
    provider: 'OpenAI',
    capabilities: ['vision', 'reasoning', 'code'],
  },
  { 
    id: 'gpt-4', 
    name: 'GPT-4', 
    provider: 'OpenAI',
    capabilities: ['reasoning', 'code'],
  },
  { 
    id: 'gpt-3.5-turbo', 
    name: 'GPT-3.5 Turbo', 
    provider: 'OpenAI',
    capabilities: ['fast'],
  },
]
