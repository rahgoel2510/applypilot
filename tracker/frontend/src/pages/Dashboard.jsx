import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Button,
  List,
  ListItem,
  ListItemText,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Stack,
  LinearProgress,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SendIcon from '@mui/icons-material/Send';
import PercentIcon from '@mui/icons-material/Percent';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CircleIcon from '@mui/icons-material/Circle';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { fetchStats, fetchLogs, fetchJobs, getAgentStatus, triggerAgent } from '../api';
import { FunnelChart, ScoreDonut, RadialGauge, Sparkline } from '../components/D3Charts';

dayjs.extend(relativeTime);

// Shared card style
const cardSx = {
  height: '100%',
  borderRadius: '12px',
  overflow: 'hidden',
  border: '1px solid',
  borderColor: 'divider',
  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
  '&:hover': { boxShadow: '0 2px 8px rgba(0,0,0,0.08)' },
};

const cardContentSx = { p: 2.5, '&:last-child': { pb: 2.5 } };

// Metric card colors (colored top strip)
const METRIC_COLORS = ['#0073BB', '#067D68', '#EC7211', '#6B40B2'];
const METRIC_BG = ['#E6F2FA', '#E6F5F2', '#FEF3E8', '#F3EEFB'];

// Stage colors — vibrant
const STAGE_COLORS = {
  discovered: '#0073BB',
  reached_out: '#6B40B2',
  saved: '#EC7211',
  applied: '#067D68',
  interviewing: '#EC7211',
  offered: '#067D68',
  rejected: '#D13212',
};

const STAGE_LABELS = {
  discovered: 'Discovered',
  reached_out: 'Reached Out',
  saved: 'Saved',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offered: 'Offered',
  rejected: 'Rejected',
};

