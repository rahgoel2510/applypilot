import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getAgentStatus, getAgentOutput } from '../api';

// --- Pipeline node definitions ---

const PIPELINE_STEPS = [
  { id: 'init', label: 'Initialize', emoji: '⚡', description: 'Load config & modules', x: 0, y: 0 },
  { id: 'browser', label: 'Launch Browser', emoji: '🌐', description: 'Start Chromium', x: 250, y: 0 },
  { id: 'login', label: 'LinkedIn Login', emoji: '🔐', description: 'Authenticate session', x: 500, y: 0 },
  { id: 'navigate', label: 'Navigate', emoji: '📋', description: 'Go to job collection', x: 750, y: 0 },
  { id: 'scan', label: 'Scan Jobs', emoji: '🔍', description: 'Read job listings', x: 1000, y: 0 },
  { id: 'process', label: 'Process Jobs', emoji: '⚙️', description: 'Score & decide', x: 600, y: 180 },
  { id: 'apply', label: 'Apply', emoji: '🎯', description: 'Submit Easy Apply', x: 350, y: 180 },
  { id: 'notify', label: 'Notify', emoji: '📱', description: 'Telegram + Tracker', x: 350, y: 360 },
  { id: 'inmail', label: 'InMail', emoji: '✉️', description: 'Draft to recruiter', x: 600, y: 360 },
  { id: 'complete', label: 'Cycle Complete', emoji: '🏁', description: 'Report tally', x: 1000, y: 180 },
];

const PIPELINE_EDGES = [
  { source: 'init', target: 'browser' },
  { source: 'browser', target: 'login' },
  { source: 'login', target: 'navigate' },
  { source: 'navigate', target: 'scan' },
  { source: 'scan', target: 'process' },
  { source: 'process', target: 'apply', label: '≥ threshold' },
  { source: 'process', target: 'complete', label: 'skip / done' },
  { source: 'apply', target: 'notify' },
  { source: 'apply', target: 'inmail' },
  { source: 'notify', target: 'process', label: 'next job' },
  { source: 'inmail', target: 'process', label: 'next job' },
];

// Step status: idle | active | done | error | skipped
const STEP_STYLES = {
  idle: { border: 'border-slate-200', bg: 'bg-white', ring: '', text: 'text-slate-400', glow: '' },
  active: { border: 'border-teal-400', bg: 'bg-teal-50', ring: 'ring-4 ring-teal-400/20', text: 'text-teal-700', glow: 'shadow-lg shadow-teal-500/20' },
  done: { border: 'border-emerald-300', bg: 'bg-emerald-50', ring: '', text: 'text-emerald-700', glow: '' },
  error: { border: 'border-red-300', bg: 'bg-red-50', ring: 'ring-4 ring-red-400/20', text: 'text-red-700', glow: 'shadow-lg shadow-red-500/20' },
  skipped: { border: 'border-slate-200', bg: 'bg-slate-50', ring: '', text: 'text-slate-400', glow: '' },
};

// --- Custom Node ---

