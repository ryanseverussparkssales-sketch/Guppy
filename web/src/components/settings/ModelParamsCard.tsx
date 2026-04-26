import { Sliders, RefreshCw, Save } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ModelParamsCardProps {
  temperature: number
  maxTokens: string
  isPending: boolean
  onTemperatureChange: (v: number) => void
  onMaxTokensChange: (v: string) => void
  onSave: () => void
}

export function ModelParamsCard({
  temperature,
  maxTokens,
  isPending,
  onTemperatureChange,
  onMaxTokensChange,
  onSave,
}: ModelParamsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sliders className="w-5 h-5" />
          Model Parameters
        </CardTitle>
        <CardDescription>Default parameters for AI model interactions</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label htmlFor="temperature" className="text-sm font-medium text-on-surface">
              Temperature
            </label>
            <span className="text-sm font-bold text-primary">{temperature.toFixed(2)}</span>
          </div>
          <input
            id="temperature"
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={temperature}
            onChange={(e) => onTemperatureChange(parseFloat(e.target.value))}
            className="w-full h-2 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
          />
          <p className="text-xs text-on-surface-variant">
            Lower values (0.0–0.7) produce focused outputs. Higher values (0.7–2.0) increase creativity.
          </p>
        </div>

        <div className="space-y-3">
          <label htmlFor="max-tokens" className="text-sm font-medium text-on-surface">
            Max Tokens
          </label>
          <Input
            id="max-tokens"
            type="number"
            placeholder="4096"
            value={maxTokens}
            onChange={(e) => onMaxTokensChange(e.target.value)}
            className="max-w-xs"
          />
          <p className="text-xs text-on-surface-variant">
            Maximum length of generated responses.
          </p>
        </div>

        <div className="flex justify-end">
          <Button onClick={onSave} size="lg" disabled={isPending}>
            {isPending
              ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              : <Save className="w-4 h-4 mr-2" />}
            {isPending ? 'Saving…' : 'Save Settings'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
