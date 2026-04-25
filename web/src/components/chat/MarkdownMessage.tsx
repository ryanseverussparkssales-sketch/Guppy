import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createHighlighter, type Highlighter } from 'shiki'
import DOMPurify from 'dompurify'

// Shiki produces only <pre><code><span> with class/style attrs — allow exactly that.
const PURIFY_CONFIG = {
  ALLOWED_TAGS: ['pre', 'code', 'span', 'div'] as string[],
  ALLOWED_ATTR: ['class', 'style', 'tabindex'] as string[],
  ALLOW_DATA_ATTR: false,
}

const SUPPORTED_LANGS = [
  'python', 'javascript', 'typescript', 'tsx', 'jsx',
  'bash', 'sh', 'json', 'markdown', 'html', 'css', 'sql',
  'yaml', 'toml', 'rust', 'go', 'text',
]

let _highlighterPromise: Promise<Highlighter> | null = null
function getHighlighter() {
  if (!_highlighterPromise) {
    _highlighterPromise = createHighlighter({
      themes: ['github-dark'],
      langs: SUPPORTED_LANGS,
    })
  }
  return _highlighterPromise
}

interface CodeBlockProps {
  className?: string
  children?: React.ReactNode
  inline?: boolean
}

function CodeBlock({ className, children, inline }: CodeBlockProps) {
  const [html, setHtml] = useState<string | null>(null)
  const code = String(children ?? '').replace(/\n$/, '')
  const lang = /language-(\w+)/.exec(className ?? '')?.[1]

  useEffect(() => {
    if (inline || !lang) return
    getHighlighter().then((hl) => {
      try {
        const knownLang = SUPPORTED_LANGS.includes(lang) ? lang : 'text'
        const raw = hl.codeToHtml(code, { lang: knownLang, theme: 'github-dark' })
        setHtml(DOMPurify.sanitize(raw, PURIFY_CONFIG) as string)
      } catch {
        setHtml(null)
      }
    })
  }, [code, lang, inline])

  if (inline) {
    return (
      <code className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[0.85em] font-mono">
        {children}
      </code>
    )
  }

  if (html) {
    return (
      <div
        className="my-3 rounded-lg overflow-hidden text-sm [&>pre]:p-4 [&>pre]:overflow-x-auto [&>pre]:m-0"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  }

  return (
    <pre className="my-3 p-4 rounded-lg bg-muted overflow-x-auto text-sm">
      <code className="font-mono">{children}</code>
    </pre>
  )
}

interface Props {
  content: string
  isUser?: boolean
}

export function MarkdownMessage({ content, isUser }: Props) {
  if (isUser) {
    return <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
  }

  return (
    <div className="text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }: any) {
            const isBlock = className?.startsWith('language-')
            return (
              <CodeBlock className={className} inline={!isBlock} {...props}>
                {children}
              </CodeBlock>
            )
          },
          p: ({ children }) => <p className="my-1">{children}</p>,
          ul: ({ children }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="my-1 ml-4 list-decimal space-y-0.5">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          h1: ({ children }) => <h1 className="text-base font-bold mt-3 mb-1">{children}</h1>,
          h2: ({ children }) => <h2 className="text-sm font-bold mt-2 mb-1">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-primary/50 pl-3 my-2 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full text-xs border-collapse border border-border rounded">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-border px-3 py-1.5 bg-muted text-left font-medium">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border px-3 py-1.5">{children}</td>
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          hr: () => <hr className="my-3 border-border" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
