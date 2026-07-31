import { Box, Typography, Chip, Stack, Paper, Divider } from '@mui/material';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { motion, AnimatePresence } from 'framer-motion';

dayjs.extend(relativeTime);

const EVENT_CONFIG = {
  discovered: { color: 'info', icon: '🔍', label: 'Discovered' },
  submitted: { color: 'success', icon: '✅', label: 'Applied' },
  job_submitted: { color: 'success', icon: '✅', label: 'Applied' },
  skipped: { color: 'warning', icon: '⏭️', label: 'Skipped' },
  paused: { color: 'warning', icon: '⏸️', label: 'Paused' },
  reached_out: { color: 'secondary', icon: '✉️', label: 'InMail' },
  inmail_drafted: { color: 'secondary', icon: '✉️', label: 'InMail' },
  error: { color: 'error', icon: '❌', label: 'Error' },
  job_error: { color: 'error', icon: '❌', label: 'Error' },
  cycle_start: { color: 'info', icon: '🚀', label: 'Cycle Start' },
  cycle_end: { color: 'success', icon: '📊', label: 'Cycle End' },
  agent_start: { color: 'success', icon: '🤖', label: 'Started' },
  agent_stop: { color: 'default', icon: '👋', label: 'Stopped' },
  info: { color: 'info', icon: 'ℹ️', label: 'Info' },
  warning: { color: 'warning', icon: '⚠️', label: 'Warning' },
};

export default function LiveEventFeed({ events = [], maxItems = 15 }) {
  const visibleEvents = events.slice(0, maxItems);

  return (
    <Paper
      sx={{ p: 2, height: '100%', overflow: 'hidden', position: 'relative' }}
      elevation={0}
      variant="outlined"
    >
      <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
        <FiberManualRecordIcon
          sx={{ fontSize: 10, color: events.length > 0 ? 'success.main' : 'grey.400' }}
        />
        <Typography variant="subtitle2" fontWeight={600}>
          Live Pipeline Feed
        </Typography>
        <Chip label={`${events.length}`} size="small" variant="outlined" />
      </Stack>
      <Divider sx={{ mb: 1 }} />
      <Box sx={{ overflow: 'auto', maxHeight: 400 }}>
        <AnimatePresence initial={false}>
          {visibleEvents.map((evt, idx) => {
            const data = evt.data || {};
            const config = EVENT_CONFIG[evt.event_type || data.stage] || EVENT_CONFIG.discovered;
            return (
              <motion.div
                key={evt.timestamp + idx}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={1}
                  sx={{ py: 0.5, borderBottom: '1px solid', borderColor: 'divider' }}
                >
                  <Typography fontSize={14}>{config.icon}</Typography>
                  <Box flex={1} minWidth={0}>
                    <Typography variant="body2" noWrap fontWeight={500}>
                      {data.title || data.message || 'Event'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {data.company}{data.location ? ` · ${data.location}` : ''}
                      {data.match_score != null ? ` · ${Math.round(data.match_score * 100)}%` : ''}
                      {!data.company && data.message && data.title ? data.message : ''}
                    </Typography>
                  </Box>
                  <Chip label={config.label} size="small" color={config.color} variant="outlined" />
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 50 }}>
                    {dayjs(evt.timestamp).fromNow()}
                  </Typography>
                </Stack>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {visibleEvents.length === 0 && (
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            Waiting for pipeline events...
          </Typography>
        )}
      </Box>
    </Paper>
  );
}
