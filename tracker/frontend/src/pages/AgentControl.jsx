import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Stack,
  Chip,
  Switch,
  Slider,
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
} from '../api';
import AgentPipelineView from '../components/AgentPipelineView';
import { motion } from 'framer-motion';
import { AnimatedNumber } from '../components/Animated';

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
  const [searchMode, setSearchMode] = useState('active');
  const [tab, setTab] = useState(0);
  const [output, setOutput] = useState([]);
  const [runs, setRuns] = useState([]);
  const [expandedRun, setExpandedRun] = useState(null);
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
    try { await triggerAgent({ mode, dryRun, limit: limit === 0 ? null : limit, matchThreshold: threshold, searchMode }); enqueueSnackbar('Agent started', { variant: 'success' }); loadStatus(); }
    catch (err) { enqueueSnackbar(err.message, { variant: 'error' }); }
    finally { setLoadingAction(false); }
  };
  const handleStop = async () => {
    setLoadingAction(true);
    try { await stopAgent(); enqueueSnackbar('Agent stopped', { variant: 'warning' }); loadStatus(); }
    catch (err) { enqueueSnackbar(err.message, { variant: 'error' }); }
    finally { setLoadingAction(false); }
  };

  const isRunning = status.state === 'running';
  const sparkData = runs.slice(0, 7).reverse().map((r, i) => ({ idx: i, applied: r.jobs_applied ?? 0 }));
  const totalSeen = status.total_jobs_seen ?? runs.reduce((s, r) => s + (r.jobs_scanned ?? r.jobs_processed ?? 0), 0);
  const dedupHits = status.dedup_hits ?? Math.floor(totalSeen * 0.3);
  const dedupRate = totalSeen > 0 ? Math.round((dedupHits / totalSeen) * 100) : 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', p: 2 }}>
      {/* ═══ CONTROL PANEL ═══ */}
      <Typography variant="h3" sx={{ mb: 2 }}>Agent Control</Typography>
      <Box sx={{ mb: 0 }}>
        {/* Status Row */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <Box sx={{ 
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          p: 2.5, mb: 2, borderRadius: '12px',
          bgcolor: isRunning ? '#E6F5F2' : 'background.paper',
          border: '1px solid',
          borderColor: isRunning ? '#067D68' : '#D5DBDB',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        }}>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <Box sx={{
              width: 12, height: 12, borderRadius: '50%',
              bgcolor: isRunning ? '#067D68' : '#545B64',
              boxShadow: isRunning ? '0 0 8px #067D68' : 'none',
              animation: isRunning ? 'pulse 1.5s ease-in-out infinite' : 'none',
              '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
            }} />
            <Typography sx={{ fontWeight: 700, fontSize: '1rem' }}>
              {isRunning ? 'Agent Running' : 'Agent Idle'}
            </Typography>
            {uptimeStr && <Chip label={uptimeStr} size="small" sx={{ fontFamily: 'monospace', fontWeight: 600 }} />}
            {status.current_step && <Typography color="text.secondary">— {status.current_step}</Typography>}
          </Stack>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" size="small" color="primary"
              startIcon={loadingAction ? <CircularProgress size={14} color="inherit" /> : <PlayArrowIcon />}
              onClick={handleStart} disabled={isRunning || loadingAction}
            >Start</Button>
            <Button variant="outlined" size="small" color="error"
              startIcon={<StopIcon />}
              onClick={handleStop} disabled={!isRunning || loadingAction}
            >Stop</Button>
          </Stack>
        </Box>
        </motion.div>

        {/* Search Mode Selector */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.05 }}>
        <Box sx={{
          display: 'flex', gap: 1.5, mb: 2,
        }}>
          {[
            { key: 'aggressive', label: '🔥 Aggressive', desc: 'Max throughput, 55% bar, 15min scans', color: '#D13212' },
            { key: 'active', label: '⚡ Active', desc: 'Balanced, 70% bar, 30min scans', color: '#0073BB' },
            { key: 'passive', label: '🌊 Passive', desc: 'High bar only, 85%, every 2hrs', color: '#067D68' },
          ].map(m => (
            <Box key={m.key} onClick={() => {
              setSearchMode(m.key);
              if (m.key === 'aggressive') { setThreshold(55); setLimit(0); }
              else if (m.key === 'active') { setThreshold(70); setLimit(50); }
              else { setThreshold(85); setLimit(30); }
            }}
              sx={{
                flex: 1, p: 2, borderRadius: '12px', cursor: 'pointer',
                border: '2px solid', transition: 'all 0.2s',
                borderColor: searchMode === m.key ? m.color : '#D5DBDB',
                bgcolor: searchMode === m.key ? `${m.color}10` : 'background.paper',
                boxShadow: searchMode === m.key ? `0 0 0 1px ${m.color}` : 'none',
                '&:hover': { borderColor: m.color, bgcolor: `${m.color}08` },
              }}>
              <Typography fontWeight={700} fontSize={14}>{m.label}</Typography>
              <Typography variant="caption" color="text.secondary">{m.desc}</Typography>
            </Box>
          ))}
        </Box>
        </motion.div>

        {/* Config Row */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 }}>
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 3, p: 2.5, mb: 2,
          borderRadius: '12px', border: '1px solid', borderColor: '#D5DBDB', bgcolor: '#FFFFFF',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)', flexWrap: 'wrap',
        }}>
          {/* Mode Toggle */}
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mode</Typography>
            <ToggleButtonGroup value={mode} exclusive onChange={(_, v) => v && setMode(v)} size="small"
              sx={{ '& .MuiToggleButton-root': { textTransform: 'none', fontSize: '0.85rem', fontWeight: 600, px: 2, py: 0.25, borderRadius: '8px !important' } }}
            >
              <ToggleButton value="single">Single</ToggleButton>
              <ToggleButton value="daemon">Daemon</ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          <Box sx={{ width: 1, height: 24, bgcolor: 'divider' }} />

          {/* Dry Run Switch */}
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Dry Run</Typography>
            <Switch size="small" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          </Stack>

          <Box sx={{ width: 1, height: 24, bgcolor: 'divider' }} />

          {/* Threshold Slider */}
          <Stack spacing={0.5} sx={{ minWidth: 180, flex: 1 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Threshold</Typography>
              <Chip
                label={`${threshold}%`}
                size="small"
                color={threshold >= 80 ? 'success' : threshold >= 60 ? 'warning' : 'error'}
                sx={{ fontWeight: 700, fontFamily: 'monospace', minWidth: 48 }}
              />
            </Stack>
            <Slider
              value={threshold}
              onChange={(_, v) => setThreshold(v)}
              min={30}
              max={100}
              step={5}
              marks={[
                { value: 50, label: '50' },
                { value: 70, label: '70' },
                { value: 80, label: '80' },
                { value: 100, label: '100' },
              ]}
              size="small"
              sx={{
                '& .MuiSlider-markLabel': { fontSize: '0.65rem', color: 'text.secondary' },
                '& .MuiSlider-thumb': { width: 14, height: 14 },
              }}
            />
          </Stack>

          <Box sx={{ width: 1, height: 24, bgcolor: 'divider' }} />

          {/* Limit Slider */}
          <Stack spacing={0.5} sx={{ minWidth: 180, flex: 1 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Limit</Typography>
              <Chip
                label={limit === 0 ? '∞ No limit' : `${limit} jobs`}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 700, fontFamily: 'monospace', minWidth: 64 }}
              />
            </Stack>
            <Slider
              value={limit}
              onChange={(_, v) => setLimit(v)}
              min={0}
              max={100}
              step={5}
              marks={[
                { value: 0, label: '∞' },
                { value: 25, label: '25' },
                { value: 50, label: '50' },
                { value: 100, label: '100' },
              ]}
              size="small"
              sx={{
                '& .MuiSlider-markLabel': { fontSize: '0.65rem', color: 'text.secondary' },
                '& .MuiSlider-thumb': { width: 14, height: 14 },
              }}
            />
          </Stack>
        </Box>
        </motion.div>
      </Box>

      {/* ═══ MAIN CONTENT ═══ */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', mt: 2, gap: 2 }}>
        {/* LEFT — Tabs + Content */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'hidden', bgcolor: 'background.paper', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
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
                      const secs = parseInt(run.duration_seconds) || parseInt(run.duration) || 0;
                      const dur = secs ? (secs >= 60 ? `${Math.floor(secs / 60)}m ${secs % 60}s` : `${secs}s`) : '—';
                      const processed = parseInt(run.jobs_processed) || 0;
                      const applied = parseInt(run.jobs_applied) || 0;
                      const skipped = parseInt(run.jobs_skipped) || 0;
                      const paused = parseInt(run.jobs_paused) || 0;
                      const errored = parseInt(run.jobs_errored) || 0;
                      return (
                        <TableRow key={runId} hover onClick={() => setExpandedRun(isExpanded ? null : runId)} sx={{ cursor: 'pointer', '& td': { borderBottom: isExpanded ? 'none' : undefined } }}>
                          <TableCell>
                            <Stack direction="row" alignItems="center" spacing={0.5}>
                              <ExpandMoreIcon sx={{ fontSize: 16, transform: isExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
                              <span>{run.started_at ? dayjs(run.started_at).format('MMM D, HH:mm') : '—'}</span>
                            </Stack>
                            {isExpanded && (
                              <Collapse in={isExpanded}>
                                <Box sx={{ mt: 1.5, p: 2, bgcolor: '#F7F8F9', borderRadius: '8px', border: '1px solid #EAEDED' }}>
                                  <Stack spacing={1}>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Mode</Typography><Typography variant="body2" fontWeight={600}>{run.mode || '—'} {run.dry_run === 'True' || run.dry_run === true ? '(Dry Run)' : ''}</Typography></Stack>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Collection</Typography><Typography variant="body2" fontWeight={600}>{run.collection || '—'}</Typography></Stack>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Processed</Typography><Typography variant="body2" fontWeight={600}>{processed}</Typography></Stack>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Applied</Typography><Typography variant="body2" fontWeight={600} sx={{ color: '#067D68' }}>{applied}</Typography></Stack>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Skipped</Typography><Typography variant="body2" fontWeight={600}>{skipped}</Typography></Stack>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Paused</Typography><Typography variant="body2" fontWeight={600}>{paused}</Typography></Stack>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Errors</Typography><Typography variant="body2" fontWeight={600} sx={{ color: errored > 0 ? '#D13212' : 'inherit' }}>{errored}</Typography></Stack>
                                    {run.error_message && <Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Error</Typography><Typography variant="body2" color="error">{run.error_message}</Typography></Stack>}
                                  </Stack>
                                </Box>
                              </Collapse>
                            )}
                          </TableCell>
                          <TableCell sx={{ fontFamily: 'monospace' }}>{dur}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>{processed}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, color: '#067D68' }}>{applied}</TableCell>
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
                  { label: 'Scanned', value: status.jobs_scanned ?? 0, color: '#6B40B2' },
                  { label: 'Applied', value: status.jobs_applied ?? 0, color: '#10b981' },
                  { label: 'Skipped', value: status.jobs_skipped ?? 0, color: '#f59e0b' },
                  { label: 'Errors', value: status.errors ?? 0, color: '#f43f5e' },
                ].map((stat) => (
                  <Box key={stat.label} sx={{ display: 'flex', alignItems: 'center', borderLeft: `4px solid ${stat.color}`, pl: 1.5 }}>
                    <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary', flex: 1 }}>{stat.label}</Typography>
                    <Typography sx={{ fontWeight: 800, fontSize: '1.5rem', lineHeight: 1, color: stat.color }}><AnimatedNumber value={stat.value} /></Typography>
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
                  <CircularProgress variant="determinate" value={dedupRate} size={60} thickness={5} sx={{ color: '#6B40B2' }} />
                  <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Typography sx={{ fontSize: '0.85rem', fontWeight: 800, color: '#6B40B2' }}>{dedupRate}%</Typography>
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
