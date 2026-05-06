import { useParams, useNavigate } from "react-router-dom"
import { useProjectStatus } from "@/hooks/useProjectStatus"
import { useDeleteProject, useProjects } from "@/hooks/useProjects"
import { ProjectPreview } from "@/components/ProjectPreview"
import { DeploymentCard } from "@/components/DeploymentCard"
import { StatusBadge } from "@/components/StatusBadge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { FigmaJsonViewer } from "@/components/FigmaJsonViewer"
import { ConversionTraceViewer } from "@/components/ConversionTraceViewer"
import { ArrowLeft, Trash2, ExternalLink, Loader2, FileText, Folder, ArrowUp } from "lucide-react"
import { formatDistanceToNow } from "date-fns"

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectId = id ? parseInt(id, 10) : null

  const { data: project, isLoading } = useProjectStatus(projectId, !!projectId)
  const { data: projectsData } = useProjects()
  const deleteProject = useDeleteProject()

  // Find parent project if this is a page
  const parentProject = project?.parent_project_id
    ? projectsData?.projects.find((p) => p.id === project.parent_project_id)
    : null

  // Find child pages if this is a parent project
  const childPages = projectsData?.projects.filter(
    (p) => p.parent_project_id === project?.id
  ) || []

  const handleDelete = async () => {
    if (!projectId) return
    if (window.confirm("Are you sure you want to delete this project?")) {
      await deleteProject.mutateAsync(projectId)
      navigate("/")
    }
  }

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground mb-4">Project not found</p>
            <Button onClick={() => navigate("/")} variant="outline">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const isGenerating = project.status === "pending" || project.status === "generating"
  const progress = isGenerating ? 50 : project.status === "success" ? 100 : 0

  return (
    <div className="container mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">{project.name}</h1>
              {project.is_page && (
                <Badge variant="secondary">
                  <FileText className="h-3 w-3 mr-1" />
                  Page
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground mt-1">
              {project.created_at
                ? `Created ${formatDistanceToNow(new Date(project.created_at), { addSuffix: true })}`
                : "Created recently"}
            </p>
            {project.route_path && (
              <p className="text-sm text-muted-foreground">
                Route: <code className="bg-muted px-1 rounded">{project.route_path}</code>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={project.status} />
          <Button variant="outline" size="sm" onClick={handleDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {parentProject && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <ArrowUp className="h-4 w-4" />
              Parent Project
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{parentProject.name}</p>
                <p className="text-sm text-muted-foreground">This page belongs to this project</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/projects/${parentProject.id}`)}
              >
                View Parent
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {childPages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Folder className="h-4 w-4" />
              Pages in this Project ({childPages.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {childPages.map((page) => (
                <div
                  key={page.id}
                  className="flex items-center justify-between p-2 border rounded hover:bg-muted/50 cursor-pointer"
                  onClick={() => navigate(`/projects/${page.id}`)}
                >
                  <div>
                    <p className="font-medium">{page.name}</p>
                    {page.route_path && (
                      <p className="text-xs text-muted-foreground">
                        Route: <code>{page.route_path}</code>
                      </p>
                    )}
                  </div>
                  <StatusBadge status={page.status as any} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {isGenerating && (
        <Card>
          <CardHeader>
            <CardTitle>Conversion in Progress</CardTitle>
            <CardDescription>
              Your project is being converted from Figma to React. This may take a few minutes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Progress value={progress} className="mb-2" />
            <p className="text-sm text-muted-foreground">
              Status: {project.status === "pending" ? "Queued" : "Generating components..."}
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Project Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Figma URL</p>
              <a
                href={project.figma_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                {project.figma_url}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Components Generated</p>
              <p className="text-2xl font-bold">{project.components_generated}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Components Reused</p>
              <p className="text-2xl font-bold">{project.components_reused}</p>
            </div>
            {project.conversion_time_seconds && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Conversion Time</p>
                <p className="text-lg">{Math.round(project.conversion_time_seconds)}s</p>
              </div>
            )}
            {project.error_message && (
              <div>
                <p className="text-sm font-medium text-destructive">Error</p>
                <p className="text-sm text-destructive">{project.error_message}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {project.project_path && (
          <Card>
            <CardHeader>
              <CardTitle>Project Path</CardTitle>
            </CardHeader>
            <CardContent>
              <code className="text-sm bg-muted p-2 rounded block">{project.project_path}</code>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Figma JSON Viewer */}
      {project.status === "success" && (
        <FigmaJsonViewer projectId={project.id} />
      )}

      {/* Conversion Trace */}
      {project.status === "success" && (
        <ConversionTraceViewer projectId={project.id} />
      )}

      {/* Deployment Section */}
      <DeploymentCard project={project} />

      {project.status === "success" && project.project_path && (
        <ProjectPreview key={project.id} project={project} />
      )}
    </div>
  )
}
