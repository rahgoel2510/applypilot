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
  { key: 'candidate', label: 'Candidate' },
  { key: 'search', label: 'Job Search' },
  { key: 'scheduler', label: 'Scheduler' },
  { key: 'selflearning', label: 'Self-Learning' },
  { key: 'inmail', label: 'InMail' },
  { key: 'advanced', label: 'Advanced' },
];

function StatusBadge({ configured }) {
  return configured ? (
    <Chip icon={<CheckCircleIcon />} label="Set" size="small" color="success" variant="outlined" sx={{ height: 20, fontSize: '11px', '& .MuiChip-icon': { fontSize: 12 } }} />
  ) : (
    <Chip icon={<CancelIcon />} label="—" size="small" color="default" variant="outlined" sx={{ height: 20, fontSize: '11px', '& .MuiChip-icon': { fontSize: 12 } }} />
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
          <Chip key={item} label={item} size="small" onDelete={() => onChange(value.filter((v) => v !== item))} sx={{ height: 22, fontSize: '11px' }} />
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
          <ChipInput label="Keywords" value={settings.search_keywords || []} onChange={(v) => update('search_keywords', v)} placeholder="e.g. Engineering Manager" />
          <ChipInput label="Locations" value={settings.search_locations || []} onChange={(v) => update('search_locations', v)} placeholder="e.g. Remote, Bengaluru, India" />
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 4 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Posted Within</Typography>
              <FormControl fullWidth size="small">
                <Select value={settings.posted_within} onChange={(e) => update('posted_within', e.target.value)} sx={{ fontSize: 12 }}>
                  <MenuItem value="24h">Last 24 hours</MenuItem>
                  <MenuItem value="week">Last 7 days</MenuItem>
                  <MenuItem value="month">Last 30 days</MenuItem>
                  <MenuItem value="any">Any time</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 4 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Initial Scan Window</Typography>
              <FormControl fullWidth size="small">
                <Select value={settings.initial_scan_window || 'week'} onChange={(e) => update('initial_scan_window', e.target.value)} sx={{ fontSize: 12 }}>
                  <MenuItem value="24h">24 hours</MenuItem>
                  <MenuItem value="week">1 week</MenuItem>
                  <MenuItem value="month">1 month</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 4 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Max Postings/Run</Typography>
              <TextField fullWidth size="small" type="number" value={settings.max_postings_per_run} onChange={(e) => update('max_postings_per_run', parseInt(e.target.value) || 0)} inputProps={{ min: 1, max: 200 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
            </Grid>
            <Grid size={{ xs: 4 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Daily Application Limit</Typography>
              <TextField fullWidth size="small" type="number" value={settings.daily_application_limit || 80} onChange={(e) => update('daily_application_limit', parseInt(e.target.value) || 80)} inputProps={{ min: 10, max: 200 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
            </Grid>
          </Grid>
          <Box sx={{ mt: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600 }}>Match Threshold: {settings.match_threshold}%</Typography>
            <Slider size="small" value={settings.match_threshold} onChange={(_, v) => update('match_threshold', v)} min={30} max={100} step={5} valueLabelDisplay="auto" marks={[{value:50,label:'50'},{value:70,label:'70'},{value:80,label:'80'},{value:100,label:'100'}]} sx={{ py: 1, '& .MuiSlider-markLabel': { fontSize: '0.6rem' } }} />
          </Box>
          <Box sx={{ mt: 1 }}>
            <FormControlLabel control={<Switch size="small" checked={settings.fallback_scoring !== false} onChange={(e) => update('fallback_scoring', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Fallback keyword scoring (when no Premium)</Typography>} />
            <FormControlLabel control={<Switch size="small" checked={settings.track_external_apply !== false} onChange={(e) => update('track_external_apply', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Track external apply jobs (notify via Telegram)</Typography>} />
            <FormControlLabel control={<Switch size="small" checked={settings.skip_external} onChange={(e) => update('skip_external', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Skip external apply entirely (not recommended)</Typography>} />
          </Box>
        </>
      );
      case 'candidate': return (
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Name</Typography>
            <TextField fullWidth size="small" value={settings.candidate_name} onChange={(e) => update('candidate_name', e.target.value)} placeholder="Your full name" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Email</Typography>
            <TextField fullWidth size="small" value={settings.candidate_email} onChange={(e) => update('candidate_email', e.target.value)} placeholder="you@example.com" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Phone</Typography>
            <TextField fullWidth size="small" value={settings.candidate_phone} onChange={(e) => update('candidate_phone', e.target.value)} placeholder="+91-XXXXXXXXXX" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Default Resume</Typography>
            <TextField fullWidth size="small" value={settings.resume_path} onChange={(e) => update('resume_path', e.target.value)} placeholder="resume.pdf" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Notice Period</Typography>
            <TextField fullWidth size="small" value={settings.notice_period} onChange={(e) => update('notice_period', e.target.value)} placeholder="30 days" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Work Authorization</Typography>
            <TextField fullWidth size="small" value={settings.work_authorization} onChange={(e) => update('work_authorization', e.target.value)} placeholder="Authorized to work" sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Human Input Timeout (sec)</Typography>
            <TextField fullWidth size="small" type="number" value={settings.human_input_timeout || 300} onChange={(e) => update('human_input_timeout', parseInt(e.target.value) || 300)} inputProps={{ min: 60, max: 900 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 6 }}>
            <FormControlLabel control={<Switch size="small" checked={settings.willing_to_relocate} onChange={(e) => update('willing_to_relocate', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Willing to relocate</Typography>} sx={{ mt: 1 }} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <ChipInput label="Skills" value={settings.skills || []} onChange={(v) => update('skills', v)} placeholder="e.g. engineering management, system design" />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <ChipInput label="Preferred Cities" value={settings.preferred_cities || []} onChange={(v) => update('preferred_cities', v)} placeholder="e.g. Bangalore, Remote" />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.5 }}>Resume Mapping (keyword → resume file)</Typography>
            <Typography sx={{ fontSize: 10, color: 'text.secondary', mb: 1 }}>Format: One per line — "Keywords | resume_file.pdf". E.g: "Engineering Manager, Director | EM_Resume.pdf"</Typography>
            <TextField
              fullWidth size="small" multiline rows={3}
              value={settings.resume_mapping_text || ''}
              onChange={(e) => update('resume_mapping_text', e.target.value)}
              placeholder={"Engineering Manager, Director of Engineering | EM_Resume.pdf\nTPM, Technical Program Manager | TPM_Resume.pdf"}
              sx={{ '& .MuiInputBase-input': { fontSize: 11, fontFamily: 'monospace' } }}
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.5 }}>Pre-configured Sensitive Field Answers</Typography>
            <Typography sx={{ fontSize: 10, color: 'text.secondary', mb: 1 }}>Format: One per line — "field_name: answer". Agent auto-fills these without pausing.</Typography>
            <TextField
              fullWidth size="small" multiline rows={4}
              value={settings.sensitive_field_answers_text || ''}
              onChange={(e) => update('sensitive_field_answers_text', e.target.value)}
              placeholder={"salary_expectation: As per company standards\ncurrent_ctc: Confidential - happy to discuss\nyears_of_experience: 12\ngender: Male\nveteran_status: No"}
              sx={{ '& .MuiInputBase-input': { fontSize: 11, fontFamily: 'monospace' } }}
            />
          </Grid>
        </Grid>
      );
      case 'scheduler': return (
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 6 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Scan Interval (minutes)</Typography>
            <TextField fullWidth size="small" type="number" value={settings.interval_minutes || 60} onChange={(e) => update('interval_minutes', parseInt(e.target.value) || 60)} inputProps={{ min: 10, max: 480 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 3 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Active From</Typography>
            <TextField fullWidth size="small" type="number" value={settings.active_hours_start || 9} onChange={(e) => update('active_hours_start', parseInt(e.target.value) || 9)} inputProps={{ min: 0, max: 23 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 3 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Active Until</Typography>
            <TextField fullWidth size="small" type="number" value={settings.active_hours_end || 22} onChange={(e) => update('active_hours_end', parseInt(e.target.value) || 22)} inputProps={{ min: 0, max: 23 }} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 700, mt: 2, mb: 1, color: 'primary.main' }}>⚡ Urgent Mode (First-Week Sprint)</Typography>
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormControlLabel control={<Switch size="small" checked={settings.urgent_mode || false} onChange={(e) => update('urgent_mode', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Enable Urgent Mode (higher throughput for first week)</Typography>} />
          </Grid>
          <Grid size={{ xs: 4 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Urgent Interval (min)</Typography>
            <TextField fullWidth size="small" type="number" value={settings.urgent_interval_minutes || 30} onChange={(e) => update('urgent_interval_minutes', parseInt(e.target.value) || 30)} inputProps={{ min: 10, max: 120 }} disabled={!settings.urgent_mode} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 4 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Urgent Max Postings</Typography>
            <TextField fullWidth size="small" type="number" value={settings.urgent_max_postings || 100} onChange={(e) => update('urgent_max_postings', parseInt(e.target.value) || 100)} inputProps={{ min: 25, max: 200 }} disabled={!settings.urgent_mode} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 4 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Urgent Duration (days)</Typography>
            <TextField fullWidth size="small" type="number" value={settings.urgent_duration_days || 7} onChange={(e) => update('urgent_duration_days', parseInt(e.target.value) || 7)} inputProps={{ min: 1, max: 30 }} disabled={!settings.urgent_mode} sx={{ '& .MuiInputBase-input': { fontSize: 12, py: 0.75 } }} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Typography sx={{ fontSize: 10, color: 'text.secondary', mt: 1 }}>Urgent mode auto-disables after the configured duration. Scans every 30min with 100 jobs/run instead of the normal interval.</Typography>
          </Grid>
        </Grid>
      );
      case 'selflearning': return (
        <>
          <Typography sx={{ fontSize: 12, color: 'text.secondary', mb: 2 }}>Boost scores for target companies and penalize blocklist companies from day 1. The agent also learns from your actions over time.</Typography>
          <ChipInput label="🎯 Target Companies (+boost)" value={settings.target_companies || []} onChange={(v) => update('target_companies', v)} placeholder="e.g. Google, Microsoft, Amazon" />
          <ChipInput label="🚫 Blocklist Companies (-penalty)" value={settings.blocklist_companies || []} onChange={(v) => update('blocklist_companies', v)} placeholder="e.g. Wipro, TCS, Infosys" />
          <Grid container spacing={1.5} sx={{ mt: 1 }}>
            <Grid size={{ xs: 6 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600 }}>Target Boost: +{Math.round((settings.target_boost || 0.15) * 100)}%</Typography>
              <Slider size="small" value={Math.round((settings.target_boost || 0.15) * 100)} onChange={(_, v) => update('target_boost', v / 100)} min={5} max={30} step={5} valueLabelDisplay="auto" valueLabelFormat={(v) => `+${v}%`} sx={{ py: 1 }} />
            </Grid>
            <Grid size={{ xs: 6 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600 }}>Blocklist Penalty: -{Math.round((settings.blocklist_penalty || 0.20) * 100)}%</Typography>
              <Slider size="small" value={Math.round((settings.blocklist_penalty || 0.20) * 100)} onChange={(_, v) => update('blocklist_penalty', v / 100)} min={5} max={40} step={5} valueLabelDisplay="auto" valueLabelFormat={(v) => `-${v}%`} sx={{ py: 1 }} />
            </Grid>
          </Grid>
        </>
      );
      case 'inmail': return (
        <>
          <FormControlLabel control={<Switch size="small" checked={settings.inmail_enabled} onChange={(e) => update('inmail_enabled', e.target.checked)} />} label={<Typography sx={{ fontSize: 12 }}>Enable InMail Drafting</Typography>} />
          <FormControlLabel sx={{ display: 'block', mt: 1 }} control={<Switch size="small" checked={settings.inmail_auto_send} onChange={(e) => update('inmail_auto_send', e.target.checked)} disabled={!settings.inmail_enabled} />} label={<Typography sx={{ fontSize: 12 }}>Auto-send (without review)</Typography>} />
          <Box sx={{ mt: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Template</Typography>
            <TextField fullWidth size="small" multiline rows={4} value={settings.inmail_template} onChange={(e) => update('inmail_template', e.target.value)} placeholder={"Hi {name},\n\nI noticed your team..."} disabled={!settings.inmail_enabled} sx={{ '& .MuiInputBase-input': { fontSize: 12 } }} />
            <Typography sx={{ fontSize: 11, color: 'text.secondary', mt: 0.5 }}>Variables: {'{name}'}, {'{role}'}, {'{company}'}, {'{skills}'}</Typography>
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
          <Typography sx={{ fontSize: 11, color: 'warning.main', mt: 0.5 }}>⚠ Debug generates large logs.</Typography>
        </>
      );
      default: return null;
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2 }}>
      {/* Sticky top bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1.5, mb: 2, borderBottom: '1px solid', borderColor: '#D5DBDB' }}>
        <Typography variant="h3">Settings</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" startIcon={<RestartAltIcon sx={{ fontSize: 14 }} />} onClick={handleReset} sx={{ color: 'text.secondary', textTransform: 'none' }}>Reset</Button>
          <Button variant="contained" size="small" startIcon={saving ? <CircularProgress size={14} color="inherit" /> : <SaveIcon sx={{ fontSize: 14 }} />} onClick={handleSave} disabled={saving}>Save</Button>
        </Box>
      </Box>

      {/* 2-column layout */}
      <Grid container sx={{ flex: 1, overflow: 'hidden', border: '1px solid', borderColor: '#D5DBDB', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
        {/* Sidebar */}
        <Grid size={{ xs: 12, md: 2.5 }} sx={{ borderRight: '1px solid', borderColor: '#D5DBDB' }}>
          <List dense disablePadding sx={{ pt: 1 }}>
            {GROUPS.map((g) => (
              <ListItemButton key={g.key} selected={group === g.key} onClick={() => setGroup(g.key)} sx={{ py: 0.75, px: 2, minHeight: 36, '&.Mui-selected': { bgcolor: 'action.selected' } }}>
                <ListItemText primary={g.label} primaryTypographyProps={{ fontSize: '13px', fontWeight: group === g.key ? 600 : 400 }} />
              </ListItemButton>
            ))}
          </List>
        </Grid>

        {/* Content */}
        <Grid size={{ xs: 12, md: 9.5 }} sx={{ p: 2.5, overflow: 'auto' }}>
          {renderGroup()}
        </Grid>
      </Grid>
    </Box>
  );
}
