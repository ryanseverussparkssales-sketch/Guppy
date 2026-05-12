/**
 * CalendarPanel — Monthly calendar + agenda + event CRUD
 *
 * Local events stored via /api/calendar/*. Shows a "Connect Google Calendar"
 * CTA when GOOGLE_CALENDAR_CREDENTIALS is not set (status endpoint).
 *
 * Views: Month grid | Agenda (upcoming 7 days)
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Calendar, ChevronLeft, ChevronRight, Plus, X, RefreshCw,
  Clock, MapPin, Link2, CheckCircle2, Trash2, AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/api/client'
import { toast } from 'sonner'

// ── Types ─────────────────────────────────────────────────────────────────────

interface CalEvent {
  id: string
  title: string
  description: string
  location: string
  start_time: string
  end_time: string
  all_day: boolean
  color: string
  calendar_id: string
}

const COLOR_MAP: Record<string, string> = {
  primary:   'bg-primary/20 text-primary border-primary/30',
  secondary: 'bg-secondary/20 text-secondary border-secondary/30',
  tertiary:  'bg-tertiary/20 text-tertiary border-tertiary/30',
  error:     'bg-error/20 text-error border-error/30',
  success:   'bg-success/20 text-success border-success/30',
  warning:   'bg-warning/20 text-warning border-warning/30',
}

const COLOR_DOT: Record<string, string> = {
  primary:   'bg-primary',
  secondary: 'bg-secondary',
  tertiary:  'bg-tertiary',
  error:     'bg-error',
  success:   'bg-success',
  warning:   'bg-warning',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return iso }
}

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) }
  catch { return iso }
}

function isoDateStr(d: Date) {
  return d.toISOString().slice(0, 10)
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function firstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

// ── AddEventForm ──────────────────────────────────────────────────────────────

function AddEventForm({ onSave, onClose }: { onSave: () => void; onClose: () => void }) {
  const now   = new Date()
  const later = new Date(now.getTime() + 60 * 60 * 1000)
  const pad   = (n: number) => String(n).padStart(2, '0')
  const localIso = (d: Date) =>
    `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`

  const [title,    setTitle]    = useState('')
  const [desc,     setDesc]     = useState('')
  const [loc,      setLoc]      = useState('')
  const [start,    setStart]    = useState(localIso(now))
  const [end,      setEnd]      = useState(localIso(later))
  const [color,    setColor]    = useState('primary')
  const [allDay,   setAllDay]   = useState(false)
  const [saving,   setSaving]   = useState(false)
  const [err,      setErr]      = useState('')

  const save = async () => {
    if (!title.trim()) { setErr('Title is required'); return }
    setSaving(true)
    try {
      await api.post('/api/calendar/events', {
        title: title.trim(), description: desc, location: loc,
        start_time: new Date(start).toISOString(),
        end_time:   new Date(end).toISOString(),
        all_day: allDay, color,
      })
      toast.success('Event created')
      onSave()
    } catch {
      setErr('Failed to save event')
      toast.error('Failed to save event')
    } finally { setSaving(false) }
  }

  const COLORS = ['primary', 'secondary', 'tertiary', 'success', 'warning', 'error']

  return (
    <div className="absolute inset-0 bg-surface z-20 flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/20 flex-shrink-0">
        <Plus className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold text-on-surface flex-1">New Event</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        <input
          className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
          placeholder="Event title"
          value={title} onChange={(e) => setTitle(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">Start</label>
            <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)}
              className="w-full bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none focus:border-primary/40" />
          </div>
          <div>
            <label className="text-xs text-on-surface-variant/50 mb-1 block">End</label>
            <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)}
              className="w-full bg-surface-container rounded-xl px-3 py-2 text-xs text-on-surface border border-outline-variant/20 focus:outline-none focus:border-primary/40" />
          </div>
        </div>
        <label className="flex items-center gap-2 text-xs text-on-surface-variant/60">
          <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)}
            className="rounded" />
          All day
        </label>
        <input
          className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
          placeholder="Location (optional)"
          value={loc} onChange={(e) => setLoc(e.target.value)}
        />
        <textarea
          className="w-full bg-surface-container rounded-xl px-3 py-2 text-sm text-on-surface placeholder-on-surface-variant/40 border border-outline-variant/20 focus:outline-none focus:border-primary/40 resize-none"
          placeholder="Description (optional)" rows={2}
          value={desc} onChange={(e) => setDesc(e.target.value)}
        />
        {/* Color picker */}
        <div>
          <label className="text-xs text-on-surface-variant/50 mb-1.5 block">Color</label>
          <div className="flex gap-2">
            {COLORS.map((c) => (
              <button key={c} onClick={() => setColor(c)}
                className={cn('w-6 h-6 rounded-full transition-all', COLOR_DOT[c],
                  color === c && 'ring-2 ring-offset-2 ring-on-surface/50')} />
            ))}
          </div>
        </div>
        {err && <p className="text-xs text-error/80">{err}</p>}
      </div>
      <div className="flex gap-2 px-4 py-3 border-t border-outline-variant/15 flex-shrink-0">
        <button onClick={onClose} className="flex-1 py-2 text-xs rounded-xl bg-surface-variant text-on-surface-variant hover:bg-surface-container-high transition-colors">
          Cancel
        </button>
        <button onClick={save} disabled={saving}
          className="flex-1 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-40 transition-colors font-medium">
          {saving ? 'Saving…' : 'Save event'}
        </button>
      </div>
    </div>
  )
}

