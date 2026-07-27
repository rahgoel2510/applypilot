import { useState, useEffect, useRef } from 'react';
import {
  Play, Square, Bot, Settings, Terminal, AlertCircle,
  CheckCircle2, Loader2, Zap, Clock, Eye, EyeOff,
} from 'lucide-react';
import { triggerAgent, stopAgent, getAgentStatus, getAgentOutput } from '../api';

const STATE_COLORS = {
  idle: { bg: 'bg-slate-100', text: 'text-slate-600', dot: 'bg-slate-400' },
  running: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500 animate-pulse' },
  stopping: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500 animate-pulse' },
  error: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
};

export default function AgentControlPanel() {
  const [status, setStatus] = useState({ state: 'idle', pid: null, started_at: null, uptime_seconds: 0, config: {} });
  const [output, setOutput] = useState([]);
  const [showOutput, setShowOutput] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const outputRef = useRef(null);

  // Config form
  const [config, setConfig] = useState({
    mode: 'single',
    dryRun: true,
    limit: '10',
    matchThreshold: '80',
    collection: 'Recommended',
  });

  // Poll status every 2 seconds
  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getAgentStatus();
        setStatus(s);
      } catch (e) { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  // Poll output when running
  useEffect(() => {
    if (status.state !== 'running') return;
    const poll = async () => {
      try {
        const data = await getAgentOutput(100);
        setOutput(data.lines);
      } catch (e) { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [status.state]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const handleTrigger = async () => {
    setError(null);
    setLoading(true);
    try {
      const result = await triggerAgent({
        mode: config.mode,
        dryRun: config.dryRun,
        limit: config.limit ? parseInt(config.limit) : null,
        matchThreshold: config.matchThreshold ? parseFloat(config.matchThreshold) / 100 : null,
        collection: config.collection,
      });
      if (result.error) {
        setError(result.error);
      } else {
        setOutput([]);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopAgent();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const isRunning = status.state === 'running' || status.state === 'stopping';
  const stateStyle = STATE_COLORS[status.state] || STATE_COLORS.idle;

  const formatUptime = (sec) => {
    if (!sec) return '—';
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#18B8BC] to-[#117D84] shadow-md">
          <Bot className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-[#203A5F]">Agent Control</h1>
          <p className="text-sm text-[#708198]">Trigger, configure, and monitor the LinkedIn scanning agent</p>
        </div>
      </div>

      {/* Status bar */}
      <div className={`flex items-center justify-between rounded-xl border p-4 ${stateStyle.bg} border-opacity-50`}>
        <div className="flex items-center gap-3">
          <span className={`h-3 w-3 rounded-full ${stateStyle.dot}`} />
          <span className={`text-sm font-semibold uppercase tracking-wide ${stateStyle.text}`}>
            {status.state}
          </span>
          {status.pid && <span className="text-xs text-[#8291A5]">PID: {status.pid}</span>}
          {isRunning && (
            <span className="flex items-center gap-1 text-xs text-[#52677F]">
              <Clock className="h-3 w-3" />
              {formatUptime(status.uptime_seconds)}
            </span>
          )}
          {status.dry_run && isRunning && (
            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              DRY RUN
            </span>
          )}
        </div>
        {status.last_error && (
          <div className="flex items-center gap-1 text-xs text-red-600">
            <AlertCircle className="h-3.5 w-3.5" />
            {status.last_error}
          </div>
        )}
      </div>

      {/* Control panel: config + trigger */}
      <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
        {/* Config form */}
        <div className="rounded-xl border border-[#DCE5ED] bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Settings className="h-4 w-4 text-[#18B8BC]" />
            <h3 className="text-sm font-semibold text-[#203A5F]">Scan Configuration</h3>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Mode */}
            <div>
              <label className="mb-1 block text-xs font-medium text-[#52677F]">Mode</label>
              <select
                value={config.mode}
                onChange={(e) => setConfig({ ...config, mode: e.target.value })}
                disabled={isRunning}
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1] disabled:opacity-50"
              >
                <option value="single">Single Cycle</option>
                <option value="daemon">Continuous (Daemon)</option>
              </select>
            </div>

            {/* Limit */}
            <div>
              <label className="mb-1 block text-xs font-medium text-[#52677F]">Max Jobs</label>
              <input
                type="number"
                min="1"
                max="500"
                value={config.limit}
                onChange={(e) => setConfig({ ...config, limit: e.target.value })}
                disabled={isRunning}
                placeholder="No limit"
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1] disabled:opacity-50"
              />
            </div>

            {/* Match Threshold */}
            <div>
              <label className="mb-1 block text-xs font-medium text-[#52677F]">Match Threshold (%)</label>
              <input
                type="number"
                min="0"
                max="100"
                value={config.matchThreshold}
                onChange={(e) => setConfig({ ...config, matchThreshold: e.target.value })}
                disabled={isRunning}
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1] disabled:opacity-50"
              />
            </div>

            {/* Collection */}
            <div>
              <label className="mb-1 block text-xs font-medium text-[#52677F]">Collection</label>
              <input
                type="text"
                value={config.collection}
                onChange={(e) => setConfig({ ...config, collection: e.target.value })}
                disabled={isRunning}
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1] disabled:opacity-50"
              />
            </div>

            {/* Dry Run toggle */}
            <div className="flex items-end">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.dryRun}
                  onChange={(e) => setConfig({ ...config, dryRun: e.target.checked })}
                  disabled={isRunning}
                  className="h-4 w-4 rounded border-[#DCE5ED] text-[#18B8BC] focus:ring-[#CEF2F1]"
                />
                <span className="text-sm text-[#52677F]">
                  Dry Run <span className="text-xs text-[#8291A5]">(scan only, no apply)</span>
                </span>
              </label>
            </div>
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-3 lg:w-48">
          {!isRunning ? (
            <button
              onClick={handleTrigger}
              disabled={loading}
              className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 py-4 text-sm font-semibold text-white shadow-md transition-all hover:bg-emerald-700 hover:shadow-lg disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Play className="h-5 w-5" />}
              Start Agent
            </button>
          ) : (
            <button
              onClick={handleStop}
              disabled={loading || status.state === 'stopping'}
              className="flex items-center justify-center gap-2 rounded-xl bg-red-600 px-6 py-4 text-sm font-semibold text-white shadow-md transition-all hover:bg-red-700 hover:shadow-lg disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Square className="h-5 w-5" />}
              Stop Agent
            </button>
          )}

          {/* Quick actions */}
          <button
            onClick={() => {
              setConfig({ ...config, dryRun: true, limit: '5', mode: 'single' });
              setTimeout(handleTrigger, 100);
            }}
            disabled={isRunning || loading}
            className="flex items-center justify-center gap-2 rounded-xl border border-[#DCE5ED] bg-white px-4 py-3 text-xs font-medium text-[#52677F] shadow-sm transition-colors hover:bg-[#F6F8FB] disabled:opacity-50"
          >
            <Zap className="h-4 w-4 text-amber-500" />
            Quick Scan (5 jobs, dry)
          </button>
        </div>
      </div>

      {/* Live output console */}
      <div className="rounded-xl border border-[#DCE5ED] bg-[#1e1e2e] shadow-sm">
        <div className="flex items-center justify-between border-b border-[#2e2e3e] px-4 py-2.5">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-emerald-400" />
            <span className="text-sm font-medium text-slate-300">Agent Output</span>
            {isRunning && (
              <span className="flex items-center gap-1 rounded bg-emerald-900/50 px-2 py-0.5 text-[10px] text-emerald-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                LIVE
              </span>
            )}
          </div>
          <button
            onClick={() => setShowOutput(!showOutput)}
            className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
          >
            {showOutput ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>

        {showOutput && (
          <div
            ref={outputRef}
            className="max-h-80 overflow-y-auto p-4 font-mono text-xs leading-5"
          >
            {output.length === 0 ? (
              <div className="text-slate-500 italic">
                {isRunning
                  ? 'Waiting for output...'
                  : 'No output yet. Start the agent to see live logs here.'}
              </div>
            ) : (
              output.map((line, i) => (
                <div key={i} className={getLineColor(line)}>
                  {line}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function getLineColor(line) {
  if (line.includes('ERROR') || line.includes('❌')) return 'text-red-400';
  if (line.includes('WARNING') || line.includes('⚠️')) return 'text-amber-400';
  if (line.includes('✅') || line.includes('SUCCESS') || line.includes('submitted')) return 'text-emerald-400';
  if (line.includes('INFO') || line.includes('🚀') || line.includes('📊')) return 'text-sky-400';
  if (line.includes('DRY RUN')) return 'text-amber-300';
  return 'text-slate-300';
}
