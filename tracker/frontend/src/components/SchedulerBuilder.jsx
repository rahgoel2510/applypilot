import React, { useState, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  Stack,
  Card,
  CardContent,
  Chip,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Tooltip,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Checkbox,
  FormControlLabel,
  Autocomplete,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import cronstrue from 'cronstrue';
import { CronExpressionParser } from 'cron-parser';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(relativeTime);
dayjs.extend(utc);
dayjs.extend(timezone);

// ─── Constants ───────────────────────────────────────────────────────────────

const FREQUENCIES = ['Hourly', 'Daily', 'Weekly', 'Monthly'];
const HOURLY_OPTIONS = [1, 2, 4, 6, 8, 12];
const DAYS_OF_WEEK = [
  { label: 'Mon', value: 1 },
  { label: 'Tue', value: 2 },
  { label: 'Wed', value: 3 },
  { label: 'Thu', value: 4 },
  { label: 'Fri', value: 5 },
  { label: 'Sat', value: 6 },
  { label: 'Sun', value: 0 },
];
const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);
const DAYS_OF_MONTH = Array.from({ length: 31 }, (_, i) => i + 1);

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  container: {
    backgroundColor: '#fafbfc',
    borderRadius: '12px',
    border: '1px solid #e8ebf0',
    p: 3,
    width: '100%',
  },
  containerCompact: {
    backgroundColor: 'transparent',
    p: 0,
    width: '100%',
  },
  card: {
    border: '1px solid #e8ebf0',
    borderRadius: '12px',
    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
    backgroundColor: '#ffffff',
  },
  activeCard: {
    border: '1px solid #b3d4fc',
    borderRadius: '12px',
    boxShadow: '0 2px 8px rgba(99,149,236,0.10)',
    backgroundColor: '#f0f6ff',
  },
  sectionTitle: {
    fontWeight: 600,
    fontSize: '0.95rem',
    color: '#3a4a5c',
  },
  translatorValid: {
    backgroundColor: '#e8f8e8',
    border: '1px solid #b8e6b8',
    borderRadius: '8px',
    p: 1.5,
    mt: 1,
  },
  translatorInvalid: {
    backgroundColor: '#fde8e8',
    border: '1px solid #f5b8b8',
    borderRadius: '8px',
    p: 1.5,
    mt: 1,
  },
  chip: {
    borderRadius: '8px',
    fontWeight: 500,
    px: 1,
  },
  chipActive: {
    borderRadius: '8px',
    fontWeight: 600,
    px: 1,
    backgroundColor: '#e3edfc',
    color: '#3b6cb7',
    borderColor: '#b3d4fc',
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getTimezoneList() {
  try {
    const tzList = Intl.supportedValuesOf('timeZone');
    return tzList.map((tz) => {
      const offset = dayjs().tz(tz).format('Z');
      return { label: `${tz} (UTC${offset})`, value: tz };
    });
  } catch {
    // Fallback for environments without supportedValuesOf
    return [{ label: dayjs.tz.guess(), value: dayjs.tz.guess() }];
  }
}

function getDefaultTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return 'UTC';
  }
}

function validateCronField(value, min, max) {
  if (!value || value === '*') return true;
  // Handle */n
  if (/^\*\/\d+$/.test(value)) {
    const n = parseInt(value.split('/')[1], 10);
    return n >= 1 && n <= max;
  }
  // Handle comma-separated
  const parts = value.split(',');
  return parts.every((p) => {
    // Handle range
    if (p.includes('-')) {
      const [a, b] = p.split('-').map(Number);
      return !isNaN(a) && !isNaN(b) && a >= min && b <= max && a <= b;
    }
    const num = parseInt(p, 10);
    return !isNaN(num) && num >= min && num <= max;
  });
}

function validateCron(parts) {
  if (parts.length !== 5) return false;
  const [minute, hour, day, month, weekday] = parts;
  return (
    validateCronField(minute, 0, 59) &&
    validateCronField(hour, 0, 23) &&
    validateCronField(day, 1, 31) &&
    validateCronField(month, 1, 12) &&
    validateCronField(weekday, 0, 7)
  );
}

