import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, Button, Switch, FormControlLabel, Chip,
  Slider, Select, MenuItem, FormControl, IconButton, InputAdornment,
  CircularProgress, Alert, Grid, List, ListItemButton, ListItemText,
  Paper, Divider, Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import SendIcon from '@mui/icons-material/Send';
import { useSnackbar } from 'notistack';
import { getSettings, updateSettings, testConnection } from '../api';

const GROUPS = [
  { key: 'Candidate', label: '👤 Candidate', desc: 'Your profile' },
  { key: 'Job Search', label: '🔍 Job Search', desc: 'Keywords & scoring' },
  { key: 'Scheduler', label: '⏰ Scheduler', desc: 'Timing & urgent mode' },
  { key: 'Company Preferences', label: '🏢 Companies', desc: 'Target & blocklist' },
  { key: 'Telegram', label: '📬 Telegram', desc: 'Notifications' },
  { key: 'AI', label: '🤖 AI Model', desc: 'LLM config' },
  { key: 'InMail', label: '✉️ InMail', desc: 'Cold outreach' },
  { key: 'LinkedIn', label: '🔐 LinkedIn', desc: 'Credentials' },
];

export default function Settings() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [group, setGroup] = useState('Candidate');
  const [settings, setSettings] = useState([]);
  const [values, setValues] = useState({});
  const [missingFields, setMissingFields] = useState([]);
  const [showMissing, setShowMissing] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSettings();
      setSettings(data.settings || []);
      const vals = {};
      (data.settings || []).forEach(s => {
        vals[s.key] = s.current_value || s.masked_value || '';
      });
      setValues(vals);

      // Check for missing mandatory fields
      const res = await fetch('/api/settings/missing');
      const missing = await res.json();
      if (missing.count > 0) {
        setMissingFields(missing.missing);
        setShowMissing(true);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  const update = (key, value) => setValues(prev => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(values);
      enqueueSnackbar('Settings saved ✓', { variant: 'success' });
      await loadSettings();
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

  const groupSettings = settings.filter(s => s.group === group);

  const renderField = (s) => {
    const val = values[s.key] || '';
    const key = s.key;

    // Special: Resume upload
    if (key === 'RESUME_FILENAME') {
      return <ResumeUpload key={key} value={val} onChange={v => update(key, v)} />;
    }
    // Special: Resume mapping
    if (key === 'RESUME_MAPPING') {
      return <ResumeMappingEditor key={key} value={val} onChange={v => update(key, v)} />;
    }
    // Special: Sensitive field answers
    if (key === 'SENSITIVE_FIELD_ANSWERS') {
      return <AnswersEditor key={key} value={val} onChange={v => update(key, v)} />;
    }

    if (s.sensitive) {
      return <MaskedField key={key} label={s.label} value={val} onChange={v => update(key, v)} placeholder={s.placeholder} required={s.required} />;
    }
    if (s.type === 'boolean') {
      return (
        <Box key={key} sx={{ mb: 1.5 }}>
          <FormControlLabel control={<Switch checked={val === 'true' || val === true} onChange={e => update(key, e.target.checked ? 'true' : 'false')} />}
            label={<Typography variant="body2">{s.label}{s.required && <span style={{color:'red'}}> *</span>}</Typography>} />
        </Box>
      );
    }
    if (s.type === 'list') {
      return <ChipInput key={key} label={s.label} value={val} onChange={v => update(key, v)} placeholder={s.placeholder} required={s.required} />;
    }
    if (s.type === 'number') {
      return (
        <Box key={key} sx={{ mb: 2 }}>
          <Typography variant="body2" fontWeight={600} mb={0.5}>{s.label}{s.required && <span style={{color:'red'}}> *</span>}</Typography>
          <TextField fullWidth size="small" type="number" value={val} onChange={e => update(key, e.target.value)} placeholder={s.placeholder} />
        </Box>
      );
    }
    if (s.type === 'text' && (key === 'RESUME_MAPPING' || key === 'SENSITIVE_FIELD_ANSWERS')) {
      return (
        <Box key={key} sx={{ mb: 2 }}>
          <Typography variant="body2" fontWeight={600} mb={0.5}>{s.label}</Typography>
          <TextField fullWidth size="small" multiline rows={3} value={val} onChange={e => update(key, e.target.value)}
            placeholder={s.placeholder} sx={{ '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: 12 } }} />
        </Box>
      );
    }
    return (
      <Box key={key} sx={{ mb: 2 }}>
        <Typography variant="body2" fontWeight={600} mb={0.5}>{s.label}{s.required && <span style={{color:'red'}}> *</span>}</Typography>
        <TextField fullWidth size="small" value={val} onChange={e => update(key, e.target.value)} placeholder={s.placeholder} />
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2 }}>
      {/* Missing Fields Popup */}
      <Dialog open={showMissing} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningAmberIcon color="warning" /> Required Settings Missing
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            These fields are required for the agent to work. Please configure them:
          </Typography>
          {missingFields.map(f => (
            <Chip key={f.key} label={`${f.group} → ${f.label}`} size="small" color="warning" variant="outlined" sx={{ m: 0.25 }} />
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setShowMissing(false); setGroup(missingFields[0]?.group || 'Candidate'); }} variant="contained">
            Configure Now
          </Button>
        </DialogActions>
      </Dialog>

      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h3">Settings</Typography>
        <Button variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />} onClick={handleSave} disabled={saving}>
          Save All
        </Button>
      </Box>

      {/* Layout */}
      <Box sx={{ display: 'flex', flex: 1, gap: 2, overflow: 'hidden' }}>
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

        <Paper variant="outlined" sx={{ flex: 1, p: 3, overflow: 'auto', borderRadius: 2 }}>
          <Typography variant="h6" mb={2}>{GROUPS.find(g => g.key === group)?.label}</Typography>
          {groupSettings.map(renderField)}
          {group === 'Telegram' && (
            <Button variant="outlined" size="small" startIcon={testingTelegram ? <CircularProgress size={14} /> : <SendIcon />} onClick={handleTestTelegram} disabled={testingTelegram} sx={{ mt: 1 }}>
              Send Test Message
            </Button>
          )}
        </Paper>
      </Box>
    </Box>
  );
}

// --- Helper Components ---

function MaskedField({ label, value, onChange, placeholder, required }) {
  const [visible, setVisible] = useState(false);
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>{label}{required && <span style={{color:'red'}}> *</span>}</Typography>
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

function ChipInput({ label, value, onChange, placeholder, required }) {
  const [input, setInput] = useState('');
  // Value comes as comma-separated string from DB
  const items = Array.isArray(value) ? value : (value ? value.split(',').map(s => s.trim()).filter(Boolean) : []);
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      const newItems = [...items, input.trim()];
      onChange(newItems.join(', '));
      setInput('');
    }
  };
  const handleDelete = (item) => {
    const newItems = items.filter(v => v !== item);
    onChange(newItems.join(', '));
  };
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>{label}{required && <span style={{color:'red'}}> *</span>}</Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
        {items.map(item => <Chip key={item} label={item} size="small" onDelete={() => handleDelete(item)} />)}
      </Box>
      <TextField fullWidth size="small" value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown}
        placeholder={placeholder || 'Type and press Enter'} />
    </Box>
  );
}

