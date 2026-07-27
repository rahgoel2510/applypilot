import { useState, useEffect, useRef } from 'react';
import {
  Play, Square, Bot, Terminal, AlertCircle,
  Loader2, Zap, Clock, Eye, EyeOff, Wifi, WifiOff,
  Gauge, Target, Radar, Shield, Send, Power,
  ChevronRight, Sparkles, CircleDot,
} from 'lucide-react';
import { triggerAgent, stopAgent, getAgentStatus, getAgentOutput, getSettings } from '../api';
import AgentPipelineView from './AgentPipelineView';
import MissingSettingsModal from './MissingSettingsModal';

export default function AgentControlPanel() {
  const [status, setStatus] = useState({ state: 'idle', pid: null, started_at: null, uptime_seconds: 0, config: {}, last_error: null });
  const [output, setOutput] = useState([]);
  const [showOutput, setShowOutput] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [missingFields, setMissingFields] = useState([]);
  const [showMissingModal, setShowMissingModal] = useState(false);
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

    // Check for missing required settings before launching
    try {
      const settingsData = await getSettings();
      const missing = settingsData.settings.filter(s => !s.is_set && s.required);
      if (missing.length > 0) {
        setMissingFields(missing);
        setShowMissingModal(true);
        return;
      }
    } catch (e) {
      // If we can't check, proceed anyway
    }

    await doTrigger();
  };

  const doTrigger = async () => {
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

      {/* Agent Pipeline Visualization */}
      <AgentPipelineView />

      {/* Agent Live Updates — conversational style */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <div className="flex items-center gap-3">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-teal-500 to-emerald-600">
              <Bot className="h-4 w-4 text-white" />
              {isRunning && (
                <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
              )}
            </div>
            <div>
              <span className="text-sm font-semibold text-slate-800">Pilot Updates</span>
              <p className="text-[11px] text-slate-400">
                {isRunning ? 'Working on your applications...' : 'Waiting for instructions'}
              </p>
            </div>
          </div>

      {/* Missing Settings Modal */}
      <MissingSettingsModal
        isOpen={showMissingModal}
        onClose={() => setShowMissingModal(false)}
        missingFields={missingFields}
        onSaved={() => {
          setShowMissingModal(false);
          // Retry trigger after settings are saved
          setTimeout(doTrigger, 500);
        }}
      />
          <div className="flex items-center gap-2">
            {isRunning && (
              <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-600 ring-1 ring-inset ring-emerald-200">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                Live
              </span>
            )}
            <button
              onClick={() => setShowOutput(!showOutput)}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            >
              {showOutput ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {showOutput && (
          <div
            ref={outputRef}
            className="max-h-[420px] overflow-y-auto p-4 space-y-3"
          >
            {output.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-50">
                  <Bot className="h-6 w-6 text-slate-300" />
                </div>
                <p className="text-sm font-medium text-slate-500">
                  {isRunning ? "I'm getting ready..." : "Hi! I'm your ApplyPilot."}
                </p>
                <p className="mt-1 max-w-[280px] text-xs text-slate-400">
                  {isRunning
                    ? "Setting up the browser and connecting to LinkedIn. Updates will appear shortly."
                    : "Hit 'Launch Agent' and I'll start scanning LinkedIn for matching jobs. I'll keep you updated on every step."}
                </p>
              </div>
            ) : (
              output
                .filter(line => line.trim().length > 0 && !line.match(/^\s{10,}/))
                .map((line, i) => {
                  const cleaned = line
                    .replace(/\[\d{2}\/\d{2}\/\d{2}\s\d{2}:\d{2}:\d{2}\]\s*/, '')
                    .replace(/\s{2,}\S+\.py:\d+\s*$/, '')
                    .trim();
                  if (!cleaned) return null;
                  const msg = humanizeLogLine(cleaned);
                  if (!msg) return null;
                  return <AgentMessage key={i} message={msg} />;
                })
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// --- Conversational message bubble ---

function AgentMessage({ message }) {
  const { text, type, icon: IconEmoji } = message;

  const bubbleStyles = {
    info: 'bg-slate-50 border-slate-200',
    success: 'bg-emerald-50 border-emerald-200',
    warning: 'bg-amber-50 border-amber-200',
    error: 'bg-red-50 border-red-200',
    action: 'bg-blue-50 border-blue-200',
  };

  const textStyles = {
    info: 'text-slate-700',
    success: 'text-emerald-800',
    warning: 'text-amber-800',
    error: 'text-red-800',
    action: 'text-blue-800',
  };

  return (
    <div className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2">
      <span className="mt-0.5 text-base flex-shrink-0">{IconEmoji}</span>
      <div className={`flex-1 rounded-xl border px-3.5 py-2.5 ${bubbleStyles[type] || bubbleStyles.info}`}>
        <p className={`text-sm leading-relaxed ${textStyles[type] || textStyles.info}`}>
          {text}
        </p>
      </div>
    </div>
  );
}

// --- Transform raw log lines into human-friendly messages ---

function humanizeLogLine(line) {
  const lower = line.toLowerCase();

  // Skip noise
  if (lower.includes('data_dir=') || lower.includes('application support')) return null;
  if (lower.includes('headless=')) return null;

  // Agent lifecycle
  if (lower.includes('running single scan cycle'))
    return { text: "Starting a new scan cycle. Let me check LinkedIn for matching jobs...", type: 'action', icon: '🚀' };
  if (lower.includes('starting daemon'))
    return { text: "Going into continuous mode. I'll keep scanning on schedule until you stop me.", type: 'action', icon: '🔄' };
  if (lower.includes('scan cycle started'))
    return { text: "Scan cycle initiated. Opening LinkedIn and looking for opportunities...", type: 'info', icon: '🔍' };
  if (lower.includes('shutting down'))
    return { text: "Okay, shutting down gracefully. See you next time!", type: 'info', icon: '👋' };
  if (lower.includes('shutdown complete'))
    return { text: "All done. Closed browser and saved progress.", type: 'success', icon: '✅' };

  // Browser
  if (lower.includes('browser launched'))
    return { text: "Browser is up. Navigating to LinkedIn...", type: 'info', icon: '🌐' };
  if (lower.includes('already logged in'))
    return { text: "Great — I'm already logged into your LinkedIn account.", type: 'success', icon: '🔓' };
  if (lower.includes('not logged in'))
    return { text: "Need to log in first. Entering your credentials...", type: 'warning', icon: '🔐' };
  if (lower.includes('login successful'))
    return { text: "Logged in successfully! Ready to scan jobs.", type: 'success', icon: '✅' };
  if (lower.includes('login') && lower.includes('challenge'))
    return { text: "⚠️ LinkedIn is asking for verification (CAPTCHA or email). I'll need you to handle this manually.", type: 'warning', icon: '🛑' };
  if (lower.includes('browser closed'))
    return { text: "Browser closed. Saving session for next time.", type: 'info', icon: '🔒' };

  // Job navigation
  if (lower.includes('navigated to jobs'))
    return { text: "I'm on the jobs page now. Scanning listings...", type: 'info', icon: '📋' };
  if (lower.match(/found \d+ job/))
    return { text: line.replace(/^.*?(Found)/i, 'Found'), type: 'success', icon: '📊' };

  // Job processing
  if (lower.includes('processing:'))
    return { text: `Looking at: ${line.replace(/.*Processing:\s*/i, '')}`, type: 'action', icon: '👀' };
  if (lower.includes('would apply'))
    return { text: `✓ This one's a match! ${line.replace(/.*\]\s*/, '')}`, type: 'success', icon: '🎯' };
  if (lower.includes('would skip') || lower.includes('skipping'))
    return { text: `Skipping — ${line.replace(/.*?(skip|skipping)\w*[:\s]*/i, '')}`, type: 'info', icon: '⏭️' };
  if (lower.includes('submitted') || lower.includes('application was sent'))
    return { text: `Application submitted! ${line.replace(/.*?(submitted|sent)\s*/i, '')}`, type: 'success', icon: '🎉' };
  if (lower.includes('paused') || lower.includes('needs human'))
    return { text: `Pausing on this one — need your input on some fields. Check Telegram.`, type: 'warning', icon: '⏸️' };
  if (lower.includes('duplicate'))
    return { text: "Already applied to this one. Moving on.", type: 'info', icon: '🔁' };

  // InMail
  if (lower.includes('inmail') || lower.includes('drafted'))
    return { text: `Drafted a message to the recruiter. Check Telegram for review.`, type: 'success', icon: '✉️' };

  // Telegram
  if (lower.includes('notification sent') || lower.includes('telegram'))
    return { text: "Sent you an update on Telegram.", type: 'info', icon: '📱' };

  // Tally / cycle end
  if (lower.includes('cycle complete') || lower.includes('scan cycle complete'))
    return { text: "All done with this cycle! Check the Board tab for results.", type: 'success', icon: '🏁' };

  // Errors
  if (lower.includes('error') || lower.includes('traceback') || lower.includes('failed'))
    return { text: `Something went wrong: ${line.replace(/.*?(error|failed)[:\s]*/i, '').slice(0, 100)}`, type: 'error', icon: '❌' };
  if (lower.includes('timeout'))
    return { text: "Hmm, that took too long. LinkedIn might be slow or the page structure changed.", type: 'warning', icon: '⏳' };

  // Outside active hours
  if (lower.includes('outside active hours'))
    return { text: "Outside working hours. I'll sleep and check again later.", type: 'info', icon: '😴' };

  // Generic INFO lines
  if (lower.startsWith('info'))
    return { text: line.replace(/^info\s*/i, ''), type: 'info', icon: '💬' };

  // Anything else — show as-is
  return { text: line, type: 'info', icon: '💬' };
}

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
  return 'text-slate-300';
}
