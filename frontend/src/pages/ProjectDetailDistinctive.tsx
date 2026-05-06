import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useProjectStatus } from "@/hooks/useProjectStatus";
import { useDeleteProject, useProjects } from "@/hooks/useProjects";
import {
  ArrowLeft, Trash2, ExternalLink, Box, Globe, Github,
  Code2, Layers, Clock, Maximize2, Eye, Play, RefreshCw, FileJson, Activity
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useState, useCallback } from "react";
import { projectsApi } from "@/api/client";
import { ConversionProgress } from '@/components/papercut/ConversionProgress';
import { FigmaJsonViewer } from '@/components/FigmaJsonViewer';
import { ConversionTraceViewer } from '@/components/ConversionTraceViewer';
import { VerificationDashboard } from '@/components/VerificationDashboard';
import '../styles/papercut.css';

const API_BASE = "http://localhost:8000";

/* ---- tiny shared pieces ---- */
function PcInfoCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div
      className="pc-stat-card"
      style={{
        background: color ? `var(--${color}-fill)` : '#fff',
        boxShadow: `4px 4px 0 var(--${color ?? 'violet'}-accent)`,
      }}
    >
      <div className="pc-stat-num" style={{ fontSize: '1.6rem' }}>{value}</div>
      <div className="pc-stat-label">{label}</div>
      {sub && <div className="pc-stat-change">{sub}</div>}
    </div>
  );
}

function PcSection({ title, icon: Icon, children, delay = 0 }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      style={{ marginBottom: '2rem' }}
    >
      <div className="pc-section-header">
        <Icon size={15} />
        <span className="pc-section-title">{title}</span>
      </div>
      {children}
    </motion.div>
  );
}

