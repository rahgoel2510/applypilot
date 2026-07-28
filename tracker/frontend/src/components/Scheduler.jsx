import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Switch,
  TextField,
  Button,
  Grid,
  Chip,
  FormControlLabel,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Alert,
} from '@mui/material';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SaveIcon from '@mui/icons-material/Save';
import { useSnackbar } from 'notistack';
import { getSchedule, updateSchedule, getNextRuns } from '../api';

const DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function Scheduler() {
  const { enqueueSnackbar } = useSnackbar();
  const [config, setConfig] = useState({
    enabled: true,
    interval_minutes: 60,
    active_hours_start: '09:00',
    active_hours_end: '18:00',
    cron_expression: '',
    days_of_week: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
  });
  const [nextRuns, setNextRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSchedule();
  }, []);

  async function loadSchedule() {
    try {
      const data = await getSchedule();
      if (data) setConfig(data);
      const runs = await getNextRuns();
      if (runs?.next_runs) setNextRuns(runs.next_runs);
    } catch (err) {
      console.error('Failed to load schedule:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    try {
      await updateSchedule(config);
      enqueueSnackbar('Schedule saved', { variant: 'success' });
      const runs = await getNextRuns();
      if (runs?.next_runs) setNextRuns(runs.next_runs);
    } catch (err) {
      enqueueSnackbar('Failed to save schedule', { variant: 'error' });
    }
  }

  const toggleDay = (day) => {
    setConfig((prev) => ({
      ...prev,
      days_of_week: prev.days_of_week.includes(day)
        ? prev.days_of_week.filter((d) => d !== day)
        : [...prev.days_of_week, day],
    }));
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <Typography color="text.secondary">Loading scheduler...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Scheduler
      </Typography>

      <Grid container spacing={2.5}>
        {/* Schedule Configuration */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ScheduleIcon color="primary" fontSize="small" />
                  <Typography variant="h6">Schedule Configuration</Typography>
                </Box>
                <FormControlLabel
                  control={
                    <Switch
                      checked={config.enabled}
                      onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                      size="small"
                    />
                  }
                  label={config.enabled ? 'Enabled' : 'Disabled'}
                />
              </Box>

              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Interval (minutes)"
                    type="number"
                    fullWidth
                    value={config.interval_minutes}
                    onChange={(e) => setConfig({ ...config, interval_minutes: parseInt(e.target.value) || 60 })}
                    inputProps={{ min: 5, max: 1440 }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Cron Expression (optional)"
                    fullWidth
                    value={config.cron_expression}
                    onChange={(e) => setConfig({ ...config, cron_expression: e.target.value })}
                    placeholder="e.g. 0 */2 9-18 * * 1-5"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Active Hours Start"
                    type="time"
                    fullWidth
                    value={config.active_hours_start}
                    onChange={(e) => setConfig({ ...config, active_hours_start: e.target.value })}
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Active Hours End"
                    type="time"
                    fullWidth
                    value={config.active_hours_end}
                    onChange={(e) => setConfig({ ...config, active_hours_end: e.target.value })}
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
              </Grid>

              {/* Days of Week */}
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Active Days
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {DAYS_OF_WEEK.map((day) => (
                    <Chip
                      key={day}
                      label={day}
                      size="small"
                      onClick={() => toggleDay(day)}
                      color={config.days_of_week.includes(day) ? 'primary' : 'default'}
                      variant={config.days_of_week.includes(day) ? 'filled' : 'outlined'}
                    />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave}>
                  Save Schedule
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Next Scheduled Runs */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <AccessTimeIcon color="secondary" fontSize="small" />
                <Typography variant="h6">Next Runs</Typography>
              </Box>

              {nextRuns.length === 0 ? (
                <Alert severity="info" sx={{ fontSize: '0.75rem' }}>
                  No scheduled runs. Enable the scheduler to see upcoming runs.
                </Alert>
              ) : (
                <List dense disablePadding>
                  {nextRuns.map((run, idx) => (
                    <ListItem key={idx} disablePadding sx={{ py: 0.5 }}>
                      <ListItemIcon sx={{ minWidth: 28 }}>
                        <PlayArrowIcon fontSize="small" color="primary" />
                      </ListItemIcon>
                      <ListItemText
                        primary={run}
                        primaryTypographyProps={{ fontSize: '0.75rem' }}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
