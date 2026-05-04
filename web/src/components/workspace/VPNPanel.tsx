/**
 * VPNPanel — Windows VPN + WireGuard management
 *
 * API:
 *   GET  /api/vpn/connections
 *   POST /api/vpn/connect        { name, username?, password? }
 *   POST /api/vpn/disconnect     { name }
 *   POST /api/vpn/add            { name, server, tunnel_type, ... }
 *   DELETE /api/vpn/connections/:name
 *   GET  /api/vpn/wireguard
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Shield, ShieldCheck, ShieldOff, Plus, Trash2,
  RefreshCw, ChevronDown, ChevronUp, Wifi, WifiOff,
  Lock, Unlock, X, Eye, EyeOff,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface VpnConnection {
  name: string
  server: string
  status: string
  tunnel_type: string
  auth_method: string[]
  split_tunnel: boolean
}

interface WgStatus {
  available: boolean
  raw?: string
  error?: string
}

// ── AddVpnForm ────────────────────────────────────────────────────────────────

const TUNNEL_TYPES = ['Automatic', 'IkeV2', 'L2tp', 'Pptp', 'Sstp']

function AddVpnForm({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '', server: '', tunnel_type: 'Automatic',
    auth_method: 'MSChapv2', l2tp_psk: '', split_tunnel: false,
  })

  const save = async () => {
    if (!form.name.trim() || !form.server.trim()) {
      toast.error('Name and server are required')
      return
    }
    setSaving(true)
    try {
      await api.post('/api/vpn/add', form)
      toast.success(`VPN "${form.name}" added`)
      setForm({ name: '', server: '', tunnel_type: 'Automatic', auth_method: 'MSChapv2', l2tp_psk: '', split_tunnel: false })
      setOpen(false)
      onAdded()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Failed to add VPN')
    } finally { setSaving(false) }
  }

  if (!open) return (
    <button
      onClick={() => setOpen(true)}
      className="w-full flex items-center justify-center gap-2 text-xs text-on-surface-variant/60 hover:text-primary transition-colors py-2 border border-dashed border-outline-variant/30 rounded-lg hover:border-primary/30"
    >
      <Plus className="w-3.5 h-3.5" /> Add VPN Connection
    </button>
  )

  return (
    <div className="bg-surface-container rounded-xl p-3 space-y-2 border border-primary/20">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-on-surface">New VPN Connection</span>
        <button onClick={() => setOpen(false)} className="text-on-surface-variant/40 hover:text-on-surface">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      {[
        { key: 'name',   placeholder: 'Connection name *' },
        { key: 'server', placeholder: 'Server address (hostname or IP) *' },
      ].map(({ key, placeholder }) => (
        <input
          key={key}
          value={(form as any)[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          placeholder={placeholder}
          className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        />
      ))}
      <div className="grid grid-cols-2 gap-2">
        <select
          value={form.tunnel_type}
          onChange={(e) => setForm((f) => ({ ...f, tunnel_type: e.target.value }))}
          className="text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        >
          {TUNNEL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select
          value={form.auth_method}
          onChange={(e) => setForm((f) => ({ ...f, auth_method: e.target.value }))}
          className="text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        >
          {['MSChapv2', 'Pap', 'Chap', 'Eap', 'MachineCertificate'].map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>
      {form.tunnel_type === 'L2tp' && (
        <input
          value={form.l2tp_psk}
          onChange={(e) => setForm((f) => ({ ...f, l2tp_psk: e.target.value }))}
          placeholder="L2TP Pre-shared key (optional)"
          type="password"
          className="w-full text-xs bg-surface border border-outline-variant/20 rounded-lg px-2.5 py-1.5 outline-none focus:border-primary/50 text-on-surface"
        />
      )}
      <label className="flex items-center gap-2 text-xs text-on-surface-variant/60 cursor-pointer select-none">
        <input type="checkbox" checked={form.split_tunnel} onChange={(e) => setForm((f) => ({ ...f, split_tunnel: e.target.checked }))} />
        Split tunneling (only route VPN traffic through tunnel)
      </label>
      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving || !form.name.trim() || !form.server.trim()}
          className="flex-1 text-xs bg-primary text-on-primary rounded-lg py-1.5 hover:bg-primary/90 disabled:opacity-40 transition-colors"
        >
          {saving ? 'Adding…' : 'Add Connection'}
        </button>
        <button onClick={() => setOpen(false)} className="px-3 text-xs text-on-surface-variant/60 hover:text-on-surface transition-colors">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── ConnectModal ──────────────────────────────────────────────────────────────

function ConnectModal({ name, onDone, onClose }: { name: string; onDone: () => void; onClose: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [connecting, setConnecting] = useState(false)

  const connect = async () => {
    setConnecting(true)
    try {
      await api.post('/api/vpn/connect', { name, username, password })
      toast.success(`Connected to ${name}`)
      onDone()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Connection failed')
    } finally { setConnecting(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-surface rounded-2xl border border-outline-variant/30 p-5 w-full max-w-sm shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-on-surface">Connect to {name}</span>
          <button onClick={onClose} className="text-on-surface-variant/40 hover:text-on-surface">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-on-surface-variant/60">Leave blank to use saved credentials.</p>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username (optional)"
          className="w-full text-sm bg-surface-container border border-outline-variant/20 rounded-lg px-3 py-2 outline-none focus:border-primary/50 text-on-surface"
        />
        <div className="relative">
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (optional)"
            type={showPw ? 'text' : 'password'}
            className="w-full text-sm bg-surface-container border border-outline-variant/20 rounded-lg px-3 py-2 pr-9 outline-none focus:border-primary/50 text-on-surface"
          />
          <button
            type="button"
            onClick={() => setShowPw((v) => !v)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant/40 hover:text-on-surface"
          >
            {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
        <div className="flex gap-2 pt-1">
          <button
            onClick={connect}
            disabled={connecting}
            className="flex-1 flex items-center justify-center gap-2 text-sm bg-primary text-on-primary rounded-xl py-2 hover:bg-primary/90 disabled:opacity-40 transition-colors font-medium"
          >
            {connecting ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Connecting…</> : <><Lock className="w-3.5 h-3.5" /> Connect</>}
          </button>
          <button onClick={onClose} className="px-4 text-sm text-on-surface-variant/60 hover:text-on-surface transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// ── VpnCard ───────────────────────────────────────────────────────────────────

function VpnCard({ conn, onRefresh }: { conn: VpnConnection; onRefresh: () => void }) {
  const [expanded, setExpanded]         = useState(false)
  const [connectModal, setConnectModal] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [removing, setRemoving]         = useState(false)

  const connected = conn.status === 'Connected'

  const disconnect = async () => {
    setDisconnecting(true)
    try {
      await api.post('/api/vpn/disconnect', { name: conn.name })
      toast.success(`Disconnected from ${conn.name}`)
      onRefresh()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Disconnect failed')
    } finally { setDisconnecting(false) }
  }

  const remove = async () => {
    if (!window.confirm(`Remove VPN connection "${conn.name}"?`)) return
    setRemoving(true)
    try {
      await api.delete(`/api/vpn/connections/${encodeURIComponent(conn.name)}`)
      toast.success(`Removed ${conn.name}`)
      onRefresh()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Remove failed')
    } finally { setRemoving(false) }
  }

  return (
    <>
      {connectModal && (
        <ConnectModal
          name={conn.name}
          onDone={() => { setConnectModal(false); onRefresh() }}
          onClose={() => setConnectModal(false)}
        />
      )}
      <div className={cn(
        'rounded-xl border transition-colors',
        connected ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-outline-variant/20 bg-surface-container'
      )}>
        {/* Header row */}
        <div className="flex items-center gap-3 px-3 py-3">
          <div className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
            connected ? 'bg-emerald-500/15' : 'bg-surface-container-high'
          )}>
            {connected
              ? <ShieldCheck className="w-4 h-4 text-emerald-500" />
              : <ShieldOff className="w-4 h-4 text-on-surface-variant/40" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-on-surface truncate">{conn.name}</p>
            <p className="text-xs text-on-surface-variant/50 truncate">{conn.server}</p>
          </div>
          <span className={cn(
            'text-[11px] font-medium px-2 py-0.5 rounded-full shrink-0',
            connected
              ? 'bg-emerald-500/15 text-emerald-600'
              : 'bg-surface-container-high text-on-surface-variant/60'
          )}>
            {conn.status || 'Disconnected'}
          </span>

          {/* Actions */}
          {connected ? (
            <button
              onClick={disconnect}
              disabled={disconnecting}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-error/10 text-error hover:bg-error/20 text-xs font-medium transition-colors disabled:opacity-40 shrink-0"
            >
              {disconnecting ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Unlock className="w-3 h-3" />}
              {disconnecting ? '' : 'Disconnect'}
            </button>
          ) : (
            <button
              onClick={() => setConnectModal(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 text-xs font-medium transition-colors shrink-0"
            >
              <Lock className="w-3 h-3" /> Connect
            </button>
          )}

          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-1 rounded-lg hover:bg-surface-variant text-on-surface-variant/40 hover:text-on-surface transition-colors shrink-0"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Expanded details */}
        {expanded && (
          <div className="px-3 pb-3 pt-0 space-y-2 border-t border-outline-variant/10">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mt-2">
              <span className="text-on-surface-variant/50">Tunnel</span>
              <span className="text-on-surface">{conn.tunnel_type || '—'}</span>
              <span className="text-on-surface-variant/50">Auth</span>
              <span className="text-on-surface">{Array.isArray(conn.auth_method) ? conn.auth_method.join(', ') : conn.auth_method || '—'}</span>
              <span className="text-on-surface-variant/50">Split tunnel</span>
              <span className="text-on-surface">{conn.split_tunnel ? 'Yes' : 'No'}</span>
            </div>
            <button
              onClick={remove}
              disabled={removing || connected}
              className="flex items-center gap-1.5 text-xs text-error/70 hover:text-error disabled:opacity-40 transition-colors"
              title={connected ? 'Disconnect first' : 'Remove connection'}
            >
              <Trash2 className="w-3 h-3" /> {removing ? 'Removing…' : 'Remove connection'}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

// ── VPNPanel ──────────────────────────────────────────────────────────────────

export function VPNPanel() {
  const [connections, setConnections] = useState<VpnConnection[]>([])
  const [wg, setWg]                   = useState<WgStatus | null>(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [connRes, wgRes] = await Promise.all([
        api.get('/api/vpn/connections'),
        api.get('/api/vpn/wireguard').catch(() => null),
      ])
      setConnections(connRes.data || [])
      if (wgRes) setWg(wgRes.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Could not load VPN info')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const connectedCount = connections.filter((c) => c.status === 'Connected').length

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Status header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className={cn('w-5 h-5', connectedCount > 0 ? 'text-emerald-500' : 'text-on-surface-variant/40')} />
          <div>
            <p className="text-sm font-semibold text-on-surface">VPN Manager</p>
            <p className="text-xs text-on-surface-variant/50">
              {connectedCount > 0 ? `${connectedCount} connected` : 'Not connected'}
              {wg?.available ? ' · WireGuard detected' : ''}
            </p>
          </div>
        </div>
        <button
          onClick={load}
          className="p-1.5 rounded-lg hover:bg-surface-container text-on-surface-variant/40 hover:text-on-surface transition-colors"
          title="Refresh"
        >
          <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-error bg-error/8 border border-error/15 rounded-xl px-4 py-3">
          <WifiOff className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {/* Connection list */}
      {loading && connections.length === 0 ? (
        <div className="flex items-center justify-center py-10 text-on-surface-variant/40 gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      ) : connections.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 gap-2 text-on-surface-variant/40">
          <ShieldOff className="w-8 h-8" />
          <p className="text-sm">No VPN connections configured</p>
          <p className="text-xs">Add one below to get started</p>
        </div>
      ) : (
        <div className="space-y-2">
          {connections.map((conn) => (
            <VpnCard key={conn.name} conn={conn} onRefresh={load} />
          ))}
        </div>
      )}

      {/* WireGuard status (if installed) */}
      {wg?.available && wg.raw && (
        <div className="rounded-xl border border-outline-variant/20 bg-surface-container p-3">
          <p className="text-xs font-semibold text-on-surface mb-2 flex items-center gap-1.5">
            <Wifi className="w-3.5 h-3.5 text-primary" /> WireGuard
          </p>
          <pre className="text-xs font-mono text-on-surface/70 whitespace-pre-wrap">{wg.raw}</pre>
        </div>
      )}

      {/* Add new */}
      <AddVpnForm onAdded={load} />
    </div>
  )
}
