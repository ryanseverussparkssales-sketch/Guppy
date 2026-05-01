import { useEffect, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { HighlighterCore, LanguageRegistration, ThemeRegistration } from 'shiki/core'
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

let _highlighterPromise: Promise<HighlighterCore> | null = null
function getHighlighter() {
  if (!_highlighterPromise) {
    _highlighterPromise = Promise.all([
      import('shiki/core'),
      import('@shikijs/engine-javascript'),
      import('@shikijs/themes/github-dark'),
      import('@shikijs/langs/python'),
      import('@shikijs/langs/javascript'),
      import('@shikijs/langs/typescript'),
      import('@shikijs/langs/tsx'),
      import('@shikijs/langs/jsx'),
      import('@shikijs/langs/bash'),
      import('@shikijs/langs/json'),
      import('@shikijs/langs/markdown'),
      import('@shikijs/langs/html'),
      import('@shikijs/langs/css'),
      import('@shikijs/langs/sql'),
      import('@shikijs/langs/yaml'),
      import('@shikijs/langs/toml'),
      import('@shikijs/langs/rust'),
      import('@shikijs/langs/go'),
    ]).then(([core, engine, theme, ...languageModules]) => {
      const langs = languageModules.flatMap((module) => module.default) as LanguageRegistration[]
      return core.createHighlighterCore({
        themes: [theme.default as ThemeRegistration],
        langs,
        engine: engine.createJavaScriptRegexEngine(),
      })
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
  const [copied, setCopied] = useState(false)
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

  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {})
  }

  if (inline) {
    return (
      <code className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[0.85em] font-mono">
        {children}
      </code>
    )
  }

  return (
    <div className="my-3 rounded-lg overflow-hidden text-sm border border-white/[0.08] bg-[#0d1117]">
      {/* Header: language label + copy button */}
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-white/[0.08] bg-white/[0.03]">
        <span className="text-[11px] text-white/40 font-mono tracking-wide">
          {lang ?? 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[11px] text-white/40 hover:text-white/80 transition-colors select-none"
        >
          {copied ? (
            <><Check className="w-3 h-3" />Copied</>
          ) : (
            <><Copy className="w-3 h-3" />Copy</>
          )}
        </button>
      </div>

      {html ? (
        <div
          className="text-sm [&>pre]:p-4 [&>pre]:overflow-x-auto [&>pre]:m-0"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="p-4 overflow-x-auto text-sm bg-muted">
          <code className="font-mono">{children}</code>
        </pre>
      )}
    </div>
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
