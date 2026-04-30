/**
 * Session and Partner Management Components for ConversationsView
 *
 * Provides UI for:
 * - Session picker (sidebar panel)
 * - Partner selector (modal/dropdown)
 * - Session CRUD operations
 */

import { useState, useEffect } from 'react'
import { Plus, Trash2, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/api/client'
import { cn } from '@/lib/utils'

export interface ConversationSession {
  id: string
  session_title: string
  model_backend: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationPartner {
  role: string
  backend: string
  label: string
  description: string
  port: string
  model: string
}

interface ModelRoleData {
  backend?: string
  label?: string
  description?: string
  port?: string
  model?: string
  conversation_partner_eligible?: boolean
  active_partner?: boolean
}

interface ModelRolesResponse {
  roles?: Record<string, ModelRoleData>
  conversation_partner_roles?: string[]
  active_conversation_partner?: string
  active_conversation_partner_role?: string
  active_conversation_partner_backend?: string
  operator_settings?: {
    conversation_partner?: string
  }
}

function resolvePartnerRole(
  candidate: unknown,
  roles: Record<string, ModelRoleData>,
): string | null {
  if (typeof candidate !== 'string' || !candidate.trim()) return null
  if (roles[candidate]) return candidate

  const backendMatch = Object.entries(roles).find(([, data]) => data.backend === candidate)
  return backendMatch?.[0] ?? null
}

function getResponseStatus(err: unknown): number | undefined {
  return (err as { response?: { status?: number } }).response?.status
}

async function persistConversationPartner(role: string) {
  try {
    await api.put('/api/model-roles/conversation-partner', { role })
    return
  } catch (err: unknown) {
    const status = getResponseStatus(err)
    if (status !== 404 && status !== 405 && status !== 501) throw err
  }

  await api.put('/api/control/operator-settings', { conversation_partner: role })
}

/**
 * SessionPicker — collapsible sidebar panel showing recent sessions
 */
export function SessionPicker({
  currentSessionId,
  onSelectSession,
  onNewSession,
}: {
  currentSessionId: string | null
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
}) {
  const [sessions, setSessions] = useState<ConversationSession[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const loadSessions = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/conversations/sessions')
      setSessions(r.data || [])
    } catch (e) {
      console.error('Failed to load sessions:', e)
      toast.error('Could not load sessions')
    } finally {
      setLoading(false)
    }
  }

  const toggleSessions = () => {
    const nextOpen = !open
    setOpen(nextOpen)
    if (nextOpen) void loadSessions()
  }

  const deleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this session?')) return
    try {
      await api.delete(`/api/conversations/sessions/${sessionId}`)
      setSessions((s) => s.filter((x) => x.id !== sessionId))
      toast.success('Session deleted')
    } catch {
      toast.error('Could not delete session')
    }
  }

  return (
    <div className="px-3 py-2 border-b border-outline-variant/20">
      <button
        onClick={toggleSessions}
        className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-sm hover:bg-surface-variant/50 transition-colors"
      >
        <span className="font-medium text-on-surface">Sessions</span>
        <ChevronDown className={cn("w-4 h-4 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="mt-2 space-y-1">
          {/* New session button */}
          <button
            onClick={() => {
              onNewSession()
              setOpen(false)
            }}
            className="w-full flex items-center gap-2 px-2 py-2 text-xs rounded-lg bg-primary/10 hover:bg-primary/20 text-primary transition-colors"
          >
            <Plus className="w-3 h-3" />
            New Chat
          </button>

          {/* Session list */}
          <div className="max-h-64 overflow-y-auto space-y-1">
            {loading ? (
              <p className="text-xs text-on-surface-variant/50 px-2 py-1">Loading…</p>
            ) : sessions.length === 0 ? (
              <p className="text-xs text-on-surface-variant/50 px-2 py-1">No sessions yet</p>
            ) : (
              sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => {
                    onSelectSession(session.id)
                    setOpen(false)
                  }}
                  className={cn(
                    "w-full text-left px-2 py-1.5 rounded-lg text-xs transition-colors group",
                    currentSessionId === session.id
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-surface-variant/50 text-on-surface-variant"
                  )}
                >
                  <div className="flex items-start justify-between gap-1">
                    <div className="flex-1 truncate">
                      <p className="font-medium truncate">{session.session_title}</p>
                      <p className="text-xs opacity-60">{session.message_count} messages</p>
                    </div>
                    <button
                      onClick={(e) => deleteSession(session.id, e)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-error/20 hover:text-error rounded"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * PartnerSelector — displays conversation partner options (Hermes3, Rocinante, Pepe, MiniCPM)
 */
export function PartnerSelector({
  currentPartner,
  onSelectPartner,
}: {
  currentPartner: string | null
  onSelectPartner: (partner: string) => void
}) {
  const [partners, setPartners] = useState<ConversationPartner[]>([])
  const [loading, setLoading] = useState(true)
  const [savingRole, setSavingRole] = useState<string | null>(null)

  useEffect(() => {
    const loadPartners = async () => {
      try {
        // Get all model roles + current operator settings
        const [rolesRes, settingsRes] = await Promise.all([
          api.get('/api/model-roles'),
          api.get('/api/control/operator-settings').catch(() => ({ data: null })),
        ])

        const payload = (rolesRes.data || {}) as ModelRolesResponse
        const roles = payload.roles || (payload as Record<string, ModelRoleData>)
        const settings = settingsRes.data || payload.operator_settings || {}
        const activePartner =
          resolvePartnerRole(settings.conversation_partner, roles) ||
          resolvePartnerRole(payload.operator_settings?.conversation_partner, roles) ||
          resolvePartnerRole(payload.active_conversation_partner_role, roles) ||
          resolvePartnerRole(payload.active_conversation_partner, roles) ||
          resolvePartnerRole(payload.active_conversation_partner_backend, roles) ||
          Object.entries(roles).find(([, data]) => data.active_partner)?.[0] ||
          'conversation.default'

        // Filter to conversation partners only
        const roleOrder = payload.conversation_partner_roles?.length
          ? payload.conversation_partner_roles
          : Object.keys(roles)

        const partnerList = roleOrder
          .filter((role) => {
            const data = roles[role]
            return Boolean(
              data &&
              (data.conversation_partner_eligible ||
                role.startsWith('conversation.partner') ||
                role === 'conversation.default')
            )
          })
          .map((role) => ({
            role,
            backend: roles[role].backend || '',
            label: roles[role].label || role,
            description: roles[role].description || '',
            port: roles[role].port || '',
            model: roles[role].model || '',
          }))

        setPartners(partnerList)
        onSelectPartner(activePartner)
      } catch (e) {
        console.error('Failed to load partners:', e)
        toast.error('Could not load partner options')
      } finally {
        setLoading(false)
      }
    }

    loadPartners()
  }, [onSelectPartner])

  const selectPartner = async (role: string) => {
    if (role === currentPartner || savingRole) return
    setSavingRole(role)
    try {
      await persistConversationPartner(role)
      onSelectPartner(role)
      toast.success('Conversation partner updated')
    } catch (e) {
      console.error('Failed to update partner:', e)
      toast.error('Could not update conversation partner')
    } finally {
      setSavingRole(null)
    }
  }

  if (loading) {
    return <div className="px-3 py-2 text-xs text-on-surface-variant/50">Loading partners…</div>
  }

  return (
    <div className="px-3 py-3 space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant">Conversation Partner</p>
      <div className="grid grid-cols-2 gap-2">
        {partners.map((partner) => (
          <button
            key={partner.role}
            onClick={() => selectPartner(partner.role)}
            disabled={savingRole !== null}
            className={cn(
              "px-2 py-2.5 rounded-lg border transition-all text-left",
              currentPartner === partner.role
                ? "border-primary/50 bg-primary/10"
                : "border-outline-variant/20 hover:border-outline-variant/50",
              savingRole !== null && "opacity-60 cursor-wait"
            )}
          >
            <p className="text-xs font-medium text-on-surface">{partner.label}</p>
            <p className="text-xs text-on-surface-variant/60 mt-0.5">{partner.description}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
