import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Layers, Plus, ExternalLink,
  Clock, Search,
  Eye, Trash2, Code, Box, ChevronDown
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useProjects, useCreateProject, useDeleteProject } from '@/hooks/useProjects';
import { useStats } from '@/hooks/useStats';
import { useNavigate } from 'react-router-dom';
import { ProjectForm } from '@/components/ProjectForm';
import { ConversionProgress } from '@/components/papercut/ConversionProgress';
import type { ProjectCreateRequest } from '@/types';
import '../../styles/papercut.css';

/* =============================================
   CARD COLOR PALETTE — cycles through these
   ============================================= */
const CARD_COLORS = ['rose', 'violet', 'sky', 'amber', 'emerald', 'pink', 'lime'] as const;
type CardColor = typeof CARD_COLORS[number];

function cardColor(index: number): CardColor {
  return CARD_COLORS[index % CARD_COLORS.length];
}

/* =============================================
   STATUS BADGE
   ============================================= */
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string; spin?: boolean }> = {
    completed:                { label: 'Done',       cls: 'pc-status-completed' },
    success:                  { label: 'Done',       cls: 'pc-status-completed' },
    completed_with_warnings:  { label: 'Warnings',   cls: 'pc-status-warning' },
    completed_with_errors:    { label: 'Errors',     cls: 'pc-status-warning' },
    generating:               { label: 'Generating', cls: 'pc-status-processing', spin: true },
    processing:               { label: 'Building',   cls: 'pc-status-processing', spin: true },
    in_progress:              { label: 'Building',   cls: 'pc-status-processing', spin: true },
    failed:                   { label: 'Failed',     cls: 'pc-status-failed' },
    error:                    { label: 'Error',      cls: 'pc-status-failed' },
    pending:                  { label: 'Queued',     cls: 'pc-status-pending' },
  };
  const { label, cls, spin } = map[status] ?? map['pending'];

  return (
    <span className={`pc-status ${cls}`}>
      <span className={`pc-status-dot${spin ? ' pc-spin' : ''}`} />
      {label}
    </span>
  );
}

/* =============================================
   STAT CARD (small)
   ============================================= */
