import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, Button, Switch, FormControlLabel, Chip,
  Slider, Select, MenuItem, FormControl, IconButton, InputAdornment,
  CircularProgress, Alert, Grid, List, ListItemButton, ListItemText,
  Paper, Divider,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import SendIcon from '@mui/icons-material/Send';
import { useSnackbar } from 'notistack';
import { getSettings, updateSettings, testConnection, getConfigYaml, updateConfigYaml } from '../api';

const GROUPS = [
  { key: 'candidate', label: '👤 Candidate', desc: 'Your profile info' },
  { key: 'search', label: '🔍 Job Search', desc: 'Keywords, locations, scoring' },
  { key: 'scheduler', label: '⏰ Scheduler', desc: 'Timing & urgent mode' },
  { key: 'selflearning', label: '🧠 Self-Learning', desc: 'Target & blocklist' },
  { key: 'telegram', label: '📬 Telegram', desc: 'Notifications' },
  { key: 'ai', label: '🤖 AI Model', desc: 'OpenRouter / LLM' },
  { key: 'inmail', label: '✉️ InMail', desc: 'Cold outreach' },
  { key: 'advanced', label: '⚙️ Advanced', desc: 'Browser, debug' },
];

function MaskedField({ label, value, onChange, placeholder }) {
  const [visible, setVisible] = useState(false);
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>{label}</Typography>
      <TextField fullWidth size="small" type={visible ? 'text' : 'password'}
        value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        InputProps={{ endAdornment: (
          <InputAdornment position="end">
            <IconButton size="small" onClick={() => setVisible(!visible)}>
              {visible ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
            </IconButton>
          </InputAdornment>
        )}} />
    </Box>
  );
}

function Field({ label, value, onChange, placeholder, type, multiline, rows, disabled, helperText }) {
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>{label}</Typography>
      <TextField fullWidth size="small" type={type || 'text'} value={value ?? ''}
        onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
        placeholder={placeholder} multiline={multiline} rows={rows} disabled={disabled}
        helperText={helperText}
        sx={multiline ? { '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: 12 } } : {}} />
    </Box>
  );
}

function ChipInput({ label, value, onChange, placeholder }) {
  const [input, setInput] = useState('');
  const items = Array.isArray(value) ? value : [];
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      if (!items.includes(input.trim())) onChange([...items, input.trim()]);
      setInput('');
    }
  };
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>{label}</Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
        {items.map((item) => (
          <Chip key={item} label={item} size="small" onDelete={() => onChange(items.filter(v => v !== item))} />
        ))}
      </Box>
      <TextField fullWidth size="small" value={input}
        onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
        placeholder={placeholder || 'Type and press Enter'} />
    </Box>
  );
}

