import { Box, Typography, Stack, Paper, Divider, alpha } from '@mui/material';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { motion, AnimatePresence } from 'framer-motion';

dayjs.extend(relativeTime);

/**
 * Event styling tiers — events are grouped into visual weight levels:
 *   • CRITICAL: agent start/stop, cycle start/end — bold, colored left border
 *   • ACTION: submitted, discovered, external, inmail — medium weight, icon accent
 *   • STATUS: info, warnings, skipped — lighter, subtle styling
 *
 * This makes it possible to scan the feed and immediately find what matters.
 */
const EVENT_CONFIG = {
  // Critical — agent lifecycle
  agent_start: { tier: 'critical', color: '#067D68', icon: '🤖', label: 'Agent Started' },
  agent_stop: { tier: 'critical', color: '#D13212', icon: '⏹', label: 'Agent Stopped' },
  cycle_start: { tier: 'critical', color: '#0073BB', icon: '🚀', label: 'Cycle Started' },
  cycle_end: { tier: 'critical', color: '#6B40B2', icon: '📊', label: 'Cycle Complete' },
  // Action — job-level events
  discovered: { tier: 'action', color: '#0073BB', icon: '🔍', label: 'Discovered' },
  submitted: { tier: 'action', color: '#067D68', icon: '✅', label: 'Applied' },
  job_submitted: { tier: 'action', color: '#067D68', icon: '✅', label: 'Applied' },
  reached_out: { tier: 'action', color: '#6B40B2', icon: '✉️', label: 'InMail Sent' },
  inmail_drafted: { tier: 'action', color: '#6B40B2', icon: '✉️', label: 'InMail Draft' },
  error: { tier: 'action', color: '#D13212', icon: '⚠️', label: 'Error' },
  job_error: { tier: 'action', color: '#D13212', icon: '⚠️', label: 'Error' },
  // Status — informational
  skipped: { tier: 'status', color: '#EC7211', icon: '⏭️', label: 'Skipped' },
  paused: { tier: 'status', color: '#EC7211', icon: '⏸️', label: 'Paused' },
  info: { tier: 'status', color: '#545B64', icon: 'ℹ️', label: 'Info' },
  warning: { tier: 'status', color: '#EC7211', icon: '⚠️', label: 'Warning' },
};

const DEFAULT_CONFIG = { tier: 'status', color: '#545B64', icon: '•', label: 'Event' };

export default function LiveEventFeed({ events = [], maxItems = 15 }) {
  const visibleEvents = events.slice(0, maxItems);

  return (
    <Paper
      sx={{ p: 2.5, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
      elevation={0}
      variant="outlined"
    >
      {/* ─── Header ─── */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
        <FiberManualRecordIcon
          sx={{
            fontSize: 10,
            color: events.length > 0 ? 'success.main' : 'grey.400',
            animation: events.length > 0 ? 'pulse 2s infinite' : 'none',
            '@keyframes pulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.4 },
            },
          }}
        />
        <Typography variant="h5" fontWeight={600}>
          Activity Feed
        </Typography>
        {events.length > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto !important' }}>
            {events.length} event{events.length !== 1 ? 's' : ''}
          </Typography>
        )}
      </Stack>
      <Divider sx={{ mb: 1.5 }} />

      {/* ─── Event List ─── */}
      <Box sx={{ overflow: 'auto', flex: 1, mx: -0.5, px: 0.5 }}>
        <AnimatePresence initial={false}>
          {visibleEvents.map((evt, idx) => {
            const data = evt.data || {};
            const eventType = evt.event_type || data.stage || 'info';
            const config = EVENT_CONFIG[eventType] || DEFAULT_CONFIG;
            return (
              <motion.div
                key={`${evt.timestamp}-${idx}`}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2, delay: idx * 0.02 }}
              >
                <EventRow config={config} data={data} timestamp={evt.timestamp} />
              </motion.div>
            );
          })}
        </AnimatePresence>
        {visibleEvents.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 6 }}>
            <Typography variant="body2" color="text.secondary">
              Waiting for pipeline events…
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Events will appear here when the agent runs
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}

/** Individual event row — styling varies by tier */
function EventRow({ config, data, timestamp }) {
  const { tier, color, icon, label } = config;

  const isCritical = tier === 'critical';
  const isAction = tier === 'action';

  // Build the main text line
  const mainText = data.title || data.message || label;
  const subParts = [];
  if (data.company) subParts.push(data.company);
  if (data.location) subParts.push(data.location);
  if (data.match_score != null) subParts.push(`${Math.round(data.match_score * 100)}% match`);
  // For non-job events, show the message as subtitle if title already used
  if (!data.company && data.message && data.title) subParts.push(data.message.slice(0, 80));

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1.25,
        py: isCritical ? 1 : 0.75,
        px: 1,
        mb: 0.5,
        borderRadius: 1.5,
        borderLeft: isCritical ? `3px solid ${color}` : '3px solid transparent',
        bgcolor: isCritical
          ? (theme) => alpha(color, theme.palette.mode === 'dark' ? 0.08 : 0.04)
          : 'transparent',
        '&:hover': {
          bgcolor: (theme) => alpha(color, theme.palette.mode === 'dark' ? 0.1 : 0.05),
        },
        transition: 'background-color 0.15s ease',
      }}
    >
      {/* Icon */}
      <Typography
        component="span"
        sx={{
          fontSize: isCritical ? 18 : 15,
          lineHeight: '22px',
          flexShrink: 0,
          mt: '1px',
        }}
        aria-hidden
      >
        {icon}
      </Typography>

      {/* Content */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" alignItems="center" spacing={0.75}>
          <Typography
            variant="body2"
            noWrap
            sx={{
              fontWeight: isCritical ? 600 : isAction ? 500 : 400,
              color: isCritical ? color : 'text.primary',
              flex: 1,
              minWidth: 0,
            }}
          >
            {mainText}
          </Typography>
          {/* Timestamp right-aligned */}
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ flexShrink: 0, fontSize: '0.68rem' }}
          >
            {timestamp ? dayjs(timestamp).fromNow() : ''}
          </Typography>
        </Stack>
        {subParts.length > 0 && (
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
            sx={{ mt: 0.125, display: 'block' }}
          >
            {subParts.join(' · ')}
          </Typography>
        )}
      </Box>

      {/* Category label — only for action/critical */}
      {(isCritical || isAction) && (
        <Typography
          variant="caption"
          sx={{
            flexShrink: 0,
            fontSize: '0.65rem',
            fontWeight: 600,
            color,
            bgcolor: (theme) => alpha(color, theme.palette.mode === 'dark' ? 0.12 : 0.08),
            px: 0.75,
            py: 0.25,
            borderRadius: 1,
            alignSelf: 'center',
          }}
        >
          {label}
        </Typography>
      )}
    </Box>
  );
}
