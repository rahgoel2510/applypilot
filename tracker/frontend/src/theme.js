import { createTheme, alpha } from '@mui/material/styles';

/**
 * ApplyPilot Theme — Vibrant, Energizing, Motivating
 * Inspired by modern SaaS dashboards (Linear, Vercel, Raycast)
 */
export function createAppTheme(mode) {
  const isLight = mode === 'light';

  // Vibrant palette
  const colors = {
    // Primary: Electric violet/purple — energizing and modern
    primary: '#7c3aed',
    primaryLight: '#a78bfa',
    primaryDark: '#5b21b6',
    // Accent: Hot pink/magenta for CTAs and highlights
    accent: '#ec4899',
    accentLight: '#f472b6',
    // Secondary: Vivid cyan/teal — fresh and energetic
    secondary: '#06b6d4',
    secondaryLight: '#22d3ee',
    // Success: Vivid emerald
    success: '#10b981',
    successBg: 'rgba(16, 185, 129, 0.12)',
    // Warning: Vibrant amber/orange
    warning: '#f59e0b',
    warningBg: 'rgba(245, 158, 11, 0.12)',
    // Error: Vivid rose
    error: '#f43f5e',
    errorBg: 'rgba(244, 63, 94, 0.12)',
    // Info: Bright sky blue
    info: '#3b82f6',
    infoBg: 'rgba(59, 130, 246, 0.12)',
    // Backgrounds
    bgLight: '#faf8ff',     // Very subtle warm purple tint
    bgDark: '#0c0a1a',
    paperLight: '#ffffff',
    paperDark: '#16132b',
    // Sidebar
    sidebarTop: '#1e1145',
    sidebarBottom: '#0c0a1a',
    sidebarText: '#b8a4f8',
    sidebarActive: '#e9d5ff',
    // Text
    textPrimary: isLight ? '#1a1135' : '#f3f0ff',
    textSecondary: isLight ? '#6b6280' : '#b8a4f8',
  };

  return createTheme({
    palette: {
      mode,
      primary: {
        main: colors.primary,
        light: colors.primaryLight,
        dark: colors.primaryDark,
        contrastText: '#ffffff',
      },
      secondary: {
        main: colors.secondary,
        light: colors.secondaryLight,
        dark: '#0891b2',
        contrastText: '#ffffff',
      },
      background: {
        default: isLight ? colors.bgLight : colors.bgDark,
        paper: isLight ? colors.paperLight : colors.paperDark,
      },
      divider: isLight ? 'rgba(124, 58, 237, 0.08)' : 'rgba(167, 139, 250, 0.12)',
      text: {
        primary: colors.textPrimary,
        secondary: colors.textSecondary,
      },
      success: { main: colors.success },
      warning: { main: colors.warning },
      error: { main: colors.error },
      info: { main: colors.info },
      // Custom palette for direct access
      accent: { main: colors.accent, light: colors.accentLight },
    },
    typography: {
      fontFamily: "'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      fontSize: 14,
      h1: { fontSize: '2.25rem', fontWeight: 800, letterSpacing: '-0.03em', color: colors.textPrimary },
      h2: { fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: colors.textPrimary },
      h3: { fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.01em', color: colors.textPrimary },
      h4: { fontSize: '1.25rem', fontWeight: 700, color: colors.textPrimary },
      h5: { fontSize: '1.05rem', fontWeight: 600 },
      h6: { fontSize: '0.95rem', fontWeight: 600 },
      body1: { fontSize: '0.9375rem', lineHeight: 1.6 },
      body2: { fontSize: '0.875rem', lineHeight: 1.5 },
      caption: { fontSize: '0.8125rem', lineHeight: 1.4, color: colors.textSecondary },
      button: { fontSize: '0.875rem', fontWeight: 600, textTransform: 'none', letterSpacing: '0.01em' },
    },
    spacing: 8,
    shape: {
      borderRadius: 10,
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarWidth: 'thin',
            '&::-webkit-scrollbar': { width: 6, height: 6 },
            '&::-webkit-scrollbar-track': { background: 'transparent' },
            '&::-webkit-scrollbar-thumb': {
              background: `rgba(124, 58, 237, 0.25)`,
              borderRadius: 10,
              '&:hover': { background: `rgba(124, 58, 237, 0.4)` },
            },
          },
          '*': {
            scrollbarWidth: 'thin',
            '&::-webkit-scrollbar': { width: 5, height: 5 },
            '&::-webkit-scrollbar-thumb': {
              background: `rgba(124, 58, 237, 0.2)`,
              borderRadius: 10,
            },
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: 10,
            padding: '8px 20px',
            fontWeight: 600,
            fontSize: '0.875rem',
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
          },
          contained: {
            background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.accent} 100%)`,
            boxShadow: `0 4px 14px ${alpha(colors.primary, 0.35)}`,
            '&:hover': {
              background: `linear-gradient(135deg, ${colors.primaryDark} 0%, #db2777 100%)`,
              boxShadow: `0 6px 20px ${alpha(colors.primary, 0.45)}`,
              transform: 'translateY(-1px)',
            },
          },
          outlined: {
            borderColor: alpha(colors.primary, 0.4),
            color: colors.primary,
            '&:hover': {
              borderColor: colors.primary,
              backgroundColor: alpha(colors.primary, 0.06),
              transform: 'translateY(-1px)',
            },
          },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            borderRadius: 12,
            border: `1px solid ${isLight ? 'rgba(124, 58, 237, 0.08)' : 'rgba(167, 139, 250, 0.1)'}`,
            boxShadow: 'none',
            transition: 'border-color 0.2s ease',
            '&:hover': {
              borderColor: isLight ? 'rgba(124, 58, 237, 0.18)' : 'rgba(167, 139, 250, 0.2)',
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            fontWeight: 500,
            fontSize: '0.8125rem',
          },
          colorSuccess: {
            backgroundColor: colors.successBg,
            color: colors.success,
            border: `1px solid ${alpha(colors.success, 0.2)}`,
          },
          colorError: {
            backgroundColor: colors.errorBg,
            color: colors.error,
            border: `1px solid ${alpha(colors.error, 0.2)}`,
          },
          colorWarning: {
            backgroundColor: colors.warningBg,
            color: '#b45309',
            border: `1px solid ${alpha(colors.warning, 0.3)}`,
          },
          colorInfo: {
            backgroundColor: colors.infoBg,
            color: colors.info,
            border: `1px solid ${alpha(colors.info, 0.2)}`,
          },
          colorPrimary: {
            backgroundColor: alpha(colors.primary, 0.1),
            color: colors.primary,
            border: `1px solid ${alpha(colors.primary, 0.2)}`,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          outlined: {
            borderColor: isLight ? 'rgba(124, 58, 237, 0.08)' : 'rgba(167, 139, 250, 0.1)',
            borderRadius: 12,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            boxShadow: 'none',
            borderBottom: `1px solid ${isLight ? 'rgba(124, 58, 237, 0.06)' : 'rgba(167, 139, 250, 0.08)'}`,
            backdropFilter: 'blur(12px)',
            backgroundColor: isLight ? 'rgba(250, 248, 255, 0.85)' : 'rgba(12, 10, 26, 0.85)',
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            background: `linear-gradient(180deg, ${colors.sidebarTop} 0%, ${colors.sidebarBottom} 100%)`,
            color: colors.sidebarText,
            borderRight: 'none',
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 10,
            margin: '2px 8px',
            padding: '8px 14px',
            transition: 'all 0.2s ease',
            '&:hover': {
              backgroundColor: 'rgba(124, 58, 237, 0.08)',
            },
            '&.Mui-selected': {
              backgroundColor: 'rgba(124, 58, 237, 0.15)',
              borderLeft: `3px solid ${colors.primaryLight}`,
              color: colors.sidebarActive,
              '&:hover': {
                backgroundColor: 'rgba(124, 58, 237, 0.2)',
              },
            },
          },
        },
      },
      MuiListItemIcon: {
        styleOverrides: {
          root: { minWidth: 36, color: 'inherit' },
        },
      },
      MuiTextField: {
        defaultProps: { size: 'small' },
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 10,
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: alpha(colors.primary, 0.4),
              },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                borderColor: colors.primary,
                boxShadow: `0 0 0 3px ${alpha(colors.primary, 0.1)}`,
              },
            },
          },
        },
      },
      MuiSelect: {
        styleOverrides: {
          root: { borderRadius: 10 },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .Mui-checked': {
              color: colors.primary,
              '& + .MuiSwitch-track': {
                backgroundColor: colors.primary,
                opacity: 0.7,
              },
            },
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: {
            height: 3,
            borderRadius: 3,
            backgroundColor: colors.primary,
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.875rem',
            '&.Mui-selected': { fontWeight: 600 },
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: 16,
            boxShadow: '0 25px 50px rgba(0, 0, 0, 0.15)',
          },
        },
      },
      MuiTooltip: {
        defaultProps: { arrow: true },
        styleOverrides: {
          tooltip: {
            borderRadius: 8,
            fontSize: '0.75rem',
            backgroundColor: isLight ? '#1e1145' : '#2d2654',
          },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: {
            borderRadius: 10,
            height: 6,
            backgroundColor: alpha(colors.primary, 0.1),
          },
          bar: {
            borderRadius: 10,
            background: `linear-gradient(90deg, ${colors.primary}, ${colors.accent})`,
          },
        },
      },
      MuiCircularProgress: {
        styleOverrides: {
          root: { color: colors.primary },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderColor: isLight ? 'rgba(124, 58, 237, 0.06)' : 'rgba(167, 139, 250, 0.08)',
            padding: '10px 14px',
            fontSize: '0.875rem',
          },
          head: {
            fontWeight: 600,
            color: colors.textSecondary,
            fontSize: '0.8125rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            '&:hover': {
              backgroundColor: alpha(colors.primary, 0.03),
            },
          },
        },
      },
    },
  });
}

/**
 * Get initial color mode.
 */
export function getInitialMode() {
  if (typeof window === 'undefined') return 'light';
  const stored = localStorage.getItem('applypilot-theme-mode');
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