// Severity dot colors
const SEVERITY_COLORS = {
  info: '#3b82f6',
  warning: '#f59e0b',
  error: '#ef4444',
  success: '#10b981',
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [agentStatus, setAgentStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [statsData, logsData, jobsData, statusData] = await Promise.all([
        fetchStats(),
        fetchLogs({ page: 1, pageSize: 8 }),
        fetchJobs({ sort: 'newest' }),
        getAgentStatus().catch(() => null),
      ]);
      setStats(statsData);
      setLogs(logsData.logs || logsData.items || logsData || []);
      const jobsList = Array.isArray(jobsData) ? jobsData : jobsData.jobs || jobsData.items || [];
      setJobs(jobsList.slice(0, 10));
      setAgentStatus(statusData);
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Derived values — compute from actual data
  const totalJobs = stats?.total ?? 0;
  const appliedCount = stats?.applied ?? 0;

  // Compute match rate from jobs with scores
  const matchRate = useMemo(() => {
    const scored = jobs.filter(j => j.match_score != null);
    if (scored.length === 0) return 0;
    const avg = scored.reduce((sum, j) => sum + j.match_score, 0) / scored.length;
    return avg; // 0-1 float
  }, [jobs]);

  // Stage data for pipeline bar and funnel
  const stages = useMemo(() => {
    // The API returns { discovered: 12, reached_out: 9, ... } at top level
    const src = stats || {};
    return Object.keys(STAGE_LABELS).map((key) => ({
      key,
      label: STAGE_LABELS[key],
      count: src[key] ?? src?.stages?.[key] ?? src?.by_stage?.[key] ?? 0,
      color: STAGE_COLORS[key],
    }));
  }, [stats]);

  const totalInPipeline = stages.reduce((s, st) => s + st.count, 0) || 1;

  // Score distribution — compute from actual jobs data
  const scoreDistribution = useMemo(() => {
    const buckets = [
      { range: '0-20%', count: 0, color: '#D13212' },
      { range: '21-40%', count: 0, color: '#D13212' },
      { range: '41-60%', count: 0, color: '#EC7211' },
      { range: '61-80%', count: 0, color: '#EC7211' },
      { range: '81-100%', count: 0, color: '#067D68' },
    ];
    jobs.forEach((j) => {
      const s = j.match_score;
      if (s == null) return;
      const pct = s <= 1 ? s * 100 : s;
      if (pct <= 20) buckets[0].count++;
      else if (pct <= 40) buckets[1].count++;
      else if (pct <= 60) buckets[2].count++;
      else if (pct <= 80) buckets[3].count++;
      else buckets[4].count++;
    });
    return buckets;
  }, [jobs]);

  // Top companies
  const topCompanies = useMemo(() => {
    if (stats?.top_companies) return stats.top_companies.slice(0, 5);
    const companyMap = {};
    jobs.forEach((j) => {
      const c = j.company || 'Unknown';
      companyMap[c] = (companyMap[c] || 0) + 1;
    });
    return Object.entries(companyMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count]) => ({ name, count }));
  }, [stats, jobs]);

  // Quick stats
  const totalScans = stats?.total_scans ?? stats?.scans ?? 0;
  const avgJobsPerScan = totalScans ? Math.round(totalJobs / totalScans) : 0;
  const successRate = totalJobs ? Math.round((appliedCount / totalJobs) * 100) : 0;
  const lastRun = stats?.last_run || agentStatus?.last_run || null;

  // Agent state
  const agentState = agentStatus?.status || agentStatus?.state || 'idle';
  const nextRun = agentStatus?.next_run || stats?.next_run || null;

  if (loading) {
    return (
      <Box sx={{ p: 2 }}>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', p: 2 }}>
      <Typography variant="h3" sx={{ mb: 2 }}>Dashboard</Typography>
      <Grid container spacing={2}>
        {/* ═══════════════ ROW 1: Stat Cards ═══════════════ */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ ...cardSx, borderTop: `4px solid ${METRIC_COLORS[0]}` }}>
            <CardContent sx={cardContentSx}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" sx={{ mb: 0.5, display: 'block' }}>Total Jobs</Typography>
                  <Typography variant="h2" sx={{ lineHeight: 1.2 }}>
                    {totalJobs}
                  </Typography>
                  <Typography variant="caption">All tracked jobs</Typography>
                </Box>
                <Box sx={{ width: 40, height: 40, borderRadius: '10px', bgcolor: METRIC_BG[0], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <TrendingUpIcon sx={{ color: METRIC_COLORS[0], fontSize: 20 }} />
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ ...cardSx, borderTop: `4px solid ${METRIC_COLORS[1]}` }}>
            <CardContent sx={cardContentSx}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" sx={{ mb: 0.5, display: 'block' }}>Applied</Typography>
                  <Typography variant="h2" sx={{ lineHeight: 1.2 }}>
                    {appliedCount}
                  </Typography>
                  <Typography variant="caption">This session</Typography>
                </Box>
                <Box sx={{ width: 40, height: 40, borderRadius: '10px', bgcolor: METRIC_BG[1], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <SendIcon sx={{ color: METRIC_COLORS[1], fontSize: 20 }} />
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ ...cardSx, borderTop: `4px solid ${METRIC_COLORS[2]}` }}>
            <CardContent sx={cardContentSx}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" sx={{ mb: 0.5, display: 'block' }}>Match Rate</Typography>
                  <Typography variant="h2" sx={{ lineHeight: 1.2 }}>
                    {Math.round(matchRate <= 1 ? matchRate * 100 : matchRate)}%
                  </Typography>
                  <Typography variant="caption">Avg score</Typography>
                </Box>
                <Box sx={{ width: 40, height: 40, borderRadius: '10px', bgcolor: METRIC_BG[2], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <PercentIcon sx={{ color: METRIC_COLORS[2], fontSize: 20 }} />
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ ...cardSx, borderTop: `4px solid ${METRIC_COLORS[3]}` }}>
            <CardContent sx={cardContentSx}>
              <Typography variant="overline" sx={{ mb: 0.5, display: 'block' }}>Pipeline</Typography>
              {/* Stacked progress bar */}
              <Box sx={{ display: 'flex', height: 18, borderRadius: 1, overflow: 'hidden', mb: 0.75, bgcolor: 'rgba(0,0,0,0.05)' }}>
                {stages.filter(s => s.count > 0).map((s) => (
                  <Box
                    key={s.key}
                    sx={{
                      width: `${(s.count / totalInPipeline) * 100}%`,
                      bgcolor: s.color,
                      minWidth: s.count > 0 ? 8 : 0,
                    }}
                  />
                ))}
                {totalInPipeline <= 1 && stages.every(s => s.count === 0) && (
                  <Box sx={{ width: '100%', bgcolor: 'action.disabledBackground' }} />
                )}
              </Box>
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {stages.filter(s => s.count > 0).map((s) => (
                  <Typography key={s.key} variant="caption" sx={{ color: s.color, fontWeight: 600 }}>
                    {s.label}: {s.count}
                  </Typography>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {/* ═══════════════ ROW 2: Funnel + Score Distribution ═══════════════ */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card sx={cardSx}>
            <CardContent sx={cardContentSx}>
              <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                Application Funnel
              </Typography>
              <FunnelChart data={stages.filter(s => s.count > 0 || ['discovered', 'applied', 'interviewing', 'offered'].includes(s.key))} height={240} />
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={cardSx}>
            <CardContent sx={cardContentSx}>
              <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                Score Distribution
              </Typography>
              <ScoreDonut data={scoreDistribution} size={200} />
            </CardContent>
          </Card>
        </Grid>

        {/* ═══════════════ ROW 3: Activity + Jobs Table ═══════════════ */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Card sx={cardSx}>
            <CardContent sx={cardContentSx}>
              <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                Recent Activity
              </Typography>
              <List dense disablePadding>
                {(Array.isArray(logs) ? logs : []).slice(0, 8).map((log, idx) => (
                  <ListItem key={log.id || idx} disableGutters sx={{ py: 0.25, alignItems: 'flex-start' }}>
                    <CircleIcon
                      sx={{
                        fontSize: 8,
                        color: SEVERITY_COLORS[log.severity] || SEVERITY_COLORS.info,
                        mt: 0.8,
                        mr: 1,
                        flexShrink: 0,
                      }}
                    />
                    <ListItemText
                      primary={
                        <Typography variant="body2" noWrap sx={{ fontSize: '0.8rem' }}>
                          {log.message || log.event || log.description || 'Event'}
                        </Typography>
                      }
                      secondary={
                        <Typography variant="caption" color="text.secondary">
                          {log.timestamp ? dayjs(log.timestamp).fromNow() : ''}
                        </Typography>
                      }
                      sx={{ m: 0 }}
                    />
                  </ListItem>
                ))}
                {(!logs || logs.length === 0) && (
                  <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                    No recent activity
                  </Typography>
                )}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 7 }}>
          <Card sx={cardSx}>
            <CardContent sx={{ ...cardContentSx, p: 0, '&:last-child': { pb: 0 } }}>
              <Typography variant="body2" fontWeight={600} sx={{ px: 1.5, pt: 1.5, pb: 0.5 }}>
                Jobs Table
              </Typography>
              <TableContainer sx={{ maxHeight: 320 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ py: 0.75, fontSize: '0.75rem', fontWeight: 600 }}>Title</TableCell>
                      <TableCell sx={{ py: 0.75, fontSize: '0.75rem', fontWeight: 600 }}>Company</TableCell>
                      <TableCell sx={{ py: 0.75, fontSize: '0.75rem', fontWeight: 600 }} align="center">Score</TableCell>
                      <TableCell sx={{ py: 0.75, fontSize: '0.75rem', fontWeight: 600 }}>Stage</TableCell>
                      <TableCell sx={{ py: 0.75, fontSize: '0.75rem', fontWeight: 600 }}>Date</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {jobs.map((job) => (
                      <TableRow
                        key={job.id}
                        hover
                        sx={{ cursor: 'pointer', '&:last-child td': { border: 0 } }}
                        onClick={() => navigate('/board')}
                      >
                        <TableCell sx={{ py: 0.5, maxWidth: 160 }}>
                          <Typography variant="body2" noWrap sx={{ fontSize: '0.8rem' }}>
                            {job.title || job.role || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ py: 0.5 }}>
                          <Typography variant="body2" noWrap sx={{ fontSize: '0.8rem' }}>
                            {job.company || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ py: 0.5 }} align="center">
                          {job.match_score != null ? (
                            <Chip
                              label={`${Math.round(job.match_score * 100)}%`}
                              size="small"
                              sx={{
                                height: 20,
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                bgcolor: job.match_score >= 0.70 ? 'rgba(16,185,129,0.1)' : job.match_score >= 0.40 ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)',
                                color: job.match_score >= 0.70 ? '#10b981' : job.match_score >= 0.40 ? '#f59e0b' : '#ef4444',
                              }}
                            />
                          ) : (
                            <Typography variant="caption" color="text.secondary">—</Typography>
                          )}
                        </TableCell>
                        <TableCell sx={{ py: 0.5 }}>
                          <Chip
                            label={STAGE_LABELS[job.stage] || job.stage || '—'}
                            size="small"
                            sx={{
                              height: 20,
                              fontSize: '11px',
                              fontWeight: 500,
                              bgcolor: STAGE_COLORS[job.stage] ? `${STAGE_COLORS[job.stage]}18` : 'action.hover',
                              color: STAGE_COLORS[job.stage] || 'text.secondary',
                            }}
                          />
                        </TableCell>
                        <TableCell sx={{ py: 0.5 }}>
                          <Typography variant="caption" color="text.secondary">
                            {job.created_at || job.date ? dayjs(job.created_at || job.date).format('MMM D') : '—'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                    {jobs.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                          <Typography variant="body2" color="text.secondary">No jobs found</Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* ═══════════════ ROW 4: Quick Stats + Agent Status + Top Companies ═══════════════ */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={cardSx}>
            <CardContent sx={cardContentSx}>
              <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                Quick Stats
              </Typography>
              <Stack spacing={1}>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Total Scans</Typography>
                  <Typography variant="body2" fontWeight={600}>{totalScans}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Avg Jobs/Scan</Typography>
                  <Typography variant="body2" fontWeight={600}>{avgJobsPerScan}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Success Rate</Typography>
                  <Typography variant="body2" fontWeight={600}>{successRate}%</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Last Run</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {lastRun ? dayjs(lastRun).fromNow() : 'Never'}
                  </Typography>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={cardSx}>
            <CardContent sx={cardContentSx}>
              <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                Agent Status
              </Typography>
              <Stack spacing={1.5}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <CircleIcon
                    sx={{
                      fontSize: 10,
                      color: agentState === 'running' ? '#10b981' : agentState === 'error' ? '#ef4444' : '#6b7280',
                    }}
                  />
                  <Typography variant="body2" fontWeight={500} sx={{ textTransform: 'capitalize' }}>
                    {agentState}
                  </Typography>
                </Stack>
                <Button
                  size="small"
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={() => navigate('/agent')}
                  sx={{
                    textTransform: 'none',
                    fontWeight: 600,
                    borderRadius: 1,
                    fontSize: '0.8rem',
                  }}
                >
                  Run Agent
                </Button>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="caption" color="text.secondary">Next scheduled</Typography>
                  <Typography variant="caption" fontWeight={500}>
                    {nextRun ? dayjs(nextRun).fromNow() : '—'}
                  </Typography>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={cardSx}>
            <CardContent sx={cardContentSx}>
              <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                Top Companies
              </Typography>
              {topCompanies.length > 0 ? (
                <Stack spacing={0.5}>
                  {topCompanies.map((c, idx) => (
                    <Stack key={idx} direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" noWrap sx={{ maxWidth: '70%' }}>
                        {c.name || c.company}
                      </Typography>
                      <Chip
                        label={c.count || c.jobs}
                        size="small"
                        sx={{ height: 20, fontSize: '0.7rem', fontWeight: 600 }}
                      />
                    </Stack>
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                  No data yet
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
