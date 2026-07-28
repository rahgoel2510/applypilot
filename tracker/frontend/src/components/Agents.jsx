import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Switch,
  Button,
  Grid,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import HubIcon from '@mui/icons-material/Hub';
import SearchIcon from '@mui/icons-material/Search';
import SendIcon from '@mui/icons-material/Send';
import MailIcon from '@mui/icons-material/Mail';
import TelegramIcon from '@mui/icons-material/Telegram';
import EditIcon from '@mui/icons-material/Edit';
import { useSnackbar } from 'notistack';
import { getAgentTypes, updateAgentConfig, toggleAgent } from '../api';

const AGENT_ICONS = {
  scanner: SearchIcon,
  applicant: SendIcon,
  inmail_drafter: MailIcon,
  telegram_notifier: TelegramIcon,
};

const AGENT_COLORS = {
  scanner: '#3b82f6',
  applicant: '#10b981',
  inmail_drafter: '#8b5cf6',
  telegram_notifier: '#06b6d4',
};

export default function Agents() {
  const { enqueueSnackbar } = useSnackbar();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editDialog, setEditDialog] = useState({ open: false, agent: null });
  const [editConfig, setEditConfig] = useState('');

  useEffect(() => {
    loadAgents();
  }, []);

  async function loadAgents() {
    try {
      const data = await getAgentTypes();
      setAgents(data || []);
    } catch (err) {
      console.error('Failed to load agents:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(agentId, enabled) {
    try {
      await toggleAgent(agentId, enabled);
      setAgents((prev) =>
        prev.map((a) => (a.id === agentId ? { ...a, enabled } : a))
      );
      enqueueSnackbar(`Agent ${enabled ? 'enabled' : 'disabled'}`, { variant: 'success' });
    } catch (err) {
      enqueueSnackbar('Failed to toggle agent', { variant: 'error' });
    }
  }

  function openEdit(agent) {
    setEditConfig(JSON.stringify(agent.config || {}, null, 2));
    setEditDialog({ open: true, agent });
  }

  async function handleSaveConfig() {
    try {
      const parsed = JSON.parse(editConfig);
      await updateAgentConfig(editDialog.agent.id, parsed);
      setAgents((prev) =>
        prev.map((a) => (a.id === editDialog.agent.id ? { ...a, config: parsed } : a))
      );
      setEditDialog({ open: false, agent: null });
      enqueueSnackbar('Agent config updated', { variant: 'success' });
    } catch (err) {
      enqueueSnackbar(err.message || 'Invalid JSON or save failed', { variant: 'error' });
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <Typography color="text.secondary">Loading agents...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <HubIcon color="primary" />
        <Typography variant="h4">Agent Types</Typography>
      </Box>

      <Card>
        <CardContent sx={{ p: 0 }}>
          <List disablePadding>
            {agents.map((agent, idx) => {
              const Icon = AGENT_ICONS[agent.id] || HubIcon;
              const color = AGENT_COLORS[agent.id] || '#64748b';
              return (
                <Box key={agent.id}>
                  {idx > 0 && <Divider />}
                  <ListItem sx={{ py: 2, px: 2.5 }}>
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: `${color}20`, color, width: 36, height: 36 }}>
                        <Icon fontSize="small" />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body1" fontWeight={600}>
                            {agent.name}
                          </Typography>
                          <Chip
                            label={agent.enabled ? 'Active' : 'Inactive'}
                            size="small"
                            color={agent.enabled ? 'success' : 'default'}
                            variant="outlined"
                          />
                        </Box>
                      }
                      secondary={agent.description}
                      secondaryTypographyProps={{ fontSize: '0.7rem' }}
                    />
                    <ListItemSecondaryAction>
                      <Button
                        size="small"
                        startIcon={<EditIcon />}
                        onClick={() => openEdit(agent)}
                        sx={{ mr: 1 }}
                      >
                        Config
                      </Button>
                      <Switch
                        checked={agent.enabled}
                        onChange={(e) => handleToggle(agent.id, e.target.checked)}
                        size="small"
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                </Box>
              );
            })}
          </List>
        </CardContent>
      </Card>

      {/* Edit Config Dialog */}
      <Dialog
        open={editDialog.open}
        onClose={() => setEditDialog({ open: false, agent: null })}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Configure: {editDialog.agent?.name}
        </DialogTitle>
        <DialogContent>
          <TextField
            label="Configuration (JSON)"
            multiline
            rows={10}
            fullWidth
            value={editConfig}
            onChange={(e) => setEditConfig(e.target.value)}
            sx={{ mt: 1 }}
            inputProps={{ style: { fontFamily: 'monospace', fontSize: '0.75rem' } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog({ open: false, agent: null })}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveConfig}>Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
