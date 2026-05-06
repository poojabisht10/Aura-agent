import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, Cpu, Layers, CheckCircle, Wrench, Paintbrush, Package } from 'lucide-react';
import '../../styles/papercut.css';

const API_BASE = 'http://localhost:8000';

const PHASE_META: Record<string, { label: string; icon: any; color: string }> = {
  SETUP:        { label: 'Setting up project',       icon: Package,     color: 'sky' },
  IMAGES:       { label: 'Processing images',         icon: Paintbrush,  color: 'amber' },
  CONVERSION:   { label: 'Generating components',     icon: Cpu,         color: 'violet' },
  BUILD:        { label: 'Verifying build',           icon: Package,     color: 'emerald' },
  QUALITY:      { label: 'Running quality checks',     icon: Wrench,      color: 'rose' },
  VERIFICATION: { label: 'Design verification',       icon: CheckCircle, color: 'violet' },
  DONE:         { label: 'Complete',                  icon: CheckCircle, color: 'emerald' },
};

const PHASE_ORDER = ['SETUP', 'IMAGES', 'CONVERSION', 'BUILD', 'QUALITY', 'VERIFICATION', 'DONE'];

interface ProgressLine {
  ts: string;
  level: string;
  phase: string;
  msg: string;
}

interface ProgressData {
  project_id: number;
  project_name: string;
  phase: string;
  status: string;
  elapsed_s: number;
  components: number;
  tools_used: number;
  lines: ProgressLine[];
}

export function ConversionProgress({ projectId }: { projectId: number }) {
  const [data, setData] = useState<ProgressData | null>(null);
  const [expanded, setExpanded] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/projects/${projectId}/progress`);
        if (res.ok && active) {
          const d = await res.json();
          setData(d);
        }
      } catch { /* ignore */ }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => { active = false; clearInterval(interval); };
  }, [projectId]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [data?.lines?.length]);

  if (!data || data.status === 'success' || data.status === 'failed') return null;

  const currentPhase = data.phase || 'SETUP';
  const phaseIdx = PHASE_ORDER.indexOf(currentPhase);
  const phaseMeta = PHASE_META[currentPhase] || PHASE_META.SETUP;
  const PhaseIcon = phaseMeta.icon;

  const elapsed = data.elapsed_s || 0;
  const mins = Math.floor(elapsed / 60);
  const secs = Math.round(elapsed % 60);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="pc-progress-terminal"
    >
      {/* Header bar */}
      <div className="pc-term-header" onClick={() => setExpanded(v => !v)}>
        <div className="pc-term-header-left">
          <div className="pc-term-dots">
            <span style={{ background: '#f43f5e' }} />
            <span style={{ background: '#f59e0b' }} />
            <span style={{ background: '#10b981' }} />
          </div>
          <Terminal size={12} />
          <span className="pc-term-title">Conversion Progress</span>
        </div>
        <div className="pc-term-header-right">
          <span className="pc-term-time">{mins}m {secs}s</span>
          <span className="pc-term-stats">
            <Layers size={10} /> {data.components} components
          </span>
          <span className="pc-term-stats">
            <Wrench size={10} /> {data.tools_used} tools
          </span>
        </div>
      </div>

      {/* Phase progress bar */}
      <div className="pc-term-phases">
        {PHASE_ORDER.map((p, i) => {
          const done = i < phaseIdx;
          const active = i === phaseIdx;
          const meta = PHASE_META[p] || PHASE_META.SETUP;
          return (
            <div
              key={p}
              className={`pc-term-phase ${done ? 'done' : ''} ${active ? 'active' : ''}`}
            >
              <div className={`pc-term-phase-dot ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
                {done ? <CheckCircle size={10} /> : active ? <div className="pc-term-pulse" /> : null}
              </div>
              <span className="pc-term-phase-label">{meta.label.split(' ')[0]}</span>
            </div>
          );
        })}
      </div>

      {/* Current phase banner */}
      <div className={`pc-term-phase-banner pc-term-phase-${phaseMeta.color}`}>
        <PhaseIcon size={14} className={data.status === 'running' ? 'pc-spin' : ''} />
        <span>{phaseMeta.label}</span>
        {data.status === 'running' && <div className="pc-term-typing"><span /><span /><span /></div>}
      </div>

      {/* Log output */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="pc-term-log-wrap"
          >
            <div className="pc-term-log">
              {(data.lines || []).map((line, i) => (
                <div key={i} className={`pc-term-line pc-term-line-${line.level}`}>
                  <span className="pc-term-line-ts">{line.ts}</span>
                  <span className="pc-term-line-phase">{line.phase}</span>
                  <span className="pc-term-line-msg">{line.msg}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
