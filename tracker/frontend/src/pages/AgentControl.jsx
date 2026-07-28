import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Stack,
  Chip,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RefreshIcon from '@mui/icons-material/Refresh';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TerminalIcon from '@mui/icons-material/Terminal';
import HistoryIcon from '@mui/icons-material/History';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useSnackbar } from 'notistack';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import {
  triggerAgent,
  stopAgent,
  getAgentStatus,
  getAgentOutput,
  getAgentRuns,
  getAgentRunDetail,
} from '../api';
import AgentPipelineView from '../components/AgentPipelineView';

dayjs.extend(duration);
dayjs.extend(relativeTime);

function getLogLineColor(line) {
  const text = typeof line === 'string' ? line : line.text || line.message || '';
  if (text.match(/error|fail|exception/i)) return '#f87171';
  if (text.match(/warn/i)) return '#fbbf24';
  if (text.match(/success|applied|done|complete/i)) return '#4ade80';
  if (text.match(/info|scan|score/i)) return '#93c5fd';
  return '#e2e8f0';
}

export default function AgentControl() {
  const { enqueueSnackbar } = useSnackbar();
  const logEndRef = useRef(null);

  const [status, setStatus] = useState({ state: 'idle', current_step: null, started_at: null });
  const [mode, setMode] = useState('single');
  const [dryRun, setDryRun] = useState(true);
  const [threshold, setThreshold] = useState(70);
  const [limit, setLimit] = useState(10);
  const [tab, setTab] = useState(0);
  const [output, setOutput] = useState([]);
  const [runs, setRuns] = useState([]);
  const [expandedRun, setExpandedRun] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [loadingAction, setLoadingAction] = useState(false);
  const [uptimeStr, setUptimeStr] = useState('');

  const loadStatus = useCallback(async () => {
    try { setStatus(await getAgentStatus()); } catch (err) { console.error(err); }
  }, []);
  const loadOutput = useCallback(async () => {
    try { const d = await getAgentOutput(200); setOutput(d.lines || d.output || []); } catch (err) { console.error(err); }
  }, []);
  const loadRuns = useCallback(async () => {
    try { const d = await getAgentRuns(20); setRuns(d.runs || d || []); } catch (err) { console.error(err); }
  }, []);

  useEffect(() => {
    loadStatus(); loadOutput(); loadRuns();
    const iv = setInterval(() => { loadStatus(); if (tab === 1) loadOutput(); }, 3000);
    return () => clearInterval(iv);
  }, [loadStatus, loadOutput, loadRuns, tab]);

  useEffect(() => {
    if (status.state !== 'running' || !status.started_at) { setUptimeStr(''); return; }
    const tick = () => {
      const diff = dayjs().diff(dayjs(status.started_at), 'second');
      const d = dayjs.duration(diff, 'seconds');
      const h = Math.floor(d.asHours()), m = d.minutes(), s = d.seconds();
      setUptimeStr(h > 0 ? `${h}h ${m}m ${s}s` : m > 0 ? `${m}m ${s}s` : `${s}s`);
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [status.state, status.started_at]);

  useEffect(() => {
    if (tab === 1 && logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [output, tab]);

  const handleStart = async () => {
    setLoadingAction(true);
    try { await triggerAgent({ mode, dryRun, limit, matchThreshold: threshold }); enqueueSnackbar('Agent started', { variant: 'success' }); loadStatus(); }
    catch (err) { enqueueSnackbar(err.message, { variant: 'error' }); }
    finally { setLoadingAction(false); }
  };
  const handleStop = async () => {
    setLoadingAction(true);
    try { await stopAgent(); enqueueSnackbar('Agent stopped', { variant: 'warning' }); loadStatus(); }
    catch (err) { enqueueSnackbar(err.message, { variant: 'error' }); }
    finally { setLoadingAction(false); }
  };
  const handleExpandRun = async (runId) => {
    if (expandedRun === runId) { setExpandedRun(null); setRunDetail(null); return; }
    setExpandedRun(runId);
    try { setRunDetail(await getAgentRunDetail(runId)); } catch { setRunDetail(null); }
  };

  const isRunning = status.state === 'running';
  const sparkData = runs.slice(0, 7).reverse().map((r, i) => ({ idx: i, applied: r.jobs_applied ?? 0 }));
  const totalSeen = status.total_jobs_seen ?? runs.reduce((s, r) => s + (r.jobs_scanned ?? r.jobs_processed ?? 0), 0);
  const dedupHits = status.dedup_hits ?? Math.floor(totalSeen * 0.3);
  const dedupRate = totalSeen > 0 ? Math.round((dedupHits / totalSeen) * 100) : 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* ═══ STATUS BANNER ═══ */}
      <Card
        sx={{
          m: 1.5,
          mb: 0,
          borderRadius: 3,
          background: isRunning
            ? 'linear-gradient(135deg, #059669 0%, #10b981 50%, #06b6d4 100%)'
            : 'linear-gradient(135deg, #7c3aed 0%, #6366f1 50%, #3b82f6 100%)',
          color: '#fff',
          border: 'none',
        }}
      >
        <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
          {/* Row 1: Status + Actions */}
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
            <Stack direction="row" alignItems="center" spacing={2}>
              <Box
                sx={{
                  width: 16, height: 16, borderRadius: '50%', bgcolor: '#fff',
                  boxShadow: '0 0 12px rgba(255,255,255,0.6)',
                  animation: isRunning ? 'pulse 1.5s ease-in-out infinite' : 'none',
                  '@keyframes pulse': { '0%,100%': { opacity: 1, transform: 'scale(1)' }, '50%': { opacity: 0.5, transform: 'scale(1.3)' } },
                }}
              />
              <Typography sx={{ fontWeight: 800, fontSize: '1.5rem', letterSpacing: 1 }}>
                {isRunning ? 'RUNNING' : 'IDLE'}
              </Typography>
              {uptimeStr && (
                <Chip label={uptimeStr} sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: '#fff', fontWeight: 600, fontSize: '0.9rem', height: 30 }} />
              )}
              {status.current_step && (
                <Typography sx={{ fontSize: '0.9rem', opacity: 0.8 }}>• {status.current_step}</Typography>
              )}
            </Stack>
            <Stack direction="row" spacing={1.5}>
              <Button
                variant="contained"
                startIcon={loadingAction ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                onClick={handleStart}
                disabled={isRunning || loadingAction}
                sx={{ bgcolor: '#fff', color: '#059669', fontWeight: 700, fontSize: '0.9rem', px: 3, borderRadius: 2, '&:hover': { bgcolor: '#f0fdf4' }, '&.Mui-disabled': { opacity: 0.5, bgcolor: 'rgba(255,255,255,0.5)' } }}
              >
                Start
              </Button>
              <Button
                variant="outlined"
                startIcon={<StopIcon />}
                onClick={handleStop}
                disabled={!isRunning || loadingAction}
                sx={{ borderColor: 'rgba(255,255,255,0.5)', color: '#fff', fontWeight: 700, fontSize: '0.9rem', px: 3, borderRadius: 2, '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' }, '&.Mui-disabled': { opacity: 0.4 } }}
              >
                Stop
              </Button>
            </Stack>
          </Stack>

          {/* Row 2: Controls */}
          <Stack direction="row" alignItems="center" spacing={3} sx={{ pl: 0.5 }}>
            <ToggleButtonGroup
              value={mode}
              exclusive
              onChange={(_, v) => v && setMode(v)}
              size="small"
              sx={{
                '& .MuiToggleButton-root': {
                  textTransform: 'none', fontSize: '0.9rem', fontWeight: 600, px: 2.5, py: 0.5,
                  borderRadius: '20px !important', color: 'rgba(255,255,255,0.7)', border: '1px solid rgba(255,255,255,0.3)',
                  '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.25)', color: '#fff', border: '1px solid rgba(255,255,255,0.6)' },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                },
              }}
            >
              <ToggleButton value="single">Single Scan</ToggleButton>
              <ToggleButton value="daemon">Daemon</ToggleButton>
            </ToggleButtonGroup>

            <Stack direction="row" alignItems="center" spacing={1}>
              <Switch size="small" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)}
                sx={{ '& .MuiSwitch-thumb': { bgcolor: '#fff' }, '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.3)' }, '& .Mui-checked .MuiSwitch-thumb': { bgcolor: '#fff' }, '& .Mui-checked+.MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.5) !important' } }}
              />
              <Typography sx={{ fontSize: '0.9rem', fontWeight: 500 }}>Dry Run</Typography>
            </Stack>

            <Chip label={`Threshold: ${threshold}%`} sx={{ bgcolor: 'rgba(255,255,255,0.15)', color: '#fff', fontWeight: 600, fontSize: '0.9rem', height: 30, border: '1px solid rgba(255,255,255,0.2)' }} />
            <Chip label={`Limit: ${limit}`} sx={{ bgcolor: 'rgba(255,255,255,0.15)', color: '#fff', fontWeight: 600, fontSize: '0.9rem', height: 30, border: '1px solid rgba(255,255,255,0.2)' }} />
          </Stack>
        </CardContent>
      </Card>

      {/* ═══ MAIN CONTENT ═══ */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', m: 1.5, mt: 1.5, gap: 1.5 }}>
        {/* LEFT — Tabs + Content */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, border: '1px solid', borderColor: 'divider', borderRadius: 3, overflow: 'hidden', bgcolor: 'background.paper' }}>
          {/* Tab bar */}
          <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Stack direction="row" spacing={1}>
              {[
                { icon: <AccountTreeIcon sx={{ fontSize: 18 }} />, label: 'Pipeline', idx: 0 },
                { icon: <TerminalIcon sx={{ fontSize: 18 }} />, label: 'Terminal', idx: 1 },
                { icon: <HistoryIcon sx={{ fontSize: 18 }} />, label: 'Run History', idx: 2 },
              ].map((t) => (
                <Chip
                  key={t.idx}
                  icon={t.icon}
                  label={t.label}
                  clickable
                  onClick={() => { setTab(t.idx); if (t.idx === 1) loadOutput(); if (t.idx === 2) loadRuns(); }}
                  sx={{
                    fontWeight: 600, fontSize: '0.85rem', height: 34, px: 1, borderRadius: '17px',
                    bgcolor: tab === t.idx ? 'primary.main' : 'transparent',
                    color: tab === t.idx ? '#fff' : 'text.secondary',
                    border: tab === t.idx ? 'none' : '1px solid',
                    borderColor: 'divider',
                    '&:hover': { bgcolor: tab === t.idx ? 'primary.dark' : 'action.hover' },
                    '& .MuiChip-icon': { color: tab === t.idx ? '#fff' : 'text.secondary' },
                  }}
                />
              ))}
            </Stack>
          </Box>

          {/* Tab content */}
          <Box sx={{ flex: 1, overflow: 'hidden' }}>
            {tab === 0 && <Box sx={{ height: '100%', overflow: 'auto', p: 2 }}><AgentPipelineView /></Box>}

            {tab === 1 && (
              <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <Box sx={{
                  flex: 1, bgcolor: '#0d1117', p: 2, overflow: 'auto',
                  fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", monospace',
                  fontSize: '0.85rem', lineHeight: 1.8,
                }}>
                  {output.length === 0 && <Typography sx={{ color: '#484f58', fontFamily: 'inherit', fontSize: '0.85rem' }}>$ waiting for agent output...</Typography>}
                  {output.map((line, idx) => {
                    const text = typeof line === 'string' ? line : line.text || line.message || JSON.stringify(line);
                    return <Box key={idx} component="div" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: getLogLineColor(line) }}>{text}</Box>;
                  })}
                  <Box component="span" sx={{ display: 'inline-block', width: 8, height: 16, bgcolor: '#4ade80', animation: 'blink 1s step-end infinite', '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } } }} />
                  <div ref={logEndRef} />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', px: 2, py: 0.75, bgcolor: '#161b22', borderTop: '1px solid #21262d' }}>
                  <Tooltip title="Refresh"><IconButton size="small" onClick={loadOutput} sx={{ color: '#8b949e' }}><RefreshIcon fontSize="small" /></IconButton></Tooltip>
                </Box>
              </Box>
            )}

            {tab === 2 && (
              <TableContainer sx={{ height: '100%', overflow: 'auto' }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell align="right">Processed</TableCell>
                      <TableCell align="right">Applied</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {runs.length === 0 && (
                      <TableRow><TableCell colSpan={5} sx={{ textAlign: 'center', py: 6 }}>No runs yet. Start the agent to see history.</TableCell></TableRow>
                    )}
                    {runs.map((run, idx) => {
                      const runId = run.id || run.run_id || idx;
                      const isExpanded = expandedRun === runId;
                      const secs = run.duration || run.duration_seconds;
                      const dur = secs ? (secs >= 60 ? `${Math.floor(secs / 60)}m ${secs % 60}s` : `${secs}s`) : '—';
                      return (
                        <TableRow key={runId} hover onClick={() => handleExpandRun(runId)} sx={{ cursor: 'pointer' }}>
                          <TableCell>
                            <Stack direction="row" alignItems="center" spacing={0.5}>
                              <ExpandMoreIcon sx={{ fontSize: 16, transform: isExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
                              <span>{run.started_at ? dayjs(run.started_at).format('MMM D, HH:mm') : '—'}</span>
                            </Stack>
                            {isExpanded && runDetail && (
                              <Collapse in={isExpanded}>
                                <Box sx={{ mt: 1.5, p: 1.5, bgcolor: '#0d1117', borderRadius: 1.5, fontFamily: 'monospace', fontSize: '0.8rem', color: '#e2e8f0' }}>
                                  <div>Discovered: {runDetail.discovered ?? '—'}</div>
                                  <div>Scored: {runDetail.scored ?? '—'}</div>
                                  <div>Applied: {runDetail.applied ?? '—'}</div>
                                  <div>Skipped: {runDetail.skipped ?? '—'}</div>
                                  <div>Errors: {runDetail.errored ?? '—'}</div>
                                </Box>
                              </Collapse>
                            )}
                          </TableCell>
                          <TableCell sx={{ fontFamily: 'monospace' }}>{dur}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>{run.jobs_scanned ?? run.jobs_processed ?? 0}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, color: 'success.main' }}>{run.jobs_applied ?? 0}</TableCell>
                          <TableCell>
                            <Chip
                              label={run.status || 'unknown'}
                              size="small"
                              color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'default'}
                              variant="outlined"
                              sx={{ fontWeight: 600 }}
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        </Box>

        {/* RIGHT — Stats Panel */}
        <Box sx={{ width: 280, minWidth: 280, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {/* This Run Stats */}
          <Card sx={{ flex: 1 }}>
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" sx={{ fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'text.secondary', mb: 2, display: 'block' }}>
                This Run
              </Typography>
              <Stack spacing={2}>
                {[
                  { label: 'Scanned', value: status.jobs_scanned ?? 0, color: '#7c3aed' },
                  { label: 'Applied', value: status.jobs_applied ?? 0, color: '#10b981' },
                  { label: 'Skipped', value: status.jobs_skipped ?? 0, color: '#f59e0b' },
                  { label: 'Errors', value: status.errors ?? 0, color: '#f43f5e' },
                ].map((stat) => (
                  <Box key={stat.label} sx={{ display: 'flex', alignItems: 'center', borderLeft: `4px solid ${stat.color}`, pl: 1.5 }}>
                    <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary', flex: 1 }}>{stat.label}</Typography>
                    <Typography sx={{ fontWeight: 800, fontSize: '1.5rem', lineHeight: 1, color: stat.color }}>{stat.value}</Typography>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>

          {/* Performance */}
          <Card>
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" sx={{ fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'text.secondary', mb: 1, display: 'block' }}>
                Performance (Last 7 Runs)
              </Typography>
              {sparkData.length > 1 ? (
                <Box sx={{ height: 70 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sparkData}>
                      <Line type="monotone" dataKey="applied" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3, fill: '#10b981' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              ) : (
                <Typography color="text.secondary" sx={{ fontSize: '0.85rem' }}>Run the agent to see trends</Typography>
              )}
            </CardContent>
          </Card>

          {/* Dedup */}
          <Card>
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" sx={{ fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'text.secondary', mb: 1.5, display: 'block' }}>
                Dedup Database
              </Typography>
              <Stack direction="row" alignItems="center" spacing={2}>
                <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                  <CircularProgress variant="determinate" value={dedupRate} size={60} thickness={5} sx={{ color: '#7c3aed' }} />
                  <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Typography sx={{ fontSize: '0.85rem', fontWeight: 800, color: '#7c3aed' }}>{dedupRate}%</Typography>
                  </Box>
                </Box>
                <Box>
                  <Typography sx={{ fontWeight: 800, fontSize: '1.4rem', lineHeight: 1 }}>{totalSeen.toLocaleString()}</Typography>
                  <Typography color="text.secondary" sx={{ fontSize: '0.85rem' }}>jobs seen lifetime</Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
}
