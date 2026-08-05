import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box, Typography, Switch, Grid, Chip, CircularProgress, Alert,
  Button, Card, CardContent, LinearProgress, MenuItem, Select, FormControl,
  InputLabel, Paper, Divider,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import NotificationsIcon from '@mui/icons-material/Notifications';
import WorkIcon from '@mui/icons-material/Work';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import ArticleIcon from '@mui/icons-material/Article';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import { useSnackbar } from 'notistack';
import {
  getAgentTypes, toggleAgent, getMultiAgentStatus, triggerAgentRun,
  stopAgentRun, getAgentLogs, getOrchestratorStatus, startOrchestrator,
  stopOrchestrator,
} from '../api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(date) {
  if (!date) return '—';
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

const AGENT_ICONS = {
  job_scanner: { Icon: SearchIcon, color: '#2196f3', bg: '#e3f2fd' },
  auto_applicant: { Icon: WorkIcon, color: '#4caf50', bg: '#e8f5e9' },
  inmail_drafter: { Icon: MailOutlineIcon, color: '#9c27b0', bg: '#f3e5f5' },
  telegram_notifier: { Icon: NotificationsIcon, color: '#ff9800', bg: '#fff3e0' },
  naukri_freshener: { Icon: RefreshIcon, color: '#00bcd4', bg: '#e0f7fa' },
};

const AGENT_DESC = {
  job_scanner: 'Scans LinkedIn for new job postings matching your searches.',
  auto_applicant: 'Fills & submits Easy Apply forms end-to-end.',
  inmail_drafter: 'Generates cold outreach to hiring managers.',
  telegram_notifier: 'Sends notifications & receives your input.',
  naukri_freshener: 'Keeps your Naukri profile fresh and visible to recruiters.',
};

