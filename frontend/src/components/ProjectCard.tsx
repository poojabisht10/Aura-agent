import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "./StatusBadge"
import { Eye, Trash2, FileText, Github, Rocket, CheckCircle2, XCircle, Clock, Code2, Repeat, ExternalLink } from "lucide-react"
import type { ProjectListItem } from "@/types"
import { formatDistanceToNow } from "date-fns"

interface ProjectCardProps {
  project: ProjectListItem
  onView: (id: number) => void
  onDelete: (id: number) => void
}

export function ProjectCard({ project, onView, onDelete }: ProjectCardProps) {
  const timeAgo = formatDistanceToNow(new Date(project.created_at), { addSuffix: true })
  const isSuccess = project.status === "success"
  const isProcessing = project.status === "processing"

  return (
    <Card className="group relative overflow-hidden border-border/50 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300">
      {/* Status indicator line */}
      <div className={`absolute top-0 left-0 right-0 h-1 ${
        isSuccess ? "bg-gradient-to-r from-green-500 to-emerald-500" :
        isProcessing ? "bg-gradient-to-r from-blue-500 to-cyan-500 animate-pulse" :
        project.status === "failed" ? "bg-gradient-to-r from-red-500 to-rose-500" :
        "bg-gradient-to-r from-gray-400 to-gray-500"
      }`} />

      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-lg truncate group-hover:text-primary transition-colors">
                {project.name}
              </CardTitle>
              {project.is_page && (
                <Badge variant="secondary" className="text-xs bg-purple-500/10 text-purple-600 border-purple-500/20">
                  <FileText className="h-3 w-3 mr-1" />
                  Page
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{timeAgo}</p>
            {project.route_path && (
              <code className="text-xs px-2 py-0.5 rounded bg-muted font-mono">
                {project.route_path}
              </code>
            )}
          </div>
          <StatusBadge status={project.status as any} />
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pb-4">
        {/* Component Stats */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-violet-500/10 text-violet-600">
            <Code2 className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">{project.components_generated} generated</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-orange-500/10 text-orange-600">
            <Repeat className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">{project.components_reused} reused</span>
          </div>
        </div>

        {/* Deployment Status Row */}
        {isSuccess && (
          <div className="flex items-center gap-4 pt-2 border-t border-border/50">
            {/* GitHub Status */}
            <div className="flex items-center gap-1.5">
              <Github className="h-4 w-4 text-muted-foreground" />
              {project.github_pushed ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              )}
            </div>

            {/* Vercel Status */}
            <div className="flex items-center gap-1.5">
              <Rocket className="h-4 w-4 text-muted-foreground" />
              {project.deployment_status === "deployed" ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
              ) : project.deployment_status === "failed" ? (
                <XCircle className="h-3.5 w-3.5 text-destructive" />
              ) : (
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              )}
            </div>

            {/* Deployment URL */}
            {project.deployment_url && (
              <a
                href={project.deployment_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3 w-3" />
                Live
              </a>
            )}
          </div>
        )}
      </CardContent>

      <CardFooter className="flex gap-2 pt-0">
        <Button
          variant="default"
          size="sm"
          onClick={() => onView(project.id)}
          className="flex-1 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white"
        >
          <Eye className="h-4 w-4 mr-2" />
          View Details
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDelete(project.id)}
          className="text-muted-foreground hover:text-destructive hover:border-destructive/50 transition-colors"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  )
}
