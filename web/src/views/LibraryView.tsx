/**
 * =============================================================================
 * LIBRARY VIEW
 * =============================================================================
 * 
 * Manage saved prompts, templates, and conversation artifacts.
 * 
 * BACKEND ENDPOINTS:
 * - GET /api/library/collections - List all collections
 * - POST /api/library/collections - Create collection
 * - GET /api/library/prompts - List saved prompts
 * - POST /api/library/prompts - Save prompt
 * - GET /api/library/templates - List templates
 * =============================================================================
 */

import { useState, useRef } from 'react'
import { toast } from 'sonner'
import {
  FolderOpen,
  Plus,
  Search,
  FileText,
  MessageSquare,
  Sparkles,
  Star,
  Clock,
  Copy,
  Trash2,
  Edit,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Types
interface LibraryItem {
  id: string
  type: 'prompt' | 'template' | 'artifact'
  title: string
  content: string
  collection?: string
  tags: string[]
  isFavorite: boolean
  createdAt: string
  updatedAt: string
}

interface Collection {
  id: string
  name: string
  itemCount: number
  color: string
}

// Mock data - replace with API
const MOCK_COLLECTIONS: Collection[] = [
  { id: 'coding', name: 'Coding', itemCount: 12, color: 'bg-blue-500' },
  { id: 'writing', name: 'Writing', itemCount: 8, color: 'bg-purple-500' },
  { id: 'analysis', name: 'Analysis', itemCount: 5, color: 'bg-green-500' },
]

const MOCK_ITEMS: LibraryItem[] = [
  {
    id: '1',
    type: 'prompt',
    title: 'Code Review Assistant',
    content: 'You are a senior software engineer reviewing code. Analyze the following code for bugs, performance issues, and best practices...',
    collection: 'coding',
    tags: ['code', 'review', 'best-practices'],
    isFavorite: true,
    createdAt: '2024-01-15T10:00:00Z',
    updatedAt: '2024-01-20T15:30:00Z',
  },
  {
    id: '2',
    type: 'template',
    title: 'Meeting Summary',
    content: 'Summarize the following meeting transcript. Include: key decisions, action items with owners, and next steps...',
    collection: 'writing',
    tags: ['meetings', 'summary', 'productivity'],
    isFavorite: true,
    createdAt: '2024-01-10T09:00:00Z',
    updatedAt: '2024-01-18T11:00:00Z',
  },
  {
    id: '3',
    type: 'prompt',
    title: 'Data Analysis Helper',
    content: 'Analyze the provided dataset and identify: trends, outliers, correlations, and actionable insights...',
    collection: 'analysis',
    tags: ['data', 'analytics', 'insights'],
    isFavorite: false,
    createdAt: '2024-01-12T14:00:00Z',
    updatedAt: '2024-01-12T14:00:00Z',
  },
]

const typeIcons = {
  prompt: MessageSquare,
  template: FileText,
  artifact: Sparkles,
}

export default function LibraryView() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null)
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [recentOnly, setRecentOnly] = useState(false)
  const [items, setItems] = useState(MOCK_ITEMS)
  const [collections, setCollections] = useState(MOCK_COLLECTIONS)
  const [showNewItem, setShowNewItem] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newContent, setNewContent] = useState('')
  const [newType, setNewType] = useState<'prompt' | 'template' | 'artifact'>('prompt')
  const [showNewCollection, setShowNewCollection] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState('')
  const [editingItem, setEditingItem] = useState<LibraryItem | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const titleRef = useRef<HTMLInputElement>(null)
  const collectionInputRef = useRef<HTMLInputElement>(null)

  const clearFilters = () => {
    setSelectedCollection(null)
    setShowFavoritesOnly(false)
    setRecentOnly(false)
  }

  // Filter items
  const baseFiltered = items.filter(item => {
    const matchesSearch = !searchQuery ||
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesCollection = !selectedCollection || item.collection === selectedCollection
    const matchesFavorites = !showFavoritesOnly || item.isFavorite
    return matchesSearch && matchesCollection && matchesFavorites
  })

  const filteredItems = recentOnly
    ? [...baseFiltered].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    : baseFiltered

  const toggleFavorite = (id: string) => {
    setItems(items.map(item =>
      item.id === id ? { ...item, isFavorite: !item.isFavorite } : item
    ))
  }

  const handleCopy = (item: LibraryItem) => {
    navigator.clipboard.writeText(item.content)
    toast.success('Copied to clipboard')
  }

  const openEdit = (item: LibraryItem) => {
    setEditingItem(item)
    setEditTitle(item.title)
    setEditContent(item.content)
  }

  const handleSaveEdit = () => {
    if (!editingItem || !editTitle.trim() || !editContent.trim()) return
    setItems(prev => prev.map(i => i.id === editingItem.id
      ? { ...i, title: editTitle.trim(), content: editContent.trim(), updatedAt: new Date().toISOString() }
      : i
    ))
    toast.success('Item updated')
    setEditingItem(null)
  }

  const handleDelete = (id: string) => {
    setItems(prev => prev.filter(i => i.id !== id))
    toast.success('Item deleted')
  }

  const handleAddCollection = () => {
    const name = newCollectionName.trim()
    if (!name) return
    const id = name.toLowerCase().replace(/\s+/g, '-')
    const colors = ['bg-blue-500', 'bg-purple-500', 'bg-green-500', 'bg-orange-500', 'bg-pink-500']
    setCollections(prev => [...prev, { id, name, itemCount: 0, color: colors[prev.length % colors.length] }])
    setNewCollectionName('')
    setShowNewCollection(false)
    toast.success(`Collection "${name}" created`)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const handleAddItem = () => {
    if (!newTitle.trim() || !newContent.trim()) return
    const now = new Date().toISOString()
    setItems(prev => [...prev, {
      id: `item-${Date.now()}`,
      title: newTitle.trim(),
      content: newContent.trim(),
      type: newType,
      collection: selectedCollection || collections[0]?.id || 'coding',
      tags: [],
      isFavorite: false,
      createdAt: now,
      updatedAt: now,
    }])
    setNewTitle('')
    setNewContent('')
    setShowNewItem(false)
  }

  const openNewItem = () => {
    setShowNewItem(true)
    setTimeout(() => titleRef.current?.focus(), 50)
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 border-r border-border p-4 flex flex-col">
        <button
          onClick={openNewItem}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors mb-6"
        >
          <Plus className="w-4 h-4" />
          New Item
        </button>

        <div className="space-y-1 mb-6">
          <button
            onClick={clearFilters}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              !selectedCollection && !showFavoritesOnly && !recentOnly
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            <FolderOpen className="w-4 h-4" />
            All Items
            <span className="ml-auto text-xs">{items.length}</span>
          </button>
          <button
            onClick={() => { setSelectedCollection(null); setShowFavoritesOnly(true); setRecentOnly(false) }}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              showFavoritesOnly
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            <Star className="w-4 h-4" />
            Favorites
            <span className="ml-auto text-xs">{items.filter(i => i.isFavorite).length}</span>
          </button>
          <button
            onClick={() => { setSelectedCollection(null); setShowFavoritesOnly(false); setRecentOnly(true) }}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              recentOnly
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            <Clock className="w-4 h-4" />
            Recent
          </button>
        </div>

        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Collections
            </span>
            <button
              onClick={() => { setShowNewCollection(true); setTimeout(() => collectionInputRef.current?.focus(), 50) }}
              className="p-1 rounded hover:bg-muted text-muted-foreground"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-1">
            {collections.map(collection => (
              <button
                key={collection.id}
                onClick={() => { setSelectedCollection(collection.id); setShowFavoritesOnly(false); setRecentOnly(false) }}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                  selectedCollection === collection.id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted"
                )}
              >
                <div className={cn("w-3 h-3 rounded", collection.color)} />
                {collection.name}
                <span className="ml-auto text-xs">{collection.itemCount}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search library..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-auto p-4">
          {filteredItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <FolderOpen className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">No items found</p>
              <p className="text-sm">
                {searchQuery 
                  ? 'Try adjusting your search' 
                  : 'Save prompts, templates, and artifacts for quick access'}
              </p>
              {!searchQuery && (
                <button
                  onClick={openNewItem}
                  className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Create your first item
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredItems.map(item => {
                const Icon = typeIcons[item.type]
                return (
                  <div
                    key={item.id}
                    className="group p-4 rounded-xl bg-card border border-border hover:border-primary/50 hover:shadow-lg transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-foreground truncate">{item.title}</h3>
                            <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground capitalize">
                              {item.type}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                            {item.content}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            {item.tags.slice(0, 3).map(tag => (
                              <span key={tag} className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground">
                                #{tag}
                              </span>
                            ))}
                            <span className="text-xs text-muted-foreground">
                              Updated {formatDate(item.updatedAt)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleFavorite(item.id); }}
                          className={cn(
                            "p-1.5 rounded-lg transition-colors",
                            item.isFavorite
                              ? "text-warning hover:bg-warning/10"
                              : "text-muted-foreground hover:bg-muted"
                          )}
                        >
                          <Star className={cn("w-4 h-4", item.isFavorite && "fill-current")} />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleCopy(item) }}
                          className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors"
                          title="Copy content"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); openEdit(item) }}
                          className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors"
                          title="Edit item"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                          className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-destructive transition-colors"
                          title="Delete item"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* New Collection Modal */}
      {showNewCollection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowNewCollection(false)}>
          <div className="bg-surface border border-outline-variant rounded-xl shadow-2xl p-6 w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-on-surface">New Collection</h3>
              <button onClick={() => setShowNewCollection(false)}><X className="w-4 h-4 text-on-surface-variant" /></button>
            </div>
            <input
              ref={collectionInputRef}
              value={newCollectionName}
              onChange={e => setNewCollectionName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAddCollection()}
              placeholder="Collection name"
              className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <button onClick={() => setShowNewCollection(false)} className="px-4 py-2 text-sm rounded-lg border border-outline-variant text-on-surface-variant hover:bg-surface-variant">Cancel</button>
              <button
                onClick={handleAddCollection}
                disabled={!newCollectionName.trim()}
                className="px-4 py-2 text-sm rounded-lg bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-50"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Item Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditingItem(null)}>
          <div className="bg-surface border border-outline-variant rounded-xl shadow-2xl p-6 w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-on-surface">Edit Item</h3>
              <button onClick={() => setEditingItem(null)}><X className="w-4 h-4 text-on-surface-variant" /></button>
            </div>
            <div className="space-y-3">
              <input
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                placeholder="Title"
                className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
              />
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                rows={5}
                className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm font-mono text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary resize-none"
              />
            </div>
            <div className="flex gap-2 mt-5 justify-end">
              <button onClick={() => setEditingItem(null)} className="px-4 py-2 text-sm rounded-lg border border-outline-variant text-on-surface-variant hover:bg-surface-variant">Cancel</button>
              <button
                onClick={handleSaveEdit}
                disabled={!editTitle.trim() || !editContent.trim()}
                className="px-4 py-2 text-sm rounded-lg bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-50"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Item Modal */}
      {showNewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowNewItem(false)}>
          <div className="bg-surface border border-outline-variant rounded-xl shadow-2xl p-6 w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-on-surface">New Library Item</h3>
              <button onClick={() => setShowNewItem(false)}><X className="w-4 h-4 text-on-surface-variant" /></button>
            </div>
            <div className="space-y-3">
              <div className="flex gap-2">
                {(['prompt', 'template', 'artifact'] as const).map(t => (
                  <button
                    key={t}
                    onClick={() => setNewType(t)}
                    className={`px-3 py-1 rounded-full text-xs border font-medium capitalize transition-colors ${newType === t ? 'bg-primary/10 text-primary border-primary/30' : 'border-outline-variant text-on-surface-variant hover:bg-surface-variant'}`}
                  >{t}</button>
                ))}
              </div>
              <input
                ref={titleRef}
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                placeholder="Title"
                className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary"
              />
              <textarea
                value={newContent}
                onChange={e => setNewContent(e.target.value)}
                placeholder="Prompt or template content…"
                rows={5}
                className="w-full px-3 py-2 rounded-lg bg-surface-variant border border-outline-variant text-sm font-mono text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:border-primary resize-none"
              />
            </div>
            <div className="flex gap-2 mt-5 justify-end">
              <button onClick={() => setShowNewItem(false)} className="px-4 py-2 text-sm rounded-lg border border-outline-variant text-on-surface-variant hover:bg-surface-variant">Cancel</button>
              <button
                onClick={handleAddItem}
                disabled={!newTitle.trim() || !newContent.trim()}
                className="px-4 py-2 text-sm rounded-lg bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-50"
              >
                Add to Library
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