// ── MonthGrid ─────────────────────────────────────────────────────────────────

function MonthGrid({
  year, month, events, onDayClick,
}: {
  year: number
  month: number
  events: CalEvent[]
  onDayClick: (date: string) => void
}) {
  const days    = daysInMonth(year, month)
  const firstDow = firstDayOfMonth(year, month)
  const today   = isoDateStr(new Date())
  const DAYS    = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

  // Index events by date
  const evMap: Record<string, CalEvent[]> = {}
  for (const ev of events) {
    const d = ev.start_time.slice(0, 10)
    if (!evMap[d]) evMap[d] = []
    evMap[d].push(ev)
  }

  const cells = []
  // Leading blanks
  for (let i = 0; i < firstDow; i++) cells.push(null)
  for (let d = 1; d <= days; d++) cells.push(d)

  const pad = (n: number) => String(n).padStart(2, '0')
  const monthStr = `${year}-${pad(month + 1)}`

  return (
    <div>
      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 mb-1">
        {DAYS.map((d) => (
          <div key={d} className="text-center text-xs text-on-surface-variant/40 py-1">{d}</div>
        ))}
      </div>
      {/* Cells */}
      <div className="grid grid-cols-7 gap-px">
        {cells.map((day, i) => {
          if (!day) return <div key={`blank-${i}`} />
          const dateStr = `${monthStr}-${pad(day)}`
          const dayEvs  = evMap[dateStr] || []
          const isToday = dateStr === today
          return (
            <button
              key={dateStr}
              onClick={() => onDayClick(dateStr)}
              className={cn(
                "relative min-h-[52px] p-1 rounded-lg text-left transition-colors hover:bg-surface-variant/40",
                isToday && "bg-primary/8",
              )}
            >
              <span className={cn(
                "text-xs font-medium block w-5 h-5 flex items-center justify-center rounded-full",
                isToday ? "bg-primary text-on-primary" : "text-on-surface-variant/60",
              )}>{day}</span>
              {dayEvs.slice(0, 2).map((ev) => (
                <div key={ev.id} className={cn(
                  "text-[10px] leading-tight px-1 py-0.5 rounded mt-0.5 truncate border",
                  COLOR_MAP[ev.color] || COLOR_MAP.primary,
                )}>
                  {ev.title}
                </div>
              ))}
              {dayEvs.length > 2 && (
                <span className="text-[10px] text-on-surface-variant/40 pl-1">+{dayEvs.length - 2}</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── DayDetail ─────────────────────────────────────────────────────────────────

function DayDetail({
  date, events, onDelete, onClose,
}: {
  date: string
  events: CalEvent[]
  onDelete: (id: string) => void
  onClose: () => void
}) {
  return (
    <div className="absolute inset-0 bg-surface z-10 flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-outline-variant/20 flex-shrink-0">
        <Calendar className="w-4 h-4 text-primary/60" />
        <span className="text-xs font-semibold text-on-surface flex-1">{fmtDate(date + 'T12:00')}</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {events.length === 0 ? (
          <p className="text-xs text-on-surface-variant/40 text-center pt-8">No events this day</p>
        ) : events.map((ev) => (
          <div key={ev.id} className={cn("rounded-xl p-3 border space-y-1", COLOR_MAP[ev.color] || COLOR_MAP.primary)}>
            <div className="flex items-start gap-2">
              <div className={cn("w-2.5 h-2.5 rounded-full mt-0.5 flex-shrink-0", COLOR_DOT[ev.color])} />
              <p className="text-sm font-medium text-on-surface flex-1">{ev.title}</p>
              <button onClick={() => onDelete(ev.id)}
                className="p-0.5 rounded hover:bg-error/10 text-on-surface-variant/30 hover:text-error transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
            {!ev.all_day && (
              <div className="flex items-center gap-1.5 pl-4">
                <Clock className="w-3 h-3 text-on-surface-variant/50" />
                <span className="text-xs text-on-surface-variant/60">
                  {fmtTime(ev.start_time)} – {fmtTime(ev.end_time)}
                </span>
              </div>
            )}
            {ev.location && (
              <div className="flex items-center gap-1.5 pl-4">
                <MapPin className="w-3 h-3 text-on-surface-variant/50" />
                <span className="text-xs text-on-surface-variant/60">{ev.location}</span>
              </div>
            )}
            {ev.description && (
              <p className="text-xs text-on-surface-variant/60 pl-4">{ev.description}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── CalendarPanel ─────────────────────────────────────────────────────────────

export function CalendarPanel() {
  const now  = new Date()
  const [year,    setYear]    = useState(now.getFullYear())
  const [month,   setMonth]   = useState(now.getMonth())
  const [events,  setEvents]  = useState<CalEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [gConnected, setGConnected] = useState<boolean | null>(null)
  const [addOpen,  setAddOpen]  = useState(false)
  const [dayDate,  setDayDate]  = useState<string | null>(null)

  const MONTH_NAMES = ['January','February','March','April','May','June',
                       'July','August','September','October','November','December']

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const pad = (n: number) => String(n).padStart(2, '0')
      const start = `${year}-${pad(month + 1)}-01`
      const lastDay = daysInMonth(year, month)
      const end = `${year}-${pad(month + 1)}-${pad(lastDay)}T23:59:59`
      const [evRes, stRes] = await Promise.all([
        api.get(`/api/calendar/events?start=${start}&end=${end}&limit=500`),
        api.get('/api/calendar/status'),
      ])
      setEvents(Array.isArray(evRes.data) ? evRes.data : [])
      setGConnected(stRes.data?.google_connected ?? false)
    } catch {
      setError('Failed to load calendar')
    } finally {
      setLoading(false)
    }
  }, [year, month])

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [load])

  const prevMonth = () => { if (month === 0) { setYear(y => y - 1); setMonth(11) } else setMonth(m => m - 1) }
  const nextMonth = () => { if (month === 11) { setYear(y => y + 1); setMonth(0) } else setMonth(m => m + 1) }

  const deleteEvent = async (id: string) => {
    if (!window.confirm('Delete this event?')) return
    await api.delete(`/api/calendar/events/${id}`)
      .then(() => toast.success('Event deleted'))
      .catch(() => toast.error('Failed to delete event'))
    setEvents((e) => e.filter((ev) => ev.id !== id))
  }

  const dayEvents = dayDate ? events.filter((e) => e.start_time.startsWith(dayDate)) : []

  return (
    <div className="relative flex flex-col h-full p-4 gap-3">
      {addOpen && <AddEventForm onSave={() => { setAddOpen(false); load() }} onClose={() => setAddOpen(false)} />}
      {dayDate && (
        <DayDetail
          date={dayDate}
          events={dayEvents}
          onDelete={async (id) => { await deleteEvent(id); if (dayEvents.length <= 1) setDayDate(null) }}
          onClose={() => setDayDate(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Calendar className="w-4 h-4 text-primary/70" />
        <span className="text-sm font-semibold text-on-surface">Calendar</span>
        {gConnected === false && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-warning/10 text-warning font-medium">
            Local only
          </span>
        )}
        {gConnected === true && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success font-medium flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Google synced
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => { setYear(now.getFullYear()); setMonth(now.getMonth()) }}
            className="text-xs px-2 py-1 rounded-lg bg-surface-variant text-on-surface-variant/60 hover:text-on-surface transition-colors">
            Today
          </button>
          <button onClick={load} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/40">
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Google Calendar CTA */}
      {gConnected === false && (
        <div className="flex items-start gap-2.5 bg-primary/5 rounded-xl p-3 border border-primary/10 flex-shrink-0">
          <Link2 className="w-4 h-4 text-primary/60 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-on-surface">Connect Google Calendar</p>
            <p className="text-xs text-on-surface-variant/50 mt-0.5">
              Set <span className="font-mono text-primary/70">GOOGLE_CALENDAR_CREDENTIALS</span> to
              your OAuth token path and restart. Events sync automatically.
            </p>
          </div>
        </div>
      )}

      {/* Month navigation */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <button onClick={prevMonth} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 transition-colors">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="flex-1 text-center text-sm font-semibold text-on-surface">
          {MONTH_NAMES[month]} {year}
        </span>
        <button onClick={nextMonth} className="p-1 rounded hover:bg-surface-variant text-on-surface-variant/50 transition-colors">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Calendar grid */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {error ? (
          <div className="flex items-center gap-2 text-xs text-error/70 bg-error/5 rounded-xl px-3 py-2 mt-2">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            {error}
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-5 h-5 animate-spin text-on-surface-variant/40" />
          </div>
        ) : (
          <MonthGrid
            year={year} month={month} events={events}
            onDayClick={setDayDate}
          />
        )}
      </div>

      {/* Add event */}
      <button onClick={() => setAddOpen(true)}
        className="flex items-center justify-center gap-2 py-2 text-xs rounded-xl bg-primary/10 text-primary hover:bg-primary/15 transition-colors font-medium flex-shrink-0">
        <Plus className="w-3.5 h-3.5" />
        Add event
      </button>
    </div>
  )
}
