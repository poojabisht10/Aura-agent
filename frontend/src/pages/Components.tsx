import { useState } from "react";
import { motion } from "framer-motion";
import { useComponents } from "@/hooks/useComponents";
import { Search, Package, Code, ExternalLink } from "lucide-react";
import '../styles/papercut.css';

export function Components() {
  const { data: componentsData, isLoading } = useComponents();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<any>(null);

  const components = (componentsData?.components || []).filter((c: any) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.category?.toLowerCase().includes(search.toLowerCase())
  );

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
              <div className="pc-brand-tag">Component Library</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              border: '2.5px solid rgba(255,255,255,0.15)', borderRadius: 3,
              padding: '4px 12px', display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <Package size={13} style={{ color: 'rgba(255,255,255,0.5)' }} />
              <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: 'rgba(255,255,255,0.5)', letterSpacing: 1 }}>
                {components.length} components
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="pc-main">
        <div className="pc-section-header">
          <span className="pc-section-title">Component Library</span>
          <span className="pc-section-count">Browse & search reusable React components</span>
        </div>

        {/* Search */}
        <div className="pc-search-wrap">
          <Search size={18} style={{ opacity: 0.4, flexShrink: 0 }} />
          <input
            placeholder="Search by name or category..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{ fontSize: 10, fontFamily: 'JetBrains Mono', opacity: 0.4, border: 'none', background: 'none', cursor: 'pointer', flexShrink: 0 }}
            >
              ✕ Clear
            </button>
          )}
        </div>

        {/* Content */}
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
            <div className="pc-empty-icon"><Package size={28} /></div>
            <div className="pc-empty-title">
              {search ? 'No Results' : 'No Components Yet'}
            </div>
            <div className="pc-empty-desc">
              {search
                ? `No components match "${search}" — try a different search term`
                : 'Generate projects from Figma designs to build your component library'}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div className="pc-component-name">{comp.name}</div>
                    <Code size={14} style={{ opacity: 0.3, flexShrink: 0 }} />
                  </div>
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
                    <ExternalLink size={13} style={{ opacity: 0.3 }} />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>

      {/* Detail modal */}
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
            initial={{ scale: 0.94, y: 12 }}
            animate={{ scale: 1, y: 0 }}
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
                { v: selected.reuse_count || 0, l: 'Times Reused', c: 'rose' },
                { v: selected.similarity_score || 'N/A', l: 'Similarity', c: 'sky' },
                { v: selected.project_name || '—', l: 'From Project', c: 'amber' },
              ].map(({ v, l, c }) => (
                <div key={l} style={{
                  border: '2.5px solid var(--ink)', borderRadius: 3,
                  padding: '10px 12px',
                  background: `var(--${c}-fill)`,
                  boxShadow: `3px 3px 0 var(--${c}-accent)`,
                }}>
                  <div style={{ fontSize: 20, fontWeight: 900, letterSpacing: -1 }}>{v}</div>
                  <div style={{ fontSize: 8, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', opacity: 0.5, marginTop: 3 }}>{l}</div>
                </div>
              ))}
            </div>
            {selected.code && (
              <>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', fontFamily: 'JetBrains Mono', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Code size={13} /> Source Code
                </div>
                <pre style={{
                  border: '2.5px solid var(--ink)', borderRadius: 3,
                  padding: 14, fontSize: 11, overflowX: 'auto',
                  background: '#fff', fontFamily: 'JetBrains Mono', lineHeight: 1.6,
                  boxShadow: '3px 3px 0 var(--ink)',
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
    </div>
  );
}
