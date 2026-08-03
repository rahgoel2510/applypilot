import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  IconButton,
  Badge,
  Popover,
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  Button,
  Divider,
  Tooltip,
  Chip,
  CircularProgress,
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

const BASE_URL = '/api';

// Category config with icons and labels
const CATEGORY_CONFIG = {
  external_apply: { icon: '🔗', label: 'External Apply' },
  review_inmail: { icon: '✉️', label: 'Review InMail' },
  skill_gap: { icon: '📈', label: 'Skill Gap' },
  session: { icon: '🔑', label: 'Session' },
  default: { icon: '📋', label: 'Action Required' },
};

function getCategoryConfig(category) {
  return CATEGORY_CONFIG[category] || CATEGORY_CONFIG.default;
}

export default function NotificationCenter() {
  const [anchorEl, setAnchorEl] = useState(null);
  const [todos, setTodos] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const open = Boolean(anchorEl);

  // Fetch pending todos
  const fetchTodos = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/todos?status=pending`);
      if (!res.ok) return;
      const data = await res.json();
      const items = data.todos || data.items || data || [];
      setTodos(Array.isArray(items) ? items : []);
      setCount(Array.isArray(items) ? items.length : 0);
    } catch {
      // Silent fail — don't break the UI
    }
  }, []);

  // Poll every 30s for count
  useEffect(() => {
    fetchTodos();
    const interval = setInterval(fetchTodos, 30000);
    return () => clearInterval(interval);
  }, [fetchTodos]);

  // Fetch fresh data when popover opens
  const handleOpen = (event) => {
    setAnchorEl(event.currentTarget);
    fetchTodos();
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  // Mark a todo as done
  const markDone = async (id) => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/todos/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'done' }),
      });
      if (res.ok) {
        setTodos((prev) => prev.filter((t) => t.id !== id));
        setCount((prev) => Math.max(0, prev - 1));
      }
    } catch {
      // Silent fail
    } finally {
      setLoading(false);
    }
  };

  // Group todos by category
  const grouped = todos.reduce((acc, todo) => {
    const cat = todo.category || 'default';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(todo);
    return acc;
  }, {});

  return (
    <>
      <Tooltip title="Notifications">
        <IconButton size="small" onClick={handleOpen} sx={{ mr: 1 }}>
          <Badge
            badgeContent={count}
            color="error"
            max={99}
            invisible={count === 0}
          >
            <NotificationsIcon fontSize="small" />
          </Badge>
        </IconButton>
      </Tooltip>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{
          paper: {
            sx: {
              width: 380,
              maxHeight: 480,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            },
          },
        }}
      >
        {/* Header */}
        <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle2" fontWeight={700}>
            Notifications
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {count} pending {count === 1 ? 'item' : 'items'}
          </Typography>
        </Box>

        {/* Content */}
        <Box sx={{ flex: 1, overflowY: 'auto' }}>
          {todos.length === 0 ? (
            <Box sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                🎉 All caught up! No pending items.
              </Typography>
            </Box>
          ) : (
            Object.entries(grouped).map(([category, items]) => {
              const config = getCategoryConfig(category);
              return (
                <Box key={category}>
                  {/* Category header */}
                  <Box sx={{ px: 2, py: 0.75, bgcolor: 'action.hover' }}>
                    <Chip
                      label={`${config.icon} ${config.label}`}
                      size="small"
                      variant="outlined"
                      sx={{ fontSize: '0.7rem', height: 22 }}
                    />
                  </Box>

                  <List dense disablePadding>
                    {items.map((todo) => (
                      <ListItem
                        key={todo.id}
                        sx={{
                          py: 1,
                          px: 2,
                          '&:hover': { bgcolor: 'action.hover' },
                          alignItems: 'flex-start',
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 32, mt: 0.5 }}>
                          <Typography fontSize="1.1rem">{config.icon}</Typography>
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Typography variant="body2" fontWeight={500} noWrap>
                              {todo.title || todo.description || 'Action required'}
                            </Typography>
                          }
                          secondary={
                            <Typography variant="caption" color="text.secondary" noWrap>
                              {todo.description || todo.details || ''}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Box sx={{ display: 'flex', gap: 0.5 }}>
                            {todo.url && (
                              <Tooltip title="Open">
                                <IconButton
                                  size="small"
                                  onClick={() => window.open(todo.url, '_blank')}
                                >
                                  <OpenInNewIcon sx={{ fontSize: 16 }} />
                                </IconButton>
                              </Tooltip>
                            )}
                            <Tooltip title="Mark as Done">
                              <IconButton
                                size="small"
                                onClick={() => markDone(todo.id)}
                                disabled={loading}
                                color="success"
                              >
                                {loading ? (
                                  <CircularProgress size={14} />
                                ) : (
                                  <CheckCircleIcon sx={{ fontSize: 16 }} />
                                )}
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))}
                  </List>
                  <Divider />
                </Box>
              );
            })
          )}
        </Box>

        {/* Footer */}
        <Box
          sx={{
            px: 2,
            py: 1,
            borderTop: '1px solid',
            borderColor: 'divider',
            textAlign: 'center',
          }}
        >
          <Button
            size="small"
            onClick={() => {
              handleClose();
              navigate('/board');
            }}
            sx={{ fontSize: '0.75rem', textTransform: 'none' }}
          >
            View All →
          </Button>
        </Box>
      </Popover>
    </>
  );
}
