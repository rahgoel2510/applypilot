import { useState, useEffect, useRef } from 'react';
import { getAgentStatus, getAgentOutput } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';

/**
 * Agent Pipeline View — Super-detailed live activity feed
 * Shows every action in real-time with WebSocket events,
 * progress tracking, and per-job status cards
 */

// ─── Event type config ──────────────────────────────────────────────────────

const EVENT_CONFIG = {
  discovered: { icon: '🔍', label: 'Discovered', color: '#6366f1', bg: '#eef2ff' },
  submitted: { icon: '✅', label: 'Applied', color: '#10b981', bg: '#ecfdf5' },
  skipped: { icon: '⏭️', label: 'Skipped', color: '#f59e0b', bg: '#fffbeb' },
  paused: { icon: '⏸️', label: 'Paused', color: '#8b5cf6', bg: '#f5f3ff' },
  external: { icon: '🔗', label: 'External', color: '#0891b2', bg: '#ecfeff' },
  error: { icon: '❌', label: 'Error', color: '#ef4444', bg: '#fef2f2' },
  info: { icon: 'ℹ️', label: 'Info', color: '#6b7280', bg: '#f9fafb' },
  started: { icon: '🚀', label: 'Started', color: '#7c3aed', bg: '#f5f3ff' },
  browser_ready: { icon: '🌐', label: 'Browser', color: '#3b82f6', bg: '#eff6ff' },
  connected: { icon: '🔗', label: 'Connected', color: '#10b981', bg: '#ecfdf5' },
  scanning: { icon: '📡', label: 'Scanning', color: '#3b82f6', bg: '#eff6ff' },
  evaluating: { icon: '🎯', label: 'Evaluating', color: '#06b6d4', bg: '#ecfeff' },
  applying: { icon: '📝', label: 'Applying', color: '#10b981', bg: '#ecfdf5' },
  completed: { icon: '🏁', label: 'Complete', color: '#059669', bg: '#ecfdf5' },
  failed: { icon: '💥', label: 'Failed', color: '#ef4444', bg: '#fef2f2' },
};

const PIPELINE_STAGES = [
  { id: 'startup', icon: '🚀', label: 'Initialize', color: '#7c3aed' },
  { id: 'discover', icon: '🔍', label: 'Discover', color: '#3b82f6' },
  { id: 'evaluate', icon: '🎯', label: 'Evaluate', color: '#06b6d4' },
  { id: 'apply', icon: '📝', label: 'Apply', color: '#10b981' },
  { id: 'finish', icon: '🏁', label: 'Finish', color: '#f59e0b' },
];

