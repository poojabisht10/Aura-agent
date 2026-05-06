import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { projectsApi } from '@/api/client';
import {
  ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertTriangle,
  Image, BarChart3, Layers, GitCompareArrows,
} from 'lucide-react';
import type { VerificationReport, VerificationScores } from '@/types';

/** Normalize screenshot path: strip everything up to and including "screenshots/"
 *  so both old full-path reports and new relative-path reports resolve correctly. */
function normalizeScreenshotPath(raw: string): string {
  const normalized = raw.replace(/\\/g, '/');
  const idx = normalized.lastIndexOf('screenshots/');
  if (idx !== -1) {
    return normalized.slice(idx + 'screenshots/'.length);
  }
  return normalized;
}

const SCORE_COLORS: Record<string, string> = {
  color: 'rose',
  spacing: 'sky',
  typography: 'amber',
  effects: 'emerald',
  dimension: 'violet',
  pixel: 'pink',
  layout: 'pink',
};

// Labels shown in the dashboard — hide internal/duplicate keys
const SCORE_LABELS: Record<string, string> = {
  color: 'Colors',
  spacing: 'Spacing',
  typography: 'Typography',
  effects: 'Effects',
  dimension: 'Dimensions',
  pixel: 'Pixel Match',
  layout: 'Layout (visual)',
};

// Keys to hide from the score display (internal, redundant, or misleading)
const HIDDEN_SCORES = new Set(['structural', 'element_dimensions']);