export default function Settings() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [group, setGroup] = useState('candidate');
  const [testingTelegram, setTestingTelegram] = useState(false);

  // Config from config.yaml
  const [config, setConfig] = useState({});
  // Secrets from DB
  const [secrets, setSecrets] = useState({});

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [yamlData, secretsData] = await Promise.all([getConfigYaml(), getSettings()]);
      setConfig(yamlData || {});
      if (secretsData.settings) {
        const mapped = {};
        secretsData.settings.forEach(s => { mapped[s.key.toLowerCase()] = s.masked_value || ''; });
        setSecrets(mapped);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const updateField = (section, key, value) => {
    setConfig(prev => ({
      ...prev,
      [section]: { ...(prev[section] || {}), [key]: value },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateConfigYaml(config);
      // Also save secrets if changed
      const secretUpdates = {};
      if (secrets.telegram_bot_token_new) secretUpdates.TELEGRAM_BOT_TOKEN = secrets.telegram_bot_token_new;
      if (secrets.telegram_chat_id_new) secretUpdates.TELEGRAM_CHAT_ID = secrets.telegram_chat_id_new;
      if (secrets.openai_api_key_new) secretUpdates.OPENAI_API_KEY = secrets.openai_api_key_new;
      if (secrets.linkedin_email_new) secretUpdates.LINKEDIN_EMAIL = secrets.linkedin_email_new;
      if (secrets.linkedin_password_new) secretUpdates.LINKEDIN_PASSWORD = secrets.linkedin_password_new;
      if (Object.keys(secretUpdates).length > 0) await updateSettings(secretUpdates);
      enqueueSnackbar('Settings saved ✓', { variant: 'success' });
      await loadAll();
    } catch { enqueueSnackbar('Save failed', { variant: 'error' }); }
    finally { setSaving(false); }
  };

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    try {
      const r = await testConnection('telegram');
      enqueueSnackbar(r.success ? 'Telegram OK! ✓' : (r.message || 'Failed'), { variant: r.success ? 'success' : 'error' });
    } catch { enqueueSnackbar('Test failed', { variant: 'error' }); }
    finally { setTestingTelegram(false); }
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}><CircularProgress /></Box>;

  const c = (section) => config[section] || {};

  const renderGroup = () => {
    switch (group) {
      case 'candidate': return (
        <>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Full Name" value={c('candidate').name} onChange={v => updateField('candidate', 'name', v)} placeholder="Rahul Goel" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Email" value={c('candidate').email} onChange={v => updateField('candidate', 'email', v)} placeholder="you@example.com" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Phone" value={c('candidate').phone} onChange={v => updateField('candidate', 'phone', v)} placeholder="+91-XXXXXXXXXX" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Default Resume Filename" value={c('candidate').resume_filename} onChange={v => updateField('candidate', 'resume_filename', v)} placeholder="resume.pdf" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Notice Period" value={c('candidate').notice_period} onChange={v => updateField('candidate', 'notice_period', v)} placeholder="30 days" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Work Authorization" value={c('candidate').work_authorization} onChange={v => updateField('candidate', 'work_authorization', v)} placeholder="Authorized to work" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}><Field label="Human Input Timeout (seconds)" value={c('candidate').human_input_timeout} onChange={v => updateField('candidate', 'human_input_timeout', Number(v))} type="number" placeholder="300" /></Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <FormControlLabel sx={{ mt: 3 }} control={<Switch checked={c('candidate').willing_to_relocate ?? true} onChange={e => updateField('candidate', 'willing_to_relocate', e.target.checked)} />} label="Willing to relocate" />
            </Grid>
          </Grid>
          <Divider sx={{ my: 3 }} />
          <ChipInput label="Skills" value={c('candidate').skills} onChange={v => updateField('candidate', 'skills', v)} placeholder="engineering management, system design, agile..." />
          <ChipInput label="Preferred Cities" value={c('candidate').preferred_cities} onChange={v => updateField('candidate', 'preferred_cities', v)} placeholder="Bangalore, Hyderabad, Remote..." />
          <Divider sx={{ my: 3 }} />
          <Field label="Resume Mapping" value={(c('candidate').resume_mapping || []).map(m => `${(m.keywords||[]).join(', ')} | ${m.resume}`).join('\n')}
            onChange={v => updateField('candidate', 'resume_mapping', v.split('\n').filter(l=>l.includes('|')).map(l => { const [kw,r]=l.split('|'); return {keywords: kw.split(',').map(k=>k.trim()), resume: (r||'').trim()}; }))}
            multiline rows={3} placeholder={"Engineering Manager, Director | EM_Resume.pdf\nTPM, Program Manager | TPM_Resume.pdf"}
            helperText="One per line: keywords | resume_file.pdf" />
          <Field label="Pre-configured Sensitive Answers" value={Object.entries(c('candidate').sensitive_field_answers || {}).map(([k,v]) => `${k}: ${v}`).join('\n')}
            onChange={v => updateField('candidate', 'sensitive_field_answers', Object.fromEntries(v.split('\n').filter(l=>l.includes(':')).map(l => { const i=l.indexOf(':'); return [l.slice(0,i).trim(), l.slice(i+1).trim()]; })))}
            multiline rows={4} placeholder={"salary_expectation: As per company standards\ncurrent_ctc: Confidential\nyears_of_experience: 12"}
            helperText="One per line: field_name: answer (auto-fills without pausing)" />
        </>
      );
      case 'search': return (
        <>
          <ChipInput label="Keywords" value={c('job_search').keywords} onChange={v => updateField('job_search', 'keywords', v)} placeholder="Engineering Manager, TPM..." />
          <ChipInput label="Locations" value={c('job_search').locations} onChange={v => updateField('job_search', 'locations', v)} placeholder="India, Bangalore, Remote..." />
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, md: 3 }}>
              <Typography variant="body2" fontWeight={600} mb={0.5}>Posted Within</Typography>
              <FormControl fullWidth size="small">
                <Select value={c('job_search').posted_within || '24h'} onChange={e => updateField('job_search', 'posted_within', e.target.value)}>
                  <MenuItem value="24h">Last 24 hours</MenuItem>
                  <MenuItem value="week">Last week</MenuItem>
                  <MenuItem value="month">Last month</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6, md: 3 }}>
              <Typography variant="body2" fontWeight={600} mb={0.5}>First Run Window</Typography>
              <FormControl fullWidth size="small">
                <Select value={c('job_search').initial_scan_window || 'week'} onChange={e => updateField('job_search', 'initial_scan_window', e.target.value)}>
                  <MenuItem value="24h">24 hours</MenuItem>
                  <MenuItem value="week">1 week</MenuItem>
                  <MenuItem value="month">1 month</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6, md: 3 }}><Field label="Max Jobs/Run" value={c('job_search').max_postings_per_run} onChange={v => updateField('job_search', 'max_postings_per_run', Number(v))} type="number" /></Grid>
            <Grid size={{ xs: 6, md: 3 }}><Field label="Daily Cap" value={c('job_search').daily_application_limit} onChange={v => updateField('job_search', 'daily_application_limit', Number(v))} type="number" /></Grid>
          </Grid>
          <Box sx={{ mt: 2, mb: 3 }}>
            <Typography variant="body2" fontWeight={600}>Match Threshold: {Math.round((c('job_search').match_threshold || 0.80) * 100)}%</Typography>
            <Slider value={Math.round((c('job_search').match_threshold || 0.80) * 100)} onChange={(_, v) => updateField('job_search', 'match_threshold', v / 100)}
              min={30} max={100} step={5} valueLabelDisplay="auto" valueLabelFormat={v => `${v}%`}
              marks={[{value:50,label:'50%'},{value:70,label:'70%'},{value:80,label:'80%'}]} size="small" sx={{ mt: 1 }} />
          </Box>
          <FormControlLabel control={<Switch checked={c('job_search').fallback_scoring !== false} onChange={e => updateField('job_search', 'fallback_scoring', e.target.checked)} />} label="Fallback keyword scoring (no Premium needed)" />
          <FormControlLabel control={<Switch checked={c('job_search').track_external_apply !== false} onChange={e => updateField('job_search', 'track_external_apply', e.target.checked)} />} label="Track external apply jobs (Telegram notification)" />
          <FormControlLabel control={<Switch checked={c('job_search').skip_external_apply === true} onChange={e => updateField('job_search', 'skip_external_apply', e.target.checked)} />} label="Skip external apply entirely" />
        </>
      );
      case 'scheduler': return (
        <Grid container spacing={2}>
          <Grid size={{ xs: 4 }}><Field label="Interval (minutes)" value={c('scheduler').interval_minutes} onChange={v => updateField('scheduler', 'interval_minutes', Number(v))} type="number" /></Grid>
          <Grid size={{ xs: 4 }}><Field label="Active From (hour)" value={c('scheduler').active_hours_start} onChange={v => updateField('scheduler', 'active_hours_start', Number(v))} type="number" /></Grid>
          <Grid size={{ xs: 4 }}><Field label="Active Until (hour)" value={c('scheduler').active_hours_end} onChange={v => updateField('scheduler', 'active_hours_end', Number(v))} type="number" /></Grid>
          <Grid size={{ xs: 12 }}><Divider sx={{ my: 1 }} /><Typography variant="subtitle1" fontWeight={700} color="primary">⚡ Urgent Mode</Typography></Grid>
          <Grid size={{ xs: 12 }}><FormControlLabel control={<Switch checked={c('scheduler').urgent_mode || false} onChange={e => updateField('scheduler', 'urgent_mode', e.target.checked)} />} label="Enable urgent mode (first-week sprint)" /></Grid>
          <Grid size={{ xs: 4 }}><Field label="Urgent Interval (min)" value={c('scheduler').urgent_interval_minutes} onChange={v => updateField('scheduler', 'urgent_interval_minutes', Number(v))} type="number" disabled={!c('scheduler').urgent_mode} /></Grid>
          <Grid size={{ xs: 4 }}><Field label="Urgent Max Jobs" value={c('scheduler').urgent_max_postings} onChange={v => updateField('scheduler', 'urgent_max_postings', Number(v))} type="number" disabled={!c('scheduler').urgent_mode} /></Grid>
          <Grid size={{ xs: 4 }}><Field label="Duration (days)" value={c('scheduler').urgent_duration_days} onChange={v => updateField('scheduler', 'urgent_duration_days', Number(v))} type="number" disabled={!c('scheduler').urgent_mode} /></Grid>
          <Grid size={{ xs: 12 }}><Typography variant="caption" color="text.secondary">Urgent mode scans more frequently with more jobs. Auto-disables after the set duration.</Typography></Grid>
        </Grid>
      );
      case 'selflearning': return (
        <>
          <Typography variant="body2" color="text.secondary" mb={2}>Boost target companies and penalize blocklist from day 1. The agent also learns from your Kanban actions.</Typography>
          <ChipInput label="🎯 Target Companies (score boost)" value={c('self_learning').target_companies} onChange={v => updateField('self_learning', 'target_companies', v)} placeholder="Google, Microsoft, Amazon..." />
          <ChipInput label="🚫 Blocklist Companies (score penalty)" value={c('self_learning').blocklist_companies} onChange={v => updateField('self_learning', 'blocklist_companies', v)} placeholder="Wipro, TCS, Infosys..." />
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid size={{ xs: 6 }}>
              <Typography variant="body2" fontWeight={600}>Target Boost: +{Math.round((c('self_learning').target_boost || 0.15) * 100)}%</Typography>
              <Slider value={Math.round((c('self_learning').target_boost || 0.15) * 100)} onChange={(_, v) => updateField('self_learning', 'target_boost', v / 100)}
                min={5} max={30} step={5} size="small" valueLabelDisplay="auto" valueLabelFormat={v => `+${v}%`} />
            </Grid>
            <Grid size={{ xs: 6 }}>
              <Typography variant="body2" fontWeight={600}>Blocklist Penalty: -{Math.round((c('self_learning').blocklist_penalty || 0.20) * 100)}%</Typography>
              <Slider value={Math.round((c('self_learning').blocklist_penalty || 0.20) * 100)} onChange={(_, v) => updateField('self_learning', 'blocklist_penalty', v / 100)}
                min={5} max={40} step={5} size="small" valueLabelDisplay="auto" valueLabelFormat={v => `-${v}%`} />
            </Grid>
          </Grid>
        </>
      );
      case 'telegram': return (
        <>
          <MaskedField label="Bot Token" value={secrets.telegram_bot_token_new || secrets.telegram_bot_token || ''} onChange={v => setSecrets(p => ({...p, telegram_bot_token_new: v}))} placeholder="123456:ABC-DEF1234..." />
          <Field label="Chat ID" value={secrets.telegram_chat_id_new || secrets.telegram_chat_id || ''} onChange={v => setSecrets(p => ({...p, telegram_chat_id_new: v}))} placeholder="123456789" />
          <Button variant="outlined" size="small" startIcon={testingTelegram ? <CircularProgress size={14} /> : <SendIcon />} onClick={handleTestTelegram} disabled={testingTelegram} sx={{ mt: 1 }}>
            Send Test Message
          </Button>
        </>
      );
      case 'ai': return (
        <>
          <MaskedField label="OpenRouter API Key" value={secrets.openai_api_key_new || secrets.openai_api_key || ''} onChange={v => setSecrets(p => ({...p, openai_api_key_new: v}))} placeholder="sk-or-v1-..." />
          <Typography variant="caption" color="text.secondary">Get a free key at <a href="https://openrouter.ai" target="_blank" rel="noreferrer">openrouter.ai</a></Typography>
        </>
      );
      case 'inmail': return (
        <>
          <FormControlLabel control={<Switch checked={c('inmail').enabled ?? true} onChange={e => updateField('inmail', 'enabled', e.target.checked)} />} label="Enable InMail drafting (post-application)" />
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid size={{ xs: 6 }}>
              <Typography variant="body2" fontWeight={600} mb={0.5}>Tone</Typography>
              <FormControl fullWidth size="small">
                <Select value={c('inmail').tone || 'professional'} onChange={e => updateField('inmail', 'tone', e.target.value)}>
                  <MenuItem value="professional">Professional</MenuItem>
                  <MenuItem value="casual">Casual</MenuItem>
                  <MenuItem value="confident">Confident</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 6 }}><Field label="Max Length (chars)" value={c('inmail').max_length} onChange={v => updateField('inmail', 'max_length', Number(v))} type="number" /></Grid>
          </Grid>
        </>
      );
      case 'advanced': return (
        <>
          <MaskedField label="LinkedIn Email" value={secrets.linkedin_email_new || secrets.linkedin_email || ''} onChange={v => setSecrets(p => ({...p, linkedin_email_new: v}))} placeholder="your-email@example.com" />
          <MaskedField label="LinkedIn Password" value={secrets.linkedin_password_new || secrets.linkedin_password || ''} onChange={v => setSecrets(p => ({...p, linkedin_password_new: v}))} placeholder="••••••••" />
          <Typography variant="caption" color="text.secondary" mb={2} display="block">Password is optional if you have an active browser session.</Typography>
        </>
      );
      default: return null;
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h3">Settings</Typography>
        <Button variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />} onClick={handleSave} disabled={saving}>
          Save All
        </Button>
      </Box>

      <Box sx={{ display: 'flex', flex: 1, gap: 2, overflow: 'hidden' }}>
        {/* Sidebar */}
        <Paper variant="outlined" sx={{ width: 200, flexShrink: 0, overflow: 'auto', borderRadius: 2 }}>
          <List dense disablePadding>
            {GROUPS.map(g => (
              <ListItemButton key={g.key} selected={group === g.key} onClick={() => setGroup(g.key)}
                sx={{ py: 1.5, '&.Mui-selected': { bgcolor: 'primary.main', color: 'white', '&:hover': { bgcolor: 'primary.dark' } } }}>
                <ListItemText primary={g.label} secondary={group === g.key ? null : g.desc}
                  primaryTypographyProps={{ fontSize: 13, fontWeight: group === g.key ? 700 : 500 }}
                  secondaryTypographyProps={{ fontSize: 10 }} />
              </ListItemButton>
            ))}
          </List>
        </Paper>

        {/* Content */}
        <Paper variant="outlined" sx={{ flex: 1, p: 3, overflow: 'auto', borderRadius: 2 }}>
          {renderGroup()}
        </Paper>
      </Box>
    </Box>
  );
}
