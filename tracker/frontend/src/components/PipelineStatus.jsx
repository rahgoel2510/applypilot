import { Box, Typography, LinearProgress, Stack, Paper, Chip, alpha } from '@mui/material';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import WorkIcon from '@mui/icons-material/Work';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

/**
 * Real-time pipeline status — redesigned for clarity.
 *
 * Layout:
 *   1. Connection badge (pulsing green dot + "Connected" or amber "Disconnected")
 *   2. Primary KPI row — large "Applied today" number + daily cap gauge
 *   3. Secondary metrics strip — Discovered | External | Errors (smaller, inline)
 *
 * Why this is better:
 *   - Hierarchy: the most important number (daily progress) dominates
 *   - Connection status uses natural language, not "OFFLINE"
 *   - Secondary stats are de-emphasized but still scannable
 *   - Progress gauge gives at-a-glance cap proximity
 */
export default function PipelineStatus({ events = [], isConnected = false, liveStats = null }) {
  // Compute live metrics from WebSocket events
  const applied = events.filter(
    (e) => e.event_type === 'submitted' || e.data?.stage === 'submitted'
  ).length;
  const discovered = events.filter(
    (e) => e.event_type === 'discovered' || e.data?.stage === 'discovered'
  ).length;
  const errors = events.filter(
    (e) => e.event_type === 'error' || e.data?.stage === 'error'
  ).length;
  const external = events.filter(
    (e) => e.event_type === 'external' || e.data?.status === 'external'
  ).length;

  const dailyCap = liveStats?.daily_cap || { today_count: applied, daily_limit: 80 };
  const capPercent = Math.min(100, (dailyCap.today_count / dailyCap.daily_limit) * 100);
  const capColor = capPercent > 90 ? 'error' : capPercent > 70 ? 'warning' : 'primary';

  return (
    <Paper
      elevation={0}
      variant="outlined"
      sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      {/* ─── Connection Status ─── */}
      <Chip
        icon={isConnected ? <WifiIcon sx={{ fontSize: 16 }} /> : <WifiOffIcon sx={{ fontSize: 16 }} />}
        label={isConnected ? 'Live' : 'Offline'}
        size="small"
        sx={{
          mb: 2,
          alignSelf: 'flex-start',
          fontWeight: 700,
          fontSize: '0.75rem',
          letterSpacing: '0.03em',
          height: 28,
          borderRadius: '14px',
          color: isConnected ? '#067D68' : '#D13212',
          bgcolor: isConnected ? '#E6F5F2' : '#FDF3F0',
          border: '1px solid',
          borderColor: isConnected ? '#067D68' : '#D13212',
          '& .MuiChip-icon': {
            color: isConnected ? '#067D68' : '#D13212',
            animation: isConnected ? 'pulse-icon 2s ease-in-out infinite' : 'none',
          },
          '@keyframes pulse-icon': {
            '0%, 100%': { opacity: 1, transform: 'scale(1)' },
            '50%': { opacity: 0.6, transform: 'scale(0.9)' },
          },
        }}
      />

      {/* ─── Primary KPI: Daily Applications Progress ─── */}
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="overline" sx={{ display: 'block', mb: 0.5 }}>
          Today's Applications
        </Typography>
        <Stack direction="row" alignItems="baseline" spacing={0.75}>
          <Typography variant="h1" fontWeight={700} color="text.primary" sx={{ lineHeight: 1 }}>
            {dailyCap.today_count}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            / {dailyCap.daily_limit}
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={capPercent}
          color={capColor}
          sx={{ mt: 1.5, height: 8, borderRadius: 4 }}
        />
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          {capPercent >= 100
            ? 'Daily cap reached — agent paused'
            : `${dailyCap.daily_limit - dailyCap.today_count} remaining before cap`}
        </Typography>
      </Box>

      {/* ─── Secondary Metrics Row ─── */}
      <Stack direction="row" spacing={1} sx={{ mt: 'auto' }}>
        <MetricChip
          icon={<WorkIcon sx={{ fontSize: 16 }} />}
          label="Discovered"
          value={discovered}
          colorToken="info.main"
          bgToken="info"
        />
        <MetricChip
          icon={<OpenInNewIcon sx={{ fontSize: 16 }} />}
          label="External"
          value={external}
          colorToken="warning.main"
          bgToken="warning"
        />
        <MetricChip
          icon={<WarningAmberIcon sx={{ fontSize: 16 }} />}
          label="Errors"
          value={errors}
          colorToken="error.main"
          bgToken="error"
        />
      </Stack>

      {/* ─── Retry Queue (only when relevant) ─── */}
      {liveStats?.retry_pending > 0 && (
        <Box
          sx={{
            mt: 1.5,
            px: 1.5,
            py: 0.75,
            borderRadius: 1.5,
            bgcolor: (theme) => alpha(theme.palette.warning.main, 0.08),
            border: '1px solid',
            borderColor: (theme) => alpha(theme.palette.warning.main, 0.2),
          }}
        >
          <Typography variant="caption" fontWeight={500} color="warning.main">
            {liveStats.retry_pending} job{liveStats.retry_pending > 1 ? 's' : ''} queued for retry
          </Typography>
        </Box>
      )}
    </Paper>
  );
}

/** Small metric pill for secondary stats */
function MetricChip({ icon, label, value, colorToken, bgToken }) {
  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        py: 1,
        px: 0.5,
        borderRadius: 2,
        bgcolor: (theme) => alpha(theme.palette[bgToken]?.main || theme.palette.grey[500], 0.06),
      }}
    >
      <Stack direction="row" alignItems="center" spacing={0.5} sx={{ color: colorToken, mb: 0.25 }}>
        {icon}
        <Typography variant="h4" fontWeight={700} color={colorToken}>
          {value}
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
        {label}
      </Typography>
    </Box>
  );
}
