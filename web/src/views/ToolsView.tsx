/**
 * =============================================================================
 * TOOLS VIEW
 * =============================================================================
 * 
 * Displays and manages available tools/functions that can be used by AI models.
 * 
 * BACKEND ENDPOINTS:
 * - GET /api/tools - List all tools
 * - POST /api/tools/:id/enable - Enable a tool
 * - POST /api/tools/:id/disable - Disable a tool
 * - POST /api/tools - Create custom tool
 * =============================================================================
 */

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Wrench,
  Search,
  Code,
  Globe,
  FileText,
  Database,
  Terminal,
  Zap,
  ToggleLeft,
  ToggleRight,
  Settings,
  Plus,
  ExternalLink,
  AlertCircle,
  Plug,
  Monitor,
  Mic,
  X,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTools, useSetToolEnabled, useCreateTool, useUpdateTool, useDeleteTool } from '@/api/queries'
import type { Tool } from '@/api/schemas'
import MCPView from './MCPView'
import DesktopView from './DesktopView'
import VoicesView from './VoicesView'

// Category icon mapping
const categoryIcons: Record<string, typeof Wrench> = {
  'search': Globe,
  'code': Code,
  'file': FileText,
  'database': Database,
  'system': Terminal,
  'api': Zap,
  'default': Wrench,
}

// Mock tools data - remove when backend is connected
const MOCK_TOOLS: Tool[] = [
  {
    id: 'web_search',
    name: 'Web Search',
    description: 'Search the web for current information using multiple search engines',
    category: 'search',
    isEnabled: true,
    type: 'builtin',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
        maxResults: { type: 'number', default: 10 }
      }
    }
  },
  {
    id: 'code_execution',
    name: 'Code Execution',
    description: 'Execute Python code in a sandboxed environment',
    category: 'code',
    isEnabled: true,
    type: 'builtin',
    parameters: {
      type: 'object',
      properties: {
        code: { type: 'string', description: 'Python code to execute' },
        timeout: { type: 'number', default: 30 }
      }
    }
  },
  {
    id: 'file_read',
    name: 'File Read',
    description: 'Read contents from local files',
    category: 'file',
    isEnabled: true,
    type: 'builtin',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'File path to read' }
      }
    }
  },
  {
    id: 'file_write',
    name: 'File Write',
    description: 'Write content to local files',
    category: 'file',
    isEnabled: false,
    type: 'builtin',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'File path to write' },
        content: { type: 'string', description: 'Content to write' }
      }
    }
  },
  {
    id: 'shell_execute',
    name: 'Shell Command',
    description: 'Execute shell commands (restricted)',
    category: 'system',
    isEnabled: false,
    type: 'builtin',
    parameters: {
      type: 'object',
      properties: {
        command: { type: 'string', description: 'Command to execute' }
      }
    }
  },
  {
    id: 'api_request',
    name: 'API Request',
    description: 'Make HTTP requests to external APIs',
    category: 'api',
    isEnabled: true,
    type: 'builtin',
    parameters: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'API endpoint URL' },
        method: { type: 'string', enum: ['GET', 'POST', 'PUT', 'DELETE'] }
      }
    }
  },
]

type Tab = 'functions' | 'plugins' | 'desktop' | 'voices'

const CATEGORIES = ['search', 'code', 'file', 'system', 'api', 'desktop', 'vision', 'comms', 'memory', 'tasks', 'media']

type ToolForm = { name: string; description: string; category: string }
const emptyForm = (): ToolForm => ({ name: '', description: '', category: 'api' })

