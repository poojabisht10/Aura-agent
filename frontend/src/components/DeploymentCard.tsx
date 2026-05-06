import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Github,
  Upload,
  Rocket,
  ExternalLink,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw
} from "lucide-react"
import { projectsApi } from "@/api/client"
import { useToast } from "@/components/ui/toast"
import type { Project, DeploymentStatus } from "@/types"

interface DeploymentCardProps {
  project: Project
  onStatusChange?: () => void
}

export function DeploymentCard({ project, onStatusChange }: DeploymentCardProps) {
  const { addToast } = useToast()
  const [deploymentStatus, setDeploymentStatus] = useState<DeploymentStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [pushingToGitHub, setPushingToGitHub] = useState(false)
  const [deployingToVercel, setDeployingToVercel] = useState(false)

  const fetchDeploymentStatus = useCallback(async () => {
    try {
      const status = await projectsApi.getDeploymentStatus(project.id)
      setDeploymentStatus(status)
    } catch (err) {
      console.error("Failed to fetch deployment status:", err)
    } finally {
      setLoading(false)
    }
  }, [project.id])

  useEffect(() => {
    fetchDeploymentStatus()
  }, [fetchDeploymentStatus])

  // Poll for status updates when deploying
  useEffect(() => {
    if (deploymentStatus?.deployment_status === "deploying") {
      const interval = setInterval(fetchDeploymentStatus, 3000)
      return () => clearInterval(interval)
    }
  }, [deploymentStatus?.deployment_status, fetchDeploymentStatus])

  const handlePushToGitHub = async () => {
    setPushingToGitHub(true)
    try {
      await projectsApi.pushToGitHub(project.id)
      addToast({
        title: "GitHub Push Started",
        description: "Your code is being pushed to GitHub. This may take a moment.",
        variant: "success",
      })
      // Refresh status after a delay
      setTimeout(fetchDeploymentStatus, 3000)
    } catch (err: any) {
      addToast({
        title: "GitHub Push Failed",
        description: err.response?.data?.detail || "Failed to push to GitHub",
        variant: "destructive",
      })
    } finally {
      setPushingToGitHub(false)
      onStatusChange?.()
    }
  }

  const handleDeployToVercel = async () => {
    setDeployingToVercel(true)
    try {
      await projectsApi.deployToVercel(project.id)
      addToast({
        title: "Deployment Started",
        description: "Your project is being deployed to Vercel. This may take a few minutes.",
        variant: "success",
      })
      // Start polling for status
      setTimeout(fetchDeploymentStatus, 3000)
    } catch (err: any) {
      addToast({
        title: "Deployment Failed",
        description: err.response?.data?.detail || "Failed to deploy to Vercel",
        variant: "destructive",
      })
    } finally {
      setDeployingToVercel(false)
      onStatusChange?.()
    }
  }

  const getDeploymentStatusBadge = () => {
    if (!deploymentStatus) return null

    switch (deploymentStatus.deployment_status) {
      case "deployed":
        return (
          <Badge variant="default" className="bg-green-500">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            Deployed
          </Badge>
        )
      case "deploying":
        return (
          <Badge variant="secondary">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Deploying
          </Badge>
        )
      case "failed":
        return (
          <Badge variant="destructive">
            <XCircle className="h-3 w-3 mr-1" />
            Failed
          </Badge>
        )
      default:
        return (
          <Badge variant="outline">
            <Clock className="h-3 w-3 mr-1" />
            Not Deployed
          </Badge>
        )
    }
  }

  const getGitHubStatusBadge = () => {
    if (!deploymentStatus) return null

    if (deploymentStatus.github_pushed) {
      return (
        <Badge variant="default" className="bg-green-500">
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Pushed
        </Badge>
      )
    }
    return (
      <Badge variant="outline">
        <Clock className="h-3 w-3 mr-1" />
        Not Pushed
      </Badge>
    )
  }

  if (project.status !== "success") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Deployment
          </CardTitle>
          <CardDescription>
            Project must be successfully generated before deployment
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-32 bg-muted rounded-lg">
            <p className="text-muted-foreground">Complete project generation first</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Deployment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Deployment
            </CardTitle>
            <CardDescription>
              Push to GitHub and deploy to Vercel
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchDeploymentStatus}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* GitHub Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Github className="h-5 w-5" />
              <span className="font-medium">GitHub</span>
              {getGitHubStatusBadge()}
            </div>
          </div>

          {deploymentStatus?.github_repo_url ? (
            <div className="pl-7 space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Repository:</span>
                <a
                  href={deploymentStatus.github_repo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline flex items-center gap-1"
                >
                  {deploymentStatus.github_repo_url.replace("https://github.com/", "")}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              {deploymentStatus.github_branch && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Branch:</span>
                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                    {deploymentStatus.github_branch}
                  </code>
                </div>
              )}
              {deploymentStatus.github_pr_url && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">PR:</span>
                  <a
                    href={deploymentStatus.github_pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline flex items-center gap-1"
                  >
                    View Pull Request
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="pl-7">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePushToGitHub}
                disabled={pushingToGitHub}
              >
                {pushingToGitHub ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Pushing...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Push to GitHub
                  </>
                )}
              </Button>
            </div>
          )}
        </div>

        <hr className="border-border" />

        {/* Vercel Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="h-5 w-5" viewBox="0 0 76 65" fill="currentColor">
                <path d="M37.5274 0L75.0548 65H0L37.5274 0Z" />
              </svg>
              <span className="font-medium">Vercel</span>
              {getDeploymentStatusBadge()}
            </div>
          </div>

          {deploymentStatus?.deployment_url ? (
            <div className="pl-7 space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">URL:</span>
                <a
                  href={deploymentStatus.deployment_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline flex items-center gap-1"
                >
                  {deploymentStatus.deployment_url.replace("https://", "")}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              {deploymentStatus.last_deployed_at && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Deployed:</span>
                  <span>{new Date(deploymentStatus.last_deployed_at).toLocaleString()}</span>
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleDeployToVercel}
                disabled={deployingToVercel || deploymentStatus.deployment_status === "deploying"}
              >
                {deployingToVercel || deploymentStatus.deployment_status === "deploying" ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Deploying...
                  </>
                ) : (
                  <>
                    <Rocket className="h-4 w-4 mr-2" />
                    Redeploy
                  </>
                )}
              </Button>
            </div>
          ) : (
            <div className="pl-7 space-y-2">
              {deploymentStatus?.deployment_error && (
                <p className="text-sm text-destructive">{deploymentStatus.deployment_error}</p>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleDeployToVercel}
                disabled={deployingToVercel || deploymentStatus?.deployment_status === "deploying"}
              >
                {deployingToVercel || deploymentStatus?.deployment_status === "deploying" ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Deploying...
                  </>
                ) : (
                  <>
                    <Rocket className="h-4 w-4 mr-2" />
                    Deploy to Vercel
                  </>
                )}
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
