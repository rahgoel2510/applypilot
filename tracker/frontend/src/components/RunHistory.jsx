import { useState, useEffect } from 'react';import {
  History, ChevronDown, ChevronRight, Copy, Check, Clock,
  CheckCircle2, XCircle, StopCircle, Loader2, Download, Wrench, Brain,
} from 'lucide-react';
import { getAgentRuns, getAgentRunDetail, diagnoseRun, autoRepair } from '../api';

const STATUS_STYLES = {
  completed: { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50', badge: 'bg-emerald-100 text-emerald-700' },
  failed: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50', badge: 'bg-red-100 text-red-700' },
  stopped: { icon: StopCircle, color: 'text-amber-600', bg: 'bg-amber-50', badge: 'bg-amber-100 text-amber-700' },
  running: { icon: Loader2, color: 'text-blue-600', bg: 'bg-blue-50', badge: 'bg-blue-100 text-blue-700' },
};

export default function RunHistory() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRun, setExpandedRun] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [copied, setCopied] = useState(null);
  const [diagnosing, setDiagnosing] = useState(null);
  const [diagnosisResult, setDiagnosisResult] = useState(null);
  const [repairing, setRepairing] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getAgentRuns(50);
        setRuns(data);
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleExpand = async (runId) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
      setRunDetail(null);
      return;
    }
    setExpandedRun(runId);
    setDetailLoading(true);
    try {
      const detail = await getAgentRunDetail(runId);
      setRunDetail(detail);
    } catch (e) { console.error(e); }
    finally { setDetailLoading(false); }
  };

  const handleCopyLogs = (runId, logs) => {
    navigator.clipboard.writeText(logs);
    setCopied(runId);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleDownload = (run, logs) => {
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `applypilot-run-${run.started_at?.slice(0, 16) || run.id.slice(0, 8)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDiagnose = async (runId) => {
    setDiagnosing(runId);
    setDiagnosisResult(null);
    try {
      const result = await diagnoseRun(runId);
      setDiagnosisResult(result);
    } catch (e) {
      setDiagnosisResult({ diagnosed: false, message: 'Failed to reach diagnosis API.' });
    } finally {
      setDiagnosing(null);
    }
  };

  const handleAutoRepair = async () => {
    setRepairing(true);
    try {
      const result = await autoRepair();
      setDiagnosisResult(result);
    } catch (e) {
      setDiagnosisResult({ diagnosed: false, message: 'Auto-repair request failed.' });
    } finally {
      setRepairing(false);
    }
  };

  const formatDuration = (sec) => {
    const s = parseInt(sec) || 0;
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  };

  const formatTime = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return <div className="flex items-center justify-center py-12 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading run history...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md">
          <History className="h-5 w-5 text-white" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-[#203A5F]">Run History</h2>
          <p className="text-sm text-[#708198]">{runs.length} past runs · click to expand full logs</p>
        </div>
      </div>

      {runs.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center">
          <History className="mx-auto h-8 w-8 text-slate-300 mb-3" />
          <p className="text-sm font-medium text-slate-500">No runs yet</p>
          <p className="text-xs text-slate-400 mt-1">Launch the agent to see run history here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map(run => {
            const st = STATUS_STYLES[run.status] || STATUS_STYLES.completed;
            const Icon = st.icon;
            const isExpanded = expandedRun === run.id;

            return (
              <div key={run.id} className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                {/* Run header — clickable */}
                <button
                  onClick={() => handleExpand(run.id)}
                  className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-slate-50 transition-colors"
                >
                  <Icon className={`h-5 w-5 flex-shrink-0 ${st.color} ${run.status === 'running' ? 'animate-spin' : ''}`} />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800">
                        {run.mode === 'daemon' ? 'Daemon Run' : 'Single Cycle'}
                      </span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${st.badge}`}>
                        {run.status.toUpperCase()}
                      </span>
                      {run.dry_run === 'True' && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                          DRY RUN
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-0.5 text-xs text-slate-500">
                      <span>{formatTime(run.started_at)}</span>
                      <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDuration(run.duration_seconds)}</span>
                      {parseInt(run.jobs_applied) > 0 && <span className="text-emerald-600 font-medium">{run.jobs_applied} applied</span>}
                      {parseInt(run.jobs_skipped) > 0 && <span>{run.jobs_skipped} skipped</span>}
                    </div>
                  </div>

                  {isExpanded ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
                </button>

                {/* Expanded detail — full logs */}
                {isExpanded && (
                  <div className="border-t border-slate-100">
                    {detailLoading ? (
                      <div className="flex items-center justify-center py-8 text-sm text-slate-400">
                        <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading logs...
                      </div>
                    ) : runDetail ? (
                      <div>
                        {/* Stats row */}
                        <div className="flex items-center gap-4 px-5 py-3 bg-slate-50 border-b border-slate-100 text-xs text-slate-600">
                          <span>Processed: <strong>{runDetail.jobs_processed || 0}</strong></span>
                          <span>Applied: <strong className="text-emerald-600">{runDetail.jobs_applied || 0}</strong></span>
                          <span>Skipped: <strong>{runDetail.jobs_skipped || 0}</strong></span>
                          <span>Paused: <strong>{runDetail.jobs_paused || 0}</strong></span>
                          <span>Errors: <strong className="text-red-600">{runDetail.jobs_errored || 0}</strong></span>
                          <div className="ml-auto flex gap-2">
                            <button
                              onClick={() => handleCopyLogs(run.id, runDetail.output_log || '')}
                              className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium hover:bg-slate-50"
                            >
                              {copied === run.id ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                              {copied === run.id ? 'Copied!' : 'Copy Full Log'}
                            </button>
                            <button
                              onClick={() => handleDownload(run, runDetail.output_log || '')}
                              className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium hover:bg-slate-50"
                            >
                              <Download className="h-3 w-3" /> Download .log
                            </button>
                          </div>
                        </div>

                        {/* Error message if failed */}
                        {runDetail.error_message && (
                          <div className="mx-5 mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700 select-text">
                            <strong>Error:</strong> {runDetail.error_message}
                          </div>
                        )}

                        {/* AI Diagnosis section */}
                        {(run.status === 'failed' || runDetail.error_message) && (
                          <div className="mx-5 mt-3">
                            {!diagnosisResult || diagnosisResult.run_id !== run.id ? (
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleDiagnose(run.id)}
                                  disabled={diagnosing === run.id}
                                  className="flex items-center gap-2 rounded-lg bg-purple-50 border border-purple-200 px-4 py-2 text-sm font-medium text-purple-700 hover:bg-purple-100 transition-colors disabled:opacity-50"
                                >
                                  {diagnosing === run.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
                                  {diagnosing === run.id ? 'Analyzing...' : 'AI Diagnose'}
                                </button>
                                <button
                                  onClick={handleAutoRepair}
                                  disabled={repairing}
                                  className="flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-50"
                                >
                                  {repairing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
                                  {repairing ? 'Repairing...' : 'Auto-Repair & Retry'}
                                </button>
                              </div>
                            ) : (
                              <DiagnosisCard diagnosis={diagnosisResult} />
                            )}
                          </div>
                        )}

                        {/* Full raw tech log — no formatting, exactly as captured */}
                        <div className="border-t border-slate-800 bg-[#0d1117]">
                          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
                            <span className="text-[11px] font-mono text-slate-500">
                              RAW OUTPUT — {runDetail.output_log?.split('\n').length || 0} lines
                            </span>
                            <span className="text-[10px] text-slate-600">
                              Includes timestamps, file refs, tracebacks, Playwright call logs
                            </span>
                          </div>
                          <pre className="max-h-[600px] overflow-y-auto p-4 font-mono text-[11px] leading-5 text-slate-300 select-text whitespace-pre-wrap break-words">
                            {runDetail.output_log || 'No output captured.'}
                          </pre>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function getLogColor(line) {
  if (line.includes('ERROR') || line.includes('Traceback') || line.includes('failed')) return 'text-red-400';
  if (line.includes('WARNING') || line.includes('⚠')) return 'text-amber-400';
  if (line.includes('✅') || line.includes('submitted') || line.includes('SUCCESS')) return 'text-emerald-400';
  if (line.includes('INFO') || line.includes('🚀')) return 'text-sky-300';
  return 'text-slate-300';
}

function DiagnosisCard({ diagnosis }) {
  if (!diagnosis?.diagnosed) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {diagnosis?.message || 'No diagnosis available.'}
      </div>
    );
  }

  const d = diagnosis.diagnosis;
  const severityColors = {
    low: 'bg-blue-100 text-blue-700',
    medium: 'bg-amber-100 text-amber-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700',
  };
  const categoryIcons = {
    session: '🔐', selector: '🎯', network: '🌐', timeout: '⏳',
    config: '⚙️', permission: '🔒', unknown: '❓',
  };

  const [copied, setCopied] = useState(false);
  const copyDiagnosis = () => {
    const text = [
      `═══ AI Diagnosis ═══`,
      `Category: ${d.category}`,
      `Severity: ${d.severity}`,
      `Confidence: ${Math.round(d.confidence * 100)}%`,
      ``,
      `Diagnosis: ${d.diagnosis}`,
      ``,
      `Fix: ${d.fix_description}`,
      d.auto_fixable ? `\nAuto-fixable: Yes` : `\nUser action required: ${d.user_action_required}`,
      d.model_used ? `\nModel: ${d.model_used}` : '',
    ].join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-purple-200 bg-gradient-to-br from-purple-50 to-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-purple-600" />
          <span className="text-sm font-semibold text-purple-800">AI Diagnosis</span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${severityColors[d.severity] || severityColors.medium}`}>
            {d.severity?.toUpperCase()}
          </span>
          <span className="text-xs text-slate-500">
            {categoryIcons[d.category] || '❓'} {d.category}
          </span>
        </div>
        <button onClick={copyDiagnosis} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700">
          {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <p className="text-sm text-slate-800 font-medium mb-2">{d.diagnosis}</p>
      <p className="text-xs text-slate-600 mb-3">{d.fix_description}</p>

      {d.auto_fixable ? (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <span className="text-xs text-emerald-700 font-medium">Auto-fixable — retry was triggered with adjusted parameters</span>
        </div>
      ) : d.user_action_required ? (
        <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
          <Wrench className="h-4 w-4 text-amber-600" />
          <span className="text-xs text-amber-700">{d.user_action_required}</span>
        </div>
      ) : null}

      {d.confidence > 0 && (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-400">
          <span>Confidence: {Math.round(d.confidence * 100)}%</span>
          {d.model_used && <span>· Model: {d.model_used}</span>}
        </div>
      )}
    </div>
  );
}
