import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Chip,
  Tooltip,
  Divider,
  Badge,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ViewKanbanIcon from '@mui/icons-material/ViewKanban';
import ScheduleIcon from '@mui/icons-material/Schedule';
import HubIcon from '@mui/icons-material/Hub';
import TimelineIcon from '@mui/icons-material/Timeline';
import SettingsIcon from '@mui/icons-material/Settings';
import CloudIcon from '@mui/icons-material/Cloud';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import NotificationsIcon from '@mui/icons-material/Notifications';
import CircleIcon from '@mui/icons-material/Circle';

const DRAWER_WIDTH = 240;
const DRAWER_COLLAPSED = 56;

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: DashboardIcon },
  { path: '/agent', label: 'Agent Control', icon: SmartToyIcon },
  { path: '/pipeline', label: 'Pipeline', icon: AccountTreeIcon },
  { path: '/board', label: 'Board', icon: ViewKanbanIcon },
  { path: '/scheduler', label: 'Scheduler', icon: ScheduleIcon },
  { path: '/agents', label: 'Agents', icon: HubIcon },
  { path: '/activity', label: 'Activity Log', icon: TimelineIcon },
  { path: '/settings', label: 'Settings', icon: SettingsIcon },
  { path: '/service', label: 'Service', icon: CloudIcon },
];

function getPageName(pathname) {
  const item = NAV_ITEMS.find((nav) => {
    if (nav.path === '/') return pathname === '/';
    return pathname.startsWith(nav.path);
  });
  return item ? item.label : 'Dashboard';
}

export default function AppLayout({ mode, toggleMode }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const drawerWidth = collapsed ? DRAWER_COLLAPSED : DRAWER_WIDTH;

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const currentPage = getPageName(location.pathname);

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          transition: 'width 0.2s ease',
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            transition: 'width 0.2s ease',
            overflowX: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            '&::after': {
              content: '""',
              position: 'absolute',
              inset: 0,
              background: 'transparent',
              pointerEvents: 'none',
            },
          },
        }}
      >
        {/* Sidebar Header */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
            px: collapsed ? 1 : 2,
            py: 1.5,
            minHeight: 48,
            position: 'relative',
            zIndex: 1,
          }}
        >
          {!collapsed && (
            <Typography
              variant="h6"
              sx={{
                color: '#f5f3ff',
                fontWeight: 700,
                fontSize: '0.9rem',
                letterSpacing: '-0.02em',
              }}
            >
              ApplyPilot
            </Typography>
          )}
          <IconButton
            size="small"
            onClick={() => setCollapsed(!collapsed)}
            sx={{ color: '#8b9bab' }}
          >
            {collapsed ? <MenuIcon fontSize="small" /> : <ChevronLeftIcon fontSize="small" />}
          </IconButton>
        </Box>

        <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.1)' }} />

        {/* Navigation */}
        <List sx={{ flex: 1, py: 1, position: 'relative', zIndex: 1 }}>
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <Tooltip key={path} title={collapsed ? label : ''} placement="right" arrow>
              <ListItemButton
                selected={isActive(path)}
                onClick={() => navigate(path)}
                sx={{
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  px: collapsed ? 1.5 : undefined,
                  '&.Mui-selected': {
                    color: '#f5f3ff',
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    justifyContent: 'center',
                    color: isActive(path) ? '#fff' : 'rgba(255,255,255,0.6)',
                  }}
                >
                  <Icon fontSize="small" />
                </ListItemIcon>
                {!collapsed && (
                  <ListItemText
                    primary={label}
                    primaryTypographyProps={{
                      fontSize: '0.875rem',
                      fontWeight: isActive(path) ? 600 : 400,
                    }}
                  />
                )}
              </ListItemButton>
            </Tooltip>
          ))}
        </List>

        {/* Sidebar Footer */}
        <Box sx={{ p: collapsed ? 1 : 2, borderTop: '1px solid rgba(255, 255, 255, 0.1)', position: 'relative', zIndex: 1 }}>
          {!collapsed && (
            <>
              <Chip
                icon={<CircleIcon sx={{ fontSize: '8px !important', color: '#34d399 !important' }} />}
                label="Service: Running"
                size="small"
                sx={{
                  mb: 1,
                  width: '100%',
                  justifyContent: 'flex-start',
                  bgcolor: 'rgba(52, 211, 153, 0.1)',
                  color: '#34d399',
                  border: '1px solid rgba(52, 211, 153, 0.2)',
                  fontSize: '0.65rem',
                }}
              />
              <Typography variant="caption" sx={{ color: '#a78bfa', display: 'block', textAlign: 'center' }}>
                v1.0.0
              </Typography>
            </>
          )}
          {collapsed && (
            <Tooltip title="v1.0.0 — Running" placement="right">
              <CircleIcon sx={{ fontSize: 8, color: '#34d399', display: 'block', mx: 'auto' }} />
            </Tooltip>
          )}
        </Box>
      </Drawer>

      {/* Main content area */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, height: '100vh' }}>
        {/* Top App Bar */}
        <AppBar
          position="sticky"
          color="inherit"
          elevation={0}
          sx={{
            bgcolor: (theme) =>
              theme.palette.mode === 'light' ? 'rgba(255, 255, 255, 0.8)' : 'rgba(26, 26, 46, 0.8)',
            backdropFilter: 'blur(8px)',
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Toolbar variant="dense" sx={{ minHeight: 40, px: 2 }}>
            <Typography
              sx={{ fontSize: '0.85rem', fontWeight: 600, color: 'text.primary', flexGrow: 1 }}
            >
              {currentPage}
            </Typography>

            {/* Dark/Light mode toggle */}
            <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
              <IconButton size="small" onClick={toggleMode} sx={{ mr: 1 }}>
                {mode === 'dark' ? (
                  <LightModeIcon fontSize="small" />
                ) : (
                  <DarkModeIcon fontSize="small" />
                )}
              </IconButton>
            </Tooltip>

            {/* Notification Bell */}
            <Tooltip title="Notifications">
              <IconButton size="small" sx={{ mr: 1 }}>
                <Badge badgeContent={3} color="error" variant="dot">
                  <NotificationsIcon fontSize="small" />
                </Badge>
              </IconButton>
            </Tooltip>

            {/* User Avatar */}
            <Avatar
              sx={{
                width: 28,
                height: 28,
                fontSize: '0.7rem',
                bgcolor: 'primary.main',
                cursor: 'pointer',
              }}
            >
              RG
            </Avatar>
          </Toolbar>
        </AppBar>

        {/* Page Content */}
        <Box
          component="main"
          sx={{
            flex: 1,
            p: 1.5,
            height: 'calc(100vh - 40px)',
            overflowY: 'auto',
            overflowX: 'hidden',
            bgcolor: 'background.default',
          }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
