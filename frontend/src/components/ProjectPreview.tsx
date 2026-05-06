import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ExternalLink, RefreshCw, Loader2, Hammer } from "lucide-react"
import { projectsApi } from "@/api/client"
import { useToast } from "@/components/ui/toast"
import type { Project } from "@/types"

interface ProjectPreviewProps {
  project: Project
}

export function ProjectPreview({ project }: ProjectPreviewProps) {
  const { addToast } = useToast()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [fetchingUrl, setFetchingUrl] = useState(false)
  const [needsBuild, setNeedsBuild] = useState(false)
  const [building, setBuilding] = useState(false)

  // Reset all state when switching projects so old preview doesn't linger
  useEffect(() => {
    setPreviewUrl(null)
    setError(null)
    setLoading(true)
    setFetchingUrl(false)
    setNeedsBuild(false)
  }, [project.id])

  const fetchPreviewUrl = useCallback(async () => {
    if (!project.project_path || project.status !== "success") {
      setLoading(false)
      return
    }

    setFetchingUrl(true)
    setError(null)
    try {
      const response = await projectsApi.getPreviewUrl(project.id)
      if (response.preview_url) {
        // Preview URL is already a full URL (http://localhost:PORT) for dev servers
        // or a relative path for built projects
        if (response.preview_url.startsWith("http://")) {
          setPreviewUrl(response.preview_url)
        } else {
          setPreviewUrl(`http://localhost:8000${response.preview_url}`)
        }
        setNeedsBuild(false)
      } else {
        setNeedsBuild(response.needs_build || false)
        setError(response.message || "Preview not available. Project may need dependencies installed.")
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to get preview URL")
    } finally {
      setFetchingUrl(false)
      setLoading(false)
    }
  }, [project.id, project.project_path, project.status])

  useEffect(() => {
    fetchPreviewUrl()
  }, [fetchPreviewUrl])

  const handleBuild = async () => {
    setBuilding(true)
    try {
      await projectsApi.build(project.id)
      addToast({
        title: "Build started",
        description: "The project is being built in the background. This may take a few minutes.",
        variant: "success",
      })
      // Refresh preview URL after a delay
      setTimeout(() => {
        fetchPreviewUrl()
      }, 5000)
    } catch (err: any) {
      addToast({
        title: "Build failed",
        description: err.response?.data?.detail || "Failed to start build",
        variant: "destructive",
      })
    } finally {
      setBuilding(false)
    }
  }

  if (!project.project_path) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Project Preview</CardTitle>
          <CardDescription>Project is still being generated</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 bg-muted rounded-lg">
            <p className="text-muted-foreground">No preview available yet</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (project.status !== "success") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Project Preview</CardTitle>
          <CardDescription>Project must be completed to view preview</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 bg-muted rounded-lg">
            <p className="text-muted-foreground">Status: {project.status}</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const handleLoad = () => {
    setLoading(false)
    setError(null)
  }

  const handleError = () => {
    setLoading(false)
    setError("Failed to load project preview. The project may need to be built first.")
  }

  const openInNewTab = () => {
    if (previewUrl) {
      window.open(previewUrl, "_blank")
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Project Preview</CardTitle>
            <CardDescription>Live preview of the generated website</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={openInNewTab}>
              <ExternalLink className="h-4 w-4 mr-2" />
              Open in New Tab
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative border rounded-lg overflow-hidden bg-muted">
          {(loading || fetchingUrl) && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {fetchingUrl ? "Getting preview URL..." : "Loading preview..."}
                </p>
              </div>
            </div>
          )}
          {error && !loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
              <div className="text-center p-4">
                <p className="text-sm text-destructive mb-2">{error}</p>
                <div className="flex gap-2 justify-center">
                  {needsBuild && (
                    <Button 
                      variant="default" 
                      size="sm" 
                      onClick={handleBuild}
                      disabled={building}
                    >
                      {building ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Building...
                        </>
                      ) : (
                        <>
                          <Hammer className="h-4 w-4 mr-2" />
                          Build Project
                        </>
                      )}
                    </Button>
                  )}
                  {previewUrl && (
                    <Button variant="outline" size="sm" onClick={openInNewTab}>
                      Open in New Tab
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}
          {previewUrl && !error ? (
            <iframe
              key={`${project.id}-${previewUrl}`}
              src={previewUrl}
              className="w-full h-[600px] border-0"
              onLoad={handleLoad}
              onError={handleError}
              title={`Preview of ${project.name}`}
            />
          ) : !loading && !fetchingUrl ? (
            <div className="flex items-center justify-center h-[600px] bg-muted">
              <div className="text-center p-4">
                <p className="text-muted-foreground mb-2">
                  {error || "Preview URL not available"}
                </p>
                <p className="text-xs text-muted-foreground">
                  The project may need to be built. Check the project directory.
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