export default function ToolsView() {
  const toolsQuery = useTools()
  const setToolEnabled = useSetToolEnabled()
  const createTool = useCreateTool()
  const updateTool = useUpdateTool()
  const deleteTool = useDeleteTool()

  const [activeTab, setActiveTab] = useState<Tab>('functions')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [pendingToggles, setPendingToggles] = useState<Record<string, boolean>>({})

  // Add-tool modal
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState<ToolForm>(emptyForm())

  // Edit-tool modal (custom tools only)
  const [editTool, setEditTool] = useState<Tool | null>(null)
  const [editForm, setEditForm] = useState<ToolForm>(emptyForm())

  const isLoading = toolsQuery.isPending
  const error = toolsQuery.error
  const apiTools = toolsQuery.data ?? []
  const tools = apiTools.length > 0 ? apiTools : MOCK_TOOLS

  const categories = Array.from(new Set(tools.map(t => t.category)))

  const filteredTools = tools.filter(tool => {
    const matchesSearch = !searchQuery ||
      tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = !selectedCategory || tool.category === selectedCategory
    return matchesSearch && matchesCategory
  })

  const handleToggle = async (toolId: string, currentState: boolean) => {
    const enabling = !currentState
    setPendingToggles(prev => ({ ...prev, [toolId]: true }))
    try {
      await setToolEnabled.mutateAsync({ toolId, enabled: enabling })
      const tool = tools.find(t => t.id === toolId)
      toast.success(`${tool?.name ?? toolId} ${enabling ? 'enabled' : 'disabled'}`)
    } catch {
      toast.error(`Failed to ${enabling ? 'enable' : 'disable'} tool`)
    } finally {
      setPendingToggles(prev => { const n = { ...prev }; delete n[toolId]; return n })
    }
  }

  const getToolEnabled = (tool: Tool) => tool.isEnabled

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const { name, description, category } = addForm
    if (!name.trim() || !description.trim()) return
    try {
      await createTool.mutateAsync({ name: name.trim(), description: description.trim(), category })
      toast.success(`Tool "${name.trim()}" created`)
      setShowAdd(false)
      setAddForm(emptyForm())
    } catch {
      toast.error('Failed to create tool')
    }
  }

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editTool) return
    const { name, description, category } = editForm
    if (!name.trim() || !description.trim()) return
    try {
      await updateTool.mutateAsync({ toolId: editTool.id, name: name.trim(), description: description.trim(), category })
      toast.success(`Tool "${name.trim()}" updated`)
      setEditTool(null)
    } catch {
      toast.error('Failed to update tool')
    }
  }

  const handleDelete = async (tool: Tool) => {
    if (!window.confirm(`Delete "${tool.name}"?`)) return
    try {
      await deleteTool.mutateAsync(tool.id)
      toast.success(`Tool "${tool.name}" deleted`)
      setEditTool(null)
    } catch {
      toast.error('Failed to delete tool')
    }
  }

  const openEdit = (tool: Tool) => {
    setEditTool(tool)
    setEditForm({ name: tool.name, description: tool.description, category: tool.category })
  }

  // Don't render tool list state when on non-tool tabs
  const showToolContent = activeTab === 'functions' || activeTab === 'plugins'

  return (
    <div className="flex flex-col h-full">
      {/* Header — only for tool tabs */}
      {showToolContent && (
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Tools & Plugins</h1>
            <p className="text-muted-foreground mt-1">
              Manage AI model functions and MCP server extensions
            </p>
          </div>
          {activeTab === 'functions' && (
            <button
              onClick={() => { setAddForm(emptyForm()); setShowAdd(true) }}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Tool
            </button>
          )}
        </div>
      )}

      {/* Tab Bar */}
      <div className="flex items-center gap-1 px-6 pt-4 border-b border-border shrink-0">
        {[
          { id: 'functions' as Tab, icon: <Wrench className="w-4 h-4" />,  label: 'Functions' },
          { id: 'plugins'  as Tab, icon: <Plug className="w-4 h-4" />,    label: 'MCP Plugins' },
          { id: 'desktop'  as Tab, icon: <Monitor className="w-4 h-4" />, label: 'Desktop' },
          { id: 'voices'   as Tab, icon: <Mic className="w-4 h-4" />,     label: 'Voice' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors',
              activeTab === t.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'desktop' && <DesktopView />}
      {activeTab === 'voices'  && <VoicesView />}
      {activeTab === 'plugins' ? (
        <MCPView />
      ) : activeTab === 'functions' ? (
        <>
          {/* Filters */}
          <div className="flex items-center gap-4 p-4 border-b border-border">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search tools..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-sm transition-colors",
                  !selectedCategory
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                All
              </button>
              {categories.map(category => {
                const Icon = categoryIcons[category] || categoryIcons.default
                return (
                  <button
                    key={category}
                    onClick={() => setSelectedCategory(category)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm capitalize transition-colors",
                      selectedCategory === category
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {category}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Tools Grid */}
          <div className="flex-1 overflow-auto p-6">
            {isLoading ? (
              <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-64 text-destructive">
                <AlertCircle className="w-8 h-8 mb-2" />
                <p>Failed to load tools</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredTools.map(tool => {
                  const Icon = categoryIcons[tool.category] || categoryIcons.default
                  const isEnabled = getToolEnabled(tool)

                  return (
                    <div
                      key={tool.id}
                      className={cn(
                        "group relative p-5 rounded-xl border transition-all",
                        isEnabled
                          ? "bg-card border-border hover:border-primary/50 hover:shadow-lg"
                          : "bg-muted/50 border-border/50 opacity-75"
                      )}
                    >
                      <div className="absolute top-4 right-4">
                        <span className={cn(
                          "px-2 py-0.5 text-xs rounded-full",
                          tool.type === 'builtin' && "bg-blue-500/10 text-blue-500",
                          tool.type === 'custom' && "bg-purple-500/10 text-purple-500",
                          tool.type === 'mcp' && "bg-green-500/10 text-green-500"
                        )}>
                          {tool.type}
                        </span>
                      </div>

                      <div className="flex items-start gap-3 mb-3">
                        <div className={cn(
                          "p-2.5 rounded-lg",
                          isEnabled ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                        )}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-foreground truncate">{tool.name}</h3>
                          <p className="text-xs text-muted-foreground capitalize">{tool.category}</p>
                        </div>
                      </div>

                      <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                        {tool.description}
                      </p>

                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => handleToggle(tool.id, isEnabled)}
                          disabled={!!pendingToggles[tool.id]}
                          className={cn(
                            "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
                            isEnabled
                              ? "bg-success/10 text-success hover:bg-success/20"
                              : "bg-muted text-muted-foreground hover:bg-muted/80"
                          )}
                        >
                          {pendingToggles[tool.id] ? (
                            <div className="w-4 h-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          ) : isEnabled ? (
                            <><ToggleRight className="w-4 h-4" />Enabled</>
                          ) : (
                            <><ToggleLeft className="w-4 h-4" />Disabled</>
                          )}
                        </button>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          {tool.type === 'custom' && (
                            <button
                              onClick={() => openEdit(tool)}
                              className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                              title="Edit tool"
                            >
                              <Settings className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {filteredTools.length === 0 && !isLoading && !error && (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <Wrench className="w-12 h-12 mb-4 opacity-50" />
                <p className="text-lg">No tools found</p>
                <p className="text-sm">Try adjusting your search or filters</p>
              </div>
            )}
          </div>
        </>
      ) : null}

      {/* Add Tool Modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-surface-container border border-border rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-foreground">Add Custom Tool</h2>
              <button onClick={() => setShowAdd(false)} className="p-1 rounded-lg hover:bg-muted text-muted-foreground"><X className="w-4 h-4" /></button>
            </div>
            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={addForm.name}
                  onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="My Custom Tool"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Description</label>
                <textarea
                  required
                  rows={3}
                  value={addForm.description}
                  onChange={e => setAddForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="What this tool does..."
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Category</label>
                <select
                  value={addForm.category}
                  onChange={e => setAddForm(f => ({ ...f, category: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 rounded-lg border border-border text-muted-foreground hover:bg-muted transition-colors">Cancel</button>
                <button type="submit" disabled={createTool.isPending} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50">
                  {createTool.isPending ? 'Creating…' : 'Create Tool'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Tool Modal (custom tools only) */}
      {editTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-surface-container border border-border rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-foreground">Edit Tool</h2>
              <button onClick={() => setEditTool(null)} className="p-1 rounded-lg hover:bg-muted text-muted-foreground"><X className="w-4 h-4" /></button>
            </div>
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={editForm.name}
                  onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Description</label>
                <textarea
                  required
                  rows={3}
                  value={editForm.description}
                  onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Category</label>
                <select
                  value={editForm.category}
                  onChange={e => setEditForm(f => ({ ...f, category: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => handleDelete(editTool)}
                  disabled={deleteTool.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-destructive hover:bg-destructive/10 transition-colors text-sm disabled:opacity-50"
                >
                  <Trash2 className="w-4 h-4" />Delete
                </button>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setEditTool(null)} className="px-4 py-2 rounded-lg border border-border text-muted-foreground hover:bg-muted transition-colors">Cancel</button>
                  <button type="submit" disabled={updateTool.isPending} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50">
                    {updateTool.isPending ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