function buildCronFromBasic(frequency, hourlyInterval, hour, minute, weekDays, dayOfMonth) {
  switch (frequency) {
    case 'Hourly':
      return `0 */${hourlyInterval} * * *`;
    case 'Daily':
      return `${minute} ${hour} * * *`;
    case 'Weekly': {
      const days = weekDays.length > 0 ? weekDays.join(',') : '*';
      return `${minute} ${hour} * * ${days}`;
    }
    case 'Monthly':
      return `${minute} ${hour} ${dayOfMonth} * *`;
    default:
      return '0 * * * *';
  }
}

function getHumanReadable(cronExpression) {
  try {
    const text = cronstrue.toString(cronExpression, { use24HourTimeFormat: true });
    return { text, valid: true };
  } catch (e) {
    return { text: e.message || 'Invalid cron expression', valid: false };
  }
}

function getNextRuns(cronExpression, tz, count = 5) {
  try {
    const cron = CronExpressionParser.parse(cronExpression, {
      tz,
      currentDate: new Date(),
    });
    const runs = [];
    for (let i = 0; i < count; i++) {
      const next = cron.next();
      runs.push(next.toDate());
    }
    return { runs, error: null };
  } catch (e) {
    return { runs: [], error: e.message || 'Invalid expression' };
  }
}


// ─── InfoTooltip Sub-component ───────────────────────────────────────────────

