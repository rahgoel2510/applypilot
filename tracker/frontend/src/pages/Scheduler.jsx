import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Typography, Switch, TextField, Button, Chip, Stack,
  FormControl, InputLabel, Select, MenuItem, ToggleButton, ToggleButtonGroup,
  CircularProgress, Card, CardContent,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import TimerIcon from '@mui/icons-material/Timer';
import EventRepeatIcon from '@mui/icons-material/EventRepeat';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { useSnackbar } from 'notistack';
import { getSchedule, updateSchedule, getNextRuns } from '../api';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function describeCron(expression) {
  if (!expression || !expression.trim()) return '';
  const parts = expression.trim().split(/\s+/);
  if (parts.length < 5) return 'Invalid expression';
  const [minute, hour, , , dayOfWeek] = parts;
  const dayNames = { '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat' };
  let desc = '';
  if (minute.startsWith('*/')) desc += `Every ${minute.slice(2)} minutes`;
  else if (minute === '*') desc += 'Every minute';
  else desc += `At minute ${minute}`;
  if (hour.includes('-')) { const [s, e] = hour.split('-'); desc += ` between ${s}:00–${e}:00`; }
  else if (hour !== '*') desc += ` at ${hour.padStart(2, '0')}:00`;
  if (dayOfWeek !== '*' && dayOfWeek !== '?') {
    const days = dayOfWeek.split(',').map(d => dayNames[d] || d).join(', ');
    desc += ` on ${days}`;
  }
  return desc;
}

