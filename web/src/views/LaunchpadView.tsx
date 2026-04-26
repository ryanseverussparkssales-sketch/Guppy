import { useStatus } from '@/api/queries'
import LauncherView from './LauncherView'

export default function LaunchpadView() {
  const { data: status } = useStatus()

  const chips = [
    { label: 'API',    ok: status?.status === 'healthy' },
    { label: 'Memory', ok: status?.memory_available },
    { label: 'Voice',  ok: status?.voice_available },
    { label: 'Local',  ok: status?.local_runtime?.chat_ready },
  ]

  return (
    <div className="flex flex-col h-full bg-[#0a0a10]">
      {/* compact status strip */}
      <div className="flex items-center gap-3 px-5 py-2 bg-[#0d0d14] border-b border-[#1e1e2a] shrink-0">
        <span className="text-xs font-semibold text-slate-500 mr-1 tracking-wider uppercase">Status</span>
        {chips.map(c => (
          <span
            key={c.label}
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              c.ok ? 'bg-green-500/15 text-green-400' : 'bg-slate-700/30 text-slate-600'
            }`}
          >
            {c.ok ? '● ' : '○ '}{c.label}
          </span>
        ))}
        {status?.local_runtime && (
          <span className="ml-auto text-xs text-slate-600 font-mono">
            {status.local_runtime.backend} · {status.local_runtime.state}
          </span>
        )}
      </div>

      {/* service manager */}
      <div className="flex-1 min-h-0">
        <LauncherView />
      </div>
    </div>
  )
}
