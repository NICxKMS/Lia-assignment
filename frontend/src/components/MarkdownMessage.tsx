import React, { useState, useCallback, useMemo, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import { Check, Copy } from 'lucide-react'
import 'highlight.js/styles/github-dark.css'

interface MarkdownMessageProps {
  content: string
}

// Memoized plugins arrays to prevent re-creation
const remarkPlugins = [remarkGfm]
const rehypePlugins = [rehypeHighlight, rehypeRaw]

// Code block component with copy button - memoized
const CodeBlock = memo<{
  className?: string
  children?: React.ReactNode
}>(({ className, children }) => {
  const [copied, setCopied] = useState(false)
  
  const { language, codeString } = useMemo(() => {
    const match = /language-(\w+)/.exec(className || '')
    return {
      language: match ? match[1] : '',
      codeString: String(children).replace(/\n$/, '')
    }
  }, [className, children])
  
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(codeString)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [codeString])
  
  return (
    <div className="relative group my-4">
      {language && (
        <div className="absolute top-0 left-0 px-3 py-1 text-xs font-mono text-muted-foreground bg-muted/80 rounded-tl-lg rounded-br-lg border-r border-b border-border/50">
          {language}
        </div>
      )}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-md bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-all"
        aria-label="Copy code"
      >
        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
      </button>
      <pre className={`${className || ''} overflow-x-auto p-4 pt-8 rounded-lg bg-muted/50 border border-border`}>
        <code className={className}>{children}</code>
      </pre>
    </div>
  )
})

CodeBlock.displayName = 'CodeBlock'

// Inline code component - memoized
const InlineCode = memo<{ children?: React.ReactNode }>(({ children }) => (
  <code className="px-1.5 py-0.5 rounded-md bg-muted/70 text-accent font-mono text-sm">
    {children}
  </code>
))

InlineCode.displayName = 'InlineCode'

// Memoized components object to prevent re-creation on each render
const markdownComponents = {
  // Custom code block rendering
  pre: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  code: ({ className, children }: { className?: string; children?: React.ReactNode }) => {
    const isInline = !className && typeof children === 'string' && !children.includes('\n')
    
    if (isInline) {
      return <InlineCode>{children}</InlineCode>
    }
    
    return <CodeBlock className={className}>{children}</CodeBlock>
  },
  // Heading elements with proper hierarchy
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-2xl font-bold text-foreground mt-6 mb-3 pb-2 border-b border-border/50 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-xl font-bold text-foreground mt-5 mb-2 pb-1.5 border-b border-border/30 first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-lg font-semibold text-foreground mt-4 mb-2 first:mt-0">
      {children}
    </h3>
  ),
  h4: ({ children }: { children?: React.ReactNode }) => (
    <h4 className="text-base font-semibold text-foreground mt-3 mb-1.5 first:mt-0">
      {children}
    </h4>
  ),
  h5: ({ children }: { children?: React.ReactNode }) => (
    <h5 className="text-sm font-semibold text-foreground mt-3 mb-1 first:mt-0">
      {children}
    </h5>
  ),
  h6: ({ children }: { children?: React.ReactNode }) => (
    <h6 className="text-sm font-medium text-muted-foreground mt-3 mb-1 first:mt-0">
      {children}
    </h6>
  ),
  // Paragraph styling
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="my-3 leading-7 text-foreground/90 first:mt-0 last:mb-0">
      {children}
    </p>
  ),
  // Custom link rendering - open external links in new tab
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a 
      href={href} 
      target={href?.startsWith('http') ? '_blank' : undefined}
      rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
      className="text-primary underline underline-offset-2 hover:text-primary/80 transition-colors"
    >
      {children}
    </a>
  ),
  // Strong and emphasis
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-foreground/90">{children}</em>
  ),
  // List styling
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-3 ml-4 list-disc space-y-1.5 marker:text-muted-foreground first:mt-0 last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-3 ml-4 list-decimal space-y-1.5 marker:text-muted-foreground first:mt-0 last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="leading-7 text-foreground/90 pl-1">{children}</li>
  ),
  // Blockquote styling
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-4 border-l-4 border-primary/50 bg-muted/30 pl-4 pr-3 py-2 italic text-muted-foreground rounded-r-md first:mt-0 last:mb-0">
      {children}
    </blockquote>
  ),
  // Horizontal rule
  hr: () => (
    <hr className="my-6 border-t border-border" />
  ),
  // Table styling
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-border first:mt-0 last:mb-0">
      <table className="w-full border-collapse text-sm">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-muted/50">{children}</thead>
  ),
  tbody: ({ children }: { children?: React.ReactNode }) => (
    <tbody className="divide-y divide-border">{children}</tbody>
  ),
  tr: ({ children }: { children?: React.ReactNode }) => (
    <tr className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
      {children}
    </tr>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-4 py-2.5 text-left font-semibold text-foreground border-r border-border last:border-r-0">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-4 py-2.5 text-foreground/90 border-r border-border last:border-r-0">
      {children}
    </td>
  ),
  // Image styling
  img: ({ src, alt }: { src?: string; alt?: string }) => (
    <img 
      src={src} 
      alt={alt} 
      className="my-4 max-w-full rounded-lg shadow-md border border-border/50 first:mt-0 last:mb-0" 
    />
  ),
  // Task list items (GFM)
  input: ({ type, checked }: { type?: string; checked?: boolean }) => {
    if (type === 'checkbox') {
      return (
        <input 
          type="checkbox" 
          checked={checked} 
          readOnly 
          className="mr-2 h-4 w-4 rounded border-border accent-primary cursor-default"
        />
      )
    }
    return <input type={type} />
  },
  // Delete/strikethrough text
  del: ({ children }: { children?: React.ReactNode }) => (
    <del className="text-muted-foreground line-through">{children}</del>
  ),
}

const PROSE_CLASSES = `max-w-none text-foreground`

export const MarkdownMessage = memo<MarkdownMessageProps>(({ content }) => {
  return (
    <div className={PROSE_CLASSES}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})

MarkdownMessage.displayName = 'MarkdownMessage'

export default MarkdownMessage
