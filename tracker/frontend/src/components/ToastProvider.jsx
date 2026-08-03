import { useEffect, useRef } from 'react';
import { useSnackbar } from 'notistack';
import { useNavigate } from 'react-router-dom';
import { Button } from '@mui/material';
import { useWebSocket } from '../hooks/useWebSocket';

/**
 * ToastProvider — listens to WebSocket pipeline events and shows
 * notistack toast notifications for important events.
 * Wrap this inside your app (below SnackbarProvider + BrowserRouter).
 */
export default function ToastProvider({ children }) {
  const { events } = useWebSocket();
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const seenRef = useRef(new Set());

  useEffect(() => {
    if (!events.length) return;

    // Process only the latest event (events are prepended)
    const latest = events[0];
    if (!latest) return;

    // Create a unique key for deduplication
    const eventKey = latest.id || `${latest.event || latest.stage}-${latest.job_id || ''}-${latest.timestamp || ''}`;
    if (seenRef.current.has(eventKey)) return;
    seenRef.current.add(eventKey);

    // Cap the seen set to prevent memory leak
    if (seenRef.current.size > 500) {
      const entries = [...seenRef.current];
      seenRef.current = new Set(entries.slice(-300));
    }

    const data = latest.data || latest;
    const eventType = data.event || data.stage || latest.event || '';
    const title = data.title || data.job_title || '';
    const company = data.company || data.company_name || '';
    const message = data.message || data.error || '';
    const score = data.score || data.match_score || 0;

    const viewAction = (snackbarId) => (
      <Button
        size="small"
        sx={{ color: 'inherit', fontWeight: 600, fontSize: '0.75rem' }}
        onClick={() => {
          navigate('/board');
          closeSnackbar(snackbarId);
        }}
      >
        View
      </Button>
    );

    switch (eventType) {
      case 'submitted':
      case 'applied':
        enqueueSnackbar(`🎉 Applied to ${title} @ ${company}`, {
          variant: 'success',
          autoHideDuration: 5000,
          action: viewAction,
        });
        break;

      case 'error':
      case 'failed':
        enqueueSnackbar(`❌ Error: ${message || title}`, {
          variant: 'error',
          autoHideDuration: 5000,
          action: viewAction,
        });
        break;

      case 'paused':
      case 'human_input_needed':
        enqueueSnackbar(`⏸️ Agent needs input: ${title}`, {
          variant: 'warning',
          autoHideDuration: 5000,
          action: viewAction,
        });
        break;

      case 'external':
      case 'external_apply':
        if (score >= 0.75) {
          enqueueSnackbar(`🔗 High-match external: ${title} @ ${company}`, {
            variant: 'info',
            autoHideDuration: 5000,
            action: viewAction,
          });
        }
        break;

      default:
        break;
    }
  }, [events, enqueueSnackbar, closeSnackbar, navigate]);

  return children;
}
