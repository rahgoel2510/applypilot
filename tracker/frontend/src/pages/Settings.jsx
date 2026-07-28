import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, Button, Switch, FormControlLabel, Chip,
  Slider, Select, MenuItem, FormControl, IconButton, InputAdornment,
  CircularProgress, Alert, Grid, List, ListItemButton, ListItemText,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import SendIcon from '@mui/icons-material/Send';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useSnackbar } from 'notistack';
import { getSettings, updateSettings, testConnection } from '../api';

const GROUPS = [
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'ai', label: 'AI Model' },
  { key: 'telegram', label: 'Telegram' },
  { key: 'search', label: 'Job Search' },
  { key: 'application', label: 'Application' },
  { key: 'inmail', label: 'InMail' },
  { key: 'advanced', label: 'Advanced' },
];

function StatusBadge({ configured }) {
  return configured ? (
    <Chip icon={<CheckCircleIcon />} label="Set" size="small" color="success" variant="outlined" sx={{ height: 18, fontSize: '0.6rem', '& .MuiChip-icon': { fontSize: 12 } }} />
  ) : (
    <Chip icon={<CancelIcon />} label="—" size="small" color="default" variant="outlined" sx={{ height: 18, fontSize: '0.6rem', '& .MuiChip-icon': { fontSize: 12 } }} />
  );
}

function MaskedField({ label, value, onChange, configured, placeholder, multiline }) {
  const [visible, setVisible] = useState(false);
  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 600 }}>{label}</Typography>
        <StatusBadge configured={configured} />
      </Box>
      <TextField
        fullWidth
        size="small"
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        multiline={multiline}
        rows={multiline ? 3 : undefined}
        sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }}
        InputProps={{
          endAdornment: !multiline && (
            <InputAdornment position="end">
              <IconButton size="small" onClick={() => setVisible(!visible)} sx={{ p: 0.25 }}>
                {visible ? <VisibilityOffIcon sx={{ fontSize: 14 }} /> : <VisibilityIcon sx={{ fontSize: 14 }} />}
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
    </Box>
  );
}

function ChipInput({ label, value, onChange, placeholder }) {
  const [input, setInput] = useState('');
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      if (!value.includes(input.trim())) onChange([...value, input.trim()]);
      setInput('');
    }
  };
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>{label}</Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.5 }}>
        {value.map((item) => (
          <Chip key={item} label={item} size="small" onDelete={() => onChange(value.filter((v) => v !== item))} sx={{ height: 20, fontSize: '0.65rem' }} />
        ))}
      </Box>
      <TextField
        fullWidth size="small" value={input}
        onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
        placeholder={placeholder || 'Type and press Enter'}
        sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }}
      />
    </Box>
  );
}

