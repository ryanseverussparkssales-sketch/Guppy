import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Search, Plus, Trash2, MessageSquare } from 'lucide-react'
import type { Conversation } from '@/hooks/useChatHistory'

interface ChatHistorySidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  loading: boolean
  onSelectConversation: (convId: string) => void
  onCreateNew: () => void
  onDeleteConversation: (convId: string) => void
  onSearch: (query: string) => void
  searchResults?: Conversation[]
}

export function ChatHistorySidebar({
  conversations,
  activeConversationId,
  loading,
  onSelectConversation,
  onCreateNew,
  onDeleteConversation,
  onSearch,
  searchResults,
}: ChatHistorySidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [showSearch, setShowSearch] = useState(false)

  const displayConversations = searchQuery && searchResults ? searchResults : conversations
  const isEmpty = displayConversations.length === 0

  const handleSearch = (value: string) => {
    setSearchQuery(value)
    onSearch(value)
  }

  return (
    <aside className="w-72 bg-surface-container-lowest border-r border-outline-variant/10 flex flex-col h-[calc(100vh-80px)] overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-outline-variant/10">
        <div className="flex items-center justify-between gap-2 mb-3">
          <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">
            {searchQuery ? 'Search Results' : 'Chat History'}
          </h3>
          <button
            onClick={onCreateNew}
            disabled={loading}
            className="p-1.5 hover:bg-surface-container rounded-lg transition-colors text-on-surface-variant hover:text-on-surface"
            title="New conversation"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full bg-surface-container px-3 py-2 rounded-lg text-xs text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {searchQuery && (
            <button
              onClick={() => handleSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-on-surface-variant/50 hover:text-on-surface-variant"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center">
            <p className="text-xs text-on-surface-variant italic">Loading conversations...</p>
          </div>
        ) : isEmpty ? (
          <div className="p-6 text-center">
            <MessageSquare className="w-8 h-8 text-on-surface-variant/30 mx-auto mb-2" />
            <p className="text-xs text-on-surface-variant italic">
              {searchQuery ? 'No conversations found' : 'No conversations yet'}
            </p>
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {displayConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={cn(
                  'group relative p-3 rounded-lg cursor-pointer transition-all duration-200 hover:bg-surface-container',
                  activeConversationId === conv.id && 'bg-primary/10 ring-1 ring-primary'
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p
                      className={cn(
                        'text-xs font-bold truncate',
                        activeConversationId === conv.id ? 'text-primary' : 'text-on-surface'
                      )}
                    >
                      {conv.title}
                    </p>
                    <p className="text-xs text-on-surface-variant/60 mt-0.5">
                      {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
                    </p>
                  </div>

                  {/* Delete Button (shows on hover) */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm(`Delete "${conv.title}"?`)) {
                        onDeleteConversation(conv.id)
                      }
                    }}
                    className="p-1 opacity-0 group-hover:opacity-100 transition-opacity text-on-surface-variant hover:text-error"
                    title="Delete conversation"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Info */}
      {!isEmpty && (
        <div className="p-3 border-t border-outline-variant/10 bg-surface-container text-center">
          <p className="text-xs text-on-surface-variant/60">
            {displayConversations.length} conversation{displayConversations.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </aside>
  )
}