export default function AgentPipelineView() {
  const { events, isConnected, agentStatus, liveStats } = useWebSocket();
  const [status, setStatus] = useState({ state: 'idle' });
  const [outputLines, setOutputLines] = useState([]);
  const [currentStage, setCurrentStage] = useState(null);
  const [currentAction, setCurrentAction] = useState('');
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [liveJobs, setLiveJobs] = useState([]);
  const [stageStatuses, setStageStatuses] = useState({});
  const feedEndRef = useRef(null);

  // Poll for status + parse output for stages
  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getAgentStatus();
        setStatus(s);
        if (s.state === 'running' || s.state === 'error') {
          const outputData = await getAgentOutput(200);
          const lines = outputData.lines || [];
          setOutputLines(lines);
          parseStagesFromOutput(lines);
        }
      } catch (e) { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 2500);
    return () => clearInterval(interval);
  }, []);

  // Process WebSocket events into live job cards
  useEffect(() => {
    if (!events || events.length === 0) return;

    const recentEvents = events.slice(0, 50);
    const jobMap = {};

    recentEvents.forEach(ev => {
      const data = ev.data || {};
      const eventType = ev.event_type || data.event_type || '';
      const key = `${data.title || ''}::${data.company || ''}`;

      if (!key || key === '::') return;

      if (!jobMap[key]) {
        jobMap[key] = {
          title: data.title || 'Unknown',
          company: data.company || 'Unknown',
          location: data.location || '',
          score: data.match_score,
          status: eventType,
          message: data.message || '',
          timestamp: ev.timestamp,
          events: [],
        };
      }
      jobMap[key].events.push({ type: eventType, message: data.message, timestamp: ev.timestamp });
      jobMap[key].status = eventType;
      if (data.match_score != null) jobMap[key].score = data.match_score;
    });

    setLiveJobs(Object.values(jobMap).slice(0, 20));

    // Update progress from metadata
    const latestWithProgress = recentEvents.find(ev => ev.data?.metadata?.progress);
    if (latestWithProgress) {
      setProgress({
        current: latestWithProgress.data.metadata.progress || 0,
        total: latestWithProgress.data.metadata.total || 0,
      });
    }
  }, [events]);

  // Auto-scroll
  useEffect(() => {
    if (feedEndRef.current) {
      feedEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [events, liveJobs]);

  const parseStagesFromOutput = (lines) => {
    const text = lines.join('\n').toLowerCase();
    const stages = {};
    let action = '';
    let stage = null;

    if (text.includes('pipeline started') || text.includes('launching browser')) {
      stages.startup = 'active'; action = 'Launching browser...'; stage = 'startup';
    }
    if (text.includes('browser ready')) {
      stages.startup = 'active'; action = 'Browser ready, checking session...'; stage = 'startup';
    }
    if (text.includes('linkedin connected')) {
      stages.startup = 'done'; action = 'LinkedIn connected ✓'; stage = 'discover';
    }
    if (text.includes('searching by keywords') || text.includes('checking recommended')) {
      stages.startup = 'done'; stages.discover = 'active';
      action = 'Scanning LinkedIn for jobs...'; stage = 'discover';
    }
    if (text.includes('unique jobs to evaluate')) {
      stages.startup = 'done'; stages.discover = 'done'; stages.evaluate = 'active';
      const m = text.match(/found (\d+) unique/);
      action = m ? `Evaluating ${m[1]} jobs...` : 'Evaluating jobs...';
      stage = 'evaluate';
    }
    if (text.match(/scanning \d+\/\d+/)) {
      stages.startup = 'done'; stages.discover = 'done'; stages.evaluate = 'active';
      const m = text.match(/scanning (\d+)\/(\d+)/g);
      if (m) {
        const last = m[m.length - 1].match(/scanning (\d+)\/(\d+)/);
        action = `Evaluating job ${last[1]} of ${last[2]}...`;
        setProgress({ current: parseInt(last[1]), total: parseInt(last[2]) });
      }
      stage = 'evaluate';
    }
    if (text.includes('worth applying') || text.includes('submitting')) {
      stages.startup = 'done'; stages.discover = 'done'; stages.evaluate = 'done';
      stages.apply = 'active'; action = 'Submitting applications...'; stage = 'apply';
    }
    if (text.includes('applied successfully') || text.includes('dry run')) {
      stages.apply = 'done';
    }
    if (text.includes('scan cycle complete') || text.includes('summary:')) {
      stages.startup = 'done'; stages.discover = 'done'; stages.evaluate = 'done';
      stages.apply = 'done'; stages.finish = 'done';
      action = 'Run complete!'; stage = 'finish';
    }
    if (text.includes('error') && text.includes('failed')) {
      stages.finish = 'error'; action = 'Error occurred — check logs';
    }

    setStageStatuses(stages);
    setCurrentAction(action);
    setCurrentStage(stage);
  };

  const isRunning = status.state === 'running';
  const isIdle = status.state === 'idle' && !isRunning;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Connection + Status Header */}
      <ConnectionHeader isConnected={isConnected} isRunning={isRunning} agentStatus={agentStatus} />

      {/* Stage Progress Bar */}
      <StageProgressBar stages={PIPELINE_STAGES} stageStatuses={stageStatuses} currentStage={currentStage} isRunning={isRunning} />

      {/* Current Action Banner */}
      {isRunning && currentAction && (
        <CurrentActionBanner action={currentAction} progress={progress} />
      )}

      {/* Live Stats Bar */}
      {liveStats && isRunning && <LiveStatsBar stats={liveStats} />}

      {/* Main Content: Split — Feed Left, Screenshot Right */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', gap: 12, padding: '12px 0' }}>
        {/* Left: Live Feed */}
        <div style={{ flex: 1, overflow: 'auto', minWidth: 0 }}>
          {isIdle && events.length === 0 ? (
            <IdleState />
          ) : (
            <LiveActivityFeed events={events} liveJobs={liveJobs} isRunning={isRunning} feedEndRef={feedEndRef} />
          )}
        </div>

        {/* Right: Live Screenshot Panel */}
        <LiveScreenshotPanel events={events} />
      </div>

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }
        @keyframes slideIn { from { opacity:0; transform:translateY(-8px) } to { opacity:1; transform:translateY(0) } }
        @keyframes shimmer { 0% { background-position: -200% 0 } 100% { background-position: 200% 0 } }
        @keyframes bounce { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-3px) } }
      `}</style>
    </div>
  );
}

// ─── Connection Header ──────────────────────────────────────────────────────

function ConnectionHeader({ isConnected, isRunning, agentStatus }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 16px', marginBottom: 12,
      borderRadius: 12, border: '1px solid',
      borderColor: isRunning ? '#a7f3d0' : '#e5e7eb',
      background: isRunning ? '#ecfdf5' : '#f9fafb',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: isConnected ? '#10b981' : '#ef4444',
          boxShadow: isConnected ? '0 0 6px #10b981' : '0 0 6px #ef4444',
          animation: isRunning ? 'pulse 1.5s infinite' : 'none',
        }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: isRunning ? '#059669' : '#6b7280' }}>
          {isRunning ? '● LIVE — Agent Running' : isConnected ? '● Connected — Waiting' : '○ Disconnected'}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 6,
          background: isConnected ? '#d1fae5' : '#fee2e2',
          color: isConnected ? '#065f46' : '#991b1b',
        }}>
          WS {isConnected ? 'LIVE' : 'OFF'}
        </span>
      </div>
    </div>
  );
}

// ─── Stage Progress Bar ─────────────────────────────────────────────────────

function StageProgressBar({ stages, stageStatuses, currentStage, isRunning }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0, marginBottom: 12,
      padding: '14px 16px', borderRadius: 12, background: '#f8fafc',
      border: '1px solid #e2e8f0',
    }}>
      {stages.map((stage, idx) => {
        const status = stageStatuses[stage.id];
        const isActive = status === 'active' || currentStage === stage.id;
        const isDone = status === 'done';
        const isError = status === 'error';
        const isPending = !status && !isDone;

        return (
          <div key={stage.id} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
            {/* Stage Node */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16,
                background: isDone ? '#10b981' : isActive ? stage.color : isError ? '#ef4444' : '#e5e7eb',
                color: (isDone || isActive || isError) ? '#fff' : '#9ca3af',
                boxShadow: isActive ? `0 0 12px ${stage.color}50` : 'none',
                animation: isActive && isRunning ? 'bounce 1s infinite' : 'none',
                transition: 'all 0.3s ease',
                border: isActive ? `3px solid ${stage.color}` : 'none',
              }}>
                {isDone ? '✓' : stage.icon}
              </div>
              <span style={{
                fontSize: 10, fontWeight: 700, marginTop: 4,
                color: isDone ? '#059669' : isActive ? stage.color : '#9ca3af',
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>
                {stage.label}
              </span>
            </div>
            {/* Connector Line */}
            {idx < stages.length - 1 && (
              <div style={{
                height: 3, flex: '0 0 20px', borderRadius: 2,
                background: isDone ? '#10b981' : isActive ? `linear-gradient(90deg, ${stage.color}, #e5e7eb)` : '#e5e7eb',
                transition: 'background 0.5s',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Current Action Banner ──────────────────────────────────────────────────

function CurrentActionBanner({ action, progress }) {
  const hasProgress = progress.total > 0;
  const pct = hasProgress ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <div style={{
      padding: '12px 16px', marginBottom: 12, borderRadius: 12,
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: '#fff', animation: 'slideIn 0.3s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: hasProgress ? 8 : 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 18, animation: 'bounce 1.5s infinite' }}>⚡</span>
          <span style={{ fontSize: 14, fontWeight: 700 }}>{action}</span>
        </div>
        {hasProgress && (
          <span style={{ fontSize: 13, fontWeight: 700, opacity: 0.9 }}>
            {progress.current}/{progress.total} ({pct}%)
          </span>
        )}
      </div>
      {hasProgress && (
        <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.2)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 3,
            background: 'rgba(255,255,255,0.9)',
            width: `${pct}%`,
            transition: 'width 0.5s ease',
          }} />
        </div>
      )}
    </div>
  );
}

