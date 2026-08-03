import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Stack, Button, CircularProgress } from '@mui/material';
import ScheduleIcon from '@mui/icons-material/Schedule';
import SaveIcon from '@mui/icons-material/Save';
import { useSnackbar } from 'notistack';
import { getSchedule, updateSchedule } from '../api';
import SchedulerBuilder from '../components/SchedulerBuilder';

export default function Scheduler() {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [initialConfig, setInitialConfig] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getSchedule();
        if (data) setInitialConfig(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSave = async (config) => {
    try {
      await updateSchedule(config);
      enqueueSnackbar('Schedule saved and activated!', { variant: 'success' });
    } catch (err) {
      enqueueSnackbar('Failed to save schedule', { variant: 'error' });
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
        <ScheduleIcon sx={{ fontSize: 28, color: 'primary.main' }} />
        <Box>
          <Typography variant="h4" fontWeight={700}>Scheduler</Typography>
          <Typography variant="body2" color="text.secondary">
            Configure when the agent runs automatically
          </Typography>
        </Box>
      </Stack>

      <SchedulerBuilder onSave={handleSave} initialConfig={initialConfig} />
    </Box>
  );
}
