import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Chip,
  Switch,
  FormControlLabel,
  Alert,
  LinearProgress,
} from '@mui/material';
import CloudIcon from '@mui/icons-material/Cloud';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { useSnackbar } from 'notistack';
import { getServiceStatus, startService, stopService, setAutoStart } from '../api';

function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function ServiceManager() {
  const { enqueueSnackbar } = useSnackbar();
  const [status, setStatus] = useState({
    running: false,
    pid: null,
    uptime_seconds: 0,
    auto_start: false,
  });
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const data = await getServiceStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to load service status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  async function handleStart() {
    setActionLoading(true);
    try {
      await startService();
      enqueueSnackbar('Service started', { variant: 'success' });
      setTimeout(loadStatus, 1000);
    } catch (err) {
      enqueueSnackbar('Failed to start service', { variant: 'error' });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStop() {
    setActionLoading(true);
    try {
      await stopService();
      enqueueSnackbar('Service stopped', { variant: 'info' });
      setTimeout(loadStatus, 1000);
    } catch (err) {
      enqueueSnackbar('Failed to stop service', { variant: 'error' });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAutoStartToggle(enabled) {
    try {
      await setAutoStart(enabled);
      setStatus((prev) => ({ ...prev, auto_start: enabled }));
      enqueueSnackbar(`Auto-start ${enabled ? 'enabled' : 'disabled'}`, { variant: 'success' });
    } catch (err) {
      enqueueSnackbar('Failed to update auto-start', { variant: 'error' });
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <Typography color="text.secondary">Loading service status...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <CloudIcon color="primary" />
        <Typography variant="h4">Service Manager</Typography>
      </Box>

      <Grid container spacing={2.5}>
        {/* Status Card */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Service Status
              </Typography>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Chip
                  label={status.running ? 'Running' : 'Stopped'}
                  color={status.running ? 'success' : 'default'}
                  variant="filled"
                />
                {status.pid && (
                  <Typography variant="caption" color="text.secondary">
                    PID: {status.pid}
                  </Typography>
                )}
              </Box>

              {status.running && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <AccessTimeIcon fontSize="small" color="action" />
                  <Typography variant="body2">
                    Uptime: {formatUptime(status.uptime_seconds)}
                  </Typography>
                </Box>
              )}

              {actionLoading && <LinearProgress sx={{ mb: 2 }} />}

              <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleStart}
                  disabled={status.running || actionLoading}
                  size="small"
                >
                  Start
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleStop}
                  disabled={!status.running || actionLoading}
                  size="small"
                >
                  Stop
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<RestartAltIcon />}
                  onClick={async () => { await handleStop(); setTimeout(handleStart, 2000); }}
                  disabled={!status.running || actionLoading}
                  size="small"
                >
                  Restart
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Settings Card */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Service Settings
              </Typography>

              <FormControlLabel
                control={
                  <Switch
                    checked={status.auto_start}
                    onChange={(e) => handleAutoStartToggle(e.target.checked)}
                    size="small"
                  />
                }
                label="Auto-start on boot"
              />

              <Alert severity="info" sx={{ mt: 2, fontSize: '0.7rem' }}>
                When enabled, the agent will automatically start as a background daemon when the system boots.
              </Alert>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
