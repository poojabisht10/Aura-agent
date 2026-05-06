import { useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { projectsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  Loader2,
  Copy,
  Download,
  ChevronDown,
  ChevronRight,
  FileJson,
  Check,
} from "lucide-react"

interface FigmaJsonViewerProps {
  projectId: number
}

function StatsBadges({ stats }: { stats: Record<string, any> | null }) {
  if (!stats) return null

  const entries = [
    { label: "Pages", value: stats.page_count ?? stats.pageCount },
    { label: "Frames", value: stats.frame_count ?? stats.frameCount },
    { label: "Colors", value: stats.color_count ?? stats.colorCount },
    { label: "Fonts", value: stats.font_count ?? stats.fontCount },
    { label: "Images", value: stats.image_count ?? stats.imageCount },
  ].filter((e) => e.value != null)

  if (entries.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map((entry) => (
        <Badge key={entry.label} variant="secondary" className="text-xs">
          {entry.label}: {entry.value}
        </Badge>
      ))}
    </div>
  )
}

function JsonSection({
  label,
  data,
  defaultOpen = false,
}: {
  label: string
  data: any
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  if (data == null) return null

  const jsonString = JSON.stringify(data, null, 2)
  const lineCount = jsonString.split("\n").length

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium bg-muted/50 hover:bg-muted transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" />
        )}
        {label}
        <span className="text-muted-foreground ml-auto text-xs">
          {lineCount} lines
        </span>
      </button>
      {open && (
        <pre className="p-3 text-xs leading-relaxed overflow-auto max-h-96 bg-zinc-950 text-zinc-300 font-mono">
          {jsonString}
        </pre>
      )}
    </div>
  )
}

function JsonPanel({
  projectId,
  fetchFn,
  queryKey,
}: {
  projectId: number
  fetchFn: (id: number) => Promise<any>
  queryKey: string
}) {
  const [enabled, setEnabled] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: [queryKey, projectId],
    queryFn: () => fetchFn(projectId),
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  const handleCopy = useCallback(() => {
    if (!data) return
    navigator.clipboard.writeText(JSON.stringify(data, null, 2)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [data])

  const handleDownload = useCallback(() => {
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${queryKey}-${projectId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [data, queryKey, projectId])

  if (!enabled) {
    return (
      <div className="flex items-center justify-center py-8">
        <Button variant="outline" onClick={() => setEnabled(true)}>
          <FileJson className="h-4 w-4 mr-2" />
          Load JSON Data
        </Button>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          Loading JSON...
        </span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-6 text-center">
        <p className="text-sm text-destructive">
          Failed to load JSON data. The file may not exist for this project.
        </p>
      </div>
    )
  }

  if (!data) return null

  const stats = data.stats ?? null
  const hasStructuredSections =
    data.pages || data.colors || data.fonts || data.images

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <StatsBadges stats={stats} />
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? (
              <Check className="h-3.5 w-3.5 mr-1.5" />
            ) : (
              <Copy className="h-3.5 w-3.5 mr-1.5" />
            )}
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="h-3.5 w-3.5 mr-1.5" />
            Download
          </Button>
        </div>
      </div>

      {hasStructuredSections && (
        <div className="space-y-2">
          {data.pages && <JsonSection label="Pages" data={data.pages} />}
          {data.colors && <JsonSection label="Colors" data={data.colors} />}
          {data.fonts && <JsonSection label="Fonts" data={data.fonts} />}
          {data.images && <JsonSection label="Images" data={data.images} />}
          {data.stats && <JsonSection label="Stats" data={data.stats} />}
        </div>
      )}

      <div className="border border-border rounded-md overflow-hidden">
        <button
          className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium bg-muted/50 hover:bg-muted transition-colors text-left"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0" />
          )}
          Full JSON
          <span className="text-muted-foreground ml-auto text-xs">
            {JSON.stringify(data, null, 2).split("\n").length} lines
          </span>
        </button>
        {expanded && (
          <pre className="p-3 text-xs leading-relaxed overflow-auto max-h-[600px] bg-zinc-950 text-zinc-300 font-mono">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

export function FigmaJsonViewer({ projectId }: FigmaJsonViewerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <FileJson className="h-5 w-5" />
          Figma JSON Data
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="design">
          <TabsList>
            <TabsTrigger value="design">Design Data</TabsTrigger>
            <TabsTrigger value="raw">Raw Figma Response</TabsTrigger>
          </TabsList>
          <TabsContent value="design">
            <JsonPanel
              projectId={projectId}
              fetchFn={projectsApi.getFigmaJson}
              queryKey="figma-json"
            />
          </TabsContent>
          <TabsContent value="raw">
            <JsonPanel
              projectId={projectId}
              fetchFn={projectsApi.getFigmaJsonRaw}
              queryKey="figma-json-raw"
            />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
