import { Card, CardContent } from "@/components/ui/card"
import { FolderOpen, CheckCircle2, Package, Repeat, TrendingUp } from "lucide-react"
import type { Stats } from "@/types"

interface StatsPanelProps {
  stats: Stats
  loading?: boolean
}

export function StatsPanel({ stats, loading }: StatsPanelProps) {
  const statItems = [
    {
      label: "Total Projects",
      value: stats.total_projects,
      icon: FolderOpen,
      color: "text-violet-500",
      bgColor: "bg-violet-500/10",
      borderColor: "border-violet-500/20",
    },
    {
      label: "Completed",
      value: stats.completed_projects,
      icon: CheckCircle2,
      color: "text-green-500",
      bgColor: "bg-green-500/10",
      borderColor: "border-green-500/20",
      subtext: stats.total_projects > 0
        ? `${Math.round((stats.completed_projects / stats.total_projects) * 100)}% success`
        : undefined,
    },
    {
      label: "Components",
      value: stats.total_components,
      icon: Package,
      color: "text-purple-500",
      bgColor: "bg-purple-500/10",
      borderColor: "border-purple-500/20",
    },
    {
      label: "Reuses",
      value: stats.total_component_reuses,
      icon: Repeat,
      color: "text-orange-500",
      bgColor: "bg-orange-500/10",
      borderColor: "border-orange-500/20",
      subtext: stats.total_components > 0
        ? `${((stats.total_component_reuses / stats.total_components) * 100).toFixed(0)}% reuse rate`
        : undefined,
    },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {statItems.map((item, index) => {
        const Icon = item.icon
        return (
          <Card
            key={item.label}
            className={`relative overflow-hidden border-${item.borderColor} hover:shadow-lg transition-all duration-300 animate-fade-in-up group`}
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            {/* Gradient overlay on hover */}
            <div className={`absolute inset-0 ${item.bgColor} opacity-0 group-hover:opacity-50 transition-opacity`} />

            <CardContent className="relative p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">{item.label}</p>
                  {loading ? (
                    <div className="h-9 w-16 bg-muted animate-pulse rounded" />
                  ) : (
                    <p className="text-3xl font-bold tracking-tight">{item.value}</p>
                  )}
                  {item.subtext && !loading && (
                    <div className="flex items-center gap-1 mt-1">
                      <TrendingUp className="h-3 w-3 text-green-500" />
                      <span className="text-xs text-muted-foreground">{item.subtext}</span>
                    </div>
                  )}
                </div>
                <div className={`w-12 h-12 rounded-xl ${item.bgColor} flex items-center justify-center group-hover:scale-110 transition-transform`}>
                  <Icon className={`h-6 w-6 ${item.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
