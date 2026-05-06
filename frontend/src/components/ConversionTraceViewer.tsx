import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { projectsApi } from "@/api/client"
import { Activity, ChevronDown, ChevronRight, Copy, Download, Clock, Cpu, Wrench, MessageSquare } from "lucide-react"

interface ConversionTraceViewerProps {
  projectId: number
}

export function ConversionTraceViewer({ projectId }: ConversionTraceViewerProps) {
  const [expanded, setExpanded] = useState(false)
  const [showPrompts, setShowPrompts] = useState(false)
  const [showMessages, setShowMessages] = useState(false)
  const [showTools, setShowTools] = useState(false)

  const { data: trace, isLoading, error, refetch } = useQuery({
    queryKey: ["trace", projectId],
    queryFn: () => projectsApi.getTrace(projectId),
    enabled: expanded,
    retry: false,
  })

  return (
    <Card>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={() => {
          setExpanded(!expanded)
          if (!expanded && !trace) refetch()
        }}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Conversion Trace
          </CardTitle>
          <div className="flex items-center gap-2">
            {trace && (
              <>
                <Badge variant="outline" className="text-xs">
                  <Cpu className="h-3 w-3 mr-1" />
                  {(trace.total_input_tokens + trace.total_output_tokens).toLocaleString()} tokens
                </Badge>
                <Badge variant="outline" className="text-xs">
                  <Wrench className="h-3 w-3 mr-1" />
                  {trace.tool_calls?.length || 0} tools
                </Badge>
                <Badge variant="outline" className="text-xs">
                  <MessageSquare className="h-3 w-3 mr-1" />
                  {trace.agent_messages?.length || 0} turns
                </Badge>
              </>
            )}
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-4">
          {isLoading && <p className="text-sm text-muted-foreground">Loading trace...</p>}
          {error && (
            <p className="text-sm text-muted-foreground">
              No trace available for this project.
            </p>
          )}
          {trace && (
            <>
              {/* Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-muted rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">Model</p>
                  <p className="text-sm font-medium">{trace.model || "N/A"}</p>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">Input Tokens</p>
                  <p className="text-sm font-medium">{trace.total_input_tokens?.toLocaleString() || 0}</p>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">Output Tokens</p>
                  <p className="text-sm font-medium">{trace.total_output_tokens?.toLocaleString() || 0}</p>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">Duration</p>
                  <p className="text-sm font-medium">
                    {trace.finished_at && trace.started_at
                      ? `${Math.round((new Date(trace.finished_at).getTime() - new Date(trace.started_at).getTime()) / 1000)}s`
                      : "N/A"}
                  </p>
                </div>
              </div>

              {/* System Prompt */}
              <CollapsibleSection
                title="System Prompt"
                badge={trace.system_prompt ? `${trace.system_prompt.length.toLocaleString()} chars` : ""}
                open={showPrompts}
                onToggle={() => setShowPrompts(!showPrompts)}
              >
                <pre className="text-xs bg-zinc-950 text-zinc-300 p-3 rounded-lg overflow-auto max-h-[400px] whitespace-pre-wrap">
                  {trace.system_prompt || "Not captured"}
                </pre>
              </CollapsibleSection>

              {/* Conversion Prompt */}
              <CollapsibleSection
                title="Conversion Prompt (Design Data)"
                badge={trace.conversion_prompt ? `${trace.conversion_prompt.length.toLocaleString()} chars` : ""}
                open={showMessages}
                onToggle={() => setShowMessages(!showMessages)}
              >
                <pre className="text-xs bg-zinc-950 text-zinc-300 p-3 rounded-lg overflow-auto max-h-[400px] whitespace-pre-wrap">
                  {trace.conversion_prompt || "Not captured"}
                </pre>
              </CollapsibleSection>

              {/* Tool Calls */}
              <CollapsibleSection
                title="Tool Calls"
                badge={`${trace.tool_calls?.length || 0} calls`}
                open={showTools}
                onToggle={() => setShowTools(!showTools)}
              >
                <div className="space-y-1 max-h-[400px] overflow-auto">
                  {trace.tool_calls?.map((tc: any, i: number) => (
                    <div key={i} className="text-xs bg-zinc-950 text-zinc-300 p-2 rounded flex items-start gap-2">
                      <Badge variant="secondary" className="text-[10px] shrink-0 mt-0.5">
                        {tc.tool_name || tc.tool}
                      </Badge>
                      <span className="text-zinc-500 truncate">
                        {tc.args_preview || tc.args || ""}
                      </span>
                    </div>
                  )) || <p className="text-xs text-muted-foreground">No tool calls</p>}
                </div>
              </CollapsibleSection>

              {/* Actions */}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigator.clipboard.writeText(JSON.stringify(trace, null, 2))}
                >
                  <Copy className="h-3 w-3 mr-1" /> Copy Full Trace
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const blob = new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement("a")
                    a.href = url
                    a.download = `trace_project_${projectId}.json`
                    a.click()
                    URL.revokeObjectURL(url)
                  }}
                >
                  <Download className="h-3 w-3 mr-1" /> Download
                </Button>
              </div>
            </>
          )}
        </CardContent>
      )}
    </Card>
  )
}

function CollapsibleSection({
  title,
  badge,
  open,
  onToggle,
  children,
}: {
  title: string
  badge?: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="flex items-center gap-2 text-sm font-medium w-full text-left py-1 hover:text-foreground text-muted-foreground transition-colors"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {title}
        {badge && <Badge variant="outline" className="text-[10px] ml-auto">{badge}</Badge>}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  )
}
