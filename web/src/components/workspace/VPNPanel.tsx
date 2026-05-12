/**
 * VPNPanel — Mullvad VPN control panel.
 * Shows connection status, relay info, quick connect/disconnect/reconnect,
 * relay location picker, and kill-switch toggle.
 */
import { useState, useEffect, useCallback } from 'react'
import { Shield, ShieldOff, RefreshCw, Wifi, WifiOff, Globe, Lock, Unlock } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import toast from 'react-hot-toast'

interface VpnStatus {
  available: boolean
  connected: boolean
  state: string
  relay?: string
  location?: { country: string; city: string }
  tunnel_type?: string
}

interface RelayCountry {
  name: string
  code: string
  cities: { name: string; code: string }[]
}

export function VPNPanel() {
  const [status, setStatus]         = useState<VpnStatus | null>(null)
  const [relays, setRelays]         = useState<RelayCountry[]>([])
  const [killSwitch, setKillSwitch] = useState(false)
  const [loading, setLoading]       = useState(false)
  const [country, setCountry]       = useState('')
  const [city, setCity]             = useState('')

  const loadStatus = useCallback(async () => {
    try {
      const [s, ks] = await Promise.all([
        api.get('/api/vpn/status'),
        api.get('/api/vpn/killswitch'),
      ])
      setStatus(s.data)
      setKillSwitch(ks.data?.enabled ?? false)
    } catch {
      setStatus({ available: false, connected: false, state: 'error' })
    }
  }, [])

  const loadRelays = useCallback(async () => {
    try {
      const r = await api.get('/api/vpn/relays')
      setRelays(Array.isArray(r.data) ? r.data : [])
    } catch {}
  }, [])

  useEffect(() => {
    loadStatus()
    loadRelays()
    const id = setInterval(loadStatus, 10_000)
    return () => clearInterval(id)
  }, [loadStatus, loadRelays])

  const act = useCallback(async (action: 'connect' | 'disconnect' | 'reconnect') => {
    setLoading(true)
    try {
      if (action === 'connect') {
        await api.post('/api/vpn/connect', (country || city) ? { country: country || undefined, city: city || undefined } : undefined)
        toast.success('Connecting to Mullvad…')
      } else if (action === 'disconnect') {
        await api.post('/api/vpn/disconnect')
        toast.success('Disconnected')
      } else {
        await api.post('/api/vpn/reconnect')
        toast.success('Reconnecting…')
      }
      setTimeout(loadStatus, 1500)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'VPN action failed')
    } finally {
      setLoading(false)
    }
  }, [country, city, loadStatus])

  const toggleKillSwitch = useCallback(async () => {
    try {
      const next = !killSwitch
      await api.post('/api/vpn/killswitch', { enabled: next })
      setKillSwitch(next)
      toast.success(`Kill-switch ${next ? 'enabled' : 'disabled'}`)
    } catch {
      toast.error('Failed to toggle kill-switch')
    }
  }, [killSwitch])

  if (!status) {
    return <div className="p-6 text-on-surface-variant/50 text-sm">Loading…</div>
  }

  if (!status.available) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-on-surface-variant/50">
        <ShieldOff className="w-10 h-10" />
        <p className="text-sm">Mullvad VPN is not installed.</p>
        <p className="text-xs">Install the Mullvad desktop app and ensure the CLI is on PATH.</p>
      </div>
    )
  }

  const isConnected     = status.connected
  const isTransitioning = ['connecting', 'disconnecting'].includes(status.state)
  const selectedCities  = relays.find(c => c.code === country)?.cities ?? []

  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 gap-4">

      {/* Status card */}
      <div className={cn(
        'rounded-xl border p-4 flex items-start gap-4 transition-colors',
        isConnected
          ? 'border-primary/30 bg-primary/5'
          : 'border-outline-variant/20 bg-surface-container-low/40'
      )}>
        <div className={cn(
          'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
          isConnected ? 'bg-primary/20 text-primary' : 'bg-surface-container text-on-surface-variant/40'
        )}>
          {isConnected ? <Shield className="w-5 h-5" /> : <ShieldOff className="w-5 h-5" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn('text-sm font-semibold', isConnected ? 'text-primary' : 'text-on-surface-variant')}>
              {isConnected ? 'Protected' : isTransitioning ? status.state : 'Unprotected'}
            </span>
            {isTransitioning && <RefreshCw className="w-3 h-3 animate-spin text-on-surface-variant/50" />}
          </div>
          {status.location && (
            <p className="text-xs text-on-surface-variant/60 mt-0.5">
              <Globe className="w-3 h-3 inline mr-1" />
              {status.location.city}, {status.location.country}
            </p>
          )}
          {status.relay && (
            <p className="text-xs text-on-surface-variant/40 font-mono mt-0.5">{status.relay}</p>
          )}
          {status.tunnel_type && (
            <p className="text-xs text-on-surface-variant/40 mt-0.5">{status.tunnel_type}</p>
          )}
        </div>
        <div className="flex-shrink-0">
          {isConnected
            ? <Wifi className="w-4 h-4 text-primary" />
            : <WifiOff className="w-4 h-4 text-on-surface-variant/40" />}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        {!isConnected ? (
          <button
            onClick={() => act('connect')}
            disabled={loading || isTransitioning}
            className="flex-1 py-2 px-4 rounded-lg bg-primary text-on-primary text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            Connect
          </button>
        ) : (
          <>
            <button
              onClick={() => act('disconnect')}
              disabled={loading || isTransitioning}
              className="flex-1 py-2 px-4 rounded-lg border border-outline-variant/30 text-on-surface-variant text-sm font-medium hover:bg-surface-variant/30 transition-colors disabled:opacity-50"
            >
              Disconnect
            </button>
            <button
              onClick={() => act('reconnect')}
              disabled={loading || isTransitioning}
              title="Reconnect (cycle relay)"
              className="py-2 px-3 rounded-lg border border-outline-variant/30 text-on-surface-variant hover:bg-surface-variant/30 transition-colors disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </>
        )}
      </div>

      {/* Relay picker */}
      <div className="rounded-xl border border-outline-variant/20 bg-surface-container-low/30 p-4 flex flex-col gap-3">
        <h3 className="text-xs font-semibold text-on-surface-variant/60 uppercase tracking-wide">Relay Location</h3>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">Country</label>
            <select
              value={country}
              onChange={e => { setCountry(e.target.value); setCity('') }}
              className="w-full text-sm bg-surface-container border border-outline-variant/25 rounded-lg px-2.5 py-1.5 text-on-surface focus:outline-none focus:border-primary/40"
            >
              <option value="">Any</option>
              {relays.map(c => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">City</label>
            <select
              value={city}
              onChange={e => setCity(e.target.value)}
              disabled={!country}
              className="w-full text-sm bg-surface-container border border-outline-variant/25 rounded-lg px-2.5 py-1.5 text-on-surface focus:outline-none focus:border-primary/40 disabled:opacity-40"
            >
              <option value="">Any</option>
              {selectedCities.map(c => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>
        {(country || city) && (
          <button
            onClick={() =>
              api.post('/api/vpn/relay', { country: country || undefined, city: city || undefined })
                .then(() => toast.success('Relay updated'))
                .catch(() => toast.error('Failed'))
            }
            className="text-xs text-primary hover:underline text-left"
          >
            Apply without connecting
          </button>
        )}
      </div>

      {/* Kill-switch */}
      <div className="rounded-xl border border-outline-variant/20 bg-surface-container-low/30 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {killSwitch
            ? <Lock className="w-4 h-4 text-warning" />
            : <Unlock className="w-4 h-4 text-on-surface-variant/40" />}
          <div>
            <p className="text-sm font-medium text-on-surface">Kill-switch</p>
            <p className="text-xs text-on-surface-variant/50">Block all traffic if VPN drops</p>
          </div>
        </div>
        <button
          onClick={toggleKillSwitch}
          className={cn(
            'relative w-10 h-5 rounded-full transition-colors flex-shrink-0',
            killSwitch ? 'bg-warning' : 'bg-outline-variant/40'
          )}
        >
          <span className={cn(
            'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all',
            killSwitch ? 'left-[22px]' : 'left-0.5'
          )} />
        </button>
      </div>

    </div>
  )
}