function confidenceColor(c: number): string {
  if (c >= 0.95) return 'emerald';
  if (c >= 0.85) return 'amber';
  return 'rose';
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConfidenceGauge({ report }: { report: VerificationReport }) {
  const color = confidenceColor(report.overall_confidence);
  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
      {/* Main confidence card */}
      <div style={{
        flex: '1 1 200px',
        border: '2.5px solid var(--ink)',
        borderRadius: 4,
        padding: '1.5rem',
        background: `var(--${color}-fill)`,
        boxShadow: `5px 5px 0 var(--${color}-accent)`,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', opacity: 0.6, marginBottom: 8 }}>
          Overall Confidence
        </div>
        <div style={{ fontSize: '3rem', fontWeight: 900, letterSpacing: -2, color: `var(--${color}-text)` }}>
          {pct(report.overall_confidence)}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 10 }}>
          <span className={`pc-status pc-status-${report.status === 'success' ? 'completed' : report.status === 'completed_with_warnings' ? 'warning' : (report.status === 'needs_review' || report.status === 'failed') ? 'failed' : 'pending'}`}
            style={{ fontSize: 8, padding: '3px 10px' }}>
            <span className="pc-status-dot" />
            {report.status.toUpperCase().replace(/_/g, ' ')}
          </span>
          <span style={{ fontSize: 8, fontFamily: 'JetBrains Mono', opacity: 0.4, alignSelf: 'center' }}>
            {report.method}
          </span>
        </div>
      </div>

      {/* Quick stats */}
      <div style={{ flex: '1 1 300px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {[
          { label: 'Iterations', value: String(report.iterations), color: 'violet' },
          { label: 'Elements', value: String(report.element_comparison.element_count), color: 'sky' },
          { label: 'Discrepancies', value: String(report.discrepancies.length), color: report.discrepancies.length === 0 ? 'emerald' : 'rose' },
          { label: 'Dim Accuracy', value: pct(report.element_comparison.overall_dimension_accuracy || 0), color: 'amber' },
        ].map(({ label, value, color: c }) => (
          <div key={label} style={{
            border: '2.5px solid var(--ink)',
            borderRadius: 4,
            padding: '10px 14px',
            background: `var(--${c}-fill)`,
            boxShadow: `3px 3px 0 var(--${c}-accent)`,
          }}>
            <div style={{ fontSize: 8, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', opacity: 0.5 }}>{label}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, letterSpacing: -1 }}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CategoryScores({ scores }: { scores: VerificationScores }) {
  // Filter out hidden/internal scores and show only meaningful ones
  const entries = Object.entries(scores)
    .filter(([key, v]) => v !== undefined && v !== null && !HIDDEN_SCORES.has(key))
    .sort(([a], [b]) => {
      // Sort by SCORE_COLORS key order for consistency
      const order = Object.keys(SCORE_COLORS);
      return (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) - (order.indexOf(b) === -1 ? 99 : order.indexOf(b));
    });
  if (entries.length === 0) return null;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 10, opacity: 0.5 }}>
        <BarChart3 size={11} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Category Scores
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {entries.map(([key, val]) => {
          const v = val as number;
          const color = SCORE_COLORS[key] || 'violet';
          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 110, fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>
                {SCORE_LABELS[key] || key}
              </div>
              <div style={{ flex: 1, height: 12, border: '2px solid var(--ink)', borderRadius: 2, overflow: 'hidden', background: 'var(--cream-2)' }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.round(v * 100)}%` }}
                  transition={{ duration: 0.8 }}
                  style={{ height: '100%', background: `var(--${color}-accent)`, borderRadius: 1 }}
                />
              </div>
              <div style={{ width: 40, fontSize: 10, fontFamily: 'JetBrains Mono', fontWeight: 800, textAlign: 'right' }}>
                {pct(v)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ElementGrid({ elements, projectId }: { elements: VerificationReport['per_element_results']; projectId: number }) {
  if (elements.length === 0) return null;

  // Show only meaningful components — filter out individual text nodes and tiny elements.
  // Heuristic: elements with a screenshot and name that looks like a section/frame (not
  // plain text like "Mobile", "IT", "Offers"). Keep elements that have width/height checks
  // or have a name starting with uppercase + containing spaces/numbers (section names).
  const meaningful = elements.filter(elem => {
    // Always show elements that have dimension checks (they are containers)
    if (elem.width_match !== undefined || elem.height_match !== undefined) return true;
    // Show elements with pixel comparison data
    if (elem.pixel_comparison) return true;
    // Show elements with a screenshot thumbnail
    if (elem.dom_screenshot) return true;
    return false;
  });

  const [showAll, setShowAll] = useState(false);
  const displayed = showAll ? meaningful : meaningful.slice(0, 12);

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 10, opacity: 0.5 }}>
        <Layers size={11} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Per-Element Results ({meaningful.length} components{meaningful.length < elements.length ? `, ${elements.length - meaningful.length} text nodes hidden` : ''})
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {displayed.map((elem, i) => {
          const score = elem.accuracy || 0;
          const color = score >= 0.9 ? 'emerald' : score >= 0.7 ? 'amber' : 'rose';
          return (
            <motion.div
              key={elem.figma_id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.03, 0.5) }}
              style={{
                border: '2.5px solid var(--ink)',
                borderRadius: 4,
                overflow: 'hidden',
                boxShadow: `3px 3px 0 var(--${color}-accent)`,
                background: '#fff',
              }}
            >
              {/* Color bar */}
              <div style={{ height: 4, background: `var(--${color}-accent)` }} />

              {/* Thumbnail */}
              {elem.dom_screenshot && (
                <div style={{ height: 100, overflow: 'hidden', borderBottom: '2px solid var(--cream-3)', background: 'var(--cream)' }}>
                  <img
                    src={projectsApi.getScreenshotUrl(projectId, normalizeScreenshotPath(elem.dom_screenshot))}
                    alt={elem.name}
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                </div>
              )}

              {/* Info */}
              <div style={{ padding: '10px 12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
                    {elem.name || elem.figma_id}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono', fontWeight: 800, color: `var(--${color}-text)` }}>
                    {pct(score)}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                  {elem.width_match !== undefined && (
                    <span style={{ fontSize: 8, fontFamily: 'JetBrains Mono', display: 'flex', alignItems: 'center', gap: 2 }}>
                      {elem.width_match ? <CheckCircle2 size={9} color="var(--emerald-accent)" /> : <XCircle size={9} color="var(--rose-accent)" />}
                      W
                    </span>
                  )}
                  {elem.height_match !== undefined && (
                    <span style={{ fontSize: 8, fontFamily: 'JetBrains Mono', display: 'flex', alignItems: 'center', gap: 2 }}>
                      {elem.height_match ? <CheckCircle2 size={9} color="var(--emerald-accent)" /> : <XCircle size={9} color="var(--rose-accent)" />}
                      H
                    </span>
                  )}
                  {elem.pixel_comparison && (
                    <span style={{ fontSize: 8, fontFamily: 'JetBrains Mono', opacity: 0.5 }}>
                      px:{pct(elem.pixel_comparison.pixel_match_ratio)}
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
      {meaningful.length > 12 && (
        <button
          onClick={() => setShowAll(!showAll)}
          style={{
            marginTop: 10,
            background: 'none',
            border: 'none',
            fontFamily: 'JetBrains Mono',
            fontSize: 9,
            letterSpacing: 1,
            cursor: 'pointer',
            color: 'var(--violet-text)',
            textDecoration: 'underline',
          }}
        >
          {showAll ? 'Show less' : `Show all ${meaningful.length} elements`}
        </button>
      )}
    </div>
  );
}

function IterationTimeline({ history }: { history: VerificationReport['iteration_history'] }) {
  if (history.length <= 1) return null;
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 10, opacity: 0.5 }}>
        <GitCompareArrows size={11} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Fix Iteration Timeline
      </div>
      <div style={{
        border: '2.5px solid var(--ink)',
        borderRadius: 4,
        padding: '16px 20px',
        background: '#fff',
        boxShadow: '3px 3px 0 var(--violet-shadow)',
        display: 'flex',
        alignItems: 'flex-end',
        gap: 4,
        height: 100,
        position: 'relative',
      }}>
        {history.map((iter, i) => {
          const h = Math.max(10, iter.confidence * 80);
          const color = confidenceColor(iter.confidence);
          return (
            <motion.div
              key={i}
              initial={{ height: 0 }}
              animate={{ height: h }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              style={{
                flex: 1,
                background: `var(--${color}-accent)`,
                borderRadius: '2px 2px 0 0',
                border: '1.5px solid var(--ink)',
                position: 'relative',
                minWidth: 24,
              }}
              title={`Iteration ${iter.iteration}: ${pct(iter.confidence)}${iter.fixes_applied != null ? ` (${iter.fixes_applied} fixes)` : ''}`}
            >
              <div style={{
                position: 'absolute',
                top: -16,
                left: '50%',
                transform: 'translateX(-50%)',
                fontSize: 8,
                fontFamily: 'JetBrains Mono',
                fontWeight: 700,
                whiteSpace: 'nowrap',
              }}>
                {pct(iter.confidence)}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function DiscrepancyList({ discrepancies }: { discrepancies: any[] }) {
  const [expanded, setExpanded] = useState(false);
  if (discrepancies.length === 0) return null;

  const shown = expanded ? discrepancies : discrepancies.slice(0, 5);
  const severityColor: Record<string, string> = { high: 'rose', medium: 'amber', low: 'sky' };

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 10, opacity: 0.5 }}>
        <AlertTriangle size={11} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Discrepancies ({discrepancies.length})
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {shown.map((d: any, i: number) => {
          const sev = d.severity || 'medium';
          const sc = severityColor[sev] || 'amber';
          return (
            <div key={i} style={{
              border: '2px solid var(--ink)',
              borderRadius: 3,
              padding: '8px 12px',
              background: `var(--${sc}-fill)`,
              display: 'flex',
              gap: 10,
              alignItems: 'center',
              fontSize: 11,
            }}>
              <span style={{
                fontSize: 7,
                fontFamily: 'JetBrains Mono',
                fontWeight: 700,
                letterSpacing: 1,
                textTransform: 'uppercase',
                background: `var(--${sc}-accent)`,
                color: '#fff',
                padding: '2px 6px',
                borderRadius: 2,
                flexShrink: 0,
              }}>
                {sev}
              </span>
              <span style={{ fontSize: 8, fontFamily: 'JetBrains Mono', opacity: 0.5, flexShrink: 0 }}>
                {d.type || 'unknown'}
              </span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {d.location || d.element || ''}: {d.expected || ''} → {d.actual || ''}
              </span>
            </div>
          );
        })}
      </div>
      {discrepancies.length > 5 && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: 8,
            fontSize: 9,
            fontFamily: 'JetBrains Mono',
            fontWeight: 600,
            letterSpacing: 1,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--violet-text)',
            textDecoration: 'underline',
          }}
        >
          {expanded ? 'Show less' : `Show all ${discrepancies.length} discrepancies`}
        </button>
      )}
    </div>
  );
}

function ScreenshotFrame({ label, src }: { label: string; src: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div style={{
      border: '2.5px solid var(--ink)',
      borderRadius: 4,
      overflow: 'hidden',
      boxShadow: '4px 4px 0 var(--ink)',
    }}>
      <div style={{
        background: 'var(--ink)',
        padding: '6px 12px',
        fontSize: 8,
        fontFamily: 'JetBrains Mono',
        fontWeight: 700,
        letterSpacing: 2,
        textTransform: 'uppercase',
        color: 'rgba(255,255,255,0.6)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: label === 'Figma Design' ? '#f43f5e' : '#10b981' }} />
        {label}
      </div>
      <div style={{ height: 300, background: 'var(--cream)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {!failed ? (
          <img
            src={src}
            alt={label}
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            onError={() => setFailed(true)}
          />
        ) : (
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: 10, opacity: 0.3, letterSpacing: 1 }}>No screenshot</div>
        )}
      </div>
    </div>
  );
}

function SideBySideScreenshots({ projectId }: { projectId: number }) {
  const figmaUrl = projectsApi.getScreenshotUrl(projectId, 'figma_design_plugin.png');
  const genUrl = projectsApi.getScreenshotUrl(projectId, 'generated_latest.png');

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 10, opacity: 0.5 }}>
        <Image size={11} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
        Side-by-Side Comparison
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <ScreenshotFrame label="Figma Design" src={figmaUrl} />
        <ScreenshotFrame label="Generated Output" src={genUrl} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function VerificationDashboard({ projectId }: { projectId: number }) {
  const [isOpen, setIsOpen] = useState(false);

  const { data: report, isLoading, isError } = useQuery({
    queryKey: ['verification-report', projectId],
    queryFn: () => projectsApi.getVerificationReport(projectId),
    enabled: isOpen, // Only fetch when expanded
    retry: false,
    staleTime: 60_000,
  });

  return (
    <div>
      {/* Toggle header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls="verification-dashboard-panel"
        style={{
          width: '100%',
          border: '2.5px solid var(--ink)',
          borderRadius: 4,
          padding: '12px 16px',
          background: isOpen ? 'var(--violet-fill)' : '#fff',
          boxShadow: `3px 3px 0 var(--${isOpen ? 'violet' : 'ink'})`,
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontFamily: 'JetBrains Mono',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: 2,
          textTransform: 'uppercase',
          transition: 'background 0.15s',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChart3 size={13} />
          Verification Report
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {report && (
            <span style={{
              fontSize: 9,
              padding: '2px 8px',
              borderRadius: 2,
              background: `var(--${confidenceColor(report.overall_confidence)}-accent)`,
              color: '#fff',
            }}>
              {pct(report.overall_confidence)}
            </span>
          )}
          {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>

      {/* Content */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            id="verification-dashboard-panel"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ paddingTop: 16 }}>
              {isLoading && (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <div className="pc-loading-dots">
                    <div className="pc-loading-dot" />
                    <div className="pc-loading-dot" />
                    <div className="pc-loading-dot" />
                  </div>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 10, letterSpacing: 2, marginTop: 12, opacity: 0.4 }}>
                    Loading verification report...
                  </div>
                </div>
              )}

              {isError && (
                <div style={{
                  border: '2.5px solid var(--ink)',
                  borderRadius: 4,
                  padding: '20px',
                  background: 'var(--cream)',
                  textAlign: 'center',
                }}>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 10, letterSpacing: 1, opacity: 0.4 }}>
                    No verification report available. Verification may not have run for this project.
                  </div>
                </div>
              )}

              {report && (
                <>
                  <ConfidenceGauge report={report} />
                  <CategoryScores scores={{
                    ...report.scores,
                    ...(report.element_comparison?.overall_pixel_accuracy != null
                      ? { pixel: report.element_comparison.overall_pixel_accuracy }
                      : {}),
                  }} />
                  <IterationTimeline history={report.iteration_history} />
                  <ElementGrid elements={report.per_element_results} projectId={projectId} />
                  <DiscrepancyList discrepancies={report.discrepancies} />
                  <SideBySideScreenshots projectId={projectId} />
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
