import { useState, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  Position,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Copy, Check, Clock } from 'lucide-react';
import { getAgentStatus, getAgentOutput } from '../api';

// --- Pipeline Steps (realistic workflow — no login step) ---

const PIPELINE_STEPS = [
  { id: 'init', label: 'Initialize', emoji: '⚡', description: 'Load config', x: 50, y: 40 },
  { id: 'browser', label: 'Browser', emoji: '🌐', description: 'Launch Chromium', x: 230, y: 40 },
  { id: 'session', label: 'Session', emoji: '🔐', description: 'Verify login', x: 410, y: 40 },
  { id: 'recommended', label: 'Recommended', emoji: '⭐', description: 'LinkedIn picks', x: 620, y: 40 },
  { id: 'keywords', label: 'Keyword Search', emoji: '🔍', description: 'Your search terms', x: 850, y: 40 },
  { id: 'custom', label: 'Custom URLs', emoji: '🔗', description: 'Additional sources', x: 1080, y: 40 },
  { id: 'evaluate', label: 'Evaluate', emoji: '🎯', description: 'Open + score each job', x: 850, y: 220 },
  { id: 'apply', label: 'Apply', emoji: '📝', description: 'Easy Apply ≥80%', x: 620, y: 220 },
  { id: 'notify', label: 'Notify', emoji: '📱', description: 'Telegram + Tracker', x: 410, y: 220 },
  { id: 'complete', label: 'Summary', emoji: '🏁', description: 'Report results', x: 230, y: 220 },
];

const PIPELINE_EDGES = [
  { source: 'init', target: 'browser' },
  { source: 'browser', target: 'session' },
  { source: 'session', target: 'recommended' },
  { source: 'recommended', target: 'keywords' },
  { source: 'keywords', target: 'custom' },
  { source: 'custom', target: 'evaluate' },
  { source: 'evaluate', target: 'apply', label: '≥ 80%' },
  { source: 'evaluate', target: 'complete', label: 'skip/done' },
  { source: 'apply', target: 'notify' },
  { source: 'notify', target: 'evaluate', label: 'next job' },
  { source: 'notify', target: 'complete', label: 'all done' },
];

