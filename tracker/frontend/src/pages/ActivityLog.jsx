import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box, Typography, Chip, TextField, Button, FormControl, InputLabel,
  Select, MenuItem, CircularProgress, Alert, IconButton, Stack,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import InfoIcon from '@mui/icons-material/Info';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import { fetchLogs } from '../api';

const SEVERITY_CONFIG = {
  info: { icon: InfoIcon, color: 'info' },
  success: { icon: CheckCircleIcon, color: 'success' },
  warning: { icon: WarningIcon, color: 'warning' },
  error: { icon: ErrorIcon, color: 'error' },
};

function SeverityCell({ value }) {
  const config = SEVERITY_CONFIG[value] || SEVERITY_CONFIG.info;
  const Icon = config.icon;
  return <Chip icon={<Icon sx={{ fontSize: 14 }} />} label={value || 'info'} size="small" color={config.color} variant="outlined" sx={{ textTransform: 'capitalize' }} />;
}

export default function ActivityLog() {
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const intervalRef = useRef(null);

  const [severityFilter, setSeverityFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [searchText, setSearchText] = useState('');

  const loadLogs = useCallback(async () => {
    try {
      const data = await fetchLogs({
        page: page + 1, pageSize,
        severity: severityFilter || undefined,
        eventType: eventTypeFilter || undefined,
        search: searchText || undefined,
      });
      setRows((data.logs || data.items || []).map((row, idx) => ({ id: row.id || idx, ...row })));
      setTotalRows(data.total || data.count || 0);
    } catch { setError('Failed to load activity logs'); }
    finally { setLoading(false); }
  }, [page, pageSize, severityFilter, eventTypeFilter, searchText]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  useEffect(() => {
    if (autoRefresh) intervalRef.current = setInterval(loadLogs, 10000);
    else clearInterval(intervalRef.current);
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh, loadLogs]);

  const handleExportCSV = () => {
    if (rows.length === 0) return;
    const headers = ['Timestamp', 'Event Type', 'Severity', 'Job Title', 'Company', 'Message', 'Stage'];
    const csvRows = rows.map((r) => [
      r.timestamp || r.created_at || '', r.event_type || '', r.severity || '',
      r.job_title || '', r.company || '', (r.message || '').replace(/,/g, ';'), r.stage || '',
    ]);
    const csv = [headers.join(','), ...csvRows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `activity_log_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  const columns = [
    {
      field: 'timestamp', headerName: 'Time', width: 160,
      renderCell: (params) => {
        const val = params.row.timestamp || params.row.created_at;
        return <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{val ? new Date(val).toLocaleString() : '—'}</Typography>;
      },
    },
    {
      field: 'event_type', headerName: 'Event', width: 120,
      renderCell: (params) => <Chip label={(params.value || '—').replace(/_/g, ' ')} size="small" variant="outlined" sx={{ textTransform: 'capitalize' }} />,
    },
    { field: 'severity', headerName: 'Severity', width: 110, renderCell: (params) => <SeverityCell value={params.value} /> },
    { field: 'title', headerName: 'Job Title', flex: 1, minWidth: 160 },
    { field: 'company', headerName: 'Company', width: 140 },
    { field: 'message', headerName: 'Message', flex: 1.5, minWidth: 200 },
    { field: 'stage', headerName: 'Stage', width: 100 },
  ];

  if (error) return <Alert severity="error" sx={{ fontSize: 12 }}>{error}</Alert>;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      {/* Slim top bar - 40px */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5, minHeight: 40, flexWrap: 'wrap' }}>
        {/* Severity chips */}
        {Object.entries(SEVERITY_CONFIG).map(([key, cfg]) => (
          <Chip
            key={key} label={key} size="small"
            color={severityFilter === key ? cfg.color : 'default'}
            variant={severityFilter === key ? 'filled' : 'outlined'}
            onClick={() => setSeverityFilter(severityFilter === key ? '' : key)}
            sx={{ textTransform: 'capitalize' }}
          />
        ))}

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <Select value={eventTypeFilter} onChange={(e) => setEventTypeFilter(e.target.value)} displayEmpty sx={{ fontSize: 11, height: 28 }}>
            <MenuItem value="" sx={{ fontSize: 11 }}>All Events</MenuItem>
            <MenuItem value="scan" sx={{ fontSize: 11 }}>Scan</MenuItem>
            <MenuItem value="apply" sx={{ fontSize: 11 }}>Apply</MenuItem>
            <MenuItem value="inmail" sx={{ fontSize: 11 }}>InMail</MenuItem>
            <MenuItem value="notify" sx={{ fontSize: 11 }}>Notify</MenuItem>
            <MenuItem value="service" sx={{ fontSize: 11 }}>Service</MenuItem>
            <MenuItem value="error" sx={{ fontSize: 11 }}>Error</MenuItem>
          </Select>
        </FormControl>

        <TextField
          size="small" placeholder="Search..." value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          InputProps={{ startAdornment: <SearchIcon sx={{ fontSize: 14, mr: 0.5, color: 'text.disabled' }} />, sx: { fontSize: 11, height: 28 } }}
          sx={{ width: 160 }}
        />

        <Box sx={{ flex: 1 }} />

        <Stack direction="row" spacing={0.5} alignItems="center">
          <Chip label={`${totalRows}`} size="small" variant="outlined" sx={{ fontSize: 10, height: 18 }} />
          <IconButton size="small" onClick={loadLogs} sx={{ p: 0.25 }}><RefreshIcon sx={{ fontSize: 16 }} /></IconButton>
          <Button size="small" startIcon={<DownloadIcon sx={{ fontSize: 12 }} />} onClick={handleExportCSV} sx={{ fontSize: 10, py: 0.25, minWidth: 0, textTransform: 'none' }}>CSV</Button>
        </Stack>
      </Box>

      {/* DataGrid fills remaining space */}
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          rowCount={totalRows}
          pageSizeOptions={[25, 50, 100]}
          paginationModel={{ page, pageSize }}
          onPaginationModelChange={(model) => { setPage(model.page); setPageSize(model.pageSize); }}
          paginationMode="server"
          sortingMode="server"
          disableRowSelectionOnClick
          density="compact"
          rowHeight={36}
          sx={{
            border: 'none',
            '& .MuiDataGrid-columnHeader': { fontWeight: 600 },
            '& .MuiDataGrid-footerContainer': { borderTop: '1px solid', borderColor: 'divider' },
          }}
          slots={{
            noRowsOverlay: () => (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <Typography sx={{ fontSize: 12, color: 'text.secondary' }}>No logs found</Typography>
              </Box>
            ),
          }}
        />
      </Box>
    </Box>
  );
}