function PipelineNode({ data }) {
  const style = STEP_STYLES[data.status] || STEP_STYLES.idle;
  const isActive = data.status === 'active';

  return (
    <div className={`relative rounded-2xl border-2 ${style.border} ${style.bg} ${style.ring} ${style.glow} px-5 py-4 min-w-[160px] transition-all duration-500`}>
      <Handle type="target" position={Position.Left} className="!bg-slate-300 !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-slate-300 !w-2 !h-2" />

      {/* Active pulse */}
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

      {/* Status indicator */}
      {data.status === 'done' && (
        <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-bold text-white">
          ✓ DONE
        </div>
      )}
      {data.status === 'error' && (
        <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 rounded-full bg-red-500 px-2 py-0.5 text-[9px] font-bold text-white">
          ✗ ERROR
        </div>
      )}

      {/* Live message */}
      {data.message && isActive && (
        <div className="mt-2 rounded-lg bg-white/80 px-2 py-1 text-[10px] text-teal-600 font-medium border border-teal-200">
          {data.message}
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
  const [status, setStatus] = useState({ state: 'idle' });
  const [jobsProcessed, setJobsProcessed] = useState(0);
  const [jobsApplied, setJobsApplied] = useState(0);

  // Build nodes from steps + statuses
  const nodes = useMemo(() =>
    PIPELINE_STEPS.map(step => ({
      id: step.id,
      type: 'pipeline',
      position: { x: step.x, y: step.y },
      data: {
        ...step,
        status: stepStatuses[step.id] || 'idle',
        message: stepMessages[step.id] || '',
      },
    })),
    [stepStatuses, stepMessages]
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
        stroke: (stepStatuses[edge.source] === 'done' || stepStatuses[edge.source] === 'active') ? '#14b8a6' : '#cbd5e1',
        strokeWidth: stepStatuses[edge.source] === 'active' ? 2.5 : 1.5,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: stepStatuses[edge.source] === 'active' ? '#14b8a6' : '#cbd5e1' },
      labelStyle: { fontSize: 10, fill: '#64748b' },
    })),
    [stepStatuses]
  );

  // Poll agent status and output
  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getAgentStatus();
        setStatus(s);

        if (s.state === 'running' || s.state === 'error') {
          const outputData = await getAgentOutput(100);
          parseOutputToSteps(outputData.lines);
        } else if (s.state === 'idle') {
          // Reset after completion
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
    let processed = 0;
    let applied = 0;

    const text = lines.join('\n').toLowerCase();

    // Determine which steps are done/active based on output
    if (text.includes('running single scan') || text.includes('starting daemon')) {
      newStatuses.init = 'done';
    }
    if (text.includes('browser launched')) {
      newStatuses.init = 'done';
      newStatuses.browser = 'done';
    }
    if (text.includes('already logged in') || text.includes('login successful')) {
      newStatuses.init = 'done';
      newStatuses.browser = 'done';
      newStatuses.login = 'done';
      newMessages.login = 'Session active';
    } else if (text.includes('not logged in') || text.includes('proceeding with login')) {
      newStatuses.init = 'done';
      newStatuses.browser = 'done';
      newStatuses.login = 'active';
      newMessages.login = 'Entering credentials...';
    }
    if (text.includes('login') && (text.includes('challenge') || text.includes('timeout'))) {
      newStatuses.login = 'error';
      newMessages.login = 'Needs manual login';
    }
    if (text.includes('navigated to jobs')) {
      newStatuses.login = 'done';
      newStatuses.navigate = 'done';
    }
    if (text.includes('found') && text.includes('job')) {
      newStatuses.navigate = 'done';
      newStatuses.scan = 'done';
      const match = text.match(/found (\d+) job/);
      if (match) newMessages.scan = `${match[1]} jobs found`;
    }
    if (text.includes('processing:') || text.includes('looking at')) {
      newStatuses.scan = 'done';
      newStatuses.process = 'active';
      // Count processed
      const processMatches = text.match(/processing:/gi);
      if (processMatches) processed = processMatches.length;
      newMessages.process = `${processed} job(s) evaluated`;
    }
    if (text.includes('submitted') || text.includes('would apply')) {
      newStatuses.apply = 'active';
      const submitMatches = text.match(/(submitted|would apply)/gi);
      if (submitMatches) applied = submitMatches.length;
      newMessages.apply = `${applied} application(s)`;
    }
    if (text.includes('notification sent') || text.includes('telegram')) {
      newStatuses.notify = 'done';
      newMessages.notify = 'Updates sent';
    }
    if (text.includes('inmail') || text.includes('drafted')) {
      newStatuses.inmail = 'done';
      newMessages.inmail = 'Message drafted';
    }
    if (text.includes('scan cycle complete') || text.includes('cycle complete')) {
      newStatuses.process = 'done';
      newStatuses.apply = 'done';
      newStatuses.complete = 'done';
      newMessages.complete = 'All done!';
    }
    if (text.includes('error') || text.includes('traceback')) {
      // Find which step errored
      if (!newStatuses.browser || newStatuses.browser !== 'done') {
        newStatuses.browser = 'error';
      } else if (newStatuses.login === 'active') {
        newStatuses.login = 'error';
      }
    }

    // If agent is running but nothing parsed yet, show init as active
    if (Object.keys(newStatuses).length === 0 && status.state === 'running') {
      newStatuses.init = 'active';
      newMessages.init = 'Loading modules...';
    }

    setStepStatuses(newStatuses);
    setStepMessages(newMessages);
    setJobsProcessed(processed);
    setJobsApplied(applied);
  };

  const isRunning = status.state === 'running';

  return (
    <div className="space-y-4">
      {/* Pipeline stats bar */}
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-3">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
            <span className="text-sm font-medium text-slate-600">
              {isRunning ? 'Pipeline Active' : 'Pipeline Idle'}
            </span>
          </div>
          {isRunning && (
            <>
              <div className="text-xs text-slate-500">
                Processed: <span className="font-bold text-slate-700">{jobsProcessed}</span>
              </div>
              <div className="text-xs text-slate-500">
                Applied: <span className="font-bold text-emerald-600">{jobsApplied}</span>
              </div>
            </>
          )}
        </div>
        <div className="text-[11px] text-slate-400">
          {isRunning ? 'Edges animate to show data flow' : 'Start the agent to see the pipeline in action'}
        </div>
      </div>

      {/* React Flow canvas */}
      <div className="h-[480px] rounded-2xl border border-slate-200 bg-slate-50 overflow-hidden shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={true}
          zoomOnScroll={true}
          minZoom={0.5}
          maxZoom={1.5}
        >
          <Background color="#e2e8f0" gap={20} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
