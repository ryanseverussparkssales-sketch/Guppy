import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MarkdownMessage } from '../components/chat/MarkdownMessage'

describe('MarkdownMessage', () => {
  it('renders user messages as plain text', () => {
    render(<MarkdownMessage content="Hello **world**" isUser />)
    expect(screen.getByText('Hello **world**')).toBeInTheDocument()
  })

  it('renders assistant markdown — bold text', () => {
    render(<MarkdownMessage content="Hello **world**" />)
    expect(screen.getByText('world').tagName).toBe('STRONG')
  })

  it('renders assistant markdown — inline code', () => {
    render(<MarkdownMessage content="Use `npm install`" />)
    expect(screen.getByText('npm install').tagName).toBe('CODE')
  })

  it('renders a link with target=_blank', () => {
    render(<MarkdownMessage content="See [docs](https://example.com)" />)
    const link = screen.getByRole('link', { name: 'docs' })
    expect(link).toHaveAttribute('href', 'https://example.com')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders GFM table', () => {
    const md = '| A | B |\n|---|---|\n| 1 | 2 |'
    render(<MarkdownMessage content={md} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
  })
})
