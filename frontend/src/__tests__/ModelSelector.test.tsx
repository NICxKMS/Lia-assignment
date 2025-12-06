import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ModelSelector, ModelDropdown, ModelBadgeSelector } from '../components/ai-elements/model-selector'
import { defaultModels } from '../components/ai-elements/model-data'
import type { AIModel } from '../components/ai-elements/model-data'

// Sample test models
const testModels: AIModel[] = [
  {
    id: 'model-1',
    name: 'Model One',
    provider: 'Provider A',
    description: 'First model description',
    capabilities: ['fast', 'code'],
    badge: 'New',
  },
  {
    id: 'model-2',
    name: 'Model Two',
    provider: 'Provider A',
    capabilities: ['reasoning'],
  },
  {
    id: 'model-3',
    name: 'Model Three',
    provider: 'Provider B',
    description: 'Third model',
  },
]

// Note: Radix UI Select has issues with pointer events in jsdom,
// so we test basic rendering and avoid clicking on the select dropdown

describe('ModelSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders the select component', () => {
      render(<ModelSelector models={testModels} />)
      
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })

    it('shows placeholder when no value is selected', () => {
      render(<ModelSelector models={testModels} placeholder="Choose a model" />)
      
      expect(screen.getByRole('combobox')).toHaveTextContent('Choose a model')
    })

    it('displays selected model name', () => {
      render(<ModelSelector models={testModels} value="model-1" />)
      
      expect(screen.getByRole('combobox')).toHaveTextContent('Model One')
    })

    it('renders with default select model placeholder', () => {
      render(<ModelSelector models={testModels} />)
      
      expect(screen.getByRole('combobox')).toHaveTextContent('Select model')
    })
  })

  describe('Styling', () => {
    it('applies custom className', () => {
      render(<ModelSelector models={testModels} className="custom-class" />)
      
      const trigger = screen.getByRole('combobox')
      expect(trigger).toHaveClass('custom-class')
    })
  })

  describe('Default Models', () => {
    it('uses defaultModels correctly', () => {
      render(<ModelSelector models={defaultModels} value="gemini-2.5-flash" />)
      
      expect(screen.getByRole('combobox')).toHaveTextContent('Gemini 2.5 Flash')
    })

    it('shows different model when value changes', () => {
      render(<ModelSelector models={defaultModels} value="gpt-4o" />)
      
      expect(screen.getByRole('combobox')).toHaveTextContent('GPT-4o')
    })
  })
})

describe('ModelDropdown', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders as a combobox', () => {
      render(<ModelDropdown models={testModels} />)
      
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })

    it('shows "Select model" when no value', () => {
      render(<ModelDropdown models={testModels} />)
      
      expect(screen.getByText('Select model')).toBeInTheDocument()
    })

    it('displays selected model', () => {
      render(<ModelDropdown models={testModels} value="model-2" />)
      
      expect(screen.getByText('Model Two')).toBeInTheDocument()
    })
  })

  describe('Dropdown Menu', () => {
    it('opens dropdown on click', async () => {
      const user = userEvent.setup({ delay: null })
      render(<ModelDropdown models={testModels} />)
      
      await user.click(screen.getByRole('combobox'))
      
      // Menu items should be visible
      await waitFor(() => {
        expect(screen.getAllByRole('menuitem').length).toBeGreaterThan(0)
      })
    })

    it('calls onValueChange when selecting', async () => {
      const user = userEvent.setup({ delay: null })
      const onValueChange = vi.fn()
      render(<ModelDropdown models={testModels} onValueChange={onValueChange} />)
      
      await user.click(screen.getByRole('combobox'))
      
      await waitFor(async () => {
        const items = screen.getAllByRole('menuitem')
        await user.click(items[0])
      })
      
      expect(onValueChange).toHaveBeenCalled()
    })
  })
})

describe('ModelBadgeSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders as compact badge button', () => {
      const { container } = render(<ModelBadgeSelector models={testModels} />)
      
      // Should have rounded-full class for badge style
      const button = container.querySelector('button')
      expect(button).toHaveClass('rounded-full')
    })

    it('shows "Model" when no value', () => {
      render(<ModelBadgeSelector models={testModels} />)
      
      expect(screen.getByText('Model')).toBeInTheDocument()
    })

    it('displays selected model name', () => {
      render(<ModelBadgeSelector models={testModels} value="model-1" />)
      
      expect(screen.getByText('Model One')).toBeInTheDocument()
    })
  })

  describe('Dropdown', () => {
    it('opens dropdown on click', async () => {
      const user = userEvent.setup({ delay: null })
      render(<ModelBadgeSelector models={testModels} />)
      
      const button = screen.getByRole('button')
      await user.click(button)
      
      await waitFor(() => {
        expect(screen.getAllByRole('menuitem').length).toBe(3)
      })
    })

    it('calls onValueChange when selecting', async () => {
      const user = userEvent.setup({ delay: null })
      const onValueChange = vi.fn()
      render(<ModelBadgeSelector models={testModels} onValueChange={onValueChange} />)
      
      const button = screen.getByRole('button')
      await user.click(button)
      
      await waitFor(async () => {
        const items = screen.getAllByRole('menuitem')
        await user.click(items[1])
      })
      
      expect(onValueChange).toHaveBeenCalledWith('model-2')
    })
  })

  describe('Styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <ModelBadgeSelector models={testModels} className="custom-badge" />
      )
      
      const button = container.querySelector('button')
      expect(button).toHaveClass('custom-badge')
    })
  })
})

describe('model-data', () => {
  describe('defaultModels', () => {
    it('has correct structure', () => {
      defaultModels.forEach(model => {
        expect(model).toHaveProperty('id')
        expect(model).toHaveProperty('name')
        expect(model).toHaveProperty('provider')
      })
    })

    it('contains expected models', () => {
      const modelIds = defaultModels.map(m => m.id)
      
      expect(modelIds).toContain('gemini-2.5-flash')
      expect(modelIds).toContain('gpt-4o')
      expect(modelIds).toContain('gpt-4.1')
    })

    it('has valid capabilities', () => {
      const validCapabilities = ['reasoning', 'vision', 'code', 'fast']
      
      defaultModels.forEach(model => {
        if (model.capabilities) {
          model.capabilities.forEach(cap => {
            expect(validCapabilities).toContain(cap)
          })
        }
      })
    })
  })
})
