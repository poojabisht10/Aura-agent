import { useState, useEffect } from "react"
import { X, Plus } from "lucide-react"
import { useProjects } from "@/hooks/useProjects"
import type { ProjectCreateRequest } from "@/types"
import '../styles/papercut.css'

interface ProjectFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: ProjectCreateRequest, isNewProject: boolean) => Promise<void>
  isNewProject?: boolean
}

export function ProjectForm({ open, onOpenChange, onSubmit, isNewProject = true }: ProjectFormProps) {
  const { data: projectsData } = useProjects()
  const [formData, setFormData] = useState<ProjectCreateRequest>({
    figma_url: "",
    project_name: "",
    ui_library: "tailwind",
    add_as: isNewProject ? "new_project" : "new_page",
    parent_project_id: null,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setFormData({
        figma_url: "",
        project_name: "",
        ui_library: "tailwind",
        add_as: isNewProject ? "new_project" : "new_page",
        parent_project_id: null,
      })
      setError(null)
    }
  }, [open, isNewProject])

  const availableParents = projectsData?.projects.filter(
    (p) => p.status === "success" && !p.is_page
  ) || []

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (!formData.figma_url.trim()) { setError("Figma URL is required"); setLoading(false); return }
      if (!formData.project_name.trim()) { setError("Project name is required"); setLoading(false); return }
      if (!formData.figma_url.includes("figma.com")) { setError("Please enter a valid Figma URL"); setLoading(false); return }
      if (formData.add_as === "new_page" && !formData.parent_project_id) {
        setError("Please select a parent project when adding as a new page"); setLoading(false); return
      }
      await onSubmit(formData, isNewProject)
      setFormData({ figma_url: "", project_name: "", ui_library: "tailwind", add_as: isNewProject ? "new_project" : "new_page", parent_project_id: null })
      onOpenChange(false)
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create project")
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  const inputStyle: React.CSSProperties = {
    width: '100%',
    border: '2.5px solid var(--ink)',
    borderRadius: 3,
    padding: '10px 12px',
    fontSize: 13,
    fontFamily: 'Space Grotesk, system-ui, sans-serif',
    background: '#fff',
    color: 'var(--ink)',
    outline: 'none',
    boxShadow: '3px 3px 0 var(--cream-3)',
    transition: 'box-shadow 0.1s',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
    fontFamily: 'JetBrains Mono, monospace',
    marginBottom: 6,
    color: 'var(--ink)',
    opacity: 0.6,
  }

  return (
    <div className="pc-modal-overlay" onClick={() => onOpenChange(false)}>
      <div className="pc-modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        {/* Title row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', paddingBottom: '1rem', borderBottom: '2.5px solid var(--ink)' }}>
          <div>
            <div className="pc-section-title" style={{ fontSize: 11 }}>
              {isNewProject ? 'New Project' : 'Add Page to Project'}
            </div>
            <div style={{ fontSize: 11, opacity: 0.5, marginTop: 3, fontFamily: 'JetBrains Mono' }}>
              {isNewProject ? 'Convert Figma → React' : 'Add to workspace'}
            </div>
          </div>
          <button onClick={() => onOpenChange(false)}
            style={{ border: '2.5px solid var(--ink)', borderRadius: 3, background: 'var(--rose-fill)', width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '2px 2px 0 var(--rose-accent)' }}>
            <X size={13} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Figma URL */}
            <div>
              <label style={labelStyle}>Figma URL</label>
              <input
                style={inputStyle}
                placeholder="https://www.figma.com/design/..."
                value={formData.figma_url}
                onChange={e => setFormData({ ...formData, figma_url: e.target.value })}
                required
              />
            </div>

            {/* Project Name */}
            <div>
              <label style={labelStyle}>Project Name</label>
              <input
                style={inputStyle}
                placeholder="my-awesome-website"
                value={formData.project_name}
                onChange={e => setFormData({ ...formData, project_name: e.target.value })}
                required
                pattern="[a-zA-Z0-9-_]+"
                title="Only alphanumeric characters, hyphens, and underscores"
              />
            </div>

            {/* Parent Project (always shown for Add Page flow) */}
            {!isNewProject && (
              <div>
                <label style={labelStyle}>Parent Project</label>
                <select
                  style={{ ...inputStyle }}
                  value={formData.parent_project_id || ""}
                  onChange={e => setFormData({ ...formData, parent_project_id: e.target.value ? parseInt(e.target.value) : null })}
                  required
                >
                  <option value="">Select a parent project...</option>
                  {availableParents.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', opacity: 0.4, marginTop: 4, letterSpacing: 0.5 }}>
                  Only completed projects are available as parents
                </div>
              </div>
            )}

            {/* UI Library */}
            <div>
              <label style={labelStyle}>UI Library</label>
              <select
                style={{ ...inputStyle }}
                value={formData.ui_library}
                onChange={e => setFormData({ ...formData, ui_library: e.target.value as any })}
              >
                <option value="tailwind">Tailwind CSS</option>
                <option value="mui">Material-UI</option>
                <option value="chakra">Chakra UI</option>
                <option value="css-modules">CSS Modules</option>
              </select>
            </div>

            {/* Error */}
            {error && (
              <div style={{
                border: '2.5px solid var(--rose-accent)', borderRadius: 3,
                background: 'var(--rose-fill)', padding: '10px 12px',
                fontSize: 12, color: 'var(--rose-text)', fontWeight: 600,
                boxShadow: '3px 3px 0 var(--rose-accent)',
              }}>
                {error}
              </div>
            )}
          </div>

          {/* Footer */}
          <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '2.5px solid var(--ink)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button type="button" className="pc-btn pc-btn-secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </button>
            <button type="submit" className="pc-btn pc-btn-primary" disabled={loading}>
              <Plus size={13} />
              {loading
                ? 'Creating...'
                : isNewProject
                  ? "Create Project"
                  : "Add Page"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