export default function Scheduler() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [nextRuns, setNextRuns] = useState([]);
  const [config, setConfig] = useState({
    enabled: true, mode: 'interval', interval_minutes: 60,
    cron_expression: '', active_hours_start: 9, active_hours_end: 18,
    days_of_week: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
  });

  const loadSchedule = useCallback(async () => {
    try {
      const data = await getSchedule();
      if (data) setConfig(prev => ({ ...prev, ...data }));
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
      enqueueSnackbar('Schedule saved successfully', { variant: 'success' });
      const runs = await getNextRuns();
      if (runs?.next_runs) setNextRuns(runs.next_runs);
    } catch { enqueueSnackbar('Failed to save schedule', { variant: 'error' }); }
    finally { setSaving(false); }
  };

  const toggleDay = (day) => setConfig(p => ({
    ...p, days_of_week: p.days_of_week.includes(day) ? p.days_of_week.filter(d => d !== day) : [...p.days_of_week, day]
  }));

  const cronDescription = useMemo(() => describeCron(config.cron_expression), [config.cron_expression]);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}><CircularProgress /></Box>;

  return (
    <Box sx={{ p: 2, maxWidth: 1100, mx: 'auto' }}>
      {/* Header */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
        <Stack direction="row" alignItems="center" spacing={2}>
          <ScheduleIcon sx={{ fontSize: 28, color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>Agent Scheduler</Typography>
            <Typography color="text.secondary">Configure when the agent runs automatically</Typography>
          </Box>
        </Stack>
        <Stack direction="row" alignItems="center" spacing={2}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography fontWeight={600} color={config.enabled ? 'success.main' : 'text.secondary'}>
              {config.enabled ? 'Enabled' : 'Disabled'}
            </Typography>
            <Switch checked={config.enabled} onChange={(e) => setConfig({ ...config, enabled: e.target.checked })} />
          </Stack>
          <Button
            variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
            onClick={handleSave} disabled={saving}
          >
            Save Schedule
          </Button>
        </Stack>
      </Stack>

      <Stack direction="row" spacing={2} sx={{ alignItems: 'flex-start' }}>
        {/* LEFT: Configuration */}
        <Box sx={{ flex: 1 }}>
          {/* Schedule Mode */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Typography fontWeight={700} sx={{ mb: 1.5 }}>Schedule Mode</Typography>
              <ToggleButtonGroup
                value={config.mode} exclusive
                onChange={(_, v) => v && setConfig({ ...config, mode: v })}
                sx={{ '& .MuiToggleButton-root': { textTransform: 'none', fontWeight: 600, px: 3, py: 1 } }}
              >
                <ToggleButton value="interval"><TimerIcon sx={{ mr: 1 }} />Fixed Interval</ToggleButton>
                <ToggleButton value="cron"><EventRepeatIcon sx={{ mr: 1 }} />Custom Schedule</ToggleButton>
              </ToggleButtonGroup>

              <Box sx={{ mt: 2.5 }}>
                {config.mode === 'interval' ? (
                  <TextField
                    type="number" value={config.interval_minutes}
                    onChange={(e) => setConfig({ ...config, interval_minutes: parseInt(e.target.value) || 30 })}
                    inputProps={{ min: 5, max: 1440 }}
                    label="Interval (minutes)"
                    helperText="Agent will scan every X minutes during active hours"
                    sx={{ width: 220 }}
                  />
                ) : (
                  <Stack spacing={2.5}>
                    <Typography color="text.secondary" sx={{ fontSize: '0.9rem' }}>
                      Pick specific times when the agent should run
                    </Typography>

                    {/* Frequency type */}
                    <FormControl sx={{ width: 280 }}>
                      <InputLabel>Run frequency</InputLabel>
                      <Select value={config.cron_frequency || 'specific_times'} label="Run frequency"
                        onChange={(e) => setConfig({ ...config, cron_frequency: e.target.value })}
                      >
                        <MenuItem value="every_15_min">Every 15 minutes</MenuItem>
                        <MenuItem value="every_30_min">Every 30 minutes</MenuItem>
                        <MenuItem value="every_hour">Every hour</MenuItem>
                        <MenuItem value="every_2_hours">Every 2 hours</MenuItem>
                        <MenuItem value="specific_times">At specific times each day</MenuItem>
                      </Select>
                    </FormControl>

                    {/* Specific time slots */}
                    {config.cron_frequency === 'specific_times' && (
                      <Box>
                        <Typography fontWeight={600} sx={{ mb: 1 }}>Run at these times:</Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
                          {(config.run_times || ['09:00', '13:00', '17:00']).map((time, idx) => (
                            <Chip
                              key={idx}
                              label={time}
                              color="primary"
                              onDelete={() => {
                                const times = [...(config.run_times || ['09:00', '13:00', '17:00'])];
                                times.splice(idx, 1);
                                setConfig({ ...config, run_times: times });
                              }}
                              sx={{ fontWeight: 600, fontSize: '0.9rem', height: 32 }}
                            />
                          ))}
                        </Stack>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <FormControl sx={{ width: 120 }}>
                            <InputLabel>Hour</InputLabel>
                            <Select value={config._newHour ?? 9} label="Hour"
                              onChange={(e) => setConfig({ ...config, _newHour: e.target.value })}
                            >
                              {HOURS.map(h => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}</MenuItem>)}
                            </Select>
                          </FormControl>
                          <Typography fontWeight={600}>:</Typography>
                          <FormControl sx={{ width: 120 }}>
                            <InputLabel>Minute</InputLabel>
                            <Select value={config._newMinute ?? 0} label="Minute"
                              onChange={(e) => setConfig({ ...config, _newMinute: e.target.value })}
                            >
                              {[0, 15, 30, 45].map(m => <MenuItem key={m} value={m}>{String(m).padStart(2, '0')}</MenuItem>)}
                            </Select>
                          </FormControl>
                          <Button variant="outlined" size="small"
                            onClick={() => {
                              const h = String(config._newHour ?? 9).padStart(2, '0');
                              const m = String(config._newMinute ?? 0).padStart(2, '0');
                              const newTime = `${h}:${m}`;
                              const times = [...(config.run_times || ['09:00', '13:00', '17:00'])];
                              if (!times.includes(newTime)) {
                                times.push(newTime);
                                times.sort();
                                setConfig({ ...config, run_times: times });
                              }
                            }}
                          >
                            + Add Time
                          </Button>
                        </Stack>
                      </Box>
                    )}

                    {/* On which days */}
                    <Box>
                      <Typography fontWeight={600} sx={{ mb: 1 }}>On which days:</Typography>
                      <Stack direction="row" spacing={1}>
                        {DAYS.map(day => (
                          <Chip
                            key={day} label={day} clickable
                            onClick={() => {
                              const days = config.cron_days || ['Mon','Tue','Wed','Thu','Fri'];
                              setConfig({ ...config, cron_days: days.includes(day) ? days.filter(d => d !== day) : [...days, day] });
                            }}
                            color={(config.cron_days || ['Mon','Tue','Wed','Thu','Fri']).includes(day) ? 'primary' : 'default'}
                            variant={(config.cron_days || ['Mon','Tue','Wed','Thu','Fri']).includes(day) ? 'filled' : 'outlined'}
                            sx={{ fontWeight: 600, fontSize: '0.85rem', height: 34 }}
                          />
                        ))}
                      </Stack>
                    </Box>

                    {/* Summary */}
                    <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'rgba(124,58,237,0.05)', border: '1px solid', borderColor: 'rgba(124,58,237,0.15)' }}>
                      <Typography sx={{ fontSize: '0.9rem', color: 'primary.main', fontWeight: 500 }}>
                        📅 {config.cron_frequency === 'every_15_min' ? 'Every 15 minutes'
                          : config.cron_frequency === 'every_30_min' ? 'Every 30 minutes'
                          : config.cron_frequency === 'every_hour' ? 'Every hour'
                          : config.cron_frequency === 'every_2_hours' ? 'Every 2 hours'
                          : `At ${(config.run_times || ['09:00', '13:00', '17:00']).join(', ')}`}
                        {' '}on {(config.cron_days || ['Mon','Tue','Wed','Thu','Fri']).join(', ')}
                      </Typography>
                    </Box>
                  </Stack>
                )}
              </Box>
            </CardContent>
          </Card>

          {/* Active Hours */}
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
                <AccessTimeIcon sx={{ color: 'text.secondary' }} />
                <Typography fontWeight={700}>Active Hours</Typography>
              </Stack>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Agent will only run between these hours
              </Typography>
              <Stack direction="row" alignItems="center" spacing={2}>
                <FormControl sx={{ width: 130 }}>
                  <InputLabel>From</InputLabel>
                  <Select value={config.active_hours_start} label="From" onChange={(e) => setConfig({ ...config, active_hours_start: e.target.value })}>
                    {HOURS.map(h => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}:00</MenuItem>)}
                  </Select>
                </FormControl>
                <Typography fontWeight={600} color="text.secondary">to</Typography>
                <FormControl sx={{ width: 130 }}>
                  <InputLabel>To</InputLabel>
                  <Select value={config.active_hours_end} label="To" onChange={(e) => setConfig({ ...config, active_hours_end: e.target.value })}>
                    {HOURS.map(h => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}:00</MenuItem>)}
                  </Select>
                </FormControl>
                <Chip label={`${config.active_hours_end - config.active_hours_start}h window`} size="small" color="primary" variant="outlined" />
              </Stack>
            </CardContent>
          </Card>

          {/* Days of Week */}
          <Card>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
                <CalendarTodayIcon sx={{ color: 'text.secondary' }} />
                <Typography fontWeight={700}>Days of Week</Typography>
              </Stack>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Select which days the agent is allowed to run
              </Typography>
              <Stack direction="row" spacing={1}>
                {DAYS.map(day => (
                  <Chip
                    key={day} label={day} clickable
                    onClick={() => toggleDay(day)}
                    color={config.days_of_week.includes(day) ? 'primary' : 'default'}
                    variant={config.days_of_week.includes(day) ? 'filled' : 'outlined'}
                    sx={{ fontWeight: 600, fontSize: '0.85rem', height: 34, px: 0.5 }}
                  />
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Box>

        {/* RIGHT: Preview */}
        <Box sx={{ width: 320, minWidth: 320 }}>
          {/* Summary */}
          <Card sx={{ mb: 2, background: 'linear-gradient(135deg, #7c3aed 0%, #6366f1 100%)', color: '#fff', border: 'none' }}>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Typography sx={{ fontWeight: 700, fontSize: '1rem', mb: 1 }}>Current Schedule</Typography>
              <Typography sx={{ opacity: 0.9 }}>
                {config.mode === 'interval'
                  ? `Every ${config.interval_minutes} min`
                  : config.cron_expression || 'No cron set'}
              </Typography>
              <Typography sx={{ opacity: 0.7, fontSize: '0.85rem', mt: 0.5 }}>
                {String(config.active_hours_start).padStart(2, '0')}:00 – {String(config.active_hours_end).padStart(2, '0')}:00 • {config.days_of_week.join(', ')}
              </Typography>
            </CardContent>
          </Card>

          {/* Next Runs */}
          <Card>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
              <Typography fontWeight={700} sx={{ mb: 1.5 }}>Upcoming Runs</Typography>
              {!config.enabled ? (
                <Typography color="warning.main" sx={{ fontStyle: 'italic' }}>Scheduler is disabled</Typography>
              ) : nextRuns.length === 0 ? (
                <Typography color="text.secondary">No upcoming runs calculated</Typography>
              ) : (
                <Stack spacing={1}>
                  {nextRuns.slice(0, 5).map((run, idx) => (
                    <Stack key={idx} direction="row" alignItems="center" spacing={1.5}
                      sx={{ p: 1, borderRadius: 1.5, bgcolor: idx === 0 ? 'rgba(124,58,237,0.06)' : 'transparent', border: idx === 0 ? '1px solid rgba(124,58,237,0.15)' : 'none' }}
                    >
                      <PlayArrowIcon sx={{ fontSize: 16, color: idx === 0 ? 'primary.main' : 'text.disabled' }} />
                      <Typography sx={{ fontFamily: 'monospace', fontWeight: idx === 0 ? 700 : 400, color: idx === 0 ? 'primary.main' : 'text.secondary' }}>
                        {run}
                      </Typography>
                      {idx === 0 && <Chip label="NEXT" size="small" color="primary" sx={{ height: 20, fontSize: '0.7rem', fontWeight: 700 }} />}
                    </Stack>
                  ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Box>
      </Stack>
    </Box>
  );
}
