/**
 * =============================================================================
 * LIBRARY VIEW
 * =============================================================================
 *
 * Manage saved prompts, templates, and conversation artifacts.
 *
 * BACKEND ENDPOINTS:
 * - GET    /api/library/collections          — list with item_count
 * - POST   /api/library/collections          — create collection
 * - DELETE /api/library/collections/{id}     — delete collection
 * - GET    /api/library/items                — list (supports ?collection, ?type, ?q, ?favorites)
 * - POST   /api/library/items               — create item
 * - PATCH  /api/library/items/{id}           — update (title, content, is_favorite, collection, tags)
 * - DELETE /api/library/items/{id}           — delete item
 * =============================================================================
 */

import { useState, useRef, useEffect, useCallback } from 'react'
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
  Loader2,
  Upload,
  BookOpen,
  WandSparkles,
  Link2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'

// Types
interface LibraryItem {
  id: string
  type: 'prompt' | 'template' | 'artifact'
  title: string
  content: string
  collection?: string | null
  tags: string[]
  is_favorite: boolean
  created_at: string
  updated_at: string
  file_path?: string | null
  file_ext?: string | null
  metadata_status?: 'pending' | 'enriched' | 'missing' | 'failed'
  cover_url?: string | null
  description?: string | null
  isbn?: string | null
  subjects?: string[]
  publish_year?: number | null
}

interface Collection {
  id: string
  name: string
  item_count: number
  color: string
}

const typeIcons = {
  prompt: MessageSquare,
  template: FileText,
  artifact: Sparkles,
}

const COLORS = [
  'bg-blue-500', 'bg-purple-500', 'bg-green-500',
  'bg-orange-500', 'bg-pink-500', 'bg-teal-500',
]