function ResumeUpload({ value, onChange }) {
  const [uploading, setUploading] = useState(false);
  const [resumes, setResumes] = useState([]);

  useEffect(() => {
    fetch('/api/settings/resumes').then(r => r.json()).then(d => setResumes(d.resumes || [])).catch(() => {});
  }, [value]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await fetch('/api/settings/upload-resume', { method: 'POST', body: formData });
      const data = await resp.json();
      if (data.filename) {
        onChange(data.filename);
        setResumes(prev => [...prev.filter(r => r.filename !== data.filename), { filename: data.filename, size_kb: data.size_kb }]);
      } else {
        alert(data.error || 'Upload failed');
      }
    } catch { alert('Upload failed'); }
    finally { setUploading(false); }
  };

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>Resume <span style={{color:'red'}}>*</span></Typography>
      {value && <Chip label={`📄 ${value}`} color="primary" variant="outlined" size="small" sx={{ mb: 1 }} />}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
        <Button variant="outlined" size="small" component="label" disabled={uploading}>
          {uploading ? <CircularProgress size={14} /> : '📎 Upload Resume'}
          <input type="file" hidden accept=".pdf,.docx,.doc,.txt" onChange={handleUpload} />
        </Button>
        <Typography variant="caption" color="text.secondary">PDF, DOCX, DOC, TXT</Typography>
      </Box>
      {resumes.length > 0 && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary" mb={0.5} display="block">Available resumes:</Typography>
          {resumes.map(r => (
            <Chip key={r.filename} label={`${r.filename} (${r.size_kb}KB)`} size="small"
              variant={r.filename === value ? 'filled' : 'outlined'}
              color={r.filename === value ? 'primary' : 'default'}
              onClick={() => onChange(r.filename)}
              sx={{ m: 0.25, cursor: 'pointer' }} />
          ))}
        </Box>
      )}
    </Box>
  );
}

