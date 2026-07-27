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
  { id: 'init', label: 'Initialize', emoji: '⚡', description: 'Load config & connect services', x: 0, y: 80 },
  { id: 'browser', label: 'Open Browser', emoji: '🌐', description: 'Launch Chromium instance', x: 220, y: 80 },
  { id: 'session', label: 'Session Check', emoji: '🔐', description: 'Verify LinkedIn cookies', x: 440, y: 80 },
  { id: 'navigate', label: 'Job Collection', emoji: '📋', description: 'Navigate to LinkedIn jobs', x: 660, y: 80 },
  { id: 'scan', label: 'Scan Listings', emoji: '🔍', description: 'Extract job cards from page', x: 880, y: 80 },
  { id: 'match', label: 'Score & Match', emoji: '🎯', description: 'Evaluate fit against profile', x: 880, y: 260 },
  { id: 'apply', label: 'Easy Apply', emoji: '📝', description: 'Fill & submit application', x: 660, y: 260 },
  { id: 'notify', label: 'Telegram Alert', emoji: '📱', description: 'Notify + log to tracker', x: 440, y: 260 },
  { id: 'inmail', label: 'Draft InMail', emoji: '✉️', description: 'AI message to recruiter', x: 440, y: 400 },
  { id: 'complete', label: 'Report & Close', emoji: '🏁', description: 'Tally results + close browser', x: 220, y: 260 },
];