function StatCard({
  value, label, change, color, dotColor,
}: {
  value: string; label: string; change: string;
  color: 'rose' | 'amber' | 'emerald'; dotColor: string;
}) {
  return (
    <motion.div
      className={`pc-stat-card pc-stat-${color}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="pc-stat-corner-dot" style={{ background: dotColor }} />
      <div className="pc-stat-num">{value}</div>
      <div className="pc-stat-label">{label}</div>
      <div className="pc-stat-change">{change}</div>
    </motion.div>
  );
}

/* =============================================
   FEATURED STAT CARD (large)
   ============================================= */
function FeaturedStatCard({ value, change }: { value: string; change: string }) {
  return (
    <motion.div
      className="pc-stat-card pc-stat-featured"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.05 }}
    >
      <div className="pc-stat-num">{value}</div>
      <div className="pc-stat-label">Components Generated</div>
      <div className="pc-stat-change">{change} this month</div>
      <div className="pc-stat-featured-bars">
        {[45, 62, 38, 80, 55, 90, 70].map((h, i) => (
          <span key={i} style={{ height: `${h}%` }} />
        ))}
      </div>
    </motion.div>
  );
}

/* =============================================
   PROJECT CARD
   ============================================= */
function ProjectCard({
  project, index, onView, onDelete, childPages = [],
}: {
  project: any; index: number;
  onView: (id: number) => void;
  onDelete: (id: number) => void;
  childPages?: any[];
}) {
  const color = cardColor(index);
  const hasActivePages = childPages.some(
    p => p.status === 'generating' || p.status === 'in_progress'
  );
  const [pagesOpen, setPagesOpen] = useState(hasActivePages);

  useEffect(() => {
    if (hasActivePages) setPagesOpen(true);
  }, [hasActivePages]);

  const progress =
    project.status === 'completed' || project.status === 'success' || project.status === 'completed_with_warnings' ? 100 :
    project.status === 'completed_with_errors' ? 100 :
    project.status === 'processing' || project.status === 'in_progress' || project.status === 'generating' ? 60 :
    project.status === 'failed' || project.status === 'error' ? 100 :
    20;

  return (
    <motion.div
      className={`pc-project-card pc-card-${color}`}
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.06 * index }}
    >
      <div className="pc-card-bar" />
      <div className="pc-card-body">
        {/* Top row */}
        <div className="pc-card-top">
          <div>
            <div className="pc-card-name">{project.name || project.project_name}</div>
          </div>
          <StatusBadge status={project.status} />
        </div>

        {/* Progress */}
        <div className="pc-progress">
          <div className="pc-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="pc-progress-label">{progress}% complete</div>

        {/* Metrics */}
        <div className="pc-metrics">
          <div className="pc-metric">
            <div className="pc-metric-num">{project.components_generated || 0}</div>
            <div className="pc-metric-label">Components</div>
          </div>
          <div className="pc-metric">
            <div className="pc-metric-num">{project.components_reused || 0}</div>
            <div className="pc-metric-label">Reused</div>
          </div>
        </div>

        {childPages.length > 0 && (
          <div className="pc-card-pages">
            <button className="pc-pages-toggle" onClick={(e) => { e.stopPropagation(); setPagesOpen(v => !v); }}>
              <ChevronDown size={10} style={{ transform: pagesOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
              {childPages.length} page{childPages.length !== 1 ? 's' : ''}
            </button>
            {pagesOpen && (
              <div className="pc-pages-list">
                {childPages.map(page => (
                  <div key={page.id} className="pc-page-row" onClick={(e) => { e.stopPropagation(); onView(page.id); }}>
                    <span className="pc-page-route">{page.route_path || '/'}</span>
                    <StatusBadge status={page.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tags */}
        <div className="pc-tags">
          <span className="pc-tag pc-tag-sky">React</span>
          <span className="pc-tag pc-tag-amber">Figma</span>
          {(project.status === 'completed' || project.status === 'success') && (
            <span className="pc-tag pc-tag-emerald">Live</span>
          )}
          <span className="pc-tag pc-tag-violet">AI</span>
        </div>

        {/* Footer */}
        <div className="pc-card-footer">
          <div className="pc-card-date">
            <Clock size={10} />
            {new Date(project.created_at).toLocaleDateString()}
          </div>
          <div className="pc-card-actions">
            <button className="pc-card-btn" onClick={() => onView(project.id)}>
              <Eye size={10} /> View
            </button>
            <button
              className="pc-card-btn pc-card-btn-danger"
              onClick={(e) => { e.stopPropagation(); onDelete(project.id); }}
            >
              <Trash2 size={10} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* =============================================
   COMPONENT SHOWCASE
   ============================================= */
function ComponentShowcase() {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<any>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['components'],
    queryFn: async () => {
      const r = await fetch('/api/components');
      return r.json();
    },
  });

  const components = (data?.components || []).filter((c: any) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.category?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      {/* Search */}
      <div className="pc-search-wrap">
        <Search size={18} style={{ opacity: 0.4 }} />
        <input
          placeholder="Search components..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="pc-loading">
          <div className="pc-loading-dots">
            <div className="pc-loading-dot" />
            <div className="pc-loading-dot" />
            <div className="pc-loading-dot" />
          </div>
        </div>
      ) : components.length === 0 ? (
        <div className="pc-empty">
          <div className="pc-empty-icon"><Box size={28} /></div>
          <div className="pc-empty-title">No components</div>
          <div className="pc-empty-desc">
            {search ? 'Try a different search term' : 'Generate projects to build your component library'}
          </div>
        </div>
      ) : (
        <div className="pc-projects-grid">
          {components.map((comp: any, i: number) => (
            <motion.div
              key={comp.id}
              className="pc-component-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 * i }}
              onClick={() => setSelected(comp)}
            >
              <div className="pc-component-card-bar" />
              <div className="pc-component-body">
                <div className="pc-component-name">{comp.name}</div>
                {comp.category && (
                  <div className="pc-tags" style={{ marginBottom: 8 }}>
                    <span className="pc-tag pc-tag-violet">{comp.category}</span>
                  </div>
                )}
                <div className="pc-component-desc">
                  {comp.description || 'No description available'}
                </div>
                <div className="pc-component-footer">
                  <span className="pc-component-stat">Used {comp.reuse_count || 0}×</span>
                  <ExternalLink size={13} style={{ opacity: 0.4 }} />
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Detail modal */}
      <AnimatePresence>
        {selected && (
          <motion.div
            className="pc-modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelected(null)}
          >
            <motion.div
              className="pc-modal"
              initial={{ scale: 0.92, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, y: 16 }}
              onClick={e => e.stopPropagation()}
            >
              <div className="pc-modal-title">{selected.name}</div>
              {selected.description && (
                <p style={{ fontSize: 13, marginBottom: 16, opacity: 0.7, lineHeight: 1.6 }}>
                  {selected.description}
                </p>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 16 }}>
                {[
                  { v: selected.reuse_count || 0, l: 'Times Reused' },
                  { v: selected.similarity_score || 'N/A', l: 'Similarity' },
                  { v: selected.project_name || '—', l: 'From Project' },
                ].map(({ v, l }) => (
                  <div key={l} style={{
                    border: '2.5px solid var(--ink)', borderRadius: 3,
                    padding: '10px 12px', background: 'rgba(255,255,255,0.5)',
                    boxShadow: '3px 3px 0 var(--violet-shadow)',
                  }}>
                    <div style={{ fontSize: 20, fontWeight: 900, letterSpacing: -1 }}>{v}</div>
                    <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700,
                      letterSpacing: 1, textTransform: 'uppercase', opacity: 0.5, marginTop: 3 }}>{l}</div>
                  </div>
                ))}
              </div>
              {selected.code && (
                <>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2,
                    textTransform: 'uppercase', fontFamily: 'JetBrains Mono',
                    marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Code size={14} /> Code
                  </div>
                  <pre style={{
                    border: '2.5px solid var(--ink)', borderRadius: 3, padding: 14,
                    fontSize: 12, overflowX: 'auto', background: '#fff',
                    fontFamily: 'JetBrains Mono', lineHeight: 1.5,
                  }}>
                    <code>{selected.code}</code>
                  </pre>
                </>
              )}
              <div style={{ marginTop: 16, textAlign: 'right' }}>
                <button className="pc-btn pc-btn-secondary" onClick={() => setSelected(null)}>
                  Close
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* =============================================
   MAIN DASHBOARD
   ============================================= */
export default function PaperCutDashboard() {
  const navigate = useNavigate();
  const [activeView, setActiveView] = useState<'projects' | 'components' | 'analytics'>('projects');
  const [createOpen, setCreateOpen] = useState(false);
  const [addPageOpen, setAddPageOpen] = useState(false);

  const { data: projectsData, isLoading: projectsLoading } = useProjects();
  const { data: statsData, isLoading: statsLoading } = useStats();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();

  const allProjects = projectsData?.projects || [];
  const standalone = allProjects.filter(p => !p.is_page);
  const pages = allProjects.filter(p => p.is_page);

  const pagesByParent = new Map<number, any[]>();
  allProjects
    .filter(p => p.is_page && p.parent_project_id != null)
    .forEach(p => {
      const parentId = p.parent_project_id as number;
      const arr = pagesByParent.get(parentId) ?? [];
      arr.push(p);
      pagesByParent.set(parentId, arr);
    });

  const handleCreate = async (data: ProjectCreateRequest, isNew: boolean) => {
    await createProject.mutateAsync({ data, isNewProject: isNew });
    setCreateOpen(false);
    setAddPageOpen(false);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Delete this project?')) {
      await deleteProject.mutateAsync(id);
    }
  };

  return (
    <div className="pc-dashboard">
      {/* ── HEADER ── */}
      <header className="pc-header">
        <div className="pc-header-inner">
          {/* Brand */}
          <div className="pc-brand">
            <div className="pc-brand-dots">
              <div className="pc-brand-dot" style={{ background: '#f43f5e' }} />
              <div className="pc-brand-dot" style={{ background: '#f59e0b' }} />
              <div className="pc-brand-dot" style={{ background: '#10b981' }} />
            </div>
            <div>
              <div className="pc-brand-name">Aura Agent</div>
              <div className="pc-brand-tag">Figma → React</div>
            </div>
          </div>

          {/* Nav */}
          <nav className="pc-nav">
            {(['projects', 'components', 'analytics'] as const).map(v => (
              <button
                key={v}
                className={`pc-nav-btn ${activeView === v ? 'active' : ''}`}
                onClick={() => setActiveView(v)}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </nav>

          {/* Actions */}
          <div className="pc-header-actions">
            <button className="pc-btn pc-btn-secondary" onClick={() => setAddPageOpen(true)}>
              <Plus size={14} /> Add Page
            </button>
            <button className="pc-btn pc-btn-primary" onClick={() => setCreateOpen(true)}>
              <Plus size={14} /> New Project
            </button>
          </div>
        </div>
      </header>

      {/* ── MAIN ── */}
      <main className="pc-main">
        <AnimatePresence mode="wait">

          {/* PROJECTS VIEW */}
          {activeView === 'projects' && (
            <motion.div
              key="projects"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3 }}
            >
              {/* Stats */}
              <div className="pc-section-header">
                <span className="pc-section-title">Overview</span>
              </div>

              {statsLoading ? (
                <div className="pc-loading">
                  <div className="pc-loading-dots">
                    <div className="pc-loading-dot" />
                    <div className="pc-loading-dot" />
                    <div className="pc-loading-dot" />
                  </div>
                </div>
              ) : (
                <div className="pc-stats-grid" style={{ marginBottom: '2.5rem' }}>
                  <FeaturedStatCard
                    value={statsData?.total_components?.toString() ?? '0'}
                    change="+38%"
                  />
                  <StatCard
                    value={statsData?.total_projects?.toString() ?? '0'}
                    label="Projects"
                    change="+12% ↑"
                    color="rose"
                    dotColor="#f43f5e"
                  />
                  <StatCard
                    value={statsData?.completed_projects?.toString() ?? '0'}
                    label="Completed"
                    change={`${Math.round((statsData?.completed_projects ?? 0) / Math.max(statsData?.total_projects ?? 1, 1) * 100)}%`}
                    color="emerald"
                    dotColor="#10b981"
                  />
                  <StatCard
                    value={statsData?.total_component_reuses?.toString() ?? '0'}
                    label="Reuses"
                    change="saved"
                    color="amber"
                    dotColor="#f59e0b"
                  />
                </div>
              )}

              {/* Active conversions */}
              {allProjects
                .filter(p => p.status === 'generating' || p.status === 'pending')
                .map(p => (
                  <ConversionProgress key={`progress-${p.id}`} projectId={p.id} />
                ))
              }

              {/* Projects list */}
              <div className="pc-section-header">
                <span className="pc-section-title">All Projects</span>
                {standalone.length > 0 && (
                  <span className="pc-section-count">
                    {standalone.length} projects · {pages.length} pages
                  </span>
                )}
              </div>

              {projectsLoading ? (
                <div className="pc-loading">
                  <div className="pc-loading-dots">
                    <div className="pc-loading-dot" />
                    <div className="pc-loading-dot" />
                    <div className="pc-loading-dot" />
                  </div>
                </div>
              ) : standalone.length === 0 ? (
                <div className="pc-empty">
                  <div className="pc-empty-icon">
                    <Layers size={28} />
                  </div>
                  <div className="pc-empty-title">No Projects Yet</div>
                  <div className="pc-empty-desc">
                    Create your first project by uploading a Figma design or using the Figma plugin.
                  </div>
                  <button className="pc-btn pc-btn-primary" onClick={() => setCreateOpen(true)}>
                    <Plus size={14} /> Create First Project
                  </button>
                </div>
              ) : (
                <div className="pc-projects-grid">
                  {standalone.map((p, i) => (
                    <ProjectCard
                      key={p.id}
                      project={p}
                      index={i}
                      childPages={pagesByParent.get(p.id) ?? []}
                      onView={id => navigate(`/projects/${id}`)}
                      onDelete={handleDelete}
                    />
                  ))}
                </div>
              )}

            </motion.div>
          )}

          {/* COMPONENTS VIEW */}
          {activeView === 'components' && (
            <motion.div
              key="components"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3 }}
            >
              <div className="pc-section-header">
                <span className="pc-section-title">Component Library</span>
              </div>
              <ComponentShowcase />
            </motion.div>
          )}

          {/* ANALYTICS VIEW */}
          {activeView === 'analytics' && (
            <motion.div
              key="analytics"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3 }}
            >
              <div className="pc-coming-soon">
                <h2>Analytics</h2>
                <p>Coming soon...</p>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </main>

      {/* Forms */}
      <ProjectForm
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
        isNewProject
      />
      <ProjectForm
        open={addPageOpen}
        onOpenChange={setAddPageOpen}
        onSubmit={handleCreate}
        isNewProject={false}
      />
    </div>
  );
}
