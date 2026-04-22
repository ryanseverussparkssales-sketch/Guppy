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

import { useState } from 'react'
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
  const [items, setItems] = useState(MOCK_ITEMS)
  const [collections] = useState(MOCK_COLLECTIONS)

  // Filter items
  const filteredItems = items.filter(item => {
    const matchesSearch = !searchQuery || 
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesCollection = !selectedCollection || item.collection === selectedCollection
    const matchesFavorites = !showFavoritesOnly || item.isFavorite
    return matchesSearch && matchesCollection && matchesFavorites
  })

  const toggleFavorite = (id: string) => {
    setItems(items.map(item => 
      item.id === id ? { ...item, isFavorite: !item.isFavorite } : item
    ))
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 border-r border-border p-4 flex flex-col">
        <button className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors mb-6">
          <Plus className="w-4 h-4" />
          New Item
        </button>

        <div className="space-y-1 mb-6">
          <button
            onClick={() => { setSelectedCollection(null); setShowFavoritesOnly(false); }}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              !selectedCollection && !showFavoritesOnly
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            <FolderOpen className="w-4 h-4" />
            All Items
            <span className="ml-auto text-xs">{items.length}</span>
          </button>
          <button
            onClick={() => { setSelectedCollection(null); setShowFavoritesOnly(true); }}
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
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted transition-colors">
            <Clock className="w-4 h-4" />
            Recent
          </button>
        </div>

        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Collections
            </span>
            <button className="p-1 rounded hover:bg-muted text-muted-foreground">
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-1">
            {collections.map(collection => (
              <button
                key={collection.id}
                onClick={() => { setSelectedCollection(collection.id); setShowFavoritesOnly(false); }}
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
                <button className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2">
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
                        <button className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors">
                          <Copy className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted transition-colors">
                          <Edit className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-destructive transition-colors">
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
    </div>
  )
}