// ─── Live Stats Bar ─────────────────────────────────────────────────────────

function LiveStatsBar({ stats }) {
  const items = [
    { label: 'Scanned', value: stats.total_jobs || stats.jobs_scanned || 0, color: '#6366f1' },
    { label: 'Applied', value: stats.applied || stats.jobs_applied || 0, color: '#10b981' },
    { label: 'Skipped', value: stats.skipped || stats.jobs_skipped || 0, color: '#f59e0b' },
    { label: 'Errors', value: stats.errors || 0, color: '#ef4444' },
  ];

  return (
    <div style={{
      display: 'flex', gap: 12, marginBottom: 12, padding: '10px 16px',
      borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0',
    }}>
      {items.map(item => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
          <div style={{ width: 4, height: 24, borderRadius: 2, background: item.color }} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: item.color, lineHeight: 1 }}>{item.value}</div>
            <div style={{ fontSize: 10, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase' }}>{item.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Idle State ─────────────────────────────────────────────────────────────

function IdleState() {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
      <h3 style={{ fontSize: 18, fontWeight: 700, color: '#1e1b4b', margin: '0 0 8px 0' }}>
        Your Agent is Ready
      </h3>
      <p style={{ fontSize: 14, color: '#6b7280', margin: '0 0 16px 0', maxWidth: 400, marginLeft: 'auto', marginRight: 'auto' }}>
        Click <strong>Start</strong> above to begin scanning LinkedIn for jobs that match your profile. Every action will appear here in real-time.
      </p>
      <div style={{
        display: 'inline-flex', gap: 8, padding: '8px 16px',
        borderRadius: 8, background: '#f0fdf4', border: '1px solid #bbf7d0',
        fontSize: 13, color: '#059669', fontWeight: 600,
      }}>
        <span>💡</span> Tip: Start with Dry Run ON to preview without applying
      </div>
    </div>
  );
}

// ─── Live Activity Feed ─────────────────────────────────────────────────────

function LiveActivityFeed({ events, liveJobs, isRunning, feedEndRef }) {
  return (
    <div style={{ padding: '0 4px' }}>
      {/* Live Job Cards (top section) */}
      {liveJobs.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8, paddingLeft: 4 }}>
            Jobs This Run ({liveJobs.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {liveJobs.map((job, idx) => (
              <LiveJobCard key={`${job.title}-${job.company}-${idx}`} job={job} />
            ))}
          </div>
        </div>
      )}

      {/* Event Stream */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8, paddingLeft: 4 }}>
          {isRunning ? '🔴 Live Event Stream' : 'Recent Events'}
        </div>
        {events.length === 0 ? (
          <div style={{ padding: '20px 16px', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
            {isRunning ? 'Waiting for first event...' : 'No events yet. Start the agent to see live activity.'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {events.slice(0, 50).map((ev, idx) => (
              <EventRow key={`${ev.timestamp}-${idx}`} event={ev} isNew={idx === 0 && isRunning} />
            ))}
          </div>
        )}
      </div>
      <div ref={feedEndRef} />
    </div>
  );
}

// ─── Live Job Card ──────────────────────────────────────────────────────────

function LiveJobCard({ job }) {
  const config = EVENT_CONFIG[job.status] || EVENT_CONFIG.info;
  const scorePercent = job.score != null ? Math.round(job.score * 100) : null;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '10px 14px', borderRadius: 10,
      background: config.bg, border: `1px solid ${config.color}25`,
      animation: 'slideIn 0.3s ease',
      transition: 'all 0.2s',
    }}>
      {/* Status Icon */}
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: `${config.color}15`, fontSize: 16, flexShrink: 0,
      }}>
        {config.icon}
      </div>

      {/* Job Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#1e1b4b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {job.title}
        </div>
        <div style={{ fontSize: 12, color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {job.company}{job.location ? ` · ${job.location}` : ''}
        </div>
      </div>

      {/* Score Badge */}
      {scorePercent !== null && (
        <div style={{
          padding: '3px 8px', borderRadius: 6, fontSize: 12, fontWeight: 800,
          fontFamily: 'monospace',
          background: scorePercent >= 80 ? '#d1fae5' : scorePercent >= 60 ? '#fef3c7' : '#fee2e2',
          color: scorePercent >= 80 ? '#065f46' : scorePercent >= 60 ? '#92400e' : '#991b1b',
        }}>
          {scorePercent}%
        </div>
      )}

      {/* Status Chip */}
      <div style={{
        padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
        background: `${config.color}15`, color: config.color,
        textTransform: 'uppercase', letterSpacing: '0.03em', flexShrink: 0,
      }}>
        {config.label}
      </div>
    </div>
  );
}

