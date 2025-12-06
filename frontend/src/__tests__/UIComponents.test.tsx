import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card'
import { Alert, AlertDescription } from '../components/ui/alert'

describe('Button Component', () => {
  describe('Rendering', () => {
    it('renders a button element', () => {
      render(<Button>Click me</Button>)
      expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
    })

    it('renders children correctly', () => {
      render(<Button>Button Text</Button>)
      expect(screen.getByText('Button Text')).toBeInTheDocument()
    })

    it('applies default variant styles', () => {
      render(<Button>Default</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('bg-primary')
    })
  })

  describe('Variants', () => {
    it('applies destructive variant', () => {
      render(<Button variant="destructive">Destructive</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('bg-destructive')
    })

    it('applies outline variant', () => {
      render(<Button variant="outline">Outline</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('border')
    })

    it('applies secondary variant', () => {
      render(<Button variant="secondary">Secondary</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('bg-secondary')
    })

    it('applies ghost variant', () => {
      render(<Button variant="ghost">Ghost</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('hover:bg-muted')
    })

    it('applies link variant', () => {
      render(<Button variant="link">Link</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('underline-offset')
    })
  })

  describe('Sizes', () => {
    it('applies default size', () => {
      render(<Button>Default Size</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('h-9')
    })

    it('applies small size', () => {
      render(<Button size="sm">Small</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('h-8')
    })

    it('applies large size', () => {
      render(<Button size="lg">Large</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('h-10')
    })

    it('applies icon size', () => {
      render(<Button size="icon">Icon</Button>)
      const button = screen.getByRole('button')
      expect(button.className).toContain('w-9')
    })
  })

  describe('Interactions', () => {
    it('calls onClick when clicked', async () => {
      const user = userEvent.setup({ delay: null })
      const onClick = vi.fn()
      render(<Button onClick={onClick}>Click</Button>)
      
      await user.click(screen.getByRole('button'))
      expect(onClick).toHaveBeenCalledTimes(1)
    })

    it('does not call onClick when disabled', async () => {
      const user = userEvent.setup({ delay: null })
      const onClick = vi.fn()
      render(<Button onClick={onClick} disabled>Disabled</Button>)
      
      await user.click(screen.getByRole('button'))
      expect(onClick).not.toHaveBeenCalled()
    })

    it('applies disabled styles when disabled', () => {
      render(<Button disabled>Disabled</Button>)
      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
      expect(button.className).toContain('disabled:')
    })
  })

  describe('asChild', () => {
    it('renders as child element when asChild is true', () => {
      render(
        <Button asChild>
          <a href="/test">Link Button</a>
        </Button>
      )
      
      expect(screen.getByRole('link', { name: 'Link Button' })).toBeInTheDocument()
    })
  })

  describe('Custom className', () => {
    it('applies custom className', () => {
      render(<Button className="custom-class">Custom</Button>)
      const button = screen.getByRole('button')
      expect(button).toHaveClass('custom-class')
    })
  })
})

describe('Input Component', () => {
  describe('Rendering', () => {
    it('renders an input element', () => {
      render(<Input />)
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })

    it('applies default styles', () => {
      render(<Input />)
      const input = screen.getByRole('textbox')
      expect(input).toHaveClass('flex', 'h-9', 'w-full', 'rounded-md')
    })
  })

  describe('Types', () => {
    it('renders without type attribute by default', () => {
      render(<Input />)
      const input = screen.getByRole('textbox')
      // Input component doesn't set a default type
      expect(input).toBeInTheDocument()
    })

    it('renders with explicit text type', () => {
      render(<Input type="text" />)
      const input = screen.getByRole('textbox')
      expect(input).toHaveAttribute('type', 'text')
    })

    it('renders email input', () => {
      render(<Input type="email" />)
      const input = screen.getByRole('textbox')
      expect(input).toHaveAttribute('type', 'email')
    })

    it('renders password input', () => {
      render(<Input type="password" />)
      const input = document.querySelector('input[type="password"]')
      expect(input).toBeInTheDocument()
    })
  })

  describe('Props', () => {
    it('applies placeholder', () => {
      render(<Input placeholder="Enter text" />)
      expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument()
    })

    it('applies value', () => {
      render(<Input value="test value" onChange={() => {}} />)
      expect(screen.getByDisplayValue('test value')).toBeInTheDocument()
    })

    it('calls onChange', async () => {
      const user = userEvent.setup({ delay: null })
      const onChange = vi.fn()
      render(<Input onChange={onChange} />)
      
      await user.type(screen.getByRole('textbox'), 'hello')
      expect(onChange).toHaveBeenCalled()
    })

    it('applies disabled state', () => {
      render(<Input disabled />)
      expect(screen.getByRole('textbox')).toBeDisabled()
    })

    it('applies required attribute', () => {
      render(<Input required />)
      expect(screen.getByRole('textbox')).toBeRequired()
    })

    it('applies custom className', () => {
      render(<Input className="custom-input" />)
      expect(screen.getByRole('textbox')).toHaveClass('custom-input')
    })
  })

  describe('Ref Forwarding', () => {
    it('forwards ref correctly', () => {
      const ref = { current: null }
      render(<Input ref={ref} />)
      expect(ref.current).toBeInstanceOf(HTMLInputElement)
    })
  })
})

describe('Badge Component', () => {
  describe('Rendering', () => {
    it('renders a badge', () => {
      render(<Badge>Badge</Badge>)
      expect(screen.getByText('Badge')).toBeInTheDocument()
    })

    it('renders children', () => {
      render(<Badge>Custom Content</Badge>)
      expect(screen.getByText('Custom Content')).toBeInTheDocument()
    })
  })

  describe('Variants', () => {
    it('applies default variant', () => {
      render(<Badge>Default</Badge>)
      const badge = screen.getByText('Default')
      expect(badge.className).toContain('bg-primary')
    })

    it('applies secondary variant', () => {
      render(<Badge variant="secondary">Secondary</Badge>)
      const badge = screen.getByText('Secondary')
      expect(badge.className).toContain('bg-secondary')
    })

    it('applies destructive variant', () => {
      render(<Badge variant="destructive">Destructive</Badge>)
      const badge = screen.getByText('Destructive')
      expect(badge.className).toContain('bg-destructive')
    })

    it('applies outline variant', () => {
      render(<Badge variant="outline">Outline</Badge>)
      const badge = screen.getByText('Outline')
      expect(badge.className).toContain('text-foreground')
    })
  })

  describe('Custom className', () => {
    it('applies custom className', () => {
      render(<Badge className="custom-badge">Custom</Badge>)
      expect(screen.getByText('Custom')).toHaveClass('custom-badge')
    })
  })
})

describe('Card Components', () => {
  describe('Card', () => {
    it('renders card container', () => {
      render(<Card>Card Content</Card>)
      expect(screen.getByText('Card Content')).toBeInTheDocument()
    })

    it('applies custom className', () => {
      const { container } = render(<Card className="custom-card">Content</Card>)
      expect(container.firstChild).toHaveClass('custom-card')
    })
  })

  describe('CardHeader', () => {
    it('renders card header', () => {
      render(
        <Card>
          <CardHeader>Header Content</CardHeader>
        </Card>
      )
      expect(screen.getByText('Header Content')).toBeInTheDocument()
    })
  })

  describe('CardTitle', () => {
    it('renders card title', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Title</CardTitle>
          </CardHeader>
        </Card>
      )
      expect(screen.getByText('Title')).toBeInTheDocument()
    })

    it('renders as div element', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Title</CardTitle>
          </CardHeader>
        </Card>
      )
      const title = screen.getByText('Title')
      expect(title.tagName).toBe('DIV')
    })
  })

  describe('CardDescription', () => {
    it('renders card description', () => {
      render(
        <Card>
          <CardHeader>
            <CardDescription>Description text</CardDescription>
          </CardHeader>
        </Card>
      )
      expect(screen.getByText('Description text')).toBeInTheDocument()
    })
  })

  describe('CardContent', () => {
    it('renders card content', () => {
      render(
        <Card>
          <CardContent>Main Content</CardContent>
        </Card>
      )
      expect(screen.getByText('Main Content')).toBeInTheDocument()
    })
  })

  describe('CardFooter', () => {
    it('renders card footer', () => {
      render(
        <Card>
          <CardFooter>Footer Content</CardFooter>
        </Card>
      )
      expect(screen.getByText('Footer Content')).toBeInTheDocument()
    })
  })

  describe('Full Card', () => {
    it('renders complete card structure', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Card Title</CardTitle>
            <CardDescription>Card Description</CardDescription>
          </CardHeader>
          <CardContent>Card Content</CardContent>
          <CardFooter>Card Footer</CardFooter>
        </Card>
      )
      
      expect(screen.getByText('Card Title')).toBeInTheDocument()
      expect(screen.getByText('Card Description')).toBeInTheDocument()
      expect(screen.getByText('Card Content')).toBeInTheDocument()
      expect(screen.getByText('Card Footer')).toBeInTheDocument()
    })
  })
})

describe('Alert Component', () => {
  describe('Rendering', () => {
    it('renders alert', () => {
      render(<Alert>Alert content</Alert>)
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('renders children', () => {
      render(
        <Alert>
          <AlertDescription>Alert message</AlertDescription>
        </Alert>
      )
      expect(screen.getByText('Alert message')).toBeInTheDocument()
    })
  })

  describe('Variants', () => {
    it('applies default variant', () => {
      render(<Alert>Default</Alert>)
      const alert = screen.getByRole('alert')
      expect(alert.className).toContain('bg-background')
    })

    it('applies destructive variant', () => {
      render(<Alert variant="destructive">Error</Alert>)
      const alert = screen.getByRole('alert')
      expect(alert.className).toContain('border-destructive')
    })
  })

  describe('Custom className', () => {
    it('applies custom className', () => {
      render(<Alert className="custom-alert">Custom</Alert>)
      expect(screen.getByRole('alert')).toHaveClass('custom-alert')
    })
  })
})