function ResumeMappingEditor({ value, onChange }) {
  // value is "Keywords1 | resume1.pdf\nKeywords2 | resume2.pdf"
  const lines = (value || '').split('\n').filter(l => l.trim());
  const entries = lines.map(l => {
    const [kw, resume] = l.split('|').map(s => s.trim());
    return { keywords: kw || '', resume: resume || '' };
  });

  const updateEntry = (idx, field, val) => {
    const updated = [...entries];
    updated[idx] = { ...updated[idx], [field]: val };
    onChange(updated.map(e => `${e.keywords} | ${e.resume}`).join('\n'));
  };
  const addEntry = () => onChange([...lines, ' | '].join('\n'));
  const removeEntry = (idx) => onChange(entries.filter((_, i) => i !== idx).map(e => `${e.keywords} | ${e.resume}`).join('\n'));

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>Resume Mapping</Typography>
      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
        Match different resumes to different job types. When a job title contains any of the keywords, the agent uses that resume.
      </Typography>
      {entries.map((entry, idx) => (
        <Paper key={idx} variant="outlined" sx={{ p: 1.5, mb: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
          <Box sx={{ flex: 2 }}>
            <Typography variant="caption" color="text.secondary">When job title contains:</Typography>
            <TextField fullWidth size="small" value={entry.keywords} onChange={e => updateEntry(idx, 'keywords', e.target.value)}
              placeholder="Engineering Manager, Director" sx={{ mt: 0.25 }} />
          </Box>
          <Typography variant="body2" sx={{ mx: 0.5 }}>→</Typography>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">Use resume:</Typography>
            <TextField fullWidth size="small" value={entry.resume} onChange={e => updateEntry(idx, 'resume', e.target.value)}
              placeholder="EM_Resume.pdf" sx={{ mt: 0.25 }} />
          </Box>
          <IconButton size="small" onClick={() => removeEntry(idx)} sx={{ color: 'error.main' }}>✕</IconButton>
        </Paper>
      ))}
      <Button size="small" onClick={addEntry} sx={{ textTransform: 'none' }}>+ Add mapping</Button>
    </Box>
  );
}

function AnswersEditor({ value, onChange }) {
  // value is "key1: value1\nkey2: value2"
  const lines = (value || '').split('\n').filter(l => l.includes(':'));
  const entries = lines.map(l => {
    const idx = l.indexOf(':');
    return { field: l.slice(0, idx).trim(), answer: l.slice(idx + 1).trim() };
  });

  const updateEntry = (idx, key, val) => {
    const updated = [...entries];
    updated[idx] = { ...updated[idx], [key]: val };
    onChange(updated.map(e => `${e.field}: ${e.answer}`).join('\n'));
  };
  const addEntry = () => onChange([...lines, ': '].join('\n'));
  const removeEntry = (idx) => onChange(entries.filter((_, i) => i !== idx).map(e => `${e.field}: ${e.answer}`).join('\n'));

  const COMMON_FIELDS = ['salary_expectation', 'current_ctc', 'expected_ctc', 'years_of_experience', 'gender', 'veteran_status', 'disability', 'race_ethnicity'];

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>Auto-Fill Answers</Typography>
      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
        When LinkedIn asks these questions, the agent fills your answer automatically instead of pausing.
      </Typography>
      {entries.map((entry, idx) => (
        <Box key={idx} sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <Select value={entry.field} onChange={e => updateEntry(idx, 'field', e.target.value)} displayEmpty>
              <MenuItem value="" disabled><em>Select question...</em></MenuItem>
              {COMMON_FIELDS.map(f => <MenuItem key={f} value={f}>{f.replace(/_/g, ' ')}</MenuItem>)}
              <MenuItem value={entry.field && !COMMON_FIELDS.includes(entry.field) ? entry.field : '__custom'}>Custom...</MenuItem>
            </Select>
          </FormControl>
          <TextField size="small" sx={{ flex: 1 }} value={entry.answer} onChange={e => updateEntry(idx, 'answer', e.target.value)}
            placeholder="Your answer" />
          <IconButton size="small" onClick={() => removeEntry(idx)} sx={{ color: 'error.main' }}>✕</IconButton>
        </Box>
      ))}
      <Button size="small" onClick={addEntry} sx={{ textTransform: 'none' }}>+ Add answer</Button>
    </Box>
  );
}
