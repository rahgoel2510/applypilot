import { useState, useEffect, useRef } from 'react';
import { Terminal, Copy, Check, RefreshCw, Download, Filter, Trash2 } from 'lucide-react';
import { getAgentOutput, getAgentStatus } from '../api';

export default function TechLogs() {
  const [lines, setLines] = useState([]);
  const [totalLines, setTotalLines] = useState(0);
  const [status, setStatus] = useState({ state: 'idle' });
  const [copied, setCopied] = useState(false);
  const [filter, setFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const [outputData, statusData] = await Promise.all([
          getAgentOutput(500),
          getAgentStatus(),
        ]);
        setLines(outputData.lines);
        setTotalLines(outputData.total_lines);
        setStatus(statusData);
      } catch (e) { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  const filteredLines = filter
    ? lines.filter(l => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  const handleCopy = () => {
    navigator.clipboard.writeText(filteredLines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `applypilot-logs-${new Date().toISOString().slice(0, 19)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isRunning = status.state === 'running';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 shadow-md">
            <Terminal className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-[#203A5F]">Tech Logs</h1>
            <p className="text-sm text-[#708198]">
              Raw agent output · {totalLines} lines
              {isRunning && <span className="ml-2 text-emerald-600 font-medium">● Live</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied!' : 'Copy All'}
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Download
          </button>
        </div>
      </div>

      {/* Filter + controls bar */}
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <Filter className="h-4 w-4 text-slate-400" />
        <input
          type="text"
          placeholder="Filter logs (e.g. ERROR, Processing, submitted)..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 text-sm outline-none placeholder:text-slate-300 text-slate-700"
        />
        <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-slate-300 text-teal-500"
          />
          Auto-scroll
        </label>
        <span className="text-[11px] text-slate-400">
          {filteredLines.length} / {lines.length} lines
        </span>
      </div>

      {/* Log viewer */}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0d1117] shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-800 bg-[#161b22] px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            </div>
            <span className="text-xs text-slate-500 font-mono">applypilot — raw output</span>
            {isRunning && (
              <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                STREAMING
              </span>
            )}
          </div>
        </div>

        <div
          ref={logRef}
          className="max-h-[600px] overflow-y-auto p-4 font-mono text-[12px] leading-5 select-text"
        >
          {filteredLines.length === 0 ? (
            <div className="py-12 text-center text-slate-600">
              {lines.length === 0
                ? 'No logs yet. Launch the agent to see output here.'
                : `No lines match "${filter}"`}
            </div>
          ) : (
            filteredLines.map((line, i) => (
              <div
                key={i}
                className={`group flex hover:bg-slate-800/50 rounded px-1 ${getLineClass(line)}`}
              >
                <span className="mr-4 min-w-[3ch] select-none text-right text-slate-700">
                  {i + 1}
                </span>
                <span className="whitespace-pre-wrap break-all flex-1">{line}</span>
                <button
                  onClick={() => { navigator.clipboard.writeText(line); }}
                  className="ml-2 opacity-0 group-hover:opacity-100 text-slate-600 hover:text-slate-400 flex-shrink-0"
                  title="Copy line"
                >
                  <Copy className="h-3 w-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function getLineClass(line) {
  if (line.includes('ERROR') || line.includes('Traceback') || line.includes('Error:') || line.includes('failed'))
    return 'text-red-400';
  if (line.includes('WARNING') || line.includes('⚠'))
    return 'text-amber-400';
  if (line.includes('SUCCESS') || line.includes('✅') || line.includes('submitted'))
    return 'text-emerald-400';
  if (line.includes('INFO') || line.includes('🚀') || line.includes('Starting'))
    return 'text-sky-300';
  return 'text-slate-300';
}
