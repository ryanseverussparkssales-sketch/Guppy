import { useState, useEffect, useCallback } from "react"
import {
  Plug,
  Plus,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
} from "lucide-react"
import { api } from "../api/client"

interface MCPServer {
  id: string
  name: string
  description: string
  command: string
  args: string[]
  envVars: Record<string, string>
  isEnabled: boolean
  isPreset: boolean
}

interface MCPTool {
  name: string
  description?: string
  inputSchema?: Record<string, unknown>
}

type TestStatus = "idle" | "testing" | "ok" | "error"

function EnvEditor({
  serverId,
  envVars,
  onSaved,
}: {
  serverId: string
  envVars: Record<string, string>
  onSaved: (updated: MCPServer) => void
}) {
  const [vals, setVals] = useState<Record<string, string>>(envVars)
  const [shown, setShown] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)

  const toggle = (k: string) => setShown((p) => ({ ...p, [k]: !p[k] }))

  const save = async () => {
    setSaving(true)
    try {
      const data = await api.put(`/api/mcp/servers/${serverId}/env`, { envVars: vals })
      onSaved(data.data)
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  if (!Object.keys(vals).length) return null

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">Credentials</p>
      {Object.entries(vals).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-xs text-gray-400 w-48 shrink-0 font-mono">{k}</span>
          <div className="relative flex-1">
            <input
              type={shown[k] ? "text" : "password"}
              value={v}
              onChange={(e) => setVals((p) => ({ ...p, [k]: e.target.value }))}
              placeholder="Enter value…"
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs font-mono text-gray-200 pr-7"
            />
            <button
              onClick={() => toggle(k)}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              {shown[k] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      ))}
      <button
        onClick={save}
        disabled={saving}
        className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white"
      >
        {saving ? "Saving…" : "Save credentials"}
      </button>
    </div>
  )
}

