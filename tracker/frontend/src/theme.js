import { createTheme, alpha } from '@mui/material/styles';

/**
 * ApplyPilot Design System
 * Based on Amazon Ember typography, AWS-inspired color palette,
 * clean professional cards with subtle shadows and multicolor accents.
 */
export function createAppTheme(mode) {
  const isLight = mode === 'light';

  const colors = {
    // Primary (dark navy)
    primary: '#232F3E',
    primaryLight: '#37475A',
    primaryDark: '#131A22',
    // Accents
    blue: '#0073BB',
    blueLight: '#E6F2FA',
    teal: '#067D68',
    tealLight: '#E6F5F2',
    orange: '#EC7211',
    orangeLight: '#FEF3E8',
    purple: '#6B40B2',
    purpleLight: '#F3EEFB',
    red: '#D13212',
    redLight: '#FCECEA',
    // Surfaces
    bgPage: isLight ? '#F2F3F3' : '#0F1B2D',
    bgCard: isLight ? '#FFFFFF' : '#1A2B3F',
    bgHover: isLight ? '#FAFAFA' : '#213347',
    // Borders
    border: isLight ? '#D5DBDB' : '#2D4054',
    borderSubtle: isLight ? '#EAEDED' : '#253545',
    // Text
    textPrimary: isLight ? '#16191F' : '#F2F3F3',
    textSecondary: isLight ? '#545B64' : '#AAB7B8',
    textTertiary: isLight ? '#687078' : '#879596',
  };

  return createTheme({
    palette: {
      mode,
      primary: { main: colors.blue, light: '#3399CC', dark: '#004B8C', contrastText: '#fff' },
      secondary: { main: colors.teal, light: '#0AA88A', dark: '#045B4F', contrastText: '#fff' },
      error: { main: colors.red, light: '#E85D42', dark: '#8B1A0E' },
      warning: { main: colors.orange, light: '#F49342', dark: '#8A4B06' },
      success: { main: colors.teal, light: '#0AA88A', dark: '#045B4F' },
      info: { main: colors.blue, light: '#3399CC', dark: '#004B8C' },
      background: { default: colors.bgPage, paper: colors.bgCard },
      text: { primary: colors.textPrimary, secondary: colors.textSecondary, disabled: colors.textTertiary },
      divider: colors.border,
      action: {
        hover: isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.04)',
        selected: isLight ? 'rgba(0, 115, 187, 0.08)' : 'rgba(0, 115, 187, 0.15)',
      },
    },
    typography: {
      fontFamily: "'Amazon Ember', 'Helvetica Neue', Roboto, Arial, sans-serif",
      fontSize: 14,
      h1: { fontSize: '28px', fontWeight: 700, lineHeight: '36px', letterSpacing: '-0.02em' },
      h2: { fontSize: '22px', fontWeight: 700, lineHeight: '30px', letterSpacing: '-0.015em' },
      h3: { fontSize: '18px', fontWeight: 600, lineHeight: '24px', letterSpacing: '-0.01em' },
      h4: { fontSize: '16px', fontWeight: 600, lineHeight: '22px' },
      h5: { fontSize: '14px', fontWeight: 600, lineHeight: '20px' },
      h6: { fontSize: '12px', fontWeight: 600, lineHeight: '16px', letterSpacing: '0.04em', textTransform: 'uppercase' },
      body1: { fontSize: '14px', fontWeight: 400, lineHeight: '20px' },
      body2: { fontSize: '13px', fontWeight: 400, lineHeight: '18px' },
      caption: { fontSize: '12px', fontWeight: 400, lineHeight: '16px', letterSpacing: '0.01em', color: colors.textSecondary },
      button: { fontSize: '14px', fontWeight: 500, lineHeight: '20px', textTransform: 'none' },
      overline: { fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: colors.textSecondary },
    },
    spacing: 8,
    shape: { borderRadius: 8 },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarWidth: 'thin',
            '&::-webkit-scrollbar': { width: 6, height: 6 },
            '&::-webkit-scrollbar-thumb': { background: isLight ? '#AAB7B8' : '#2D4054', borderRadius: 3 },
            '&::-webkit-scrollbar-track': { background: 'transparent' },
          },
          '*': {
            '&::-webkit-scrollbar': { width: 5, height: 5 },
            '&::-webkit-scrollbar-thumb': { background: isLight ? '#D5DBDB' : '#2D4054', borderRadius: 3 },
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 8, padding: '8px 16px', fontWeight: 500, transition: 'all 0.15s ease' },
          contained: {
            '&:hover': { boxShadow: '0 2px 4px rgba(0,0,0,0.1)' },
          },
          outlined: {
            borderColor: colors.border,
            '&:hover': { borderColor: '#AAB7B8', backgroundColor: colors.bgPage },
          },
          sizeSmall: { padding: '4px 12px', fontSize: '12px', borderRadius: 6 },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            borderRadius: 12,
            border: `1px solid ${colors.border}`,
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
            transition: 'box-shadow 0.15s ease',
            '&:hover': { boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' },
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          outlined: { borderColor: colors.border, borderRadius: 12 },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 6, fontWeight: 500, fontSize: '12px' },
          colorPrimary: { backgroundColor: colors.blueLight, color: colors.blue, border: `1px solid ${alpha(colors.blue, 0.2)}` },
          colorSecondary: { backgroundColor: colors.tealLight, color: colors.teal, border: `1px solid ${alpha(colors.teal, 0.2)}` },
          colorSuccess: { backgroundColor: colors.tealLight, color: colors.teal, border: `1px solid ${alpha(colors.teal, 0.2)}` },
          colorError: { backgroundColor: colors.redLight, color: colors.red, border: `1px solid ${alpha(colors.red, 0.2)}` },
          colorWarning: { backgroundColor: colors.orangeLight, color: colors.orange, border: `1px solid ${alpha(colors.orange, 0.2)}` },
          colorInfo: { backgroundColor: colors.blueLight, color: colors.blue, border: `1px solid ${alpha(colors.blue, 0.2)}` },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.04)',
            borderBottom: `1px solid ${colors.border}`,
            backgroundColor: colors.bgCard,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: colors.primary,
            color: 'rgba(255, 255, 255, 0.8)',
            borderRight: 'none',
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            margin: '2px 8px',
            padding: '10px 12px',
            fontSize: '14px',
            transition: 'all 0.15s ease',
            '&:hover': { backgroundColor: colors.primaryLight, color: '#fff' },
            '&.Mui-selected': {
              backgroundColor: 'rgba(0, 115, 187, 0.25)',
              color: '#fff',
              fontWeight: 500,
              borderLeft: `3px solid ${colors.blue}`,
              paddingLeft: '9px',
              '&:hover': { backgroundColor: 'rgba(0, 115, 187, 0.3)' },
            },
          },
        },
      },
      MuiListItemIcon: {
        styleOverrides: { root: { minWidth: 36, color: 'inherit', opacity: 0.8 } },
      },
      MuiTextField: {
        defaultProps: { size: 'small' },
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 8,
              '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#AAB7B8' },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: colors.blue, boxShadow: `0 0 0 3px ${alpha(colors.blue, 0.1)}` },
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { padding: '12px 16px', fontSize: '14px', borderColor: colors.borderSubtle },
          head: { fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.04em', color: colors.textSecondary, backgroundColor: colors.bgPage },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: { '&:hover': { backgroundColor: colors.bgHover } },
        },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: { height: 2, borderRadius: 1, backgroundColor: colors.blue },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: { textTransform: 'none', fontWeight: 500, fontSize: '14px', '&.Mui-selected': { fontWeight: 600, color: colors.blue } },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: { borderRadius: 12, boxShadow: '0 20px 25px rgba(0, 0, 0, 0.08), 0 8px 10px rgba(0, 0, 0, 0.04)' },
        },
      },
      MuiTooltip: {
        defaultProps: { arrow: true },
        styleOverrides: {
          tooltip: { backgroundColor: colors.primary, borderRadius: 6, fontSize: '12px' },
          arrow: { color: colors.primary },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .Mui-checked': { color: colors.blue },
            '& .Mui-checked + .MuiSwitch-track': { backgroundColor: colors.blue },
          },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { borderRadius: 4, height: 4, backgroundColor: isLight ? '#EAEDED' : '#253545' },
          bar: { borderRadius: 4 },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            textTransform: 'none', fontWeight: 500, borderRadius: 8, fontSize: '14px',
            '&.Mui-selected': { backgroundColor: alpha(colors.blue, 0.1), color: colors.blue, borderColor: colors.blue },
          },
        },
      },
    },
  });
}

export function getInitialMode() {
  if (typeof window === 'undefined') return 'light';
  const stored = localStorage.getItem('applypilot-theme-mode');
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