export default function LibraryView() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null)
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [recentOnly, setRecentOnly] = useState(false)
  const [items, setItems] = useState<LibraryItem[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)

  const [showNewItem, setShowNewItem] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newContent, setNewContent] = useState('')
  const [newType, setNewType] = useState<'prompt' | 'template' | 'artifact'>('prompt')

  const [showNewCollection, setShowNewCollection] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState('')

  const [editingItem, setEditingItem] = useState<LibraryItem | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [readerItem, setReaderItem] = useState<LibraryItem | null>(null)
  const [acquireUrl, setAcquireUrl] = useState('')
  const [acquireQuery, setAcquireQuery] = useState('')
  const [requiresAcquireConfirm, setRequiresAcquireConfirm] = useState(false)

  const titleRef = useRef<HTMLInputElement>(null)
  const collectionInputRef = useRef<HTMLInputElement>(null)

  // ── Data loading ───────────────────────────────────────────────────────────

  const loadLibrary = useCallback(async () => {
    try {
      const [colRes, itemRes] = await Promise.all([
        api.get<Collection[]>('/api/library/collections'),
        api.get<LibraryItem[]>('/api/library/items'),
      ])
      setCollections(colRes.data)
      setItems(itemRes.data)
    } catch {
      toast.error('Failed to load library')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadLibrary() }, [loadLibrary])

  // ── Derived counts (keep sidebar live without a full refetch) ──────────────

  const collectionsWithCounts = collections.map(c => ({
    ...c,
    item_count: items.filter(i => i.collection === c.id).length,
  }))

  // ── Filters ────────────────────────────────────────────────────────────────

  const clearFilters = () => {
    setSelectedCollection(null)
    setShowFavoritesOnly(false)
    setRecentOnly(false)
  }

  const baseFiltered = items.filter(item => {
    const matchesSearch = !searchQuery ||
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesCollection = !selectedCollection || item.collection === selectedCollection
    const matchesFavorites = !showFavoritesOnly || item.is_favorite
    return matchesSearch && matchesCollection && matchesFavorites
  })

  const filteredItems = recentOnly
    ? [...baseFiltered].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    : baseFiltered

  // ── Mutations ──────────────────────────────────────────────────────────────

  const toggleFavorite = async (id: string) => {
    const item = items.find(i => i.id === id)
    if (!item) return
    const next = !item.is_favorite
    // Optimistic
    setItems(prev => prev.map(i => i.id === id ? { ...i, is_favorite: next } : i))
    try {
      await api.patch(`/api/library/items/${id}`, { is_favorite: next })
    } catch {
      // Revert
      setItems(prev => prev.map(i => i.id === id ? { ...i, is_favorite: !next } : i))
      toast.error('Failed to update favorite')
    }
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

  const handleSaveEdit = async () => {
    if (!editingItem || !editTitle.trim() || !editContent.trim()) return
    try {
      const res = await api.patch<LibraryItem>(`/api/library/items/${editingItem.id}`, {
        title: editTitle.trim(),
        content: editContent.trim(),
      })
      setItems(prev => prev.map(i => i.id === editingItem.id ? res.data : i))
      toast.success('Item updated')
      setEditingItem(null)
    } catch {
      toast.error('Failed to update item')
    }
  }

  const handleDelete = async (id: string) => {
    // Optimistic
    setItems(prev => prev.filter(i => i.id !== id))
    try {
      await api.delete(`/api/library/items/${id}`)
      toast.success('Item deleted')
    } catch {
      toast.error('Failed to delete item')
      loadLibrary() // Revert by refetching
    }
  }

  const handleAddCollection = async () => {
    const name = newCollectionName.trim()
    if (!name) return
    const color = COLORS[collections.length % COLORS.length]
    try {
      const res = await api.post<Collection>('/api/library/collections', { name, color })
      setCollections(prev => [...prev, res.data])
      setNewCollectionName('')
      setShowNewCollection(false)
      toast.success(`Collection "${name}" created`)
    } catch {
      toast.error('Failed to create collection')
    }
  }

  const handleAddItem = async () => {
    if (!newTitle.trim() || !newContent.trim()) return
    try {
      const res = await api.post<LibraryItem>('/api/library/items', {
        title: newTitle.trim(),
        content: newContent.trim(),
        type: newType,
        collection: selectedCollection || collections[0]?.id || null,
        tags: [],
      })
      setItems(prev => [res.data, ...prev])
      setNewTitle('')
      setNewContent('')
      setShowNewItem(false)
      toast.success('Item saved to library')
    } catch {
      toast.error('Failed to save item')
    }
  }

  const handleDropUpload = async (file: File) => {
    const ext = file.name.toLowerCase().split('.').pop() || ''
    if (!['pdf', 'epub', 'mobi'].includes(ext)) {
      toast.error('Only PDF, EPUB, and MOBI are supported')
      return
    }

    const form = new FormData()
    form.append('file', file)
    if (selectedCollection) {
      form.append('collection', selectedCollection)
    }

    setUploading(true)
    try {
      const res = await api.post<LibraryItem>('/api/library/drop', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setItems(prev => [res.data, ...prev])
      toast.success('File imported to library')
    } catch {
      toast.error('BookDrop upload failed')
    } finally {
      setUploading(false)
      setDragActive(false)
    }
  }

  const handleEnrich = async (itemId: string) => {
    try {
      const res = await api.post<LibraryItem>(`/api/library/items/${itemId}/enrich`)
      setItems(prev => prev.map(i => i.id === itemId ? res.data : i))
      toast.success('Metadata enrichment complete')
    } catch {
      toast.error('Metadata enrichment failed')
    }
  }

  const handleAcquire = async (confirmed = false) => {
    if (!acquireUrl.trim() && !acquireQuery.trim()) {
      toast.error('Enter a URL or search query')
      return
    }

    try {
      const res = await api.post('/api/library/acquire', {
        url: acquireUrl.trim() || undefined,
        query: acquireQuery.trim() || undefined,
        confirmed,
      })
      if (res.data?.requires_confirmation) {
        setRequiresAcquireConfirm(true)
        toast.message('Confirm acquisition to continue')
        return
      }

      setRequiresAcquireConfirm(false)
      setAcquireUrl('')
      setAcquireQuery('')
      toast.success('Acquisition queued')
    } catch {
      toast.error('Acquisition request failed')
    }
  }

  const openNewItem = () => {
    setShowNewItem(true)
    setTimeout(() => titleRef.current?.focus(), 50)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const metadataLabel = (status?: string) => {
    if (status === 'enriched') return 'Enriched'
    if (status === 'missing') return 'No metadata'
    if (status === 'failed') return 'Enrichment failed'
    return 'Pending'
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading library…
      </div>
    )
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
            <span className="ml-auto text-xs">{items.filter(i => i.is_favorite).length}</span>
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
              title="New collection"
              aria-label="New collection"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-1">
            {collectionsWithCounts.map(collection => (
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
                <span className="ml-auto text-xs">{collection.item_count}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-border space-y-3">
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

          <div
            onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault()
              const file = e.dataTransfer.files?.[0]
              if (file) void handleDropUpload(file)
            }}
            className={cn(
              'rounded-lg border-2 border-dashed p-3 flex items-center justify-between gap-3 transition-colors',
              dragActive ? 'border-primary bg-primary/5' : 'border-border bg-muted/40'
            )}
          >
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Upload className="w-4 h-4" />
              Drop PDF/EPUB/MOBI here (BookDrop)
            </div>
            <label className="px-3 py-1.5 text-xs rounded-md bg-card border border-border cursor-pointer hover:bg-muted">
              Choose file
              <input
                type="file"
                className="hidden"
                accept=".pdf,.epub,.mobi"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void handleDropUpload(file)
                }}
              />
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              type="text"
              placeholder="Acquire by URL"
              value={acquireUrl}
              onChange={(e) => setAcquireUrl(e.target.value)}
              className="px-3 py-2 bg-muted border border-border rounded-lg text-sm"
            />
            <input
              type="text"
              placeholder="Or search query"
              value={acquireQuery}
              onChange={(e) => setAcquireQuery(e.target.value)}
              className="px-3 py-2 bg-muted border border-border rounded-lg text-sm"
            />
            <div className="flex gap-2">
              <button
                onClick={() => void handleAcquire(false)}
                className="px-3 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
              >
                Request Acquire
              </button>
              {requiresAcquireConfirm && (
                <button
                  onClick={() => void handleAcquire(true)}
                  className="px-3 py-2 text-sm rounded-lg border border-amber-500 text-amber-600 hover:bg-amber-50"
                >
                  Confirm
                </button>
              )}
            </div>
          </div>

          <div className="text-xs text-muted-foreground flex items-center gap-2">
            <Link2 className="w-3.5 h-3.5" />
            OPDS: /api/library/opds
            {uploading && <span className="ml-2">Uploading…</span>}
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
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-medium text-foreground truncate">{item.title}</h3>
                            <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground capitalize">
                              {item.type}
                            </span>
                            <span className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary">
                              {metadataLabel(item.metadata_status)}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                            {item.description || item.content}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            {item.tags.slice(0, 3).map(tag => (
                              <span key={tag} className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground">
                                #{tag}
                              </span>
                            ))}
                            <span className="text-xs text-muted-foreground">
                              Updated {formatDate(item.updated_at)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => { e.stopPropagation(); void handleEnrich(item.id) }}
                          className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors"
                          title="Enrich metadata"
                        >
                          <WandSparkles className="w-4 h-4" />
                        </button>
                        {item.file_path && (
                          <button
                            onClick={(e) => { e.stopPropagation(); setReaderItem(item) }}
                            className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors"
                            title="Open reader"
                          >
                            <BookOpen className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleFavorite(item.id) }}
                          className={cn(
                            "p-1.5 rounded-lg transition-colors",
                            item.is_favorite
                              ? "text-warning hover:bg-warning/10"
                              : "text-muted-foreground hover:bg-muted"
                          )}
                          title={item.is_favorite ? 'Remove favorite' : 'Add favorite'}
                          aria-label={item.is_favorite ? 'Remove favorite' : 'Add favorite'}
                        >
                          <Star className={cn("w-4 h-4", item.is_favorite && "fill-current")} />
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

      {/* Reader Modal */}
      {readerItem && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black/60">
          <div className="p-3 flex items-center justify-between bg-card border-b border-border">
            <div className="font-medium">{readerItem.title}</div>
            <button
              onClick={() => setReaderItem(null)}
              className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted"
            >
              Close
            </button>
          </div>
          <iframe
            title={readerItem.title}
            src={`/api/library/items/${readerItem.id}/read`}
            className="flex-1 w-full bg-white"
          />
        </div>
      )}

      {/* New Collection Modal */}
      {showNewCollection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowNewCollection(false)}>
          <div className="bg-surface border border-outline-variant rounded-xl shadow-2xl p-6 w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-on-surface">New Collection</h3>
              <button onClick={() => setShowNewCollection(false)} title="Close" aria-label="Close"><X className="w-4 h-4 text-on-surface-variant" /></button>
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
              <button onClick={() => setEditingItem(null)} title="Close" aria-label="Close"><X className="w-4 h-4 text-on-surface-variant" /></button>
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
                placeholder="Item content"
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
              <button onClick={() => setShowNewItem(false)} title="Close" aria-label="Close"><X className="w-4 h-4 text-on-surface-variant" /></button>
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
