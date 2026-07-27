import { useState, useEffect, useCallback } from 'react';
import {
  Activity, Play, Square, RotateCcw, CheckCircle2, PauseCircle, SkipForward,
  AlertTriangle, XCircle, Mail, Send, MessageSquare, Clock, Filter,
  ChevronDown, RefreshCw,
} from 'lucide-react';
import { fetchLogs } from '../api';

const EVENT_ICONS = {
  agent_start: { icon: Play, color: 'text-green-600', bg: 'bg-green-50' },
  agent_stop: { icon: Square, color: 'text-gray-600', bg: 'bg-gray-50' },
  cycle_start: { icon: RotateCcw, color: 'text-blue-600', bg: 'bg-blue-50' },
  cycle_end: { icon: CheckCircle2, color: 'text-blue-700', bg: 'bg-blue-50' },
  job_submitted: { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50' },
  job_paused: { icon: PauseCircle, color: 'text-amber-600', bg: 'bg-amber-50' },
  job_skipped: { icon: SkipForward, color: 'text-slate-500', bg: 'bg-slate-50' },
  job_error: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50' },
  inmail_drafted: { icon: Mail, color: 'text-purple-600', bg: 'bg-purple-50' },
  inmail_sent: { icon: Send, color: 'text-purple-700', bg: 'bg-purple-50' },
  telegram_sent: { icon: Send, color: 'text-sky-600', bg: 'bg-sky-50' },
  human_input_requested: { icon: MessageSquare, color: 'text-orange-600', bg: 'bg-orange-50' },
  human_input_received: { icon: MessageSquare, color: 'text-green-600', bg: 'bg-green-50' },
  error: { icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' },
  warning: { icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' },
  info: { icon: Activity, color: 'text-blue-500', bg: 'bg-blue-50' },
};

const SEVERITY_STYLES = {
  info: 'border-l-blue-400',
  success: 'border-l-emerald-400',
  warning: 'border-l-amber-400',
  error: 'border-l-red-400',
};

const EVENT_TYPES = [
  { value: '', label: 'All events' },
  { value: 'agent_start', label: 'Agent Start' },
  { value: 'agent_stop', label: 'Agent Stop' },
  { value: 'cycle_start', label: 'Cycle Start' },
  { value: 'cycle_end', label: 'Cycle End' },
  { value: 'job_submitted', label: 'Job Submitted' },
  { value: 'job_paused', label: 'Job Paused' },
  { value: 'job_skipped', label: 'Job Skipped' },
  { value: 'job_error', label: 'Job Error' },
  { value: 'inmail_drafted', label: 'InMail Drafted' },
  { value: 'error', label: 'System Error' },
];

const SEVERITIES = [
  { value: '', label: 'All severities' },
  { value: 'info', label: '🔵 Info' },
  { value: 'success', label: '🟢 Success' },
  { value: 'warning', label: '🟡 Warning' },
  { value: 'error', label: '🔴 Error' },
];

export default function ActivityFeed({ compact = false, limit = 50 }) {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [eventType, setEventType] = useState('');
  const [severity, setSeverity] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);

  const pageSize = compact ? Math.min(limit, 15) : limit;

  const loadLogs = useCallback(async () => {
    try {
      const data = await fetchLogs({
        page,
        pageSize,
        eventType: eventType || undefined,
        severity: severity || undefined,
        search: search || undefined,
      });
      setLogs(data.logs);
      setTotal(data.total);
      setHasMore(data.has_more);
    } catch (err) {
      console.error('Failed to load logs:', err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, eventType, severity, search]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    const interval = setInterval(loadLogs, 5000);
    return () => clearInterval(interval);
  }, [loadLogs]);

  const formatTime = (ts) => {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMin / 60);

    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className={compact ? '' : 'bg-white rounded-xl border border-[#DCE5ED] shadow-sm'}>
      {/* Header */}
      {!compact && (
        <div className="flex items-center justify-between border-b border-[#EDF1F5] px-5 py-4">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-[#18B8BC]" />
            <h2 className="text-lg font-semibold text-[#203A5F]">Activity Feed</h2>
            <span className="rounded-full bg-[#CEF2F1] px-2 py-0.5 text-xs font-medium text-[#117078]">
              {total} events
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                showFilters ? 'border-[#18B8BC] bg-[#ECFAFA] text-[#117D84]' : 'border-[#DCE5ED] text-[#52677F] hover:bg-[#F6F8FB]'
              }`}
            >
              <Filter className="h-3.5 w-3.5" />
              Filters
            </button>
            <button
              onClick={loadLogs}
              className="rounded-lg border border-[#DCE5ED] p-1.5 text-[#8291A5] hover:bg-[#F6F8FB] hover:text-[#52677F]"
              title="Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Filters (collapsible) */}
      {showFilters && !compact && (
        <div className="flex flex-wrap items-center gap-2 border-b border-[#EDF1F5] bg-[#F8FAFC] px-5 py-3">
          <select
            value={eventType}
            onChange={(e) => { setEventType(e.target.value); setPage(1); }}
            className="h-8 rounded-md border border-[#DCE5ED] bg-white px-2 text-xs text-[#52677F] outline-none focus:border-[#18B8BC]"
          >
            {EVENT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <select
            value={severity}
            onChange={(e) => { setSeverity(e.target.value); setPage(1); }}
            className="h-8 rounded-md border border-[#DCE5ED] bg-white px-2 text-xs text-[#52677F] outline-none focus:border-[#18B8BC]"
          >
            {SEVERITIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="h-8 w-40 rounded-md border border-[#DCE5ED] bg-white px-2 text-xs text-[#203A5F] outline-none placeholder:text-[#9AA8B8] focus:border-[#18B8BC]"
          />
        </div>
      )}

      {/* Log entries */}
      <div className={compact ? 'space-y-1' : 'divide-y divide-[#EDF1F5]'}>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-sm text-[#8291A5]">
            <Clock className="mr-2 h-4 w-4 animate-spin" /> Loading activity...
          </div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Activity className="mb-3 h-8 w-8 text-[#DCE5ED]" />
            <p className="text-sm font-medium text-[#294A73]">No activity yet</p>
            <p className="mt-1 text-xs text-[#8291A5]">Events will appear here when the agent runs.</p>
          </div>
        ) : (
          logs.map((log) => <LogEntry key={log.id} log={log} compact={compact} formatTime={formatTime} />)
        )}
      </div>

      {/* Pagination */}
      {!compact && hasMore && (
        <div className="flex items-center justify-center border-t border-[#EDF1F5] py-3">
          <button
            onClick={() => setPage((p) => p + 1)}
            className="flex items-center gap-1 rounded-lg border border-[#DCE5ED] px-4 py-2 text-xs font-medium text-[#52677F] hover:bg-[#F6F8FB]"
          >
            <ChevronDown className="h-3.5 w-3.5" />
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

function LogEntry({ log, compact, formatTime }) {
  const eventConfig = EVENT_ICONS[log.event_type] || EVENT_ICONS.info;
  const Icon = eventConfig.icon;
  const severityBorder = SEVERITY_STYLES[log.severity] || SEVERITY_STYLES.info;

  if (compact) {
    return (
      <div className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-[#F6F8FB]">
        <div className={`mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded ${eventConfig.bg}`}>
          <Icon className={`h-3 w-3 ${eventConfig.color}`} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-[#203A5F]">{log.message}</p>
          {log.title && (
            <p className="truncate text-[11px] text-[#8291A5]">{log.title} @ {log.company}</p>
          )}
        </div>
        <span className="flex-shrink-0 text-[10px] text-[#9AA8B8]">{formatTime(log.timestamp)}</span>
      </div>
    );
  }

  return (
    <div className={`flex items-start gap-3 border-l-[3px] ${severityBorder} px-5 py-3.5 transition-colors hover:bg-[#F8FAFC]`}>
      <div className={`mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg ${eventConfig.bg}`}>
        <Icon className={`h-4 w-4 ${eventConfig.color}`} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-[#203A5F]">{log.message}</p>
        {log.title && (
          <p className="mt-0.5 text-xs text-[#52677F]">
            <span className="font-medium">{log.title}</span>
            {log.company && <span> @ {log.company}</span>}
            {log.stage && (
              <span className="ml-2 rounded bg-[#EDF1F5] px-1.5 py-0.5 text-[11px] font-medium text-[#52677F]">
                {log.stage}
              </span>
            )}
          </p>
        )}
      </div>
      <span className="flex-shrink-0 text-xs text-[#9AA8B8]">{formatTime(log.timestamp)}</span>
    </div>
  );
}
