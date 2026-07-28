import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Typography, Switch, TextField, Button, Grid, Chip,
  FormControl, InputLabel, Select, MenuItem, List, ListItem,
  ListItemIcon, ListItemText, Alert, ToggleButton, ToggleButtonGroup,
  CircularProgress, RadioGroup, Radio, FormControlLabel, Stack,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SaveIcon from '@mui/icons-material/Save';
import TimerIcon from '@mui/icons-material/Timer';
import EventRepeatIcon from '@mui/icons-material/EventRepeat';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { useSnackbar } from 'notistack';
import { getSchedule, updateSchedule, getNextRuns } from '../api';

const DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function describeCron(expression) {
  if (!expression || !expression.trim()) return '';
  const parts = expression.trim().split(/\s+/);
  if (parts.length < 5) return 'Invalid cron expression';
  const [minute, hour, , , dayOfWeek] = parts;
  const dayNames = { '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat', '7': 'Sun' };
  let desc = '';
  if (minute.startsWith('*/')) desc += `Every ${minute.slice(2)} min`;
  else if (minute === '*') desc += 'Every min';
  else desc += `At :${minute.padStart(2, '0')}`;
  if (hour.includes('-')) { const [s, e] = hour.split('-'); desc += ` (${s}:00–${e}:00)`; }
  else if (hour.startsWith('*/')) desc += `, every ${hour.slice(2)}h`;
  else if (hour !== '*') desc += ` at ${hour.padStart(2, '0')}:00`;
  if (dayOfWeek !== '*' && dayOfWeek !== '?') {
    if (dayOfWeek.includes(',')) desc += `, ${dayOfWeek.split(',').map((d) => dayNames[d] || d).join('/')}`;
    else if (dayOfWeek.includes('-')) { const [s, e] = dayOfWeek.split('-'); desc += `, ${dayNames[s]||s}–${dayNames[e]||e}`; }
    else desc += `, ${dayNames[dayOfWeek] || dayOfWeek}`;
  }
  return desc;
}

