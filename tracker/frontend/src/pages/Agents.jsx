import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Switch, Grid, Chip, CircularProgress, Alert, IconButton,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import MailOutlineIcon from '@mui/icons-material/MailOutlined';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import WorkIcon from '@mui/icons-material/Work';
import AddIcon from '@mui/icons-material/Add';
import { useSnackbar } from 'notistack';
import { getAgentTypes, toggleAgent } from '../api';

const AGENT_ICONS = {
  job_scanner: { Icon: SearchIcon, color: '#2196f3', bg: '#e3f2fd' },
  auto_applicant: { Icon: WorkIcon, color: '#4caf50', bg: '#e8f5e9' },
  inmail_drafter: { Icon: MailOutlineIcon, color: '#9c27b0', bg: '#f3e5f5' },
  telegram_notifier: { Icon: NotificationsActiveIcon, color: '#ff9800', bg: '#fff3e0' },
};

const AGENT_DESC = {
  job_scanner: 'Scans LinkedIn for new job postings matching your searches.',
  auto_applicant: 'Fills & submits Easy Apply forms end-to-end.',
  inmail_drafter: 'Generates cold outreach to hiring managers.',
  telegram_notifier: 'Sends notifications & receives your input.',
};

export default function Agents() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [agents, setAgents] = useState([]);
  const [error, setError] = useState(null);

  const loadAgents = useCallback(async () => {
    try {
      const data = await getAgentTypes();
      setAgents(data.agents || data || []);
    } catch { setError('Failed to load agents'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadAgents(); }, [loadAgents]);

  const handleToggle = async (agentId, enabled) => {
    try {
      await toggleAgent(agentId, enabled);
      setAgents((prev) => prev.map((a) => a.id === agentId ? { ...a, enabled, status: enabled ? 'active' : 'disabled' } : a));
      enqueueSnackbar(`Agent ${enabled ? 'enabled' : 'disabled'}`, { variant: 'success' });
    } catch { enqueueSnackbar('Failed to toggle agent', { variant: 'error' }); }
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress size={24} /></Box>;
  if (error) return <Alert severity="error" sx={{ fontSize: 12 }}>{error}</Alert>;

  return (
    <Box>
      {/* Top bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1, borderBottom: 1, borderColor: 'divider', mb: 1.5 }}>
        <Typography sx={{ fontSize: 14, fontWeight: 700 }}>Agents</Typography>
        <Chip label={`${agents.filter((a) => a.enabled).length} active`} size="small" color="success" variant="outlined" sx={{ fontSize: 10, height: 18 }} />
      </Box>

      <Grid container spacing={1.5}>
        {agents.map((agent) => {
          const iconCfg = AGENT_ICONS[agent.id] || { Icon: SmartToyIcon, color: '#607d8b', bg: '#eceff1' };
          const { Icon } = iconCfg;
          return (
            <Grid size={{ xs: 12, sm: 6, md: 3 }} key={agent.id}>
              <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
                {/* Icon + toggle row */}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Box sx={{ width: 48, height: 48, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: iconCfg.bg }}>
                    <Icon sx={{ fontSize: 22, color: iconCfg.color }} />
                  </Box>
                  <Switch size="small" checked={agent.enabled} onChange={(e) => handleToggle(agent.id, e.target.checked)} />
                </Box>
                {/* Name */}
                <Typography sx={{ fontSize: 12, fontWeight: 600, mb: 0.25 }}>{agent.name}</Typography>
                {/* Description */}
                <Typography sx={{ fontSize: 11, color: 'text.secondary', lineHeight: 1.3, mb: 1, minHeight: 28 }}>
                  {AGENT_DESC[agent.id] || agent.description || '—'}
                </Typography>
                {/* Stats row */}
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {agent.last_run && (
                    <Typography sx={{ fontSize: 10, color: 'text.secondary' }}>
                      Last: {new Date(agent.last_run).toLocaleDateString()}
                    </Typography>
                  )}
                  {agent.success_rate !== undefined && (
                    <Typography sx={{ fontSize: 10, color: agent.success_rate >= 0.8 ? 'success.main' : 'warning.main', fontWeight: 600 }}>
                      {Math.round(agent.success_rate * 100)}% success
                    </Typography>
                  )}
                </Box>
                {/* Inline config hints */}
                {agent.config && Object.keys(agent.config).length > 0 && (
                  <Typography sx={{ fontSize: 9, color: 'text.disabled', mt: 0.5, fontFamily: 'monospace' }}>
                    {Object.entries(agent.config).slice(0, 2).map(([k, v]) => `${k}: ${typeof v === 'object' ? '…' : v}`).join(' | ')}
                  </Typography>
                )}
              </Box>
            </Grid>
          );
        })}

        {/* Add Agent */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box sx={{ border: '1.5px dashed', borderColor: 'divider', borderRadius: 1, p: 1.5, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 160, cursor: 'pointer', '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' } }}>
            <IconButton size="small" color="primary" sx={{ bgcolor: 'primary.50', mb: 0.5 }}>
              <AddIcon sx={{ fontSize: 18 }} />
            </IconButton>
            <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>Add Agent</Typography>
            <Typography sx={{ fontSize: 9, color: 'text.disabled' }}>Coming soon</Typography>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
