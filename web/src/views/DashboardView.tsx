import React from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Server,
  MessageSquare,
  Brain,
  Wrench,
  Activity,
  ArrowUpRight,
  Clock,
  Zap,
} from "lucide-react"
import { useInstances, useModels, useSystemStatus } from "@/hooks/useApi"

/**
 * DashboardView - Main dashboard with system overview
 * 
 * BACKEND INTEGRATION:
 * - GET /api/instances -> Instance count and status
 * - GET /api/models -> Available models
 * - GET /api/status -> System metrics (CPU, memory, uptime)
 * - All data fetched via SWR hooks with automatic revalidation
 */
export default function DashboardView() {
  const { instances, isLoading: instancesLoading } = useInstances()
  const { models, isLoading: modelsLoading } = useModels()
  const { status, isLoading: statusLoading } = useSystemStatus()

  const runningInstances = instances?.filter(i => i.status === 'running').length || 0
  const totalInstances = instances?.length || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your Guppy AI assistant system
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Instances"
          value={instancesLoading ? "..." : `${runningInstances}/${totalInstances}`}
          description="Running / Total"
          icon={<Server className="h-4 w-4" />}
          trend={runningInstances > 0 ? "positive" : "neutral"}
        />
        <StatCard
          title="Models Available"
          value={modelsLoading ? "..." : String(models?.length || 0)}
          description="LLM models configured"
          icon={<Brain className="h-4 w-4" />}
        />
        <StatCard
          title="Conversations"
          value="--"
          description="Active sessions"
          icon={<MessageSquare className="h-4 w-4" />}
        />
        <StatCard
          title="Tools Enabled"
          value="--"
          description="Available integrations"
          icon={<Wrench className="h-4 w-4" />}
        />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System Status */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              System Status
            </CardTitle>
            <CardDescription>Real-time system metrics</CardDescription>
          </CardHeader>
          <CardContent>
            {statusLoading ? (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                Loading system status...
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                  label="CPU Usage"
                  value={status?.cpu ? `${status.cpu}%` : "--"}
                  status={getMetricStatus(status?.cpu, 80, 60)}
                />
                <MetricCard
                  label="Memory"
                  value={status?.memory ? `${status.memory}%` : "--"}
                  status={getMetricStatus(status?.memory, 85, 70)}
                />
                <MetricCard
                  label="Uptime"
                  value={status?.uptime || "--"}
                  icon={<Clock className="h-3 w-3" />}
                />
                <MetricCard
                  label="API Latency"
                  value={status?.latency ? `${status.latency}ms` : "--"}
                  icon={<Zap className="h-3 w-3" />}
                  status={getMetricStatus(status?.latency, 200, 100, true)}
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <QuickActionButton
              label="New Chat"
              description="Start a conversation"
              href="/assistant"
            />
            <QuickActionButton
              label="Manage Instances"
              description="View and control instances"
              href="/instances"
            />
            <QuickActionButton
              label="Configure Models"
              description="Add or edit LLM models"
              href="/models"
            />
            <QuickActionButton
              label="System Settings"
              description="Configure Guppy"
              href="/settings"
            />
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>
            Latest events and conversations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-32 text-muted-foreground border border-dashed border-border rounded-lg">
            {/* BACKEND: GET /api/activity or /api/events */}
            Activity feed will appear here when backend is connected
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// Helper Components

interface StatCardProps {
  title: string
  value: string
  description: string
  icon: React.ReactNode
  trend?: "positive" | "negative" | "neutral"
}

function StatCard({ title, value, description, icon, trend }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            {icon}
          </div>
          {trend === "positive" && (
            <Badge variant="success" className="text-xs">Active</Badge>
          )}
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  )
}

interface MetricCardProps {
  label: string
  value: string
  status?: "good" | "warning" | "critical"
  icon?: React.ReactNode
}

function MetricCard({ label, value, status, icon }: MetricCardProps) {
  const statusColors = {
    good: "text-success",
    warning: "text-warning",
    critical: "text-destructive",
  }

  return (
    <div className="p-3 bg-muted/50 rounded-lg">
      <p className="text-xs text-muted-foreground flex items-center gap-1">
        {icon}
        {label}
      </p>
      <p className={`text-lg font-semibold ${status ? statusColors[status] : "text-foreground"}`}>
        {value}
      </p>
    </div>
  )
}

function getMetricStatus(
  value: number | undefined,
  criticalThreshold: number,
  warningThreshold: number,
  invertedScale = false
): "good" | "warning" | "critical" | undefined {
  if (value === undefined) return undefined
  
  if (invertedScale) {
    if (value >= criticalThreshold) return "critical"
    if (value >= warningThreshold) return "warning"
    return "good"
  }
  
  if (value >= criticalThreshold) return "critical"
  if (value >= warningThreshold) return "warning"
  return "good"
}

interface QuickActionButtonProps {
  label: string
  description: string
  href: string
}

function QuickActionButton({ label, description, href }: QuickActionButtonProps) {
  const handleClick = () => {
    const view = href.replace("/", "") || "dashboard"
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
  }

  return (
    <button
      onClick={handleClick}
      className="w-full flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent/50 transition-colors text-left group"
    >
      <div>
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <ArrowUpRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
    </button>
  )
}