export default function Scheduler() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [nextRuns, setNextRuns] = useState([]);
  const [config, setConfig] = useState({
    enabled: true, mode: 'interval', interval_minutes: 60, cron_expression: '',
    cron_frequency: 'hourly', cron_minute: 0, cron_hour: 9,
    cron_days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
    active_hours_start: 9, active_hours_end: 18,
    days_of_week: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
  });

  const loadSchedule = useCallback(async () => {
    try {
      const data = await getSchedule();
      if (data) setConfig((prev) => ({ ...prev, ...data }));
      const runs = await getNextRuns();
      if (runs?.next_runs) setNextRuns(runs.next_runs);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadSchedule(); }, [loadSchedule]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSchedule(config);
      enqueueSnackbar('Schedule saved', { variant: 'success' });
      const runs = await getNextRuns();
      if (runs?.next_runs) setNextRuns(runs.next_runs);
    } catch { enqueueSnackbar('Failed to save', { variant: 'error' }); }
    finally { setSaving(false); }
  };

  const toggleDay = (day) => setConfig((p) => ({ ...p, days_of_week: p.days_of_week.includes(day) ? p.days_of_week.filter((d) => d !== day) : [...p.days_of_week, day] }));
  const toggleCronDay = (day) => setConfig((p) => ({ ...p, cron_days: p.cron_days.includes(day) ? p.cron_days.filter((d) => d !== day) : [...p.cron_days, day] }));
  const cronDescription = useMemo(() => describeCron(config.cron_expression), [config.cron_expression]);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress size={24} /></Box>;

  return (
    <Box sx={{ height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column' }}>
      {/* Top bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 0.75, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography sx={{ fontSize: 14, fontWeight: 700 }}>Scheduler</Typography>
          <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: config.enabled ? 'success.main' : 'grey.400' }} />
          <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>{config.enabled ? 'Active' : 'Off'}</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Switch size="small" checked={config.enabled} onChange={(e) => setConfig({ ...config, enabled: e.target.checked })} />
          <Button variant="contained" size="small" startIcon={saving ? <CircularProgress size={12} color="inherit" /> : <SaveIcon sx={{ fontSize: 14 }} />} onClick={handleSave} disabled={saving} sx={{ fontSize: 11, py: 0.25, px: 1.5 }}>Save</Button>
        </Box>
      </Box>

      {/* 2-column content */}
      <Grid container spacing={1.5} sx={{ flex: 1, pt: 1.5, overflow: 'auto' }}>
        {/* Left: Config */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
            {/* Mode */}
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.5 }}>Mode</Typography>
            <ToggleButtonGroup value={config.mode} exclusive onChange={(_, v) => v && setConfig({ ...config, mode: v })} size="small" sx={{ mb: 1.5 }}>
              <ToggleButton value="interval" sx={{ py: 0.25, px: 1.5, fontSize: 11 }}><TimerIcon sx={{ fontSize: 14, mr: 0.5 }} />Interval</ToggleButton>
              <ToggleButton value="cron" sx={{ py: 0.25, px: 1.5, fontSize: 11 }}><EventRepeatIcon sx={{ fontSize: 14, mr: 0.5 }} />Cron</ToggleButton>
            </ToggleButtonGroup>

            {config.mode === 'interval' && (
              <Box sx={{ mb: 1.5 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Interval (minutes)</Typography>
                <TextField size="small" type="number" value={config.interval_minutes} onChange={(e) => setConfig({ ...config, interval_minutes: parseInt(e.target.value) || 30 })} inputProps={{ min: 5, max: 1440 }} sx={{ width: 120, '& .MuiInputBase-input': { fontSize: 12, py: 0.5 } }} />
              </Box>
            )}

            {config.mode === 'cron' && (
              <Box sx={{ mb: 1.5 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.25 }}>Cron Expression</Typography>
                <TextField size="small" fullWidth value={config.cron_expression} onChange={(e) => setConfig({ ...config, cron_expression: e.target.value })} placeholder="*/30 9-18 * * 1-5" sx={{ mb: 1, '& .MuiInputBase-input': { fontSize: 12, py: 0.5 } }} />
                <RadioGroup row value={config.cron_frequency} onChange={(e) => setConfig({ ...config, cron_frequency: e.target.value })} sx={{ gap: 0 }}>
                  {['every_x_min', 'hourly', 'daily', 'weekly'].map((f) => (
                    <FormControlLabel key={f} value={f} control={<Radio size="small" sx={{ p: 0.25 }} />} label={<Typography sx={{ fontSize: 11 }}>{f.replace('_', ' ')}</Typography>} sx={{ mr: 1.5 }} />
                  ))}
                </RadioGroup>
                {config.cron_frequency === 'weekly' && (
                  <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
                    {DAYS_OF_WEEK.map((day) => (
                      <Chip key={day} label={day} size="small" onClick={() => toggleCronDay(day)} color={config.cron_days.includes(day) ? 'primary' : 'default'} variant={config.cron_days.includes(day) ? 'filled' : 'outlined'} sx={{ fontSize: 10, height: 20 }} />
                    ))}
                  </Box>
                )}
                {(config.cron_frequency === 'daily' || config.cron_frequency === 'weekly') && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <FormControl size="small" sx={{ width: 80 }}>
                      <InputLabel sx={{ fontSize: 11 }}>Hour</InputLabel>
                      <Select value={config.cron_hour} label="Hour" onChange={(e) => setConfig({ ...config, cron_hour: e.target.value })} sx={{ fontSize: 11 }}>
                        {HOURS.map((h) => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}</MenuItem>)}
                      </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ width: 80 }}>
                      <InputLabel sx={{ fontSize: 11 }}>Min</InputLabel>
                      <Select value={config.cron_minute} label="Min" onChange={(e) => setConfig({ ...config, cron_minute: e.target.value })} sx={{ fontSize: 11 }}>
                        {[0, 5, 10, 15, 20, 30, 45].map((m) => <MenuItem key={m} value={m}>:{String(m).padStart(2, '0')}</MenuItem>)}
                      </Select>
                    </FormControl>
                  </Stack>
                )}
              </Box>
            )}

            {/* Active hours */}
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.5 }}>Active Hours</Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
              <FormControl size="small" sx={{ width: 80 }}>
                <Select value={config.active_hours_start} onChange={(e) => setConfig({ ...config, active_hours_start: e.target.value })} sx={{ fontSize: 11 }}>
                  {HOURS.map((h) => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}:00</MenuItem>)}
                </Select>
              </FormControl>
              <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>to</Typography>
              <FormControl size="small" sx={{ width: 80 }}>
                <Select value={config.active_hours_end} onChange={(e) => setConfig({ ...config, active_hours_end: e.target.value })} sx={{ fontSize: 11 }}>
                  {HOURS.map((h) => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}:00</MenuItem>)}
                </Select>
              </FormControl>
            </Stack>

            {/* Days */}
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.5 }}>Days of Week</Typography>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {DAYS_OF_WEEK.map((day) => (
                <Chip key={day} label={day} size="small" onClick={() => toggleDay(day)} color={config.days_of_week.includes(day) ? 'primary' : 'default'} variant={config.days_of_week.includes(day) ? 'filled' : 'outlined'} sx={{ fontSize: 10, height: 22 }} />
              ))}
            </Box>
          </Box>
        </Grid>

        {/* Right: Preview */}
        <Grid size={{ xs: 12, md: 5 }}>
          {/* Status */}
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
              <FiberManualRecordIcon sx={{ fontSize: 10, color: config.enabled ? 'success.main' : 'grey.400' }} />
              <Typography sx={{ fontSize: 11, fontWeight: 600 }}>Schedule Status</Typography>
            </Box>
            <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>
              {config.mode === 'interval'
                ? `Every ${config.interval_minutes}min, ${String(config.active_hours_start).padStart(2, '0')}:00–${String(config.active_hours_end).padStart(2, '0')}:00`
                : config.cron_expression ? `Cron: ${config.cron_expression}` : 'Cron not set'
              }
            </Typography>
            {cronDescription && config.mode === 'cron' && (
              <Typography sx={{ fontSize: 10, color: 'text.secondary', mt: 0.5, fontStyle: 'italic' }}>📅 {cronDescription}</Typography>
            )}
          </Box>

          {/* Next runs */}
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 600, mb: 0.75 }}>Next Runs</Typography>
            {!config.enabled ? (
              <Typography sx={{ fontSize: 11, color: 'warning.main' }}>Scheduler disabled</Typography>
            ) : nextRuns.length === 0 ? (
              <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>No runs scheduled</Typography>
            ) : (
              <List dense disablePadding>
                {nextRuns.slice(0, 5).map((run, idx) => (
                  <ListItem key={idx} disablePadding sx={{ py: 0.25 }}>
                    <ListItemIcon sx={{ minWidth: 20 }}>
                      <PlayArrowIcon sx={{ fontSize: 12, color: 'primary.main' }} />
                    </ListItemIcon>
                    <ListItemText primary={run} primaryTypographyProps={{ fontSize: 11, fontFamily: 'monospace' }} />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
