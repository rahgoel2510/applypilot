import { useState, useEffect } from 'react';
import { getAgentStatus, getAgentOutput } from '../api';

/**
 * Agent Pipeline View — Simple, large, readable flowchart
 * No React Flow — just CSS flexbox with big cards and clear arrows
 */

const STEPS = [
  {
    id: 'startup',
    group: 'Startup',
    icon: '🚀',
    title: 'Initialize & Connect',
    desc: 'Load config → Launch browser → Verify LinkedIn session',
    color: '#7c3aed',
  },
  {
    id: 'discover',
    group: 'Discovery',
    icon: '🔍',
    title: 'Find Jobs',
    desc: 'Scan recommended → Search keywords → Custom URLs',
    color: '#3b82f6',
  },
  {
    id: 'evaluate',
    group: 'Evaluate',
    icon: '🎯',
    title: 'Score & Filter',
    desc: 'Dedup check → External apply? → Get match score → Meets threshold?',
    color: '#06b6d4',
    decisions: ['Skip if duplicate', 'Skip if external', 'Skip if low score'],
  },
  {
    id: 'action',
    group: 'Action',
    icon: '📝',
    title: 'Apply & Outreach',
    desc: 'Draft InMail → Submit Easy Apply → Pause if human input needed',
    color: '#10b981',
    decisions: ['Pause for sensitive fields'],
  },
  {
    id: 'finish',
    group: 'Finish',
    icon: '🏁',
    title: 'Report & Notify',
    desc: 'Save to DB → Telegram alert → Sync dedup → Generate report',
    color: '#f59e0b',
  },
];

function StepCard({ step, status, message, isLast }) {
  const isActive = status === 'active';
  const isDone = status === 'done';
  const isError = status === 'error';

  const borderColor = isError ? '#f43f5e' : isActive ? step.color : isDone ? '#22c55e' : '#e2e8f0';
  const bgColor = isError ? '#fef2f2' : isActive ? `${step.color}08` : isDone ? '#f0fdf4' : '#ffffff';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {/* The card */}
      <div
        style={{
          width: '100%',
          maxWidth: 700,
          border: `3px solid ${borderColor}`,
          borderRadius: 20,
          padding: '24px 32px',
          background: bgColor,
          boxShadow: isActive
            ? `0 0 24px ${step.color}20, 0 4px 12px rgba(0,0,0,0.06)`
            : '0 2px 8px rgba(0,0,0,0.04)',
          transition: 'all 0.3s ease',
          position: 'relative',
        }}
      >
        {/* Active pulse */}
        {isActive && (
          <div style={{
            position: 'absolute', top: 12, right: 12,
            width: 14, height: 14, borderRadius: '50%',
            background: step.color,
            boxShadow: `0 0 10px ${step.color}`,
            animation: 'pulse 1.5s infinite',
          }} />
        )}

        {/* Done check */}
        {isDone && (
          <div style={{
            position: 'absolute', top: 12, right: 12,
            width: 28, height: 28, borderRadius: '50%',
            background: '#22c55e', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 16, fontWeight: 700,
          }}>✓</div>
        )}

        {/* Content */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20 }}>
          {/* Icon */}
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: `${step.color}15`,
            border: `2px solid ${step.color}30`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, flexShrink: 0,
          }}>
            {step.icon}
          </div>

          {/* Text */}
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{
                fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
                color: step.color, textTransform: 'uppercase',
                background: `${step.color}12`, padding: '2px 8px', borderRadius: 6,
              }}>
                {step.group}
              </span>
            </div>
            <h3 style={{ fontSize: 20, fontWeight: 700, color: '#1e1b4b', margin: '0 0 6px 0' }}>
              {step.title}
            </h3>
            <p style={{ fontSize: 15, color: '#64748b', margin: 0, lineHeight: 1.5 }}>
              {step.desc}
            </p>

            {/* Decision branches */}
            {step.decisions && (
              <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                {step.decisions.map((d, i) => (
                  <span key={i} style={{
                    fontSize: 13, fontWeight: 600, color: '#92400e',
                    background: '#fef3c7', border: '1px solid #fde68a',
                    padding: '4px 10px', borderRadius: 8,
                  }}>
                    ⚠️ {d}
                  </span>
                ))}
              </div>
            )}

            {/* Status message */}
            {message && (
              <div style={{
                marginTop: 10, padding: '8px 14px', borderRadius: 10,
                fontSize: 14, fontWeight: 600,
                background: isError ? '#fee2e2' : '#ecfdf5',
                color: isError ? '#dc2626' : '#059669',
                border: `1px solid ${isError ? '#fecaca' : '#a7f3d0'}`,
              }}>
                {message}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Arrow connector */}
      {!isLast && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '8px 0' }}>
          <div style={{ width: 3, height: 24, background: isDone ? '#22c55e' : '#e2e8f0', borderRadius: 2 }} />
          <div style={{
            width: 0, height: 0,
            borderLeft: '8px solid transparent', borderRight: '8px solid transparent',
            borderTop: `10px solid ${isDone ? '#22c55e' : '#e2e8f0'}`,
          }} />
        </div>
      )}
    </div>
  );
}