export function ProjectDetailDistinctive() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = id ? parseInt(id, 10) : null;

  const { data: project, isLoading } = useProjectStatus(projectId, !!projectId);
  const { data: projectsData } = useProjects();
  const deleteProject = useDeleteProject();

  const [previewMode, setPreviewMode] = useState<'live' | 'deployment' | 'figma'>('live');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string | null>(null);

  // Deployment state
  const [pushingGitHub, setPushingGitHub] = useState(false);
  const [deployingVercel, setDeployingVercel] = useState(false);
  const [deployMsg, setDeployMsg] = useState<string | null>(null);

  const startPreview = useCallback(async () => {
    if (!projectId) return;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewUrl(null);
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/preview-url`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      if (data.preview_url && data.type !== 'not_available') {
        setPreviewUrl(data.preview_url);
        setPreviewType(data.type);
      } else {
        setPreviewError('Preview not available. Try building it first.');
      }
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : 'Failed to start preview');
    } finally {
      setPreviewLoading(false);
    }
  }, [projectId]);

  const handlePushToGitHub = useCallback(async () => {
    if (!projectId) return;
    setPushingGitHub(true);
    setDeployMsg(null);
    try {
      const res = await projectsApi.pushToGitHub(projectId);
      setDeployMsg(res.message || 'Pushed to GitHub');
    } catch (e: any) {
      setDeployMsg(e?.response?.data?.detail || e.message || 'Push failed');
    } finally {
      setPushingGitHub(false);
    }
  }, [projectId]);

  const handleDeployToVercel = useCallback(async () => {
    if (!projectId) return;
    setDeployingVercel(true);
    setDeployMsg(null);
    try {
      const res = await projectsApi.deployToVercel(projectId);
      setDeployMsg(res.message || 'Deploying to Vercel…');
    } catch (e: any) {
      setDeployMsg(e?.response?.data?.detail || e.message || 'Deploy failed');
    } finally {
      setDeployingVercel(false);
    }
  }, [projectId]);

  const fullProject = projectsData?.projects.find((p) => p.id === projectId);
  const projectData = { ...project, ...fullProject };
  const parentProject = projectData?.parent_project_id
    ? projectsData?.projects.find((p) => p.id === projectData.parent_project_id)
    : null;
  const childPages = projectsData?.projects.filter(
    (p) => p.parent_project_id === projectData?.id
  ) || [];

  const handleDelete = async () => {
    if (!projectId) return;
    if (window.confirm('Delete this project?')) {
      await deleteProject.mutateAsync(projectId);
      navigate('/');
    }
  };

  const reusabilityPct = Math.round(
    ((projectData.components_reused || 0) /
      Math.max((projectData.components_generated || 0) + (projectData.components_reused || 0), 1)) * 100
  );

  const CARD_COLORS = ['rose', 'violet', 'sky', 'amber', 'emerald', 'pink', 'lime'] as const;

  if (isLoading || !projectData?.id) {
    return (
      <div className="pc-dashboard">
        <div className="pc-loading" style={{ minHeight: '100vh' }}>
          <div className="pc-loading-dots">
            <div className="pc-loading-dot" />
            <div className="pc-loading-dot" />
            <div className="pc-loading-dot" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="pc-dashboard">
      {/* Header */}
      <header className="pc-header">
        <div className="pc-header-inner">
          <div className="pc-brand">
            <div className="pc-brand-dots">
              <div className="pc-brand-dot" style={{ background: '#f43f5e' }} />
              <div className="pc-brand-dot" style={{ background: '#f59e0b' }} />
              <div className="pc-brand-dot" style={{ background: '#10b981' }} />
            </div>
            <div>
              <div className="pc-brand-name">Aura Agent</div>
              <div className="pc-brand-tag">Project Detail</div>
            </div>
          </div>
          <div className="pc-header-actions">
            <button className="pc-btn pc-btn-secondary" onClick={() => navigate('/')}>
              <ArrowLeft size={14} /> Back
            </button>
            <button className="pc-btn" onClick={handleDelete}
              style={{ background: 'var(--rose-fill)', color: 'var(--rose-text)', border: '2.5px solid var(--ink)', boxShadow: '3px 3px 0 var(--rose-accent)' }}>
              <Trash2 size={14} /> Delete
            </button>
          </div>
        </div>
      </header>

      <main className="pc-main">
        {/* Project Title */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: '2rem' }}>
          <div style={{
            border: '2.5px solid var(--ink)',
            borderRadius: 4,
            background: 'var(--ink)',
            padding: '1.5rem 1.75rem',
            boxShadow: '6px 6px 0 var(--violet-accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}>
            <div>
              <h1 style={{ fontSize: '2rem', fontWeight: 900, color: '#fff', letterSpacing: '-1px', marginBottom: 4 }}>
                {projectData.name}
              </h1>
              {parentProject && (
                <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: 'var(--violet-accent)', letterSpacing: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Box size={11} />
                  Page of {parentProject.name}
                  {projectData.route_path && <span style={{ opacity: 0.5 }}>· {projectData.route_path}</span>}
                </div>
              )}
            </div>
            <span className={`pc-status pc-status-${
              projectData.status === 'completed' || projectData.status === 'success' ? 'completed' :
              projectData.status === 'completed_with_warnings' || projectData.status === 'completed_with_errors' ? 'warning' :
              projectData.status === 'processing' || projectData.status === 'in_progress' || projectData.status === 'generating' ? 'processing' :
              projectData.status === 'failed' || projectData.status === 'error' ? 'failed' : 'pending'
            }`} style={{ fontSize: 10, padding: '5px 12px' }}>
              <span className="pc-status-dot" />
              {projectData.status?.toUpperCase() || 'PENDING'}
            </span>
          </div>
        </motion.div>

        {/* Live progress (visible during generation) */}
        {(projectData.status === 'generating' || projectData.status === 'pending') && projectId && (
          <ConversionProgress projectId={projectId} />
        )}

        {/* Metrics */}
        <PcSection title="Metrics" icon={Layers} delay={0.05}>
          <div className="pc-stats-grid">
            <PcInfoCard label="Components Generated" value={String(projectData.components_generated || 0)} color="violet" />
            <PcInfoCard label="Reused" value={String(projectData.components_reused || 0)} color="emerald" />
            <PcInfoCard label="Pages" value={String(childPages.length)} color="sky" />
            <PcInfoCard label="Project ID" value={`#${projectData.id}`} sub={projectData.conversion_time_seconds ? `built in ${projectData.conversion_time_seconds.toFixed(1)}s` : undefined} color="amber" />
          </div>
        </PcSection>

        {/* Design Verification */}
        {(projectData.status === 'success' || projectData.status === 'completed_with_warnings') && projectId && (
          <PcSection title="Design Verification" icon={Eye} delay={0.07}>
            <VerificationDashboard projectId={projectId} />
          </PcSection>
        )}

        {/* Links */}
        {(projectData.github_repo_url || projectData.deployment_url) && (
          <PcSection title="Links" icon={ExternalLink} delay={0.1}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {projectData.github_repo_url && (
                <a href={projectData.github_repo_url} target="_blank" rel="noopener noreferrer"
                  className="pc-btn pc-btn-secondary" style={{ textDecoration: 'none' }}>
                  <Github size={14} /> GitHub Repository <ExternalLink size={11} />
                </a>
              )}
              {projectData.deployment_url && (
                <a href={projectData.deployment_url} target="_blank" rel="noopener noreferrer"
                  className="pc-btn pc-btn-secondary" style={{ textDecoration: 'none' }}>
                  <Globe size={14} /> Live Deployment <ExternalLink size={11} />
                </a>
              )}
            </div>
          </PcSection>
        )}

        {/* Deployment Actions */}
        {(projectData.status === 'success' || projectData.status === 'completed_with_warnings') && (
          <PcSection title="Deploy" icon={Globe} delay={0.12}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              {!projectData.github_pushed && (
                <button className="pc-btn pc-btn-secondary" onClick={handlePushToGitHub} disabled={pushingGitHub}>
                  <Github size={14} /> {pushingGitHub ? 'Pushing…' : 'Push to GitHub'}
                </button>
              )}
              {projectData.github_pushed && projectData.github_repo_url && (
                <a href={projectData.github_repo_url} target="_blank" rel="noopener noreferrer"
                  className="pc-btn pc-btn-secondary" style={{ textDecoration: 'none' }}>
                  <Github size={14} /> View on GitHub <ExternalLink size={11} />
                </a>
              )}
              {!projectData.deployment_url ? (
                <button className="pc-btn pc-btn-primary" onClick={handleDeployToVercel} disabled={deployingVercel}>
                  <Globe size={14} /> {deployingVercel ? 'Deploying…' : 'Deploy to Vercel'}
                </button>
              ) : (
                <>
                  <a href={projectData.deployment_url} target="_blank" rel="noopener noreferrer"
                    className="pc-btn pc-btn-primary" style={{ textDecoration: 'none' }}>
                    <Globe size={14} /> Live Site <ExternalLink size={11} />
                  </a>
                  <button className="pc-btn pc-btn-secondary" onClick={handleDeployToVercel} disabled={deployingVercel}>
                    <RefreshCw size={14} /> {deployingVercel ? 'Deploying…' : 'Redeploy'}
                  </button>
                </>
              )}
            </div>
            {deployMsg && (
              <div style={{ marginTop: 8, fontSize: 11, fontFamily: 'JetBrains Mono', opacity: 0.7 }}>
                {deployMsg}
              </div>
            )}
          </PcSection>
        )}

        {/* Child Pages */}
        {childPages.length > 0 && (
          <PcSection title={`Linked Pages (${childPages.length})`} icon={Box} delay={0.15}>
            <div className="pc-projects-grid">
              {childPages.map((page, i) => (
                <motion.div
                  key={page.id}
                  className={`pc-project-card pc-card-${CARD_COLORS[i % CARD_COLORS.length]}`}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 + i * 0.06 }}
                  onClick={() => navigate(`/projects/${page.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="pc-card-bar" />
                  <div className="pc-card-body">
                    <div className="pc-card-top">
                      <div>
                        <div className="pc-card-name">{page.name}</div>
                        <div className="pc-card-page-badge"><Box size={9} /> {page.route_path || '/'}</div>
                      </div>
                    </div>
                    <div className="pc-metrics">
                      <div className="pc-metric">
                        <div className="pc-metric-num">{page.components_generated || 0}</div>
                        <div className="pc-metric-label">Components</div>
                      </div>
                      <div className="pc-metric">
                        <div className="pc-metric-num">{page.components_reused || 0}</div>
                        <div className="pc-metric-label">Reused</div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </PcSection>
        )}

        {/* Preview */}
        <PcSection title="Preview" icon={Eye} delay={0.2}>
          {/* Mode tabs + controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
            <div className="pc-nav" style={{ background: 'transparent', border: '2.5px solid var(--ink)' }}>
              {(['live', ...(projectData.deployment_url ? ['deployment'] : []), ...(projectData.figma_url ? ['figma'] : [])] as const).map((mode) => (
                <button key={mode} className={`pc-nav-btn ${previewMode === mode ? 'active' : ''}`}
                  onClick={() => setPreviewMode(mode as any)} style={{ color: previewMode === mode ? undefined : 'var(--ink)' }}>
                  {mode === 'live' ? <><Play size={11} style={{ display: 'inline', marginRight: 4 }} />Local</> :
                   mode === 'deployment' ? <><Globe size={11} style={{ display: 'inline', marginRight: 4 }} />Deployed</> :
                   <><Eye size={11} style={{ display: 'inline', marginRight: 4 }} />Figma</>}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {previewUrl && (
                <a href={previewUrl} target="_blank" rel="noopener noreferrer"
                  className="pc-btn pc-btn-secondary" style={{ textDecoration: 'none' }}>
                  <ExternalLink size={12} /> Open
                </a>
              )}
              {previewUrl && (
                <button className="pc-btn pc-btn-secondary" onClick={() => setIsFullscreen(!isFullscreen)}>
                  <Maximize2 size={12} /> {isFullscreen ? 'Exit' : 'Full'}
                </button>
              )}
            </div>
          </div>

          {/* Browser window */}
          <AnimatePresence mode="wait">
            <motion.div
              key={previewMode}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              style={{
                border: '2.5px solid var(--ink)',
                borderRadius: 4,
                overflow: 'hidden',
                boxShadow: '5px 5px 0 var(--ink)',
                position: isFullscreen ? 'fixed' : 'relative',
                inset: isFullscreen ? '1rem' : undefined,
                zIndex: isFullscreen ? 200 : undefined,
              }}
            >
              {/* Browser chrome */}
              <div style={{
                background: 'var(--ink)', padding: '8px 14px',
                display: 'flex', alignItems: 'center', gap: 10,
                borderBottom: '2.5px solid var(--ink)',
              }}>
                <div style={{ display: 'flex', gap: 5 }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#f43f5e' }} />
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b' }} />
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#10b981' }} />
                </div>
                <div style={{
                  flex: 1, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 2, padding: '3px 10px', fontSize: 10,
                  fontFamily: 'JetBrains Mono', color: 'rgba(255,255,255,0.5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {previewUrl || (previewMode === 'deployment' && projectData.deployment_url) || 'about:blank'}
                </div>
                {previewMode === 'live' && (
                  <button onClick={startPreview} disabled={previewLoading}
                    className="pc-btn" style={{
                      background: previewUrl ? 'var(--emerald-fill)' : 'var(--violet-fill)',
                      color: previewUrl ? 'var(--emerald-text)' : 'var(--violet-text)',
                      border: '2px solid rgba(255,255,255,0.2)',
                      boxShadow: 'none', padding: '4px 10px', fontSize: 8,
                    }}>
                    {previewLoading ? 'Loading...' : <><RefreshCw size={10} /> {previewUrl ? 'Reload' : 'Start'}</>}
                  </button>
                )}
                {previewType && previewUrl && (
                  <span style={{ fontSize: 8, fontFamily: 'JetBrains Mono', color: 'var(--emerald-accent)', letterSpacing: 1 }}>
                    {previewType === 'dev_server' ? '⚡ DEV' : '📦 BUILT'}
                  </span>
                )}
              </div>

              {/* Content area */}
              <div style={{ height: isFullscreen ? 'calc(100vh - 8rem)' : 580, background: '#fff', position: 'relative' }}>
                {previewMode === 'live' && (
                  <>
                    {previewLoading && (
                      <div style={{ position: 'absolute', inset: 0, background: 'var(--cream)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
                        <div className="pc-loading-dots">
                          <div className="pc-loading-dot" /><div className="pc-loading-dot" /><div className="pc-loading-dot" />
                        </div>
                        <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, letterSpacing: 2, textTransform: 'uppercase', opacity: 0.5 }}>
                          Starting dev server…
                        </div>
                      </div>
                    )}
                    {previewError && !previewLoading && (
                      <div style={{ position: 'absolute', inset: 0, background: 'var(--rose-fill)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 }}>
                        <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, letterSpacing: 1, color: 'var(--rose-text)', textAlign: 'center' }}>{previewError}</div>
                        <button className="pc-btn pc-btn-secondary" onClick={startPreview}>Try Again</button>
                      </div>
                    )}
                    {!previewUrl && !previewLoading && !previewError && (
                      <div style={{ position: 'absolute', inset: 0, background: 'var(--cream)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontWeight: 800, fontSize: 15, letterSpacing: 2, textTransform: 'uppercase', fontFamily: 'JetBrains Mono', marginBottom: 6 }}>Preview Project</div>
                          <div style={{ fontSize: 12, opacity: 0.5 }}>Starts a local Vite dev server</div>
                        </div>
                        <button className="pc-btn pc-btn-primary" onClick={startPreview}>
                          <Play size={14} /> Launch Preview
                        </button>
                        {projectData.project_path && (
                          <code style={{ fontSize: 9, fontFamily: 'JetBrains Mono', opacity: 0.3 }}>{projectData.project_path}</code>
                        )}
                      </div>
                    )}
                    {previewUrl && !previewLoading && (
                      <iframe src={previewUrl} style={{ width: '100%', height: '100%', border: 'none' }} title="Local Preview" allow="cross-origin-isolated" />
                    )}
                  </>
                )}
                {previewMode === 'deployment' && (
                  projectData.deployment_url
                    ? <iframe src={projectData.deployment_url} style={{ width: '100%', height: '100%', border: 'none' }} title="Deployed Preview" sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
                    : <div style={{ position: 'absolute', inset: 0, background: 'var(--cream)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'JetBrains Mono', fontSize: 11, opacity: 0.4, letterSpacing: 1 }}>No deployment URL available</div>
                )}
                {previewMode === 'figma' && (
                  <div style={{ position: 'absolute', inset: 0, background: 'var(--violet-fill)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
                    <Eye size={40} style={{ color: 'var(--violet-accent)', opacity: 0.4 }} />
                    <div style={{ fontWeight: 800, letterSpacing: 2, textTransform: 'uppercase', fontFamily: 'JetBrains Mono', fontSize: 12 }}>Figma Design</div>
                    {projectData.figma_url
                      ? <a href={projectData.figma_url} target="_blank" rel="noopener noreferrer" className="pc-btn pc-btn-secondary" style={{ textDecoration: 'none' }}>Open in Figma <ExternalLink size={12} /></a>
                      : <div style={{ fontSize: 11, opacity: 0.4, fontFamily: 'JetBrains Mono' }}>No Figma URL available</div>
                    }
                  </div>
                )}
              </div>
            </motion.div>
          </AnimatePresence>
        </PcSection>

        {/* Component Architecture */}
        {(projectData.components_generated || 0) > 0 && (
          <PcSection title="Component Architecture" icon={Code2} delay={0.3}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ border: '2.5px solid var(--ink)', borderRadius: 4, padding: '14px 16px', background: 'var(--sky-fill)', boxShadow: '4px 4px 0 var(--sky-accent)' }}>
                  <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--sky-text)', marginBottom: 6 }}>Generated Components</div>
                  <div style={{ fontSize: '2rem', fontWeight: 900, letterSpacing: -2 }}>{projectData.components_generated}</div>
                </div>
                <div style={{ border: '2.5px solid var(--ink)', borderRadius: 4, padding: '14px 16px', background: 'var(--emerald-fill)', boxShadow: '4px 4px 0 var(--emerald-accent)' }}>
                  <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--emerald-text)', marginBottom: 6 }}>Reused Components</div>
                  <div style={{ fontSize: '2rem', fontWeight: 900, letterSpacing: -2 }}>{projectData.components_reused}</div>
                </div>
              </div>
              <div style={{ border: '2.5px solid var(--ink)', borderRadius: 4, padding: '1.25rem', background: '#fff', boxShadow: '4px 4px 0 var(--violet-shadow)', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 12 }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', opacity: 0.6 }}>Code Reusability</span>
                    <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', fontWeight: 900, color: 'var(--violet-text)' }}>{reusabilityPct}%</span>
                  </div>
                  <div style={{ height: 8, border: '2px solid var(--ink)', borderRadius: 2, overflow: 'hidden', background: 'var(--cream-2)' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${reusabilityPct}%` }}
                      transition={{ duration: 1, delay: 0.5 }}
                      style={{ height: '100%', background: 'var(--violet-accent)' }}
                    />
                  </div>
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.6, opacity: 0.6 }}>
                  Efficient component reuse reduces development time and maintains consistency across the application.
                </div>
              </div>
            </div>
          </PcSection>
        )}

        {/* Figma JSON Viewer */}
        {(projectData.status === 'success' || projectData.status === 'completed_with_warnings' || projectData.status === 'completed_with_errors' || projectData.status === 'failed') && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} style={{ marginBottom: '2rem' }}>
            <FigmaJsonViewer projectId={projectData.id} />
          </motion.div>
        )}

        {/* Conversion Trace */}
        {(projectData.status === 'success' || projectData.status === 'completed_with_warnings' || projectData.status === 'completed_with_errors' || projectData.status === 'failed') && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.37 }} style={{ marginBottom: '2rem' }}>
            <ConversionTraceViewer projectId={projectData.id} />
          </motion.div>
        )}

        {/* Project Info */}
        <PcSection title="Project Information" icon={Clock} delay={0.4}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            {[
              {
                label: 'Created',
                value: projectData.created_at ? formatDistanceToNow(new Date(projectData.created_at), { addSuffix: true }) : 'N/A',
                sub: projectData.created_at ? new Date(projectData.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : '',
                color: 'rose',
              },
              {
                label: 'Project Type',
                value: projectData.is_page ? 'Page' : 'Full App',
                sub: projectData.route_path ? `Route: ${projectData.route_path}` : undefined,
                color: 'amber',
              },
              {
                label: 'Project ID',
                value: `#${projectData.id}`,
                sub: projectData.conversion_time_seconds ? `Built in ${projectData.conversion_time_seconds.toFixed(1)}s` : undefined,
                color: 'lime',
              },
            ].map(({ label, value, sub, color }) => (
              <div key={label} style={{
                border: '2.5px solid var(--ink)', borderRadius: 4,
                padding: '14px 16px',
                background: `var(--${color}-fill)`,
                boxShadow: `4px 4px 0 var(--${color}-accent)`,
              }}>
                <div style={{ fontSize: 8, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', opacity: 0.5, marginBottom: 6 }}>{label}</div>
                <div style={{ fontSize: 15, fontWeight: 800, marginBottom: 3 }}>{value}</div>
                {sub && <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', opacity: 0.5 }}>{sub}</div>}
              </div>
            ))}
          </div>
        </PcSection>
      </main>
    </div>
  );
}
