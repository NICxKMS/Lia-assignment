import { describe, it, expect } from 'vitest'
import { cn } from '../lib/utils'

describe('utils', () => {
  describe('cn (className utility)', () => {
    it('merges class names', () => {
      const result = cn('class1', 'class2')
      expect(result).toBe('class1 class2')
    })

    it('handles undefined values', () => {
      const result = cn('class1', undefined, 'class2')
      expect(result).toBe('class1 class2')
    })

    it('handles null values', () => {
      const result = cn('class1', null, 'class2')
      expect(result).toBe('class1 class2')
    })

    it('handles false values', () => {
      const result = cn('class1', false, 'class2')
      expect(result).toBe('class1 class2')
    })

    it('handles conditional classes', () => {
      const isActive = true
      const isDisabled = false
      
      const result = cn(
        'base-class',
        isActive && 'active',
        isDisabled && 'disabled'
      )
      
      expect(result).toBe('base-class active')
    })

    it('handles empty string', () => {
      const result = cn('class1', '', 'class2')
      expect(result).toBe('class1 class2')
    })

    it('handles arrays of classes', () => {
      const result = cn(['class1', 'class2'], 'class3')
      expect(result).toBe('class1 class2 class3')
    })

    it('handles objects with boolean values', () => {
      const result = cn({
        'class1': true,
        'class2': false,
        'class3': true,
      })
      
      expect(result).toBe('class1 class3')
    })

    it('merges Tailwind classes correctly', () => {
      // tailwind-merge should handle conflicting classes
      const result = cn('p-4', 'p-2')
      expect(result).toBe('p-2')
    })

    it('merges conflicting color classes', () => {
      const result = cn('text-red-500', 'text-blue-500')
      expect(result).toBe('text-blue-500')
    })

    it('merges conflicting size classes', () => {
      const result = cn('w-4', 'w-8')
      expect(result).toBe('w-8')
    })

    it('keeps non-conflicting classes', () => {
      const result = cn('p-4', 'm-2', 'text-lg')
      expect(result).toBe('p-4 m-2 text-lg')
    })

    it('handles complex combinations', () => {
      const variant: string = 'primary'
      const size: string = 'lg'
      
      const result = cn(
        'base-class',
        {
          'variant-primary': variant === 'primary',
          'variant-secondary': variant === 'secondary',
        },
        size === 'lg' && 'size-lg',
        ['extra-class-1', 'extra-class-2']
      )
      
      expect(result).toBe('base-class variant-primary size-lg extra-class-1 extra-class-2')
    })

    it('handles no arguments', () => {
      const result = cn()
      expect(result).toBe('')
    })

    it('handles single argument', () => {
      const result = cn('single-class')
      expect(result).toBe('single-class')
    })

    it('handles responsive classes', () => {
      const result = cn('p-2', 'sm:p-4', 'md:p-6', 'lg:p-8')
      expect(result).toBe('p-2 sm:p-4 md:p-6 lg:p-8')
    })

    it('handles hover and focus states', () => {
      const result = cn('bg-blue-500', 'hover:bg-blue-600', 'focus:bg-blue-700')
      expect(result).toBe('bg-blue-500 hover:bg-blue-600 focus:bg-blue-700')
    })

    it('handles dark mode classes', () => {
      const result = cn('text-gray-900', 'dark:text-gray-100')
      expect(result).toBe('text-gray-900 dark:text-gray-100')
    })
  })
})