export default function AgentPipelineView() {
  const [stepStatuses, setStepStatuses] = useState({});
  const [stepMessages, setStepMessages] = useState({});
  const [status, setStatus] = useState({ state: 'idle' });

  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getAgentStatus();
        setStatus(s);
        if (s.state === 'running' || s.state === 'error') {
          const outputData = await getAgentOutput(200);
          parseOutput(outputData.lines || []);
        }
      } catch (e) { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  const parseOutput = (lines) => {
    const text = lines.join('\n').toLowerCase();
    const newStatus = {};
    const newMsg = {};

    // Startup
    if (text.includes('linkedin connected') || text.includes('already logged in')) {
      newStatus.startup = 'done'; newMsg.startup = 'Session verified ✓';
    } else if (text.includes('browser ready') || text.includes('browser launched')) {
      newStatus.startup = 'active'; newMsg.startup = 'Browser ready, checking session...';
    } else if (text.includes('pipeline started') || text.includes('running single scan')) {
      newStatus.startup = 'active'; newMsg.startup = 'Initializing...';
    }
    if (text.includes('session expired')) {
      newStatus.startup = 'error'; newMsg.startup = 'Session expired! Need fresh login.';
    }

    // Discovery
    if (text.includes('unique jobs to evaluate') || text.includes('keyword')) {
      newStatus.startup = 'done';
      newStatus.discover = 'done';
      const m = text.match(/found (\d+) unique/);
      newMsg.discover = m ? `Found ${m[1]} jobs to evaluate` : 'Jobs collected';
    } else if (text.includes('searching by keywords') || text.includes('checking recommended')) {
      newStatus.startup = 'done';
      newStatus.discover = 'active'; newMsg.discover = 'Scanning LinkedIn...';
    }

    // Evaluate
    if (text.includes('scanning') && text.match(/\d+\/\d+/)) {
      newStatus.discover = 'done';
      newStatus.evaluate = 'active';
      const m = text.match(/scanning (\d+\/\d+)/);
      newMsg.evaluate = m ? `Processing job ${m[1]}...` : 'Evaluating...';
    }
    if (text.includes('worth applying') || text.includes('applied')) {
      newStatus.evaluate = 'done'; newMsg.evaluate = 'Evaluation complete';
    }

    // Action
    if (text.includes('submitting') || text.includes('applied successfully')) {
      newStatus.evaluate = 'done';
      newStatus.action = 'done'; newMsg.action = 'Applications submitted';
    } else if (text.includes('worth applying')) {
      newStatus.action = 'active'; newMsg.action = 'Submitting applications...';
    }

    // Finish
    if (text.includes('summary:') || text.includes('scan cycle complete')) {
      newStatus.startup = 'done'; newStatus.discover = 'done';
      newStatus.evaluate = 'done'; newStatus.action = 'done';
      newStatus.finish = 'done'; newMsg.finish = 'Cycle complete!';
    } else if (text.includes('notification sent') || text.includes('tally report')) {
      newStatus.finish = 'active'; newMsg.finish = 'Sending notifications...';
    }

    // Error
    if (text.includes('scan cycle error') || text.includes('scan cycle failed')) {
      newStatus.finish = 'error'; newMsg.finish = 'Cycle failed — check logs';
    }

    if (Object.keys(newStatus).length === 0 && status.state === 'running') {
      newStatus.startup = 'active'; newMsg.startup = 'Starting...';
    }

    setStepStatuses(newStatus);
    setStepMessages(newMsg);
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: 780, margin: '0 auto', overflow: 'auto', height: '100%' }}>
      {/* Header */}
      <div style={{ marginBottom: 24, textAlign: 'center' }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1e1b4b', margin: '0 0 6px 0' }}>
          Agent Pipeline
        </h2>
        <p style={{ fontSize: 14, color: '#64748b', margin: 0 }}>
          Each scan follows these 5 stages sequentially
        </p>
      </div>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {STEPS.map((step, idx) => (
          <StepCard
            key={step.id}
            step={step}
            status={stepStatuses[step.id] || 'idle'}
            message={stepMessages[step.id] || ''}
            isLast={idx === STEPS.length - 1}
          />
        ))}
      </div>

      {/* CSS Animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.3); }
        }
      `}</style>
    </div>
  );
}
