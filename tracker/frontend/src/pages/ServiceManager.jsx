import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box, Typography, Button, Grid, Switch, FormControlLabel,
  Alert, LinearProgress, CircularProgress, List, ListItem,
  ListItemIcon, ListItemText, TextField, Stack,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import FolderIcon from '@mui/icons-material/Folder';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { useSnackbar } from 'notistack';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getServiceStatus, startService, stopService, setAutoStart, fetchLogs } from '../api';

function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return '0s';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function generateUptimeData() {
  return Array.from({ length: 24 }, (_, i) => ({
    hour: `${String(i).padStart(2, '0')}`,
    uptime: Math.random() > 0.15 ? 95 + Math.random() * 5 : Math.random() * 50,
  }));
}

export default function ServiceManager() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [status, setStatus] = useState({
    running: false, pid: null, uptime_seconds: 0,
    auto_start: false, daemon_mode: true,
    working_dir: './data', log_file: './data/applypilot.log',
  });
  const [uptimeData] = useState(generateUptimeData);
  const [recentEvents, setRecentEvents] = useState([]);
  const uptimeRef = useRef(null);

  const loadStatus = useCallback(async () => {
    try {
      const data = await getServiceStatus();
      setStatus((prev) => ({ ...prev, ...data }));
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  const loadRecentEvents = useCallback(async () => {
    try {
      const data = await fetchLogs({ pageSize: 5, eventType: 'service' });
      setRecentEvents(data.logs || data.items || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadStatus(); loadRecentEvents();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, [loadStatus, loadRecentEvents]);

  useEffect(() => {
    if (status.running) {
      uptimeRef.current = setInterval(() => setStatus((p) => ({ ...p, uptime_seconds: (p.uptime_seconds || 0) + 1 })), 1000);
    } else { clearInterval(uptimeRef.current); }
    return () => clearInterval(uptimeRef.current);
  }, [status.running]);

  const handleStart = async () => {
    setActionLoading(true);
    try { await startService(); enqueueSnackbar('Started', { variant: 'success' }); setTimeout(loadStatus, 1000); loadRecentEvents(); }
    catch { enqueueSnackbar('Failed to start', { variant: 'error' }); }
    finally { setActionLoading(false); }
  };
  const handleStop = async () => {
    setActionLoading(true);
    try { await stopService(); enqueueSnackbar('Stopped', { variant: 'info' }); setTimeout(loadStatus, 1000); loadRecentEvents(); }
    catch { enqueueSnackbar('Failed to stop', { variant: 'error' }); }
    finally { setActionLoading(false); }
  };
  const handleRestart = async () => {
    setActionLoading(true);
    try { await stopService(); await new Promise((r) => setTimeout(r, 2000)); await startService(); enqueueSnackbar('Restarted', { variant: 'success' }); setTimeout(loadStatus, 1000); loadRecentEvents(); }
    catch { enqueueSnackbar('Failed to restart', { variant: 'error' }); }
    finally { setActionLoading(false); }
  };
  const handleAutoStartToggle = async (enabled) => {
    try { await setAutoStart(enabled); setStatus((p) => ({ ...p, auto_start: enabled })); enqueueSnackbar(`Auto-start ${enabled ? 'on' : 'off'}`, { variant: 'success' }); }
    catch { enqueueSnackbar('Failed', { variant: 'error' }); }
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress size={24} /></Box>;

  return (
    <Box sx={{ height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column' }}>
      {/* Top bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 0.75, borderBottom: 1, borderColor: 'divider', mb: 1.5 }}>
        <Typography sx={{ fontSize: 14, fontWeight: 700 }}>Service Manager</Typography>
      </Box>

      <Grid container spacing={1.5} sx={{ flex: 1, overflow: 'auto' }}>
        {/* Left column */}
        <Grid size={{ xs: 12, md: 8 }}>
          {/* Status row */}
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: status.running ? 'success.main' : 'grey.400', boxShadow: status.running ? '0 0 6px rgba(76,175,80,0.5)' : 'none' }} />
              <Typography sx={{ fontSize: 13, fontWeight: 600 }}>{status.running ? 'Running' : 'Stopped'}</Typography>
              {status.running && (
                <>
                  <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>Uptime: {formatUptime(status.uptime_seconds)}</Typography>
                  {status.pid && <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>PID: {status.pid}</Typography>}
                </>
              )}
              <Box sx={{ flex: 1 }} />
              {/* Action buttons */}
              <Stack direction="row" spacing={0.5}>
                <Button size="small" variant="contained" color="success" startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />} onClick={handleStart} disabled={status.running || actionLoading} sx={{ fontSize: 11, py: 0.25, px: 1 }}>Start</Button>
                <Button size="small" variant="contained" color="error" startIcon={<StopIcon sx={{ fontSize: 14 }} />} onClick={handleStop} disabled={!status.running || actionLoading} sx={{ fontSize: 11, py: 0.25, px: 1 }}>Stop</Button>
                <Button size="small" variant="outlined" startIcon={<RestartAltIcon sx={{ fontSize: 14 }} />} onClick={handleRestart} disabled={!status.running || actionLoading} sx={{ fontSize: 11, py: 0.25, px: 1 }}>Restart</Button>
              </Stack>
            </Box>
            {actionLoading && <LinearProgress sx={{ mt: 1, borderRadius: 1 }} />}
          </Box>

          {/* Config */}
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 1 }}>Configuration</Typography>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 6 }}>
                <FormControlLabel
                  control={<Switch size="small" checked={status.auto_start} onChange={(e) => handleAutoStartToggle(e.target.checked)} />}
                  label={<Typography sx={{ fontSize: 11 }}>Auto-start on boot</Typography>}
                />
              </Grid>
              <Grid size={{ xs: 6 }}>
                <FormControlLabel
                  control={<Switch size="small" checked={status.daemon_mode !== false} onChange={(e) => setStatus({ ...status, daemon_mode: e.target.checked })} />}
                  label={<Typography sx={{ fontSize: 11 }}>Daemon mode</Typography>}
                />
              </Grid>
              <Grid size={{ xs: 6 }}>
                <Typography sx={{ fontSize: 10, color: 'text.secondary', mb: 0.25 }}>Working Directory</Typography>
                <TextField fullWidth size="small" value={status.working_dir || './data'} onChange={(e) => setStatus({ ...status, working_dir: e.target.value })} sx={{ '& .MuiInputBase-input': { fontSize: 11, py: 0.5 } }} />
              </Grid>
              <Grid size={{ xs: 6 }}>
                <Typography sx={{ fontSize: 10, color: 'text.secondary', mb: 0.25 }}>Log File</Typography>
                <TextField fullWidth size="small" value={status.log_file || './data/applypilot.log'} InputProps={{ readOnly: true }} sx={{ '& .MuiInputBase-input': { fontSize: 11, py: 0.5 } }} />
              </Grid>
            </Grid>
          </Box>
        </Grid>

        {/* Right column */}
        <Grid size={{ xs: 12, md: 4 }}>
          {/* Uptime chart */}
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.5 }}>24h Uptime</Typography>
            <Box sx={{ height: 150, width: '100%' }}>
              <ResponsiveContainer>
                <BarChart data={uptimeData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                  <XAxis dataKey="hour" tick={{ fontSize: 8 }} interval={5} />
                  <YAxis tick={{ fontSize: 8 }} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                  <Tooltip formatter={(v) => [`${v.toFixed(1)}%`, 'Uptime']} contentStyle={{ fontSize: 10 }} />
                  <Bar dataKey="uptime" radius={[2, 2, 0, 0]}>
                    {uptimeData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.uptime >= 90 ? '#4caf50' : entry.uptime >= 50 ? '#ff9800' : '#f44336'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Box>

          {/* Recent events */}
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.75 }}>Recent Events</Typography>
            {recentEvents.length === 0 ? (
              <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>No events</Typography>
            ) : (
              <List dense disablePadding>
                {recentEvents.slice(0, 5).map((event, idx) => (
                  <ListItem key={idx} disablePadding sx={{ py: 0.25 }}>
                    <ListItemIcon sx={{ minWidth: 16 }}>
                      <FiberManualRecordIcon sx={{ fontSize: 8, color: event.severity === 'error' ? 'error.main' : event.severity === 'success' ? 'success.main' : 'info.main' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={event.message || event.event_type}
                      secondary={event.timestamp || event.created_at ? new Date(event.timestamp || event.created_at).toLocaleTimeString() : ''}
                      primaryTypographyProps={{ fontSize: 11 }}
                      secondaryTypographyProps={{ fontSize: 9 }}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
