import { Box, Typography, LinearProgress, Stack, Chip, Paper, Grid } from '@mui/material';
import SpeedIcon from '@mui/icons-material/Speed';
import ShieldIcon from '@mui/icons-material/Shield';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ReplayIcon from '@mui/icons-material/Replay';

/**
 * Real-time pipeline status showing:
 * - Daily cap progress
 * - Retry queue status
 * - Connection status
 * - Current cycle stats
 */
export default function PipelineStatus({ events = [], isConnected = false, liveStats = null }) {
  // Compute live metrics from events
  const applied = events.filter((e) => e.event_type === 'submitted' || e.data?.stage === 'submitted').length;
  const discovered = events.filter((e) => e.event_type === 'discovered' || e.data?.stage === 'discovered').length;
  const errors = events.filter((e) => e.event_type === 'error' || e.data?.stage === 'error').length;
  const external = events.filter((e) => e.event_type === 'external' || e.data?.status === 'external').length;

  const dailyCap = liveStats?.daily_cap || { today_count: applied, daily_limit: 80 };
  const capPercent = Math.min(100, (dailyCap.today_count / dailyCap.daily_limit) * 100);

  return (
    <Paper elevation={0} variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" spacing={1} mb={2}>
        <SpeedIcon fontSize="small" color="primary" />
        <Typography variant="subtitle2" fontWeight={600}>Pipeline Status</Typography>
        <Chip
          label={isConnected ? 'LIVE' : 'OFFLINE'}
          size="small"
          color={isConnected ? 'success' : 'default'}
          variant="filled"
          sx={{ ml: 'auto' }}
        />
      </Stack>

      <Grid container spacing={2}>
        <Grid item xs={6}>
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700} color="primary.main">{discovered}</Typography>
            <Typography variant="caption" color="text.secondary">Discovered</Typography>
          </Box>
        </Grid>
        <Grid item xs={6}>
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700} color="success.main">{applied}</Typography>
            <Typography variant="caption" color="text.secondary">Applied</Typography>
          </Box>
        </Grid>
        <Grid item xs={6}>
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700} color="warning.main">{external}</Typography>
            <Typography variant="caption" color="text.secondary">External</Typography>
          </Box>
        </Grid>
        <Grid item xs={6}>
          <Box textAlign="center">
            <Typography variant="h4" fontWeight={700} color="error.main">{errors}</Typography>
            <Typography variant="caption" color="text.secondary">Errors</Typography>
          </Box>
        </Grid>
      </Grid>

      {/* Daily Cap */}
      <Box mt={2}>
        <Stack direction="row" justifyContent="space-between" mb={0.5}>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <ShieldIcon sx={{ fontSize: 14 }} />
            <Typography variant="caption">Daily Cap</Typography>
          </Stack>
          <Typography variant="caption" fontWeight={600}>
            {dailyCap.today_count}/{dailyCap.daily_limit}
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={capPercent}
          color={capPercent > 75 ? 'warning' : 'primary'}
          sx={{ height: 6, borderRadius: 3 }}
        />
      </Box>

      {/* Retry Queue */}
      {liveStats?.retry_pending > 0 && (
        <Stack direction="row" spacing={1} alignItems="center" mt={1.5}>
          <ReplayIcon sx={{ fontSize: 14 }} color="warning" />
          <Typography variant="caption">
            {liveStats.retry_pending} job(s) in retry queue
          </Typography>
        </Stack>
      )}
    </Paper>
  );
}