const STATE_COLORS = {
  idle: { color: '#607d8b', bg: '#eceff1', label: 'Idle' },
  running: { color: '#1976d2', bg: '#e3f2fd', label: 'Running' },
  scheduled: { color: '#7b1fa2', bg: '#f3e5f5', label: 'Scheduled' },
  error: { color: '#d32f2f', bg: '#ffebee', label: 'Error' },
  disabled: { color: '#9e9e9e', bg: '#f5f5f5', label: 'Disabled' },
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function Agents() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [agents, setAgents] = useState([]);
  const [agentStatuses, setAgentStatuses] = useState({});
  const [orchestrator, setOrchestrator] = useState({ running: false });
  const [error, setError] = useState(null);

  // Log panel state
  const [logs, setLogs] = useState([]);
  const [logFilter, setLogFilter] = useState('all');
  const [logAgentId, setLogAgentId] = useState(null);
  const logEndRef = useRef(null);

  // -------------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------------

  const loadAgents = useCallback(async () => {
    try {
      const data = await getAgentTypes();
      setAgents(data.agents || data || []);
      setError(null);
    } catch {
      setError('Failed to load agents');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrchestratorStatus = useCallback(async () => {
    try {
      const data = await getOrchestratorStatus();
      setOrchestrator(data);
      if (data.agents) {
        const statusMap = {};
        Object.entries(data.agents).forEach(([id, status]) => {
          statusMap[id] = status;
        });
        setAgentStatuses(statusMap);
      }
    } catch {
      // Orchestrator may not be available — fail silently
    }
  }, []);

  const loadAgentStatus = useCallback(async (agentId) => {
    try {
      const data = await getMultiAgentStatus(agentId);
      setAgentStatuses((prev) => ({ ...prev, [agentId]: data }));
    } catch {
      // silently ignore individual status failures
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await loadOrchestratorStatus();
    // If orchestrator didn't return agent statuses, fetch individually
    agents.forEach((agent) => {
      if (!agentStatuses[agent.id]) {
        loadAgentStatus(agent.id);
      }
    });
  }, [loadOrchestratorStatus, agents, agentStatuses, loadAgentStatus]);

  // Initial load
  useEffect(() => {
    loadAgents();
    loadOrchestratorStatus();
  }, [loadAgents, loadOrchestratorStatus]);

  // Polling every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadOrchestratorStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadOrchestratorStatus]);

  // Auto-scroll logs
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  const handleToggle = async (agentId, enabled) => {
    try {
      await toggleAgent(agentId, enabled);
      setAgents((prev) =>
        prev.map((a) => (a.id === agentId ? { ...a, enabled } : a))
      );
      enqueueSnackbar(`Agent ${enabled ? 'enabled' : 'disabled'}`, { variant: 'success' });
    } catch {
      enqueueSnackbar('Failed to toggle agent', { variant: 'error' });
    }
  };

  const handleRunNow = async (agentId) => {
    try {
      await triggerAgentRun(agentId);
      enqueueSnackbar(`Agent "${agentId}" triggered`, { variant: 'success' });
      setTimeout(() => loadOrchestratorStatus(), 500);
    } catch {
      enqueueSnackbar('Failed to trigger agent run', { variant: 'error' });
    }
  };

  const handleStop = async (agentId) => {
    try {
      await stopAgentRun(agentId);
      enqueueSnackbar(`Agent "${agentId}" stopped`, { variant: 'info' });
      setTimeout(() => loadOrchestratorStatus(), 500);
    } catch {
      enqueueSnackbar('Failed to stop agent', { variant: 'error' });
    }
  };

  const handleViewLogs = async (agentId) => {
    setLogAgentId(agentId);
    setLogFilter(agentId);
    try {
      const data = await getAgentLogs(agentId, 100);
      const entries = (data.logs || data || []).map((entry) => ({
        ...entry,
        agent: agentId,
      }));
      setLogs(entries);
    } catch {
      enqueueSnackbar('Failed to load logs', { variant: 'error' });
    }
  };

  const handleOrchestratorToggle = async () => {
    try {
      if (orchestrator.running) {
        await stopOrchestrator();
        enqueueSnackbar('Orchestrator stopped', { variant: 'info' });
      } else {
        await startOrchestrator();
        enqueueSnackbar('Orchestrator started', { variant: 'success' });
      }
      setTimeout(() => loadOrchestratorStatus(), 500);
    } catch (err) {
      enqueueSnackbar('Orchestrator action failed', { variant: 'error' });
    }
  };

  const handleClearLogs = () => {
    setLogs([]);
    setLogAgentId(null);
  };

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------

  const activeCount = agents.filter((a) => a.enabled).length;
  const filteredLogs = logFilter === 'all'
    ? logs
    : logs.filter((l) => l.agent === logFilter);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error" sx={{ fontSize: 12 }}>{error}</Alert>;
  }

  return (
    <Box sx={{ height: '100%', p: 2, display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="h3">Agents</Typography>
        <Chip
          label={`${activeCount} active`}
          size="small"
          color="success"
          variant="outlined"
        />
        {/* Orchestrator status */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 'auto' }}>
          <FiberManualRecordIcon
            sx={{
              fontSize: 12,
              color: orchestrator.running ? '#4caf50' : '#9e9e9e',
            }}
          />
          <Typography variant="body2" sx={{ color: 'text.secondary', mr: 1 }}>
            Orchestrator {orchestrator.running ? 'Running' : 'Stopped'}
          </Typography>
          <Button
            size="small"
            variant={orchestrator.running ? 'outlined' : 'contained'}
            color={orchestrator.running ? 'error' : 'primary'}
            startIcon={orchestrator.running ? <StopIcon /> : <PlayArrowIcon />}
            onClick={handleOrchestratorToggle}
            sx={{ textTransform: 'none', fontSize: 12 }}
          >
            {orchestrator.running ? 'Stop' : 'Start'}
          </Button>
        </Box>
      </Box>

      {/* Agent Cards Grid */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        {agents.map((agent) => {
          const iconCfg = AGENT_ICONS[agent.id] || { Icon: SmartToyIcon, color: '#607d8b', bg: '#eceff1' };
          const { Icon } = iconCfg;
          const status = agentStatuses[agent.id] || {};
          const state = !agent.enabled ? 'disabled' : (status.state || 'idle');
          const stateStyle = STATE_COLORS[state] || STATE_COLORS.idle;
          const isRunning = state === 'running';
          const failures = status.consecutive_failures || 0;

          return (
            <Grid item xs={12} sm={6} md={4} key={agent.id}>
              <Card
                variant="outlined"
                sx={{
                  borderRadius: '12px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                  position: 'relative',
                  overflow: 'visible',
                }}
              >
                {isRunning && (
                  <LinearProgress
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      borderRadius: '12px 12px 0 0',
                      height: 3,
                    }}
                  />
                )}
                <CardContent sx={{ p: 2.5 }}>
                  {/* Top row: icon + state + toggle */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
                    <Box
                      sx={{
                        width: 44,
                        height: 44,
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        bgcolor: iconCfg.bg,
                        flexShrink: 0,
                      }}
                    >
                      <Icon sx={{ fontSize: 20, color: iconCfg.color }} />
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body1" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
                        {agent.name}
                      </Typography>
                      <Chip
                        label={stateStyle.label}
                        size="small"
                        sx={{
                          mt: 0.3,
                          fontSize: 10,
                          height: 20,
                          color: stateStyle.color,
                          bgcolor: stateStyle.bg,
                          fontWeight: 600,
                        }}
                      />
                    </Box>
                    <Switch
                      size="small"
                      checked={agent.enabled}
                      onChange={(e) => handleToggle(agent.id, e.target.checked)}
                    />
                  </Box>

                  {/* Description */}
                  <Typography
                    variant="body2"
                    sx={{ color: 'text.secondary', lineHeight: 1.4, mb: 1.5, minHeight: 36 }}
                  >
                    {AGENT_DESC[agent.id] || agent.description || '—'}
                  </Typography>

                  {/* Timestamps */}
                  <Box sx={{ display: 'flex', gap: 2, mb: 1.5 }}>
                    <Box>
                      <Typography variant="caption" sx={{ color: 'text.disabled', display: 'block' }}>
                        Last run
                      </Typography>
                      <Typography variant="caption" sx={{ fontWeight: 500 }}>
                        {timeAgo(status.last_run)}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" sx={{ color: 'text.disabled', display: 'block' }}>
                        Next run
                      </Typography>
                      <Typography variant="caption" sx={{ fontWeight: 500 }}>
                        {timeAgo(status.next_run)}
                      </Typography>
                    </Box>
                  </Box>

                  {/* Failures warning */}
                  {failures > 0 && (
                    <Chip
                      icon={<WarningAmberIcon sx={{ fontSize: 14 }} />}
                      label={`${failures} consecutive failure${failures > 1 ? 's' : ''}`}
                      size="small"
                      color="warning"
                      variant="outlined"
                      sx={{ mb: 1.5, fontSize: 11 }}
                    />
                  )}

                  {/* Action buttons */}
                  <Divider sx={{ mb: 1.5 }} />
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Button
                      size="small"
                      startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
                      onClick={() => handleRunNow(agent.id)}
                      disabled={isRunning || !agent.enabled}
                      sx={{ textTransform: 'none', fontSize: 11, minWidth: 0, px: 1 }}
                    >
                      Run
                    </Button>
                    <Button
                      size="small"
                      startIcon={<StopIcon sx={{ fontSize: 14 }} />}
                      onClick={() => handleStop(agent.id)}
                      disabled={!isRunning}
                      color="error"
                      sx={{ textTransform: 'none', fontSize: 11, minWidth: 0, px: 1 }}
                    >
                      Stop
                    </Button>
                    <Button
                      size="small"
                      startIcon={<ArticleIcon sx={{ fontSize: 14 }} />}
                      onClick={() => handleViewLogs(agent.id)}
                      sx={{ textTransform: 'none', fontSize: 11, minWidth: 0, px: 1 }}
                    >
                      Logs
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {/* Log Panel */}
      <Paper
        variant="outlined"
        sx={{
          flex: 1,
          minHeight: 240,
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Log header */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            px: 2,
            py: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Logs
          </Typography>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel sx={{ fontSize: 12 }}>Filter agent</InputLabel>
            <Select
              value={logFilter}
              label="Filter agent"
              onChange={(e) => setLogFilter(e.target.value)}
              sx={{ fontSize: 12, height: 32 }}
            >
              <MenuItem value="all" sx={{ fontSize: 12 }}>All agents</MenuItem>
              {agents.map((a) => (
                <MenuItem key={a.id} value={a.id} sx={{ fontSize: 12 }}>
                  {a.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Box sx={{ flex: 1 }} />
          <Button
            size="small"
            startIcon={<DeleteSweepIcon sx={{ fontSize: 14 }} />}
            onClick={handleClearLogs}
            sx={{ textTransform: 'none', fontSize: 11 }}
          >
            Clear
          </Button>
        </Box>

        {/* Log entries */}
        <Box
          sx={{
            flex: 1,
            overflowY: 'auto',
            px: 2,
            py: 1,
            fontFamily: 'monospace',
            fontSize: 12,
          }}
        >
          {filteredLogs.length === 0 ? (
            <Typography
              variant="body2"
              sx={{ color: 'text.disabled', textAlign: 'center', pt: 4 }}
            >
              {logAgentId
                ? 'No log entries. Click "Logs" on an agent card to load.'
                : 'Select an agent to view logs.'}
            </Typography>
          ) : (
            filteredLogs.slice(-100).map((entry, idx) => (
              <Box
                key={idx}
                sx={{
                  display: 'flex',
                  gap: 1.5,
                  py: 0.3,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  '&:last-child': { borderBottom: 'none' },
                }}
              >
                <Typography
                  component="span"
                  sx={{ fontSize: 11, color: 'text.disabled', whiteSpace: 'nowrap', minWidth: 65 }}
                >
                  {entry.timestamp
                    ? new Date(entry.timestamp).toLocaleTimeString()
                    : '—'}
                </Typography>
                <Chip
                  label={entry.agent || '—'}
                  size="small"
                  sx={{
                    fontSize: 9,
                    height: 18,
                    fontWeight: 600,
                    bgcolor: (AGENT_ICONS[entry.agent] || {}).bg || '#eceff1',
                    color: (AGENT_ICONS[entry.agent] || {}).color || '#607d8b',
                  }}
                />
                <Typography
                  component="span"
                  sx={{ fontSize: 12, color: 'text.primary', wordBreak: 'break-word' }}
                >
                  {entry.message || entry.msg || JSON.stringify(entry)}
                </Typography>
              </Box>
            ))
          )}
          <div ref={logEndRef} />
        </Box>
      </Paper>
    </Box>
  );
}