function ServerCard({
  server,
  onUpdate,
  onDelete,
}: {
  server: MCPServer
  onUpdate: (s: MCPServer) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [tools, setTools] = useState<MCPTool[]>([])
  const [loadingTools, setLoadingTools] = useState(false)
  const [toolsError, setToolsError] = useState("")
  const [testStatus, setTestStatus] = useState<TestStatus>("idle")
  const [testError, setTestError] = useState("")
  const [toggling, setToggling] = useState(false)

  const toggle = async () => {
    setToggling(true)
    try {
      const endpoint = server.isEnabled
        ? `/api/mcp/servers/${server.id}/disable`
        : `/api/mcp/servers/${server.id}/enable`
      const data = await api.post(endpoint)
      onUpdate(data.data)
    } catch {
      // ignore
    } finally {
      setToggling(false)
    }
  }

  const test = async () => {
    setTestStatus("testing")
    setTestError("")
    try {
      const data = await api.post(`/api/mcp/servers/${server.id}/test`)
      if (data.data.ok) {
        setTestStatus("ok")
      } else {
        setTestStatus("error")
        setTestError(data.data.error || "Unknown error")
      }
    } catch {
      setTestStatus("error")
      setTestError("Request failed")
    }
  }

  const loadTools = async () => {
    if (!expanded) {
      setExpanded(true)
      if (!tools.length) {
        setLoadingTools(true)
        setToolsError("")
        try {
          const data = await api.get(`/api/mcp/servers/${server.id}/tools`)
          setTools(data.data.tools || [])
        } catch (e: unknown) {
          const msg =
            (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
            "Failed to load tools — is the server process running?"
          setToolsError(msg)
        } finally {
          setLoadingTools(false)
        }
      }
    } else {
      setExpanded(false)
    }
  }

  const statusIcon = {
    idle: null,
    testing: <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />,
    ok: <CheckCircle className="w-3.5 h-3.5 text-green-400" />,
    error: <XCircle className="w-3.5 h-3.5 text-red-400" />,
  }[testStatus]

  return (
    <div className={`rounded-lg border ${server.isEnabled ? "border-blue-700/50 bg-blue-950/20" : "border-gray-700 bg-gray-800/40"}`}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${server.isEnabled ? "bg-green-400" : "bg-gray-600"}`} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-200 text-sm">{server.name}</span>
                {server.isPreset && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 uppercase tracking-wide">preset</span>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-0.5">{server.description}</p>
              <p className="text-[11px] text-gray-600 font-mono mt-1">
                {server.command} {server.args.join(" ")}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={test}
              disabled={testStatus === "testing"}
              title="Test connection"
              className="p-1.5 rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors"
            >
              {statusIcon || <RefreshCw className="w-3.5 h-3.5" />}
            </button>
            {!server.isPreset && (
              <button
                onClick={() => onDelete(server.id)}
                title="Remove server"
                className="p-1.5 rounded text-gray-500 hover:text-red-400 hover:bg-gray-700 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={toggle}
              disabled={toggling}
              className={`text-xs px-3 py-1 rounded font-medium transition-colors ${
                server.isEnabled
                  ? "bg-gray-700 hover:bg-gray-600 text-gray-300"
                  : "bg-blue-600 hover:bg-blue-500 text-white"
              } disabled:opacity-50`}
            >
              {toggling ? "…" : server.isEnabled ? "Disable" : "Enable"}
            </button>
          </div>
        </div>

        {testStatus === "error" && testError && (
          <p className="mt-2 text-xs text-red-400 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> {testError}
          </p>
        )}

        <EnvEditor
          serverId={server.id}
          envVars={server.envVars}
          onSaved={onUpdate}
        />

        {server.isEnabled && (
          <button
            onClick={loadTools}
            className="mt-3 flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            Browse tools
          </button>
        )}
      </div>

      {expanded && server.isEnabled && (
        <div className="border-t border-gray-700 px-4 py-3">
          {loadingTools ? (
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading tools…
            </div>
          ) : toolsError ? (
            <p className="text-xs text-red-400 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {toolsError}
            </p>
          ) : tools.length === 0 ? (
            <p className="text-xs text-gray-500">No tools found (server may not be running yet)</p>
          ) : (
            <div className="space-y-2">
              {tools.map((t) => (
                <div key={t.name} className="text-xs">
                  <span className="font-mono text-blue-300">{t.name}</span>
                  {t.description && <span className="text-gray-400 ml-2">— {t.description}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AddServerForm({ onAdded }: { onAdded: (s: MCPServer) => void }) {
  const [open, setOpen] = useState(false)
  const [id, setId] = useState("")
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [command, setCommand] = useState("npx")
  const [args, setArgs] = useState("")
  const [envRaw, setEnvRaw] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const submit = async () => {
    setSaving(true)
    setError("")
    try {
      const envVars: Record<string, string> = {}
      for (const line of envRaw.split("\n").filter(Boolean)) {
        const eq = line.indexOf("=")
        if (eq > 0) envVars[line.slice(0, eq).trim()] = line.slice(eq + 1).trim()
      }
      const data = await api.post("/api/mcp/servers", {
        id: id.trim(),
        name: name.trim(),
        description: description.trim(),
        command: command.trim(),
        args: args.trim() ? args.trim().split(/\s+/) : [],
        envVars,
      })
      onAdded(data.data)
      setOpen(false)
      setId(""); setName(""); setDescription(""); setCommand("npx"); setArgs(""); setEnvRaw("")
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Failed to add server"
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-4 py-2 rounded-lg border border-dashed border-gray-600 hover:border-gray-400 text-gray-400 hover:text-gray-200 text-sm transition-colors w-full"
      >
        <Plus className="w-4 h-4" /> Add custom MCP server
      </button>
    )
  }

  const field = "w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"

  return (
    <div className="rounded-lg border border-gray-600 bg-gray-800/60 p-4 space-y-3">
      <p className="text-sm font-medium text-gray-200">Add custom MCP server</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">ID (slug)</label>
          <input className={field} placeholder="my-server" value={id} onChange={(e) => setId(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Display name</label>
          <input className={field} placeholder="My Server" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
      </div>
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Description</label>
        <input className={field} placeholder="What does this server do?" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Command</label>
          <input className={field} placeholder="npx" value={command} onChange={(e) => setCommand(e.target.value)} />
        </div>
        <div className="col-span-2">
          <label className="text-xs text-gray-400 mb-1 block">Args (space separated)</label>
          <input className={field} placeholder="-y @modelcontextprotocol/server-fetch" value={args} onChange={(e) => setArgs(e.target.value)} />
        </div>
      </div>
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Env vars (KEY=value, one per line)</label>
        <textarea
          className={`${field} font-mono text-xs h-20 resize-none`}
          placeholder={"API_KEY=your-key-here\nANOTHER_VAR=value"}
          value={envRaw}
          onChange={(e) => setEnvRaw(e.target.value)}
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={saving || !id || !name || !command}
          className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm text-white"
        >
          {saving ? "Adding…" : "Add server"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="px-4 py-1.5 rounded text-sm text-gray-400 hover:text-gray-200"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export default function MCPView() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<"all" | "enabled" | "preset">("all")

  const load = useCallback(async () => {
    try {
      const data = await api.get("/api/mcp/servers")
      setServers(data.data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const updateServer = (updated: MCPServer) =>
    setServers((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))

  const deleteServer = async (id: string) => {
    try {
      await api.delete(`/api/mcp/servers/${id}`)
      setServers((prev) => prev.filter((s) => s.id !== id))
    } catch {
      // ignore
    }
  }

  const addServer = (s: MCPServer) => setServers((prev) => [...prev, s])

  const filtered = servers.filter((s) => {
    if (filter === "enabled") return s.isEnabled
    if (filter === "preset") return s.isPreset
    return true
  })

  const enabledCount = servers.filter((s) => s.isEnabled).length

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="p-6 pb-0">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-3">
            <Plug className="w-5 h-5 text-blue-400" />
            <h1 className="text-xl font-semibold text-gray-100">MCP Plugins</h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
            {enabledCount} active
          </div>
        </div>
        <p className="text-sm text-gray-400 mb-4 ml-8">
          Model Context Protocol servers extend the AI with live tools — filesystems, search, databases, and more.
        </p>

        <div className="flex gap-2 mb-4">
          {(["all", "enabled", "preset"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-xs font-medium capitalize transition-colors ${
                filter === f ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 p-6 pt-0 space-y-3">
        {loading ? (
          <div className="flex items-center gap-2 text-gray-400 text-sm pt-8">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading servers…
          </div>
        ) : (
          <>
            {filtered.map((server) => (
              <ServerCard
                key={server.id}
                server={server}
                onUpdate={updateServer}
                onDelete={deleteServer}
              />
            ))}
            {filter === "all" && <AddServerForm onAdded={addServer} />}
          </>
        )}
      </div>
    </div>
  )
}