const STEP_STYLES = {
  idle: { border: 'border-slate-200', bg: 'bg-white', text: 'text-slate-400' },
  active: { border: 'border-teal-400', bg: 'bg-teal-50', text: 'text-teal-700' },
  done: { border: 'border-emerald-300', bg: 'bg-emerald-50', text: 'text-emerald-700' },
  error: { border: 'border-red-300', bg: 'bg-red-50', text: 'text-red-700' },
  skipped: { border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-600' },
};

// --- Custom Node with hover tooltip ---

function PipelineNode({ data }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const style = STEP_STYLES[data.status] || STEP_STYLES.idle;
  const isActive = data.status === 'active';

  return (
    <div
      className={`relative rounded-2xl border-2 ${style.border} ${style.bg} px-4 py-3 min-w-[150px] max-w-[180px] transition-all duration-500 cursor-grab active:cursor-grabbing ${
        isActive ? 'ring-4 ring-teal-400/20 shadow-lg shadow-teal-500/20' : ''
      } ${data.status === 'error' ? 'ring-4 ring-red-400/20 shadow-lg shadow-red-500/20' : ''}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-300 !w-2.5 !h-2.5 !border-2 !border-white" />
      <Handle type="source" position={Position.Right} className="!bg-slate-300 !w-2.5 !h-2.5 !border-2 !border-white" />

      {isActive && (
        <div className="absolute -top-1 -right-1 flex h-4 w-4">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75" />
          <span className="relative inline-flex h-4 w-4 rounded-full bg-teal-500" />
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-xl">{data.emoji}</span>
        <div>
          <p className={`text-xs font-bold ${style.text}`}>{data.label}</p>
          <p className="text-[10px] text-slate-400 leading-tight">{data.description}</p>
        </div>
      </div>

      {/* Status badge */}
      {data.status === 'done' && (
        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-bold text-white shadow-sm">
          ✓ DONE
        </div>
      )}
      {data.status === 'error' && (
        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-red-500 px-2 py-0.5 text-[9px] font-bold text-white shadow-sm">
          ✗ FAILED
        </div>
      )}
      {data.status === 'skipped' && (
        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 px-2 py-0.5 text-[9px] font-bold text-white shadow-sm">
          ↷ SKIPPED
        </div>
      )}

      {/* Active message */}
      {data.message && (data.status === 'active' || data.status === 'done' || data.status === 'error') && (
        <div className={`mt-2 rounded-lg px-2 py-1 text-[10px] font-medium border ${
          data.status === 'error' ? 'bg-red-50 border-red-200 text-red-600' :
          data.status === 'done' ? 'bg-emerald-50 border-emerald-200 text-emerald-600' :
          'bg-white/80 border-teal-200 text-teal-600'
        }`}>
          {data.message}
        </div>
      )}

      {/* Hover tooltip with details */}
      {showTooltip && data.summary && (
        <div className="absolute -top-2 left-1/2 -translate-x-1/2 -translate-y-full z-50 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-xl text-left">
          <p className="text-xs font-semibold text-slate-800 mb-1">{data.label} — {data.status.toUpperCase()}</p>
          <p className="text-[11px] text-slate-600 whitespace-pre-wrap">{data.summary}</p>
          {data.duration && (
            <p className="mt-1 text-[10px] text-slate-400 flex items-center gap-1">
              <Clock className="h-3 w-3" /> {data.duration}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

const nodeTypes = { pipeline: PipelineNode };

// --- Main Component ---

export default function AgentPipelineView() {
  const [stepStatuses, setStepStatuses] = useState({});
  const [stepMessages, setStepMessages] = useState({});
  const [stepSummaries, setStepSummaries] = useState({});
  const [status, setStatus] = useState({ state: 'idle' });
  const [stats, setStats] = useState({ processed: 0, applied: 0, skipped: 0, errors: 0 });
  const [copied, setCopied] = useState(false);
  const [copiedLogs, setCopiedLogs] = useState(false);
  const [rawOutput, setRawOutput] = useState([]);

  const nodes = useMemo(() =>
    PIPELINE_STEPS.map(step => ({
      id: step.id,
      type: 'pipeline',
      position: { x: step.x, y: step.y },
      data: {
        ...step,
        status: stepStatuses[step.id] || 'idle',
        message: stepMessages[step.id] || '',
        summary: stepSummaries[step.id] || '',
      },
    })),
    [stepStatuses, stepMessages, stepSummaries]
  );

  const edges = useMemo(() =>
    PIPELINE_EDGES.map((edge, i) => ({
      id: `e-${i}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'smoothstep',
      animated: stepStatuses[edge.source] === 'active' || stepStatuses[edge.target] === 'active',
      style: {
        stroke: stepStatuses[edge.source] === 'done' ? '#10b981' :
                stepStatuses[edge.source] === 'active' ? '#14b8a6' :
                stepStatuses[edge.source] === 'error' ? '#ef4444' : '#cbd5e1',
        strokeWidth: stepStatuses[edge.source] === 'active' ? 2.5 : 1.5,
        strokeDasharray: edge.style === 'dashed' ? '5,5' : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: stepStatuses[edge.source] === 'active' ? '#14b8a6' : '#94a3b8' },
      labelStyle: { fontSize: 10, fill: '#64748b' },
    })),
    [stepStatuses]
  );

  // Poll
  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getAgentStatus();
        setStatus(s);
        if (s.state === 'running' || s.state === 'error') {
          const outputData = await getAgentOutput(200);
          setRawOutput(outputData.lines);
          parseOutputToSteps(outputData.lines);
        }
      } catch (e) { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, []);

  const parseOutputToSteps = (lines) => {
    const newStatuses = {};
    const newMessages = {};
    const newSummaries = {};
    const newStats = { processed: 0, applied: 0, skipped: 0, errors: 0 };

    const text = lines.join('\n').toLowerCase();
    const rawText = lines.join('\n');

    // Init
    if (text.includes('pipeline started') || text.includes('running single scan') || text.includes('scan cycle started')) {
      newStatuses.init = 'done';
      newMessages.init = 'Config loaded';
      newSummaries.init = 'Modules initialized.';
    }

    // Browser
    if (text.includes('browser ready') || text.includes('browser launched')) {
      newStatuses.init = 'done';
      newStatuses.browser = 'done';
      newMessages.browser = 'Ready';
      newSummaries.browser = 'Chromium launched.';
    }

    // Session
    if (text.includes('already logged in') || text.includes('linkedin connected')) {
      newStatuses.browser = 'done';
      newStatuses.session = 'done';
      newMessages.session = 'Connected ✓';
      newSummaries.session = 'Session valid.';
    } else if (text.includes('session expired') || text.includes('not logged in')) {
      newStatuses.session = 'error';
      newMessages.session = 'Expired';
      newSummaries.session = 'Session invalid. Need fresh login.';
    } else if (text.includes('checking linkedin')) {
      newStatuses.session = 'active';
      newMessages.session = 'Checking...';
    }

    // Recommended
    if (text.includes('recommended →') || text.includes('recommended jobs')) {
      newStatuses.session = 'done';
      newStatuses.recommended = 'done';
      const match = rawText.match(/Recommended → (\d+)/i);
      newMessages.recommended = match ? `${match[1]} jobs` : 'Done';
      newSummaries.recommended = match ? `Found ${match[1]} recommended jobs.` : '';
    } else if (text.includes('checking recommended')) {
      newStatuses.recommended = 'active';
      newMessages.recommended = 'Scanning...';
    }

    // Keywords
    const keywordMatches = rawText.match(/'[^']+' → \d+ new jobs/g);
    if (keywordMatches) {
      newStatuses.recommended = 'done';
      newStatuses.keywords = 'done';
      newMessages.keywords = `${keywordMatches.length} searches`;
      newSummaries.keywords = keywordMatches.join('\n');
    } else if (text.includes('searching by keywords')) {
      newStatuses.keywords = 'active';
      newMessages.keywords = 'Searching...';
    }

    // Custom URLs
    if (text.includes('custom url →') || text.includes('custom url(s)')) {
      newStatuses.keywords = 'done';
      newStatuses.custom = 'done';
      const match = rawText.match(/Custom URL → (\d+)/i);
      newMessages.custom = match ? `${match[1]} extra jobs` : 'Done';
    } else if (text.includes('scanning') && text.includes('custom')) {
      newStatuses.custom = 'active';
      newMessages.custom = 'Scanning...';
    } else if (newStatuses.keywords === 'done' && !text.includes('custom')) {
      newStatuses.custom = 'skipped';
      newMessages.custom = 'None configured';
    }

    // Evaluate
    const scanMatches = text.match(/scanning \d+\/\d+/g);
    if (scanMatches) {
      newStatuses.custom = newStatuses.custom || 'done';
      newStatuses.evaluate = 'active';
      newMessages.evaluate = scanMatches[scanMatches.length - 1].replace('scanning ', '');
      newStats.processed = scanMatches.length;
    }
    if (text.includes('unique jobs to evaluate')) {
      const match = rawText.match(/Found (\d+) unique/i);
      if (match) newSummaries.evaluate = `${match[1]} jobs to check.`;
    }

    // Apply
    const applyMatches = text.match(/(worth applying|applied successfully)/g);
    if (applyMatches) {
      newStatuses.apply = 'done';
      newStats.applied = applyMatches.length;
      newMessages.apply = `${newStats.applied} applied`;
    }

    // Notify
    if (text.includes('notification sent') || text.includes('tally report')) {
      newStatuses.notify = 'done';
      newMessages.notify = 'Sent';
    }

    // Complete
    if (text.includes('summary:') || text.includes('scan cycle complete')) {
      newStatuses.evaluate = 'done';
      newStatuses.apply = newStatuses.apply || 'done';
      newStatuses.notify = 'done';
      newStatuses.complete = 'done';
      newMessages.complete = 'Done';
      newSummaries.complete = 'Cycle complete.';
    }

    // Errors
    if (text.includes('scan cycle error') || text.includes('scan cycle failed')) {
      const errLine = lines.find(l => l.toLowerCase().includes('error') || l.toLowerCase().includes('failed')) || '';
      // Find which step failed
      if (!newStatuses.session || newStatuses.session === 'active') {
        newStatuses.session = 'error';
        newSummaries.session = errLine.slice(0, 80);
      } else if (!newStatuses.recommended || newStatuses.recommended === 'active') {
        newStatuses.recommended = 'error';
      } else if (!newStatuses.keywords || newStatuses.keywords === 'active') {
        newStatuses.keywords = 'error';
      } else {
        newStatuses.evaluate = 'error';
        newSummaries.evaluate = errLine.slice(0, 80);
      }
    }

    // Idle state
    if (Object.keys(newStatuses).length === 0 && status.state === 'running') {
      newStatuses.init = 'active';
      newMessages.init = 'Starting...';
    }

    setStepStatuses(newStatuses);
    setStepMessages(newMessages);
    setStepSummaries(newSummaries);
    setStats(newStats);
  };

  // Build summary text for clipboard
  const summaryText = useMemo(() => {
    const lines = ['═══ ApplyPilot Run Summary ═══', ''];
    PIPELINE_STEPS.forEach(step => {
      const s = stepStatuses[step.id];
      if (!s || s === 'idle') return;
      const icon = s === 'done' ? '✅' : s === 'error' ? '❌' : s === 'active' ? '🔄' : '⏭️';
      lines.push(`${icon} ${step.label}: ${stepMessages[step.id] || s}`);
      if (stepSummaries[step.id]) {
        stepSummaries[step.id].split('\n').forEach(l => lines.push(`   ${l}`));
      }
    });
    if (stats.processed > 0) {
      lines.push('', '── Results ──');
      lines.push(`   Processed: ${stats.processed}`);
      lines.push(`   Applied:   ${stats.applied}`);
      lines.push(`   Skipped:   ${stats.skipped}`);
    }
    return lines.join('\n');
  }, [stepStatuses, stepMessages, stepSummaries, stats]);

  const handleCopy = () => {
    navigator.clipboard.writeText(summaryText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyFullLogs = () => {
    const fullReport = [
      summaryText,
      '',
      '═══ Full Agent Output ═══',
      '',
      ...rawOutput,
    ].join('\n');
    navigator.clipboard.writeText(fullReport);
    setCopiedLogs(true);
    setTimeout(() => setCopiedLogs(false), 2000);
  };

  const isRunning = status.state === 'running';
  const hasData = Object.keys(stepStatuses).length > 0;

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-3 shadow-sm">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : hasData ? 'bg-slate-400' : 'bg-slate-300'}`} />
            <span className="text-sm font-medium text-slate-600">
              {isRunning ? 'Pipeline Active' : hasData ? 'Last Run' : 'Pipeline Idle'}
            </span>
          </div>
          {hasData && (
            <>
              <Stat label="Processed" value={stats.processed} />
              <Stat label="Applied" value={stats.applied} color="text-emerald-600" />
              <Stat label="Skipped" value={stats.skipped} color="text-amber-600" />
            </>
          )}
        </div>
        {hasData && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50 transition-colors"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied!' : 'Copy Summary'}
            </button>
            <button
              onClick={handleCopyFullLogs}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50 transition-colors"
            >
              {copiedLogs ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copiedLogs ? 'Copied!' : 'Copy Full Logs'}
            </button>
          </div>
        )}
      </div>

      {/* React Flow */}
      <div className="h-[520px] rounded-2xl border border-slate-200 bg-[#fafbfc] overflow-hidden shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={true}
          nodesConnectable={false}
          elementsSelectable={true}
          panOnDrag={true}
          zoomOnScroll={true}
          minZoom={0.4}
          maxZoom={2}
        >
          <Background color="#e2e8f0" gap={20} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {/* Tooltip hint */}
      <p className="text-center text-[11px] text-slate-400">
        Hover over any step to see details · Click "Copy Summary" for a full report
      </p>
    </div>
  );
}

function Stat({ label, value, color = 'text-slate-700' }) {
  return (
    <div className="text-xs text-slate-500">
      {label}: <span className={`font-bold ${color}`}>{value}</span>
    </div>
  );
}
