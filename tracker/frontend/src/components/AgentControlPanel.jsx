import { useState, useEffect, useRef } from 'react';
import {
  Play, Square, Bot, Terminal, AlertCircle,
  Loader2, Zap, Clock, Eye, EyeOff, Wifi, WifiOff,
  Gauge, Target, Radar, Shield, Send, Power,
  ChevronRight, Sparkles, CircleDot,
} from 'lucide-react';
import { triggerAgent, stopAgent, getAgentStatus, getAgentOutput } from '../api';

export default function AgentControlPanel() {
  const [status, setStatus] = useState({ state: 'idle', pid: null, started_at: null, uptime_seconds: 0, config: {}, last_error: null });
  const [output, setOutput] = useState([]);
  const [showOutput, setShowOutput] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const outputRef = useRef(null);

  const [config, setConfig] = useState({
    mode: 'single',
    dryRun: true,
    limit: '10',
    matchThreshold: '80',
    collection: 'Recommended',
  });

  // Poll status
  useEffect(() => {
    const poll = async () => {
      try { setStatus(await getAgentStatus()); } catch (e) { /* */ }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  // Poll output when running
  useEffect(() => {
    if (status.state !== 'running') return;
    const poll = async () => {
      try { const d = await getAgentOutput(100); setOutput(d.lines); } catch (e) { /* */ }
    };
    poll();
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, [status.state]);

  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
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
      if (result.error) setError(result.error);
      else setOutput([]);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleStop = async () => {
    setLoading(true);
    try { await stopAgent(); } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const isRunning = status.state === 'running' || status.state === 'stopping';

  const formatUptime = (sec) => {
    if (!sec) return '00:00:00';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  };

  return (
    <div className="space-y-5">
      {/* Hero header with gradient */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0f172a] via-[#1e293b] to-[#134e4a] p-6 shadow-xl">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-5" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)', backgroundSize: '24px 24px' }} />
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Animated bot icon */}
            <div className={`relative flex h-14 w-14 items-center justify-center rounded-2xl ${isRunning ? 'bg-emerald-500/20' : 'bg-white/10'} backdrop-blur-sm`}>
              <Bot className={`h-7 w-7 ${isRunning ? 'text-emerald-400' : 'text-white/80'}`} />
              {isRunning && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-4 w-4 rounded-full bg-emerald-500" />
                </span>
              )}
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">ApplyPilot Agent</h1>
              <p className="text-sm text-slate-400">Autonomous LinkedIn job scanner · <span className="text-teal-400">Powered by Rahul</span></p>
            </div>
          </div>

          {/* Status badge */}
          <div className="flex items-center gap-3">
            <StatusBadge state={status.state} />
            {isRunning && (
              <div className="rounded-lg bg-white/5 px-3 py-1.5 backdrop-blur-sm">
                <span className="font-mono text-sm text-emerald-400">{formatUptime(status.uptime_seconds)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Metrics row */}
        <div className="relative mt-5 grid grid-cols-4 gap-3">
          <MetricCard icon={Radar} label="Mode" value={isRunning ? (status.mode === 'daemon' ? 'Daemon' : 'Single') : '—'} active={isRunning} />
          <MetricCard icon={Target} label="Limit" value={isRunning ? (status.limit || '∞') : '—'} active={isRunning} />
          <MetricCard icon={Gauge} label="Threshold" value={isRunning ? `${(status.config?.match_threshold || 0.8) * 100}%` : '—'} active={isRunning} />
          <MetricCard icon={Shield} label="Dry Run" value={isRunning ? (status.dry_run ? 'ON' : 'OFF') : '—'} active={isRunning} accent={status.dry_run} />
        </div>

        {/* Error message */}
        {status.last_error && (
          <div className="relative mt-4 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5">
            <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
            <span className="text-sm text-red-300">{status.last_error}</span>
          </div>
        )}
      </div>

      {/* Control grid */}
      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        {/* Configuration panel */}
        <div className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#18B8BC] to-[#0d9488]">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <h3 className="text-base font-semibold text-[#0f172a]">Mission Parameters</h3>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <ConfigField
              label="Scan Mode"
              icon={Radar}
              description="How the agent operates"
            >
              <select
                value={config.mode}
                onChange={(e) => setConfig({ ...config, mode: e.target.value })}
                disabled={isRunning}
                className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-500/10 disabled:opacity-40"
              >
                <option value="single">⚡ Single Cycle — scan once, then stop</option>
                <option value="daemon">🔄 Continuous — scan on schedule forever</option>
              </select>
            </ConfigField>

            <ConfigField
              label="Max Jobs to Process"
              icon={Target}
              description="Limit per scan cycle"
            >
              <input
                type="number"
                min="1"
                max="500"
                value={config.limit}
                onChange={(e) => setConfig({ ...config, limit: e.target.value })}
                disabled={isRunning}
                placeholder="∞ No limit"
                className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-500/10 disabled:opacity-40"
              />
            </ConfigField>

            <ConfigField
              label="Match Threshold"
              icon={Gauge}
              description="Minimum fit score to apply"
            >
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="50"
                  max="100"
                  value={config.matchThreshold}
                  onChange={(e) => setConfig({ ...config, matchThreshold: e.target.value })}
                  disabled={isRunning}
                  className="flex-1 h-2 rounded-full appearance-none bg-slate-200 accent-teal-500 disabled:opacity-40"
                />
                <span className="w-12 rounded-lg bg-teal-50 px-2 py-1 text-center text-sm font-bold text-teal-700">
                  {config.matchThreshold}%
                </span>
              </div>
            </ConfigField>

            <ConfigField
              label="Job Collection"
              icon={CircleDot}
              description="LinkedIn saved search to scan"
            >
              <input
                type="text"
                value={config.collection}
                onChange={(e) => setConfig({ ...config, collection: e.target.value })}
                disabled={isRunning}
                className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-800 outline-none transition-all focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-500/10 disabled:opacity-40"
              />
            </ConfigField>
          </div>

          {/* Dry run toggle — prominent */}
          <div className="mt-5 rounded-xl border-2 border-dashed border-amber-200 bg-amber-50/50 p-4">
            <label className="flex cursor-pointer items-center justify-between">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-amber-600" />
                <div>
                  <span className="text-sm font-semibold text-slate-800">Safety Mode (Dry Run)</span>
                  <p className="text-xs text-slate-500">Scan & score jobs without submitting any applications</p>
                </div>
              </div>
              <div className="relative">
                <input
                  type="checkbox"
                  checked={config.dryRun}
                  onChange={(e) => setConfig({ ...config, dryRun: e.target.checked })}
                  disabled={isRunning}
                  className="peer sr-only"
                />
                <div className="h-6 w-11 rounded-full bg-slate-300 transition-colors peer-checked:bg-amber-500 peer-disabled:opacity-40" />
                <div className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-5" />
              </div>
            </label>
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>

        {/* Action panel */}
        <div className="space-y-4">
          {/* Main action button */}
          {!isRunning ? (
            <button
              onClick={handleTrigger}
              disabled={loading}
              className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-6 text-white shadow-lg shadow-emerald-500/25 transition-all hover:shadow-xl hover:shadow-emerald-500/30 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:shadow-none"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-emerald-400 to-teal-400 opacity-0 transition-opacity group-hover:opacity-20" />
              <div className="relative flex flex-col items-center gap-2">
                {loading ? (
                  <Loader2 className="h-8 w-8 animate-spin" />
                ) : (
                  <Power className="h-8 w-8" />
                )}
                <span className="text-base font-bold">Launch Agent</span>
                <span className="text-xs text-emerald-100">Begin scanning LinkedIn</span>
              </div>
            </button>
          ) : (
            <button
              onClick={handleStop}
              disabled={loading || status.state === 'stopping'}
              className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-red-600 to-rose-600 px-6 py-6 text-white shadow-lg shadow-red-500/25 transition-all hover:shadow-xl hover:shadow-red-500/30 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50"
            >
              <div className="relative flex flex-col items-center gap-2">
                {loading ? (
                  <Loader2 className="h-8 w-8 animate-spin" />
                ) : (
                  <Square className="h-8 w-8" />
                )}
                <span className="text-base font-bold">Stop Agent</span>
                <span className="text-xs text-red-100">Graceful shutdown</span>
              </div>
            </button>
          )}

          {/* Quick actions */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => {
                setConfig({ ...config, dryRun: true, limit: '5', mode: 'single' });
                setTimeout(handleTrigger, 100);
              }}
              disabled={isRunning || loading}
              className="flex flex-col items-center gap-1.5 rounded-xl border-2 border-slate-200 bg-white px-3 py-4 text-center transition-all hover:border-amber-300 hover:bg-amber-50 hover:-translate-y-0.5 disabled:opacity-40"
            >
              <Zap className="h-5 w-5 text-amber-500" />
              <span className="text-xs font-semibold text-slate-700">Quick Scan</span>
              <span className="text-[10px] text-slate-400">5 jobs · dry run</span>
            </button>
            <button
              onClick={() => {
                setConfig({ ...config, dryRun: false, limit: '25', mode: 'single' });
                setTimeout(handleTrigger, 100);
              }}
              disabled={isRunning || loading}
              className="flex flex-col items-center gap-1.5 rounded-xl border-2 border-slate-200 bg-white px-3 py-4 text-center transition-all hover:border-emerald-300 hover:bg-emerald-50 hover:-translate-y-0.5 disabled:opacity-40"
            >
              <Send className="h-5 w-5 text-emerald-500" />
              <span className="text-xs font-semibold text-slate-700">Full Run</span>
              <span className="text-[10px] text-slate-400">25 jobs · apply</span>
            </button>
          </div>

          {/* Connection status */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">LinkedIn</span>
              <span className="flex items-center gap-1 text-amber-600">
                <WifiOff className="h-3 w-3" /> Not connected
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="text-slate-500">Telegram</span>
              <span className="flex items-center gap-1 text-emerald-600">
                <Wifi className="h-3 w-3" /> Connected
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="text-slate-500">Tracker</span>
              <span className="flex items-center gap-1 text-emerald-600">
                <Wifi className="h-3 w-3" /> Active
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Terminal console */}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0d1117] shadow-2xl shadow-black/20">
        <div className="flex items-center justify-between border-b border-slate-800 bg-[#161b22] px-5 py-3">
          <div className="flex items-center gap-3">
            {/* macOS-style dots */}
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            </div>
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-300">applypilot — agent output</span>
            </div>
            {isRunning && (
              <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                STREAMING
              </span>
            )}
          </div>
          <button
            onClick={() => setShowOutput(!showOutput)}
            className="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-700 hover:text-slate-300"
          >
            {showOutput ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>

        {showOutput && (
          <div
            ref={outputRef}
            className="max-h-96 overflow-y-auto p-5 font-mono text-[13px] leading-6"
          >
            {output.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-800/50">
                  <Terminal className="h-7 w-7 text-slate-600" />
                </div>
                <p className="text-sm font-medium text-slate-400">
                  {isRunning ? 'Waiting for output...' : 'Agent is idle'}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  {isRunning ? 'Output will appear here in real-time' : 'Launch the agent to see live scanning logs'}
                </p>
              </div>
            ) : (
              output.map((line, i) => (
                <div key={i} className={`${getLineColor(line)} whitespace-pre-wrap break-all`}>
                  <span className="mr-3 select-none text-slate-700">{String(i + 1).padStart(3)}</span>
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

// --- Sub-components ---

function StatusBadge({ state }) {
  const styles = {
    idle: 'bg-slate-500/10 text-slate-400 ring-slate-500/20',
    running: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
    stopping: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
    error: 'bg-red-500/10 text-red-400 ring-red-500/20',
  };
  const icons = { idle: '⏸', running: '▶', stopping: '⏳', error: '⚠' };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wider ring-1 ring-inset ${styles[state] || styles.idle}`}>
      <span>{icons[state] || '•'}</span>
      {state}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, active, accent }) {
  return (
    <div className={`rounded-xl p-3 backdrop-blur-sm ${active ? 'bg-white/5' : 'bg-white/[0.02]'}`}>
      <div className="flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${active ? (accent ? 'text-amber-400' : 'text-teal-400') : 'text-slate-600'}`} />
        <span className="text-[11px] font-medium text-slate-500">{label}</span>
      </div>
      <p className={`mt-1 text-lg font-bold ${active ? (accent ? 'text-amber-300' : 'text-white') : 'text-slate-600'}`}>
        {value}
      </p>
    </div>
  );
}

function ConfigField({ label, icon: Icon, description, children }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 text-teal-600" />
        <span className="text-sm font-semibold text-slate-800">{label}</span>
      </div>
      {description && <p className="mb-2 text-xs text-slate-400">{description}</p>}
      {children}
    </div>
  );
}

function getLineColor(line) {
  if (line.includes('ERROR') || line.includes('❌') || line.includes('Traceback') || line.includes('Error')) return 'text-red-400';
  if (line.includes('WARNING') || line.includes('⚠️') || line.includes('DRY RUN')) return 'text-amber-400';
  if (line.includes('✅') || line.includes('submitted') || line.includes('SUCCESS')) return 'text-emerald-400';
  if (line.includes('INFO') || line.includes('🚀') || line.includes('📊') || line.includes('Starting')) return 'text-sky-400';
  if (line.includes('→') || line.includes('Processing')) return 'text-purple-400';
  return 'text-slate-300';
}