// ─── Event Row ──────────────────────────────────────────────────────────────

function EventRow({ event, isNew }) {
  const data = event.data || {};
  const eventType = event.event_type || data.event_type || 'info';
  const config = EVENT_CONFIG[eventType] || EVENT_CONFIG.info;
  const timestamp = event.timestamp ? new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';

  // Build description
  let desc = data.message || '';
  if (!desc) {
    if (data.title && data.company) {
      desc = `${data.title} @ ${data.company}`;
      if (data.match_score != null) desc += ` (${Math.round(data.match_score * 100)}%)`;
    } else if (eventType === 'info' && data.metadata?.progress) {
      desc = `Processing job ${data.metadata.progress}/${data.metadata.total}`;
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '6px 10px', borderRadius: 8,
      background: isNew ? config.bg : 'transparent',
      animation: isNew ? 'slideIn 0.3s ease' : 'none',
      borderLeft: `3px solid ${config.color}`,
      transition: 'background 0.5s',
    }}>
      {/* Timestamp */}
      <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#9ca3af', minWidth: 60, flexShrink: 0 }}>
        {timestamp}
      </span>

      {/* Icon */}
      <span style={{ fontSize: 14, flexShrink: 0 }}>{config.icon}</span>

      {/* Description */}
      <span style={{ fontSize: 13, color: '#374151', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {desc || `${config.label} event`}
      </span>

      {/* Score if present */}
      {data.match_score != null && (
        <span style={{
          fontSize: 11, fontWeight: 700, fontFamily: 'monospace',
          padding: '2px 6px', borderRadius: 4,
          background: data.match_score >= 0.8 ? '#d1fae5' : '#fef3c7',
          color: data.match_score >= 0.8 ? '#065f46' : '#92400e',
        }}>
          {Math.round(data.match_score * 100)}%
        </span>
      )}
    </div>
  );
}

// ─── Live Screenshot Panel ──────────────────────────────────────────────────

function LiveScreenshotPanel({ events }) {
  const [screenshot, setScreenshot] = useState(null);
  const [lastTs, setLastTs] = useState(null);
  const [loading, setLoading] = useState(false);

  // Poll for latest screenshot
  useEffect(() => {
    const fetchScreenshot = async () => {
      try {
        const res = await fetch('/api/agent/screenshot');
        if (res.ok) {
          const data = await res.json();
          if (data.image && data.timestamp !== lastTs) {
            setScreenshot(data.image);
            setLastTs(data.timestamp);
          }
        }
      } catch (e) { /* ignore */ }
    };
    fetchScreenshot();
    const iv = setInterval(fetchScreenshot, 2000);
    return () => clearInterval(iv);
  }, [lastTs]);

  // Also refresh when we get a screenshot event via WebSocket
  useEffect(() => {
    const screenshotEvent = events.find(e => e.event_type === 'screenshot');
    if (screenshotEvent) {
      fetch('/api/agent/screenshot')
        .then(r => r.json())
        .then(data => {
          if (data.image) {
            setScreenshot(data.image);
            setLastTs(data.timestamp);
          }
        })
        .catch(() => {});
    }
  }, [events]);

  return (
    <div style={{
      width: 420, minWidth: 320, display: 'flex', flexDirection: 'column',
      borderRadius: 12, border: '1px solid #e2e8f0', background: '#f8fafc',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid #e2e8f0',
        display: 'flex', alignItems: 'center', gap: 8,
        background: '#fff',
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: screenshot ? '#10b981' : '#9ca3af',
          boxShadow: screenshot ? '0 0 6px #10b981' : 'none',
          animation: screenshot ? 'pulse 2s infinite' : 'none',
        }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#374151', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          📸 Live Browser View
        </span>
        {lastTs && (
          <span style={{ fontSize: 10, color: '#9ca3af', marginLeft: 'auto' }}>
            {new Date(lastTs * 1000).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Screenshot Display */}
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 8, overflow: 'hidden', minHeight: 200,
      }}>
        {screenshot ? (
          <img
            src={screenshot}
            alt="Pipeline screenshot"
            style={{
              width: '100%', height: '100%', objectFit: 'contain',
              borderRadius: 8, border: '1px solid #e2e8f0',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          />
        ) : (
          <div style={{ textAlign: 'center', color: '#9ca3af', padding: 24 }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>🖥️</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>No screenshot yet</div>
            <div style={{ fontSize: 11, marginTop: 4 }}>
              Run the pipeline debugger to see<br/>live browser captures here
            </div>
            <div style={{ fontSize: 10, marginTop: 8, fontFamily: 'monospace', opacity: 0.7 }}>
              python3 debug_pipeline.py
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