const PIPELINE_EDGES = [
  { source: 'init', target: 'browser' },
  { source: 'browser', target: 'session' },
  { source: 'session', target: 'navigate' },
  { source: 'navigate', target: 'scan' },
  { source: 'scan', target: 'match' },
  { source: 'match', target: 'apply', label: 'match ≥ 80%' },
  { source: 'match', target: 'complete', label: 'all processed' },
  { source: 'apply', target: 'notify' },
  { source: 'notify', target: 'inmail', label: 'if enabled' },
  { source: 'notify', target: 'match', label: 'next job' },
  { source: 'inmail', target: 'match', label: 'next job' },
  { source: 'complete', target: 'init', label: 'daemon loop', style: 'dashed' },
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
      className={`relative rounded-2xl border-2 ${style.border} ${style.bg} px-5 py-4 min-w-[170px] transition-all duration-500 ${
        isActive ? 'ring-4 ring-teal-400/20 shadow-lg shadow-teal-500/20' : ''
      } ${data.status === 'error' ? 'ring-4 ring-red-400/20 shadow-lg shadow-red-500/20' : ''}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-300 !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-slate-300 !w-2 !h-2" />

      {isActive && (
        <div className="absolute -top-1 -right-1 flex h-4 w-4">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75" />
          <span className="relative inline-flex h-4 w-4 rounded-full bg-teal-500" />
        </div>
      )}

      <div className="flex items-center gap-3">
        <span className="text-2xl">{data.emoji}</span>
        <div>
          <p className={`text-sm font-bold ${style.text}`}>{data.label}</p>
          <p className="text-[11px] text-slate-400">{data.description}</p>
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
    if (text.includes('running single scan') || text.includes('starting daemon') || text.includes('scan cycle started')) {
      newStatuses.init = 'done';
      newMessages.init = 'Config loaded';
      newSummaries.init = 'Modules initialized. Config validated. Tracker connected.';
    }

    // Browser
    if (text.includes('browser launched')) {
      newStatuses.browser = 'done';
      newMessages.browser = 'Chromium ready';
      newSummaries.browser = 'Persistent Chromium context launched.\nSession cookies loaded from saved profile.';
    } else if (text.includes('running single scan') && !text.includes('browser launched')) {
      newStatuses.browser = 'active';
      newMessages.browser = 'Starting...';
    }

    // Session check (replaces login step)
    if (text.includes('already logged in')) {
      newStatuses.browser = 'done';
      newStatuses.session = 'done';
      newMessages.session = 'Session valid ✓';
      newSummaries.session = 'LinkedIn session is active.\nCookies verified — no login needed.';
    }
    if (text.includes('session expired') || (text.includes('not logged in') && !text.includes('login successful'))) {
      newStatuses.session = 'active';
      newMessages.session = 'Verifying...';
      newSummaries.session = 'Checking saved session cookies against LinkedIn...';
    }
    if (text.includes('login successful') || text.includes('redirected through challenge')) {
      newStatuses.session = 'done';
      newMessages.session = 'Re-authenticated ✓';
      newSummaries.session = 'Session was expired. Successfully re-authenticated with saved credentials.';
    }
    if ((text.includes('session expired') && text.includes('no credentials')) || 
        (text.includes('login') && text.includes('timeout') && !text.includes('successful'))) {
      newStatuses.session = 'error';
      newMessages.session = 'Session invalid';
      newSummaries.session = 'Session expired and could not re-authenticate.\nFix: Copy a valid browser session into Docker.\nRun: ./copy-session-to-docker.sh';
    }

    // Navigate
    if (text.includes('navigated to jobs')) {
      newStatuses.navigate = 'done';
      newMessages.navigate = 'On jobs page';
      newSummaries.navigate = 'Successfully navigated to LinkedIn job collection.';
    }

    // Scan
    const foundMatch = text.match(/found (\d+) job/);
    if (foundMatch) {
      newStatuses.scan = 'done';
      newMessages.scan = `${foundMatch[1]} jobs found`;
      newSummaries.scan = `Extracted ${foundMatch[1]} job card(s) from the page.\nReady to evaluate against your profile.`;
    }

    // Match / Process
    const processMatches = text.match(/processing:/gi);
    if (processMatches) {
      newStats.processed = processMatches.length;
      newStatuses.match = 'active';
      newMessages.match = `${newStats.processed} evaluated`;
    }
    const submitMatches = text.match(/(submitted|would apply)/gi);
    if (submitMatches) newStats.applied = submitMatches.length;
    const skipMatches = text.match(/(skipping|would skip|below threshold)/gi);
    if (skipMatches) newStats.skipped = skipMatches.length;

    if (newStats.processed > 0) {
      newSummaries.match = `Processed: ${newStats.processed}\nMatched: ${newStats.applied}\nSkipped: ${newStats.skipped}`;
    }

    // Apply
    if (newStats.applied > 0) {
      newStatuses.apply = 'done';
      newMessages.apply = `${newStats.applied} applied`;
      newSummaries.apply = `${newStats.applied} application(s) submitted via Easy Apply.`;
    }

    // Notify
    if (text.includes('notification sent') || text.includes('telegram') || text.includes('tally')) {
      newStatuses.notify = 'done';
      newMessages.notify = 'Notified';
      newSummaries.notify = 'Telegram notifications sent.\nTracker board updated.';
    }

    // InMail
    if (text.includes('inmail') || text.includes('drafted')) {
      newStatuses.inmail = 'done';
      newMessages.inmail = 'Drafted';
      newSummaries.inmail = 'AI-generated InMail sent to Telegram for review.';
    }

    // Complete
    if (text.includes('scan cycle complete') || text.includes('cycle complete') || text.includes('shutdown complete')) {
      newStatuses.match = 'done';
      newStatuses.complete = 'done';
      newMessages.complete = 'Cycle done';
      newSummaries.complete = `Cycle complete.\nApplied: ${newStats.applied} | Skipped: ${newStats.skipped}\nBrowser closed. Tally reported.`;
    }

    // Error detection
    if (text.includes('scan cycle failed') || text.includes('traceback')) {
      // Find which step failed
      const errorLine = lines.find(l => l.toLowerCase().includes('error') || l.toLowerCase().includes('failed')) || '';
      if (!newStatuses.browser || newStatuses.browser === 'active') {
        newStatuses.browser = 'error';
        newMessages.browser = 'Failed';
        newSummaries.browser = `Error: ${errorLine.slice(0, 100)}`;
      } else if (!newStatuses.navigate) {
        newStatuses.navigate = 'error';
        newSummaries.navigate = `Error: ${errorLine.slice(0, 100)}`;
      } else {
        newStatuses.match = 'error';
        newMessages.match = 'Error';
        newSummaries.match = `Error: ${errorLine.slice(0, 100)}`;
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
      <div className="h-[480px] rounded-2xl border border-slate-200 bg-[#fafbfc] overflow-hidden shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={true}
          zoomOnScroll={true}
          minZoom={0.5}
          maxZoom={1.5}
        >
          <Background color="#e2e8f0" gap={24} size={1} />
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
