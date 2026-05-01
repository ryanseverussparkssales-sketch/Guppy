import { useCallback } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, Layers, BookOpen,
  Cpu, Wrench, Settings,
  ShieldCheck, Zap, ToggleLeft, ToggleRight,
  ChevronRight,
} from 'lucide-react'
import { useProviders } from '@/api/queries'
import { useTools, useSetToolEnabled } from '@/api/queries'
import { useSettings, useSetActiveProvider } from '@/api/queries'

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

const NAV_ITEMS = [
  { id: 'companion',    label: 'Conversations', icon: MessageSquare, route: '/companion' },
  { id: 'workspace',    label: 'Workspace',     icon: Layers,        route: '/workspace' },
  { id: 'codespace',    label: 'Codespace',     icon: Wrench,        route: '/codespace' },
  { id: 'control',      label: 'Control Panel', icon: Cpu,           route: '/control' },
  { id: 'settings',     label: 'Settings',      icon: Settings,      route: '/settings' },
  { id: 'instructions', label: 'Instructions',  icon: BookOpen,      route: '/instructions' },
  { id: 'admin',        label: 'Admin',         icon: ShieldCheck,   route: '/admin' },
]

const PROVIDER_LABELS: Record<string, string> = {
  local: 'Local (Ollama)',
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()

  const providers     = useProviders({ enabled: open })
  const tools         = useTools({ enabled: open })
  const settings      = useSettings({ enabled: open })
  const setProvider   = useSetActiveProvider()
  const setToolEnabled = useSetToolEnabled()

  const activeProvider = settings.data?.active_provider

  const go = useCallback((route: string) => {
    navigate(route)
    onClose()
  }, [navigate, onClose])

  const activateProvider = useCallback((provider: string) => {
    setProvider.mutate(provider)
    onClose()
  }, [setProvider, onClose])

  const toggleTool = useCallback((toolId: string, currentlyEnabled: boolean) => {
    setToolEnabled.mutate({ toolId, enabled: !currentlyEnabled })
    onClose()
  }, [setToolEnabled, onClose])

  if (!open) return null

  const providerEntries = providers.data
    ? Object.entries(providers.data).filter(([p]) => p !== activeProvider)
    : []

  const toolList = tools.data ?? []

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-xl bg-surface border border-outline-variant rounded-xl shadow-2xl overflow-hidden">
        <Command
          label="Command palette"
          shouldFilter={true}
          className="flex flex-col"
        >
          <div className="flex items-center border-b border-outline-variant px-3">
            <span className="text-on-surface-variant mr-2 flex-shrink-0">⌘</span>
            <Command.Input
              autoFocus
              placeholder="Type a command or search…"
              className="w-full py-3 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant outline-none"
            />
            <kbd
              onClick={onClose}
              className="ml-2 px-1.5 py-0.5 rounded text-xs text-on-surface-variant border border-outline-variant cursor-pointer hover:bg-surface-variant flex-shrink-0"
            >
              Esc
            </kbd>
          </div>

          <Command.List className="max-h-[min(400px,60vh)] overflow-y-auto py-2">
            <Command.Empty className="py-8 text-center text-sm text-on-surface-variant">
              No results found.
            </Command.Empty>

            {/* Navigation */}
            <Command.Group heading="Navigate" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-on-surface-variant">
              {NAV_ITEMS.map((item) => (
                <Command.Item
                  key={item.id}
                  value={`navigate ${item.label}`}
                  onSelect={() => go(item.route)}
                  className="flex items-center gap-3 px-3 py-2 text-sm cursor-pointer text-on-surface data-[selected=true]:bg-surface-variant rounded-lg mx-1"
                >
                  <item.icon className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                  <span>{item.label}</span>
                  <ChevronRight className="w-3 h-3 text-on-surface-variant ml-auto" />
                </Command.Item>
              ))}
            </Command.Group>

            {/* Provider switching */}
            {providerEntries.length > 0 && (
              <Command.Group heading="Switch Provider" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-on-surface-variant">
                {providerEntries.map(([provider, info]) => (
                  <Command.Item
                    key={provider}
                    value={`switch provider ${provider} ${PROVIDER_LABELS[provider] ?? provider}`}
                    onSelect={() => activateProvider(provider)}
                    className="flex items-center gap-3 px-3 py-2 text-sm cursor-pointer text-on-surface data-[selected=true]:bg-surface-variant rounded-lg mx-1"
                  >
                    <Zap className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <span>Use {PROVIDER_LABELS[provider] ?? provider}</span>
                    {!info.configured && (
                      <span className="ml-auto text-xs text-on-surface-variant">(not configured)</span>
                    )}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {/* Tool toggles */}
            {toolList.length > 0 && (
              <Command.Group heading="Toggle Tools" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-on-surface-variant">
                {toolList.map((tool) => (
                  <Command.Item
                    key={tool.id}
                    value={`tool ${tool.name} ${tool.isEnabled ? 'disable' : 'enable'}`}
                    onSelect={() => toggleTool(tool.id, tool.isEnabled)}
                    className="flex items-center gap-3 px-3 py-2 text-sm cursor-pointer text-on-surface data-[selected=true]:bg-surface-variant rounded-lg mx-1"
                  >
                    {tool.isEnabled
                      ? <ToggleRight className="w-4 h-4 text-primary flex-shrink-0" />
                      : <ToggleLeft className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    }
                    <span>{tool.isEnabled ? 'Disable' : 'Enable'} {tool.name}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