export default function Settings() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [group, setGroup] = useState('linkedin');
  const [error, setError] = useState(null);
  const [testingTelegram, setTestingTelegram] = useState(false);

  const [settings, setSettings] = useState({
    linkedin_email: '', linkedin_password: '', linkedin_session_cookie: '',
    ai_provider: 'openrouter', ai_model: '', ai_api_key: '',
    telegram_bot_token: '', telegram_chat_id: '',
    search_keywords: [], search_locations: [], experience_levels: [],
    posted_within: '24h', match_threshold: 70, max_postings_per_run: 50, skip_external: false,
    candidate_name: '', candidate_email: '', candidate_phone: '', resume_path: '',
    notice_period: '', willing_to_relocate: false, work_authorization: '', preferred_cities: [],
    inmail_enabled: false, inmail_auto_send: false, inmail_template: '',
    browser_headless: true, data_dir: './data', debug_mode: false,
  });

  const [configuredFields, setConfiguredFields] = useState({});

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSettings();
      if (data.settings) {
        const mapped = {}, configured = {};
        data.settings.forEach((s) => {
          const key = s.key.toLowerCase();
          mapped[key] = s.current_value || s.masked_value || '';
          configured[key] = s.is_set;
        });
        setSettings((prev) => ({ ...prev, ...mapped }));
        setConfiguredFields(configured);
      }
    } catch { setError('Failed to load settings'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(settings);
      enqueueSnackbar('Settings saved', { variant: 'success' });
      await loadSettings();
    } catch { enqueueSnackbar('Failed to save', { variant: 'error' }); }
    finally { setSaving(false); }
  };

  const handleReset = () => {
    if (window.confirm('Reset all settings to defaults?')) {
      setSettings({
        linkedin_email: '', linkedin_password: '', linkedin_session_cookie: '',
        ai_provider: 'openrouter', ai_model: '', ai_api_key: '',
        telegram_bot_token: '', telegram_chat_id: '',
        search_keywords: [], search_locations: [], experience_levels: [],
        posted_within: '24h', match_threshold: 70, max_postings_per_run: 50, skip_external: false,
        candidate_name: '', candidate_email: '', candidate_phone: '', resume_path: '',
        notice_period: '', willing_to_relocate: false, work_authorization: '', preferred_cities: [],
        inmail_enabled: false, inmail_auto_send: false, inmail_template: '',
        browser_headless: true, data_dir: './data', debug_mode: false,
      });
      enqueueSnackbar('Reset (not saved yet)', { variant: 'info' });
    }
  };

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    try {
      const result = await testConnection('telegram');
      enqueueSnackbar(result.success ? 'Telegram OK!' : (result.message || 'Failed'), { variant: result.success ? 'success' : 'error' });
    } catch { enqueueSnackbar('Telegram test failed', { variant: 'error' }); }
    finally { setTestingTelegram(false); }
  };

  const update = (key, value) => setSettings((prev) => ({ ...prev, [key]: value }));

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress size={24} /></Box>;
  if (error) return <Alert severity="error" sx={{ fontSize: 12 }}>{error}</Alert>;

  const renderGroup = () => {
    switch (group) {
      case 'linkedin': return (
        <>
          <MaskedField label="Email" value={settings.linkedin_email} onChange={(v) => update('linkedin_email', v)} configured={configuredFields.linkedin_email} placeholder="your-email@example.com" />
          <MaskedField label="Password" value={settings.linkedin_password} onChange={(v) => update('linkedin_password', v)} configured={configuredFields.linkedin_password} placeholder="••••••••" />
          <MaskedField label="Session Cookie (li_at)" value={settings.linkedin_session_cookie} onChange={(v) => update('linkedin_session_cookie', v)} configured={configuredFields.linkedin_session_cookie} placeholder="Paste li_at cookie" />
          <Typography sx={{ fontSize: 11, color: 'text.secondary', mt: 0.5 }}>Session cookie is preferred over email/password.</Typography>
        </>
      );
      case 'ai': return (
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Provider</Typography>
            <FormControl fullWidth size="small">
              <Select value={settings.ai_provider} onChange={(e) => update('ai_provider', e.target.value)} sx={{ fontSize: 12 }}>
                <MenuItem value="openrouter">OpenRouter</MenuItem>
                <MenuItem value="openai">OpenAI</MenuItem>
                <MenuItem value="anthropic">Anthropic</MenuItem>
                <MenuItem value="ollama">Ollama (Local)</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Model Name</Typography>
            <TextField fullWidth size="small" value={settings.ai_model} onChange={(e) => update('ai_model', e.target.value)} placeholder="e.g. gpt-4o-mini" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <MaskedField label="API Key" value={settings.ai_api_key} onChange={(v) => update('ai_api_key', v)} configured={configuredFields.ai_api_key} placeholder="sk-..." />
          </Grid>
        </Grid>
      );
      case 'telegram': return (
        <>
          <MaskedField label="Bot Token" value={settings.telegram_bot_token} onChange={(v) => update('telegram_bot_token', v)} configured={configuredFields.telegram_bot_token} placeholder="123456:ABC-DEF..." />
          <Grid container spacing={1.5} alignItems="flex-end">
            <Grid size={{ xs: 8 }}>
              <Box sx={{ mb: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 600 }}>Chat ID</Typography>
                  <StatusBadge configured={configuredFields.telegram_chat_id} />
                </Box>
                <TextField fullWidth size="small" value={settings.telegram_chat_id} onChange={(e) => update('telegram_chat_id', e.target.value)} placeholder="e.g. 123456789" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
              </Box>
            </Grid>
            <Grid size={{ xs: 4 }}>
              <Button variant="outlined" size="small" fullWidth startIcon={testingTelegram ? <CircularProgress size={12} /> : <SendIcon sx={{ fontSize: 14 }} />} onClick={handleTestTelegram} disabled={testingTelegram} sx={{ fontSize: 11, mb: 1.5, py: 0.75 }}>Test</Button>
            </Grid>
          </Grid>
        </>
      );
      case 'search': return (
        <>
          <ChipInput label="Keywords" value={settings.search_keywords || []} onChange={(v) => update('search_keywords', v)} placeholder="e.g. Software Engineer" />
          <ChipInput label="Locations" value={settings.search_locations || []} onChange={(v) => update('search_locations', v)} placeholder="e.g. Remote, Bengaluru" />
          <ChipInput label="Experience Levels" value={settings.experience_levels || []} onChange={(v) => update('experience_levels', v)} placeholder="e.g. Mid-Senior" />
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 6 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Posted Within</Typography>
              <FormControl fullWidth size="small">
                <Select value={settings.posted_within} onChange={(e) => update('posted_within', e.target.value)} sx={{ fontSize: 12 }}>
                  <MenuItem value="1h">Last hour</MenuItem>
                  <MenuItem value="24h">Last 24 hours</MenuItem>
                  <MenuItem value="7d">Last 7 days</MenuItem>
                  <MenuItem value="30d">Last 30 days</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Max Postings/Run</Typography>
              <TextField fullWidth size="small" type="number" value={settings.max_postings_per_run} onChange={(e) => update('max_postings_per_run', parseInt(e.target.value) || 0)} inputProps={{ min: 1, max: 200 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
            </Grid>
          </Grid>
          <Box sx={{ mt: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600 }}>Match Threshold: {settings.match_threshold}</Typography>
            <Slider size="small" value={settings.match_threshold} onChange={(_, v) => update('match_threshold', v)} min={0} max={100} valueLabelDisplay="auto" sx={{ py: 1 }} />
          </Box>
          <FormControlLabel control={<Switch size="small" checked={settings.skip_external} onChange={(e) => update('skip_external', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Easy Apply only</Typography>} />
        </>
      );
      case 'application': return (
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Name</Typography>
            <TextField fullWidth size="small" value={settings.candidate_name} onChange={(e) => update('candidate_name', e.target.value)} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Email</Typography>
            <TextField fullWidth size="small" value={settings.candidate_email} onChange={(e) => update('candidate_email', e.target.value)} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Phone</Typography>
            <TextField fullWidth size="small" value={settings.candidate_phone} onChange={(e) => update('candidate_phone', e.target.value)} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Resume Path</Typography>
            <TextField fullWidth size="small" value={settings.resume_path} onChange={(e) => update('resume_path', e.target.value)} placeholder="./resume.pdf" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Notice Period</Typography>
            <TextField fullWidth size="small" value={settings.notice_period} onChange={(e) => update('notice_period', e.target.value)} placeholder="e.g. 30 days" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Work Auth</Typography>
            <TextField fullWidth size="small" value={settings.work_authorization} onChange={(e) => update('work_authorization', e.target.value)} placeholder="e.g. Citizen" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormControlLabel control={<Switch size="small" checked={settings.willing_to_relocate} onChange={(e) => update('willing_to_relocate', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Willing to relocate</Typography>} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <ChipInput label="Preferred Cities" value={settings.preferred_cities || []} onChange={(v) => update('preferred_cities', v)} placeholder="e.g. Bengaluru" />
          </Grid>
        </Grid>
      );
      case 'inmail': return (
        <>
          <FormControlLabel control={<Switch size="small" checked={settings.inmail_enabled} onChange={(e) => update('inmail_enabled', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Enable InMail Drafting</Typography>} />
          <FormControlLabel sx={{ display: 'block', mt: 1 }} control={<Switch size="small" checked={settings.inmail_auto_send} onChange={(e) => update('inmail_auto_send', e.target.checked)} disabled={!settings.inmail_enabled} />} label={<Typography sx={{ fontSize: 12 }}>Auto-send (without review)</Typography>} />
          <Box sx={{ mt: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Template</Typography>
            <TextField fullWidth size="small" multiline rows={4} value={settings.inmail_template} onChange={(e) => update('inmail_template', e.target.value)} placeholder={"Hi {name},\n\nI noticed your team..."} disabled={!settings.inmail_enabled} sx={{ '& .MuiInputBase-input': { fontSize: 12 } }} />
            <Typography sx={{ fontSize: 10, color: 'text.secondary', mt: 0.5 }}>Variables: {'{name}'}, {'{role}'}, {'{company}'}, {'{skills}'}</Typography>
          </Box>
        </>
      );
      case 'advanced': return (
        <>
          <FormControlLabel control={<Switch size="small" checked={settings.browser_headless} onChange={(e) => update('browser_headless', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Headless browser</Typography>} />
          <Box sx={{ mt: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Data Directory</Typography>
            <TextField fullWidth size="small" value={settings.data_dir} onChange={(e) => update('data_dir', e.target.value)} placeholder="./data" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Box>
          <FormControlLabel sx={{ mt: 1.5, display: 'block' }} control={<Switch size="small" checked={settings.debug_mode} onChange={(e) => update('debug_mode', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Debug mode (verbose logging)</Typography>} />
          <Typography sx={{ fontSize: 10, color: 'warning.main', mt: 0.5 }}>⚠ Debug generates large logs.</Typography>
        </>
      );
      default: return null;
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      {/* Sticky top bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 0.75, px: 0.5, borderBottom: 1, borderColor: 'divider', position: 'sticky', top: 0, bgcolor: 'background.paper', zIndex: 10 }}>
        <Typography sx={{ fontSize: 14, fontWeight: 700 }}>Settings</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" startIcon={<RestartAltIcon sx={{ fontSize: 14 }} />} onClick={handleReset} sx={{ fontSize: 11, color: 'text.secondary', textTransform: 'none', py: 0.25 }}>Reset</Button>
          <Button variant="contained" size="small" startIcon={saving ? <CircularProgress size={12} color="inherit" /> : <SaveIcon sx={{ fontSize: 14 }} />} onClick={handleSave} disabled={saving} sx={{ fontSize: 11, py: 0.25, px: 1.5 }}>Save</Button>
        </Box>
      </Box>

      {/* 2-column layout */}
      <Grid container sx={{ flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <Grid size={{ xs: 12, md: 2.5 }} sx={{ borderRight: 1, borderColor: 'divider' }}>
          <List dense disablePadding sx={{ pt: 0.5 }}>
            {GROUPS.map((g) => (
              <ListItemButton key={g.key} selected={group === g.key} onClick={() => setGroup(g.key)} sx={{ py: 0.5, px: 1.5, minHeight: 32, '&.Mui-selected': { bgcolor: 'action.selected' } }}>
                <ListItemText primary={g.label} primaryTypographyProps={{ fontSize: 12, fontWeight: group === g.key ? 600 : 400 }} />
              </ListItemButton>
            ))}
          </List>
        </Grid>

        {/* Content */}
        <Grid size={{ xs: 12, md: 9.5 }} sx={{ p: 1.5, overflow: 'auto' }}>
          {renderGroup()}
        </Grid>
      </Grid>
    </Box>
  );
}