function InfoTooltip({ title }) {
  return (
    <Tooltip title={title} arrow placement="top">
      <IconButton size="small" sx={{ ml: 0.5, color: '#8fa4bd' }}>
        <InfoOutlinedIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function SchedulerBuilder({ onSave, initialConfig, compact = false }) {
  // Mode: 'basic' or 'advanced'
  const [mode, setMode] = useState(initialConfig?.mode || 'basic');

  // Basic mode state
  const [frequency, setFrequency] = useState(initialConfig?.frequency || '');
  const [hourlyInterval, setHourlyInterval] = useState(initialConfig?.hourlyInterval || 1);
  const [hour, setHour] = useState(initialConfig?.hour ?? 9);
  const [minute, setMinute] = useState(initialConfig?.minute ?? 0);
  const [weekDays, setWeekDays] = useState(initialConfig?.weekDays || []);
  const [dayOfMonth, setDayOfMonth] = useState(initialConfig?.dayOfMonth || 1);

  // Advanced mode state
  const [cronParts, setCronParts] = useState(
    initialConfig?.cronParts || ['0', '*', '*', '*', '*']
  );

  // Timezone
  const [selectedTimezone, setSelectedTimezone] = useState(
    initialConfig?.timezone || getDefaultTimezone()
  );

  // Timezone list (memoized)
  const timezoneList = useMemo(() => getTimezoneList(), []);

  // Derive cron expression from current state
  const cronExpression = useMemo(() => {
    if (mode === 'advanced') {
      return cronParts.join(' ');
    }
    if (!frequency) return '0 * * * *';
    return buildCronFromBasic(frequency, hourlyInterval, hour, minute, weekDays, dayOfMonth);
  }, [mode, frequency, hourlyInterval, hour, minute, weekDays, dayOfMonth, cronParts]);

  // Validate advanced cron parts individually
  const cronFieldErrors = useMemo(() => {
    if (mode !== 'advanced') return [false, false, false, false, false];
    return [
      !validateCronField(cronParts[0], 0, 59),
      !validateCronField(cronParts[1], 0, 23),
      !validateCronField(cronParts[2], 1, 31),
      !validateCronField(cronParts[3], 1, 12),
      !validateCronField(cronParts[4], 0, 7),
    ];
  }, [mode, cronParts]);

  // Human-readable translation
  const translation = useMemo(() => getHumanReadable(cronExpression), [cronExpression]);

  // Next 5 runs
  const nextRuns = useMemo(
    () => getNextRuns(cronExpression, selectedTimezone),
    [cronExpression, selectedTimezone]
  );

  // Handlers
  const handleModeChange = useCallback((_, newMode) => {
    if (newMode !== null) setMode(newMode);
  }, []);

  const handleFrequencyChange = useCallback((freq) => {
    setFrequency(freq);
  }, []);

  const handleWeekDayToggle = useCallback((dayValue) => {
    setWeekDays((prev) =>
      prev.includes(dayValue) ? prev.filter((d) => d !== dayValue) : [...prev, dayValue]
    );
  }, []);

  const handleCronPartChange = useCallback((index, value) => {
    setCronParts((prev) => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  }, []);

  const handleSave = useCallback(() => {
    if (!onSave) return;
    onSave({
      mode,
      cronExpression,
      timezone: selectedTimezone,
      frequency,
      hourlyInterval,
      hour,
      minute,
      weekDays,
      dayOfMonth,
      cronParts,
    });
  }, [onSave, mode, cronExpression, selectedTimezone, frequency, hourlyInterval, hour, minute, weekDays, dayOfMonth, cronParts]);

  const spacing = compact ? 1.5 : 2.5;


  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <Box sx={compact ? styles.containerCompact : styles.container}>
      <Stack spacing={spacing}>
        {/* Header */}
        {!compact && (
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#2c3e50' }}>
            Schedule Builder
          </Typography>
          <InfoTooltip title="Configure when the agent should run. Use Basic mode for simple schedules or Advanced mode for full cron control." />
        </Stack>
        )}

        {/* Mode Toggle */}
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          <ToggleButtonGroup
            value={mode}
            exclusive
            onChange={handleModeChange}
            size={compact ? 'small' : 'medium'}
            sx={{
              '& .MuiToggleButton-root': {
                px: 3,
                py: 0.8,
                borderRadius: '8px',
                textTransform: 'none',
                fontWeight: 500,
                border: '1px solid #e8ebf0',
                '&.Mui-selected': {
                  backgroundColor: '#e3edfc',
                  color: '#3b6cb7',
                  borderColor: '#b3d4fc',
                  '&:hover': { backgroundColor: '#d4e4fa' },
                },
              },
            }}
          >
            <ToggleButton value="basic">Basic</ToggleButton>
            <ToggleButton value="advanced">Advanced</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* ═══ BASIC MODE ═══ */}
        {mode === 'basic' && (
          <Card sx={styles.card}>
            <CardContent sx={{ p: compact ? 2 : 3 }}>
              <Stack spacing={spacing}>
                {/* Frequency selector */}
                <Box>
                  <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                    <Typography sx={styles.sectionTitle}>Frequency</Typography>
                    <InfoTooltip title="How often should the agent scan for jobs? Hourly is recommended for active job searches." />
                  </Stack>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {FREQUENCIES.map((freq) => (
                      <Chip
                        key={freq}
                        label={freq}
                        variant={frequency === freq ? 'filled' : 'outlined'}
                        onClick={() => handleFrequencyChange(freq)}
                        sx={frequency === freq ? styles.chipActive : styles.chip}
                      />
                    ))}
                  </Stack>
                </Box>

                {/* Hourly options */}
                {frequency === 'Hourly' && (
                  <Box>
                    <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                      <Typography sx={styles.sectionTitle}>Every X hours</Typography>
                      <InfoTooltip title="The agent will run once every N hours." />
                    </Stack>
                    <FormControl size="small" sx={{ minWidth: 160 }}>
                      <InputLabel>Interval</InputLabel>
                      <Select
                        value={hourlyInterval}
                        label="Interval"
                        onChange={(e) => setHourlyInterval(e.target.value)}
                      >
                        {HOURLY_OPTIONS.map((opt) => (
                          <MenuItem key={opt} value={opt}>
                            Every {opt} hour{opt > 1 ? 's' : ''}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                )}

                {/* Daily options */}
                {frequency === 'Daily' && (
                  <Box>
                    <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                      <Typography sx={styles.sectionTitle}>Time of Day</Typography>
                      <InfoTooltip title="The agent will run once daily at this time." />
                    </Stack>
                    <Stack direction="row" spacing={1.5}>
                      <FormControl size="small" sx={{ minWidth: 100 }}>
                        <InputLabel>Hour</InputLabel>
                        <Select value={hour} label="Hour" onChange={(e) => setHour(e.target.value)}>
                          {HOURS.map((h) => (
                            <MenuItem key={h} value={h}>
                              {String(h).padStart(2, '0')}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl size="small" sx={{ minWidth: 100 }}>
                        <InputLabel>Minute</InputLabel>
                        <Select value={minute} label="Minute" onChange={(e) => setMinute(e.target.value)}>
                          {MINUTES.map((m) => (
                            <MenuItem key={m} value={m}>
                              {String(m).padStart(2, '0')}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Box>
                )}

                {/* Weekly options */}
                {frequency === 'Weekly' && (
                  <Box>
                    <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                      <Typography sx={styles.sectionTitle}>Days & Time</Typography>
                      <InfoTooltip title="Select which days of the week the agent should run, and at what time." />
                    </Stack>
                    <Stack spacing={1.5}>
                      <Stack direction="row" flexWrap="wrap" useFlexGap spacing={0.5}>
                        {DAYS_OF_WEEK.map((day) => (
                          <FormControlLabel
                            key={day.value}
                            control={
                              <Checkbox
                                checked={weekDays.includes(day.value)}
                                onChange={() => handleWeekDayToggle(day.value)}
                                size="small"
                                sx={{
                                  color: '#b3c5d9',
                                  '&.Mui-checked': { color: '#5b8cd4' },
                                }}
                              />
                            }
                            label={day.label}
                            sx={{ mr: 0.5 }}
                          />
                        ))}
                      </Stack>
                      <Stack direction="row" spacing={1.5}>
                        <FormControl size="small" sx={{ minWidth: 100 }}>
                          <InputLabel>Hour</InputLabel>
                          <Select value={hour} label="Hour" onChange={(e) => setHour(e.target.value)}>
                            {HOURS.map((h) => (
                              <MenuItem key={h} value={h}>
                                {String(h).padStart(2, '0')}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 100 }}>
                          <InputLabel>Minute</InputLabel>
                          <Select value={minute} label="Minute" onChange={(e) => setMinute(e.target.value)}>
                            {MINUTES.map((m) => (
                              <MenuItem key={m} value={m}>
                                {String(m).padStart(2, '0')}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Stack>
                    </Stack>
                  </Box>
                )}

                {/* Monthly options */}
                {frequency === 'Monthly' && (
                  <Box>
                    <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                      <Typography sx={styles.sectionTitle}>Day & Time</Typography>
                      <InfoTooltip title="Select the day of the month and time for the agent to run." />
                    </Stack>
                    <Stack direction="row" spacing={1.5}>
                      <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Day</InputLabel>
                        <Select value={dayOfMonth} label="Day" onChange={(e) => setDayOfMonth(e.target.value)}>
                          {DAYS_OF_MONTH.map((d) => (
                            <MenuItem key={d} value={d}>
                              {d}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl size="small" sx={{ minWidth: 100 }}>
                        <InputLabel>Hour</InputLabel>
                        <Select value={hour} label="Hour" onChange={(e) => setHour(e.target.value)}>
                          {HOURS.map((h) => (
                            <MenuItem key={h} value={h}>
                              {String(h).padStart(2, '0')}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControl size="small" sx={{ minWidth: 100 }}>
                        <InputLabel>Minute</InputLabel>
                        <Select value={minute} label="Minute" onChange={(e) => setMinute(e.target.value)}>
                          {MINUTES.map((m) => (
                            <MenuItem key={m} value={m}>
                              {String(m).padStart(2, '0')}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Box>
                )}
              </Stack>
            </CardContent>
          </Card>
        )}

        {/* ═══ ADVANCED MODE ═══ */}
        {mode === 'advanced' && (
          <Card sx={styles.card}>
            <CardContent sx={{ p: compact ? 2 : 3 }}>
              <Stack spacing={spacing}>
                <Stack direction="row" alignItems="center">
                  <Typography sx={styles.sectionTitle}>Cron Expression</Typography>
                  <InfoTooltip title="Enter a standard 5-field cron expression. Format: Minute Hour Day Month Weekday. Use * for any, */n for intervals, and comma-separated values." />
                </Stack>
                <Stack direction="row" spacing={1}>
                  {[
                    { label: 'Minute', placeholder: '0-59', index: 0 },
                    { label: 'Hour', placeholder: '0-23', index: 1 },
                    { label: 'Day', placeholder: '1-31', index: 2 },
                    { label: 'Month', placeholder: '1-12', index: 3 },
                    { label: 'Weekday', placeholder: '0-7', index: 4 },
                  ].map((field) => (
                    <TextField
                      key={field.index}
                      label={field.label}
                      placeholder={field.placeholder}
                      value={cronParts[field.index]}
                      onChange={(e) => handleCronPartChange(field.index, e.target.value)}
                      size="small"
                      error={cronFieldErrors[field.index]}
                      sx={{
                        flex: 1,
                        '& .MuiOutlinedInput-root': {
                          borderRadius: '8px',
                          ...(cronFieldErrors[field.index] && {
                            '& fieldset': { borderColor: '#e57373' },
                          }),
                        },
                      }}
                      inputProps={{
                        style: { textAlign: 'center', fontFamily: 'monospace' },
                      }}
                    />
                  ))}
                </Stack>
                <Typography variant="caption" sx={{ color: '#8fa4bd', textAlign: 'center' }}>
                  Use * for any, */n for every n, ranges (1-5), or lists (1,3,5)
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        )}

        {/* ═══ LIVE TRANSLATOR ═══ */}
        <Box sx={translation.valid ? styles.translatorValid : styles.translatorInvalid}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography
              sx={{
                fontSize: '0.9rem',
                fontWeight: 500,
                color: translation.valid ? '#2e7d32' : '#c62828',
              }}
            >
              {translation.valid ? '✓' : '✗'} {translation.text}
            </Typography>
          </Stack>
        </Box>

        {/* ═══ TIMEZONE SELECTOR ═══ */}
        <Card sx={styles.card}>
          <CardContent sx={{ p: compact ? 2 : 3 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" alignItems="center">
                <Typography sx={styles.sectionTitle}>Timezone</Typography>
                <InfoTooltip title="All scheduled times will be interpreted in this timezone. Defaults to your system timezone." />
              </Stack>
              <Autocomplete
                value={timezoneList.find((tz) => tz.value === selectedTimezone) || null}
                onChange={(_, newValue) => {
                  if (newValue) setSelectedTimezone(newValue.value);
                }}
                options={timezoneList}
                getOptionLabel={(option) => option.label}
                isOptionEqualToValue={(option, value) => option.value === value.value}
                size="small"
                renderInput={(params) => (
                  <TextField
                    {...params}
                    placeholder="Search timezone..."
                    sx={{
                      '& .MuiOutlinedInput-root': { borderRadius: '8px' },
                    }}
                  />
                )}
                sx={{ maxWidth: 400 }}
              />
            </Stack>
          </CardContent>
        </Card>

        {/* ═══ NEXT 5 RUNS PREVIEW ═══ */}
        <Card sx={styles.card}>
          <CardContent sx={{ p: compact ? 2 : 3 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" alignItems="center">
                <Typography sx={styles.sectionTitle}>Next 5 Runs</Typography>
                <InfoTooltip title="Preview of the next 5 scheduled execution times based on your current configuration." />
              </Stack>
              {nextRuns.error ? (
                <Typography sx={{ color: '#c62828', fontSize: '0.85rem' }}>
                  Unable to calculate: {nextRuns.error}
                </Typography>
              ) : nextRuns.runs.length === 0 ? (
                <Typography sx={{ color: '#8fa4bd', fontSize: '0.85rem' }}>
                  Configure a schedule to see upcoming runs.
                </Typography>
              ) : (
                <Stack spacing={0.75}>
                  {nextRuns.runs.map((run, idx) => {
                    const d = dayjs(run).tz(selectedTimezone);
                    const relative = dayjs(run).fromNow();
                    return (
                      <Stack
                        key={idx}
                        direction="row"
                        justifyContent="space-between"
                        alignItems="center"
                        sx={{
                          backgroundColor: idx % 2 === 0 ? '#f8fafe' : '#ffffff',
                          px: 1.5,
                          py: 0.75,
                          borderRadius: '6px',
                        }}
                      >
                        <Typography sx={{ fontSize: '0.85rem', color: '#3a4a5c', fontFamily: 'monospace' }}>
                          {d.format('ddd, MMM D, YYYY [at] HH:mm')}
                        </Typography>
                        <Chip
                          label={relative}
                          size="small"
                          sx={{
                            backgroundColor: '#e8f0fe',
                            color: '#4a7abf',
                            fontWeight: 500,
                            fontSize: '0.75rem',
                          }}
                        />
                      </Stack>
                    );
                  })}
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>

        {/* ═══ SAVE BUTTON ═══ */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={!translation.valid}
            sx={{
              textTransform: 'none',
              borderRadius: '8px',
              px: 4,
              py: 1,
              fontWeight: 600,
              backgroundColor: '#5b8cd4',
              boxShadow: '0 2px 8px rgba(91,140,212,0.25)',
              '&:hover': { backgroundColor: '#4a7abf' },
              '&.Mui-disabled': {
                backgroundColor: '#e0e5ec',
                color: '#a0aec0',
              },
            }}
          >
            Save Schedule
          </Button>
        </Box>
      </Stack>
    </Box>
  );
}
