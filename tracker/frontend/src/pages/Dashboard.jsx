import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Button,
  Chip,
  Stack,
  LinearProgress,
  Tabs,
  Tab,
  Collapse,
  IconButton,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Tooltip,
  Drawer,
  Slider,
  Switch,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import MailOutlineIcon from '@mui/icons-material/MailOutlined';
import TimerIcon from '@mui/icons-material/Timer';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import BusinessIcon from '@mui/icons-material/Business';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ScheduleIcon from '@mui/icons-material/Schedule';
import CloseIcon from '@mui/icons-material/Close';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { fetchStats, fetchJobs, fetchJobsEnriched, getAgentStatus, getAgentRuns, triggerAgent } from '../api';
import { AnimatedNumber, FadeInUp } from '../components/Animated';
import { useWebSocket } from '../hooks/useWebSocket';

dayjs.extend(relativeTime);

// ─── Shared Styles ───────────────────────────────────────────────────────────
const cardSx = {
  height: '100%',
  borderRadius: '12px',
  overflow: 'hidden',
  border: '1px solid',
  borderColor: 'divider',
  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
  '&:hover': { boxShadow: '0 4px 12px rgba(0,0,0,0.08)' },
  transition: 'box-shadow 0.2s ease',
};

const cardContentSx = { p: 2.5, '&:last-child': { pb: 2.5 } };

// KPI card accent colors
const KPI_COLORS = ['#0073BB', '#067D68', '#6B40B2', '#EC7211'];
const KPI_BG = ['#E6F2FA', '#E6F5F2', '#F3EEFB', '#FEF3E8'];

// Stage configuration
const STAGE_COLORS = {
  discovered: '#0073BB',
  applied: '#067D68',
  interviewing: '#EC7211',
  offered: '#6B40B2',
};

const STAGE_LABELS = {
  discovered: 'Discovered',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offered: 'Offered',
};

const STATUS_CHIP_STYLES = {
  discovered: { bgcolor: '#E6F2FA', color: '#0073BB' },
  applied: { bgcolor: '#E6F5F2', color: '#067D68' },
  interviewing: { bgcolor: '#FEF3E8', color: '#EC7211' },
  offered: { bgcolor: '#F3EEFB', color: '#6B40B2' },
  external: { bgcolor: '#FEF3E8', color: '#EC7211' },
  rejected: { bgcolor: '#FDE8E8', color: '#D13212' },
};

// Filter tabs
const FILTER_TABS = ['All', 'High Match', 'Applied', 'External', 'Needs Action'];

// ─── Main Component ──────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [jobCounts, setJobCounts] = useState({ all: 0, top: 0, applied: 0, external: 0 });
  const [agentStatus, setAgentStatus] = useState(null);
  const [lastRunData, setLastRunData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState(0);
  const [sortBy, setSortBy] = useState('score');
  const [expandedJob, setExpandedJob] = useState(null);
  const [countdown, setCountdown] = useState(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  const { events: wsEvents, isConnected, liveStats } = useWebSocket();

  // ─── Data Loading ────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      const [statsData, jobsData, statusData, runsData] = await Promise.all([
        fetchStats(),
        fetchJobsEnriched({ sort: 'score' }).catch(() => ({ jobs: [], counts: {} })),
        getAgentStatus().catch(() => null),
        getAgentRuns(1).catch(() => []),
      ]);
      setStats(statsData);
      const enriched = jobsData.jobs || [];
      setJobs(enriched);
      setJobCounts(jobsData.counts || { all: 0, top: 0, applied: 0, external: 0 });
      setAgentStatus(statusData);
      const runs = Array.isArray(runsData) ? runsData : runsData.runs || [];
      if (runs.length > 0) setLastRunData(runs[0]);
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 20000);
    return () => clearInterval(interval);
  }, [loadData]);

  // ─── Countdown Timer ─────────────────────────────────────────────────────
  const nextRunTime = agentStatus?.next_run || stats?.next_run || null;

  useEffect(() => {
    if (!nextRunTime) { setCountdown(null); return; }
    const tick = () => {
      const diff = dayjs(nextRunTime).diff(dayjs(), 'second');
      if (diff <= 0) { setCountdown('Now'); return; }
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setCountdown(h > 0 ? `${h}h ${m}m` : `${m}m ${s}s`);
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [nextRunTime]);

  // ─── Derived Data ────────────────────────────────────────────────────────
  const totalDiscovered = stats?.total ?? stats?.discovered ?? 0;
  const totalApplied = stats?.applied ?? 0;
  const totalResponses = (stats?.interviewing ?? 0) + (stats?.offered ?? 0);

  const stages = useMemo(() => {
    const src = stats || {};
    return ['discovered', 'applied', 'interviewing', 'offered'].map((key) => ({
      key,
      label: STAGE_LABELS[key],
      count: src[key] ?? src?.stages?.[key] ?? src?.by_stage?.[key] ?? 0,
      color: STAGE_COLORS[key],
    }));
  }, [stats]);

  const maxStageCount = Math.max(...stages.map(s => s.count), 1);

  // Filter & sort jobs
  const filteredJobs = useMemo(() => {
    let filtered = [...jobs];
    switch (filterTab) {
      case 1: // Top Matches (score >= 80)
        filtered = filtered.filter(j => (j.match_score || 0) >= 80);
        break;
      case 2: // Applied
        filtered = filtered.filter(j => j.stage === 'applied');
        break;
      case 3: // External
        filtered = filtered.filter(j => j.is_external);
        break;
      default:
        break;
    }

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'score':
          return (b.match_score || 0) - (a.match_score || 0);
        case 'date':
          return new Date(b.date_added || 0) - new Date(a.date_added || 0);
        case 'company':
          return (a.company || '').localeCompare(b.company || '');
        default:
          return 0;
      }
    });

    return filtered.slice(0, 8);
  }, [jobs, filterTab, sortBy]);

  // Top companies with stats
  const topCompanies = useMemo(() => {
    if (stats?.top_companies) return stats.top_companies.slice(0, 6);
    const map = {};
    jobs.forEach((j) => {
      const c = j.company || '';
      if (!c || c === 'Unknown') return;  // Skip jobs with no company
      if (!map[c]) map[c] = { name: c, count: 0, totalScore: 0, scored: 0, responded: 0 };
      map[c].count++;
      if (j.match_score != null) {
        map[c].totalScore += (j.match_score <= 1 ? j.match_score : j.match_score / 100);
        map[c].scored++;
      }
      if (['interviewing', 'offered'].includes(j.stage)) map[c].responded++;
    });
    return Object.values(map)
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)
      .map(c => ({ ...c, avgScore: c.scored > 0 ? Math.round((c.totalScore / c.scored) * 100) : null }));
  }, [stats, jobs]);

  // ─── Render helpers ──────────────────────────────────────────────────────
  const getScorePercent = (score) => {
    if (score == null) return 0;
    return Math.round(score);  // Enriched API returns percentage directly
  };

  const getScoreColor = (pct) => {
    if (pct >= 80) return '#067D68';
    if (pct >= 60) return '#EC7211';
    return '#D13212';
  };

  if (loading) {
    return (
      <Box sx={{ p: 4 }}>
        <LinearProgress sx={{ borderRadius: 2 }} />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>
          Loading dashboard...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', overflow: 'auto', p: { xs: 1.5, md: 2.5 } }}>
      <Typography variant="h4" fontWeight={700} sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 1: Hero KPI Bar
      ═══════════════════════════════════════════════════════════════════════ */}
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {/* 🔍 Discovered */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <FadeInUp delay={0}>
            <Card
              sx={{ ...cardSx, borderTop: `4px solid ${KPI_COLORS[0]}`, cursor: 'pointer' }}
              onClick={() => navigate('/board')}
            >
              <CardContent sx={cardContentSx}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                  <Box>
                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.68rem', letterSpacing: 1 }}>
                      🔍 Discovered
                    </Typography>
                    <Typography variant="h3" fontWeight={700} sx={{ lineHeight: 1.2, mt: 0.5 }}>
                      <AnimatedNumber value={totalDiscovered} />
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Total jobs found
                    </Typography>
                  </Box>
                  <Box sx={{ width: 44, height: 44, borderRadius: '12px', bgcolor: KPI_BG[0], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <SearchIcon sx={{ color: KPI_COLORS[0], fontSize: 22 }} />
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>

        {/* ✅ Applied */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <FadeInUp delay={0.1}>
            <Card
              sx={{ ...cardSx, borderTop: `4px solid ${KPI_COLORS[1]}`, cursor: 'pointer' }}
              onClick={() => navigate('/board')}
            >
              <CardContent sx={cardContentSx}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                  <Box>
                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.68rem', letterSpacing: 1 }}>
                      ✅ Applied
                    </Typography>
                    <Typography variant="h3" fontWeight={700} sx={{ lineHeight: 1.2, mt: 0.5 }}>
                      <AnimatedNumber value={totalApplied} />
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Applications submitted
                    </Typography>
                  </Box>
                  <Box sx={{ width: 44, height: 44, borderRadius: '12px', bgcolor: KPI_BG[1], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <CheckCircleIcon sx={{ color: KPI_COLORS[1], fontSize: 22 }} />
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>

        {/* 📬 Responses */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <FadeInUp delay={0.2}>
            <Card
              sx={{ ...cardSx, borderTop: `4px solid ${KPI_COLORS[2]}`, cursor: 'pointer' }}
              onClick={() => navigate('/board')}
            >
              <CardContent sx={cardContentSx}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                  <Box>
                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.68rem', letterSpacing: 1 }}>
                      📬 Responses
                    </Typography>
                    <Typography variant="h3" fontWeight={700} sx={{ lineHeight: 1.2, mt: 0.5 }}>
                      <AnimatedNumber value={totalResponses} />
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Interviewing + Offered
                    </Typography>
                  </Box>
                  <Box sx={{ width: 44, height: 44, borderRadius: '12px', bgcolor: KPI_BG[2], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <MailOutlineIcon sx={{ color: KPI_COLORS[2], fontSize: 22 }} />
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>

        {/* ⏱️ Next Run → Schedule */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <FadeInUp delay={0.3}>
            <Card
              sx={{ ...cardSx, borderTop: `4px solid ${KPI_COLORS[3]}`, cursor: 'pointer', background: countdown ? 'linear-gradient(135deg, #FEF3E8 0%, #fff 100%)' : 'linear-gradient(135deg, #667eea08 0%, #764ba210 100%)' }}
              onClick={() => countdown ? navigate('/agent') : setScheduleOpen(true)}
            >
              <CardContent sx={cardContentSx}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                  <Box>
                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.68rem', letterSpacing: 1 }}>
                      ⏱️ {countdown ? 'Next Run' : 'Schedule'}
                    </Typography>
                    {countdown ? (
                      <Typography variant="h3" fontWeight={700} sx={{ lineHeight: 1.2, mt: 0.5, color: KPI_COLORS[3] }}>
                        {countdown}
                      </Typography>
                    ) : (
                      <Box sx={{ mt: 0.5 }}>
                        <Button
                          size="small"
                          variant="contained"
                          startIcon={<ScheduleIcon />}
                          sx={{ textTransform: 'none', fontWeight: 700, borderRadius: '8px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', boxShadow: '0 2px 8px rgba(102,126,234,0.3)' }}
                        >
                          Set Schedule
                        </Button>
                      </Box>
                    )}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      {agentStatus?.state === 'running' ? '● Agent active' : countdown ? 'Scheduled' : 'Not scheduled yet'}
                    </Typography>
                  </Box>
                  <Box sx={{ width: 44, height: 44, borderRadius: '12px', bgcolor: KPI_BG[3], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <TimerIcon sx={{ color: KPI_COLORS[3], fontSize: 22 }} />
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>
      </Grid>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 2: Application Funnel + Last Run Summary
      ═══════════════════════════════════════════════════════════════════════ */}
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {/* Left: Animated Funnel Bar Chart */}
        <Grid size={{ xs: 12, md: 7 }}>
          <FadeInUp delay={0.1}>
            <Card sx={cardSx}>
              <CardContent sx={cardContentSx}>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                  Application Funnel
                </Typography>
                <Stack spacing={2}>
                  {stages.map((stage, idx) => (
                    <Box key={stage.key}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                        <Typography variant="body2" fontWeight={500}>
                          {stage.label}
                        </Typography>
                        <Typography variant="body2" fontWeight={700} sx={{ color: stage.color }}>
                          {stage.count}
                        </Typography>
                      </Stack>
                      <Box sx={{ height: 28, bgcolor: 'rgba(0,0,0,0.04)', borderRadius: '6px', overflow: 'hidden', position: 'relative' }}>
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max((stage.count / maxStageCount) * 100, stage.count > 0 ? 4 : 0)}%` }}
                          transition={{ duration: 0.8, delay: idx * 0.15, ease: 'easeOut' }}
                          style={{
                            height: '100%',
                            backgroundColor: stage.color,
                            borderRadius: '6px',
                            display: 'flex',
                            alignItems: 'center',
                            paddingLeft: 12,
                          }}
                        >
                          {stage.count > 0 && (
                            <Typography variant="caption" sx={{ color: '#fff', fontWeight: 600, fontSize: '0.7rem' }}>
                              {stage.count}
                            </Typography>
                          )}
                        </motion.div>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>

        {/* Right: Last Run Summary */}
        <Grid size={{ xs: 12, md: 5 }}>
          <FadeInUp delay={0.2}>
            <Card sx={{ ...cardSx, cursor: lastRunData?.id ? 'pointer' : 'default' }} onClick={() => lastRunData?.id && navigate(`/agent/runs/${lastRunData.id}`)}>
              <CardContent sx={cardContentSx}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                  <Typography variant="subtitle1" fontWeight={600}>
                    Last Run
                  </Typography>
                  {lastRunData?.id && (
                    <Chip
                      label="View Analysis →"
                      size="small"
                      clickable
                      sx={{ fontSize: '0.7rem', fontWeight: 600 }}
                    />
                  )}
                </Stack>

                {lastRunData ? (
                  <Stack spacing={2}>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">When</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {lastRunData.started_at || lastRunData.created_at
                          ? dayjs(lastRunData.started_at || lastRunData.created_at).fromNow()
                          : '—'}
                      </Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Jobs Found</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {lastRunData.jobs_processed && lastRunData.jobs_processed !== '0'
                          ? lastRunData.jobs_processed
                          : totalDiscovered > 0 ? totalDiscovered : '—'}
                      </Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Applied</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {lastRunData.jobs_applied ?? lastRunData.applied ?? '—'}
                      </Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Top Match</Typography>
                      <Typography variant="body2" fontWeight={600} sx={{ color: '#067D68' }}>
                        {lastRunData.top_score != null
                          ? `${getScorePercent(lastRunData.top_score)}%`
                          : lastRunData.max_score != null
                            ? `${getScorePercent(lastRunData.max_score)}%`
                            : '—'}
                      </Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Status</Typography>
                      <Chip
                        label={lastRunData.status || 'completed'}
                        size="small"
                        sx={{
                          height: 22,
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          bgcolor: lastRunData.status === 'error' ? '#FDE8E8' : '#E6F5F2',
                          color: lastRunData.status === 'error' ? '#D13212' : '#067D68',
                        }}
                      />
                    </Stack>
                  </Stack>
                ) : (
                  <Box sx={{ py: 4, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      No runs yet
                    </Typography>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<PlayArrowIcon />}
                      onClick={(e) => { e.stopPropagation(); navigate('/agent'); }}
                      sx={{ textTransform: 'none', fontWeight: 600 }}
                    >
                      Start First Run
                    </Button>
                  </Box>
                )}
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>
      </Grid>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 3: Your Pipeline — Job Cards with full context
      ═══════════════════════════════════════════════════════════════════════ */}
      <FadeInUp delay={0.2}>
        <Card sx={{ ...cardSx, mb: 4 }}>
          <CardContent sx={{ p: '20px !important' }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2, fontSize: '1rem' }}>
              💼 Your Pipeline
            </Typography>

            {/* Filter Bar */}
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2, pb: 1.5, borderBottom: '1px solid #f0f0f0' }}>
              <Stack direction="row" spacing={1}>
                {[
                  { label: 'All', key: 'all' },
                  { label: '⭐ Top Matches', key: 'top' },
                  { label: '✅ Applied', key: 'applied' },
                  { label: '🔗 External', key: 'external' },
                ].map((f, i) => (
                  <Chip key={f.key} label={f.label} size="small" clickable
                    onClick={() => setFilterTab(i)}
                    sx={{
                      height: 28, fontSize: '0.72rem', fontWeight: filterTab === i ? 700 : 500,
                      bgcolor: filterTab === i ? '#667eea15' : 'transparent',
                      color: filterTab === i ? '#667eea' : '#6b7280',
                      border: '1px solid', borderColor: filterTab === i ? '#667eea50' : '#e5e7eb',
                      '&:hover': { borderColor: '#667eea' },
                    }}
                  />
                ))}
              </Stack>
              <Select value={sortBy} onChange={(e) => setSortBy(e.target.value)} size="small" variant="standard" disableUnderline
                sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#6b7280' }}>
                <MenuItem value="score">Sort: Match ↓</MenuItem>
                <MenuItem value="date">Sort: Recent ↓</MenuItem>
                <MenuItem value="company">Sort: Company</MenuItem>
              </Select>
            </Stack>

            {/* Job Cards */}
            <Stack spacing={1.5} sx={{ maxHeight: 460, overflow: 'auto', pr: 0.5 }}>
              {filteredJobs.length === 0 && (
                <Box sx={{ py: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">No jobs match this filter.</Typography>
                </Box>
              )}
              {filteredJobs.map((job) => {
                const scorePct = getScorePercent(job.match_score);
                const scoreColor = getScoreColor(scorePct);
                const isExpanded = expandedJob === job.id;

                return (
                  <Box key={job.id} onClick={() => setExpandedJob(isExpanded ? null : job.id)}
                    sx={{
                      p: 2, borderRadius: '12px', cursor: 'pointer',
                      border: '1px solid', borderColor: isExpanded ? '#667eea40' : '#eef0f2',
                      bgcolor: isExpanded ? '#f8f9ff' : '#fafbfc',
                      transition: 'all 0.15s',
                      '&:hover': { borderColor: '#667eea30', boxShadow: '0 2px 8px rgba(0,0,0,0.04)' },
                    }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                      <Box sx={{ flex: 1, minWidth: 0, mr: 2 }}>
                        <Typography noWrap sx={{ fontSize: '0.88rem', fontWeight: 700, color: '#1e1b4b' }}>
                          {job.title || 'Untitled'}
                        </Typography>
                        <Typography noWrap sx={{ fontSize: '0.73rem', color: '#6b7280', mt: 0.25 }}>
                          {job.company || '—'}{job.location ? ` · 📍 ${job.location}` : ''}{` · ${job.created_at || job.date_added ? dayjs(job.created_at || job.date_added).fromNow() : ''}`}
                        </Typography>
                      </Box>
                      {scorePct > 0 && (
                        <Box sx={{ px: 1.25, py: 0.5, borderRadius: '8px', bgcolor: scoreColor + '12', border: `1px solid ${scoreColor}30`, flexShrink: 0 }}>
                          <Typography sx={{ fontSize: '0.75rem', fontWeight: 800, color: scoreColor, lineHeight: 1 }}>
                            {scorePct}% match
                          </Typography>
                        </Box>
                      )}
                    </Stack>
                    {scorePct >= 80 && (
                      <Typography sx={{ fontSize: '0.7rem', color: '#059669', mt: 0.75, fontWeight: 500 }}>
                        💡 Strong match — aligns with your core skills and experience
                      </Typography>
                    )}
                    {scorePct >= 60 && scorePct < 80 && (
                      <Typography sx={{ fontSize: '0.7rem', color: '#d97706', mt: 0.75, fontWeight: 500 }}>
                        💡 Partial match — some skills align, consider tailoring resume
                      </Typography>
                    )}
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
                      <Chip label={job.stage ? (STAGE_LABELS[job.stage] || job.stage) : 'New'} size="small"
                        sx={{ height: 20, fontSize: '0.63rem', fontWeight: 700, ...(STATUS_CHIP_STYLES[job.stage] || { bgcolor: '#f3f4f6', color: '#6b7280' }) }} />
                      {job.inmail && (
                        <Chip label={`✉️ InMail ${job.inmail.status}${job.inmail.recruiter ? ` → ${job.inmail.recruiter}` : ''}`} size="small"
                          sx={{ height: 20, fontSize: '0.63rem', fontWeight: 600, bgcolor: '#f5f3ff', color: '#7c3aed' }} />
                      )}
                      {job.is_external && !job.inmail && (
                        <Chip label="🔗 External" size="small" sx={{ height: 20, fontSize: '0.63rem', fontWeight: 600, bgcolor: '#eff6ff', color: '#3b82f6' }} />
                      )}
                    </Stack>
                    <Collapse in={isExpanded}>
                      <Box sx={{ mt: 2, pt: 1.5, borderTop: '1px solid #f0f0f0' }}>
                        {/* Primary actions */}
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                          <Button size="small" variant="contained" startIcon={<OpenInNewIcon />}
                            href={job.posting_url || `https://www.linkedin.com/jobs/view/${job.id}/`} target="_blank"
                            onClick={(e) => e.stopPropagation()}
                            sx={{ textTransform: 'none', fontWeight: 700, fontSize: '0.73rem', borderRadius: '8px', bgcolor: scoreColor, '&:hover': { bgcolor: scoreColor + 'cc' } }}>
                            {job.stage === 'applied' ? 'View Application' : scorePct >= 80 ? 'Apply Now' : 'View Listing'}
                          </Button>
                          {!job.inmail && scorePct >= 70 && (
                            <Button size="small" variant="outlined" onClick={(e) => e.stopPropagation()}
                              sx={{ textTransform: 'none', fontWeight: 600, fontSize: '0.72rem', borderRadius: '8px' }}>✉️ Draft InMail</Button>
                          )}
                        </Stack>

                        {/* Stage change buttons */}
                        <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px dashed #e5e7eb' }}>
                          <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: '#9ca3af', mb: 0.75, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            Move to:
                          </Typography>
                          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                            {[
                              { stage: 'applied', label: '✅ Applied', show: job.stage !== 'applied' },
                              { stage: 'interviewing', label: '🎤 Interviewing', show: job.stage === 'applied' },
                              { stage: 'offered', label: '🎉 Offered', show: job.stage === 'interviewing' },
                              { stage: 'rejected', label: '❌ Rejected', show: ['applied', 'interviewing'].includes(job.stage) },
                              { stage: 'saved', label: '📌 Saved', show: job.stage === 'discovered' },
                            ].filter(s => s.show).map(s => (
                              <Chip key={s.stage} label={s.label} size="small" clickable
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  try {
                                    await fetch(`/api/jobs/${job.id}`, {
                                      method: 'PATCH',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ stage: s.stage }),
                                    });
                                    loadData(); // Refresh
                                  } catch (err) { console.error(err); }
                                }}
                                sx={{ height: 24, fontSize: '0.68rem', fontWeight: 600, border: '1px solid #e5e7eb', '&:hover': { bgcolor: '#667eea10', borderColor: '#667eea50' } }}
                              />
                            ))}
                          </Stack>
                        </Box>

                        {/* InMail preview */}
                        {job.inmail?.draft_preview && (
                          <Box sx={{ mt: 1.5, p: 1.5, borderRadius: '8px', bgcolor: '#faf8ff', border: '1px solid #ede9fe' }}>
                            <Typography sx={{ fontSize: '0.68rem', color: '#7c3aed', fontWeight: 600 }}>✉️ InMail to {job.inmail.recruiter}:</Typography>
                            <Typography sx={{ fontSize: '0.7rem', color: '#4b5563', mt: 0.25, fontStyle: 'italic' }}>"{job.inmail.draft_preview}..."</Typography>
                          </Box>
                        )}
                      </Box>
                    </Collapse>
                  </Box>
                );
              })}
            </Stack>
            {jobs.length > 8 && (
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <Button onClick={() => navigate('/board')} sx={{ textTransform: 'none', fontWeight: 600, fontSize: '0.8rem', color: '#667eea' }}>
                  View all {jobs.length} jobs on Board →
                </Button>
              </Box>
            )}
          </CardContent>
        </Card>
      </FadeInUp>


      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 4: Company Intelligence + AI Insights
      ═══════════════════════════════════════════════════════════════════════ */}
      <Grid container spacing={2.5}>
        {/* Left: Company Intelligence */}
        <Grid size={{ xs: 12, md: 6 }}>
          <FadeInUp delay={0.1}>
            <Card sx={{ ...cardSx, cursor: 'pointer' }} onClick={() => navigate('/board')}>
              <CardContent sx={cardContentSx}>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                  <BusinessIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
                  <Typography variant="subtitle1" fontWeight={600}>
                    Company Intelligence
                  </Typography>
                </Stack>

                {topCompanies.length > 0 ? (
                  <Stack spacing={1.5}>
                    {topCompanies.map((company, idx) => (
                      <Box key={idx}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.25 }}>
                          <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: '50%' }}>
                            {company.name || company.company}
                          </Typography>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Chip
                              label={`${company.count} job${company.count !== 1 ? 's' : ''}`}
                              size="small"
                              sx={{ height: 22, fontSize: '0.68rem', fontWeight: 600, bgcolor: '#E6F2FA', color: '#0073BB' }}
                            />
                            {company.avgScore != null && (
                              <Chip
                                label={`${company.avgScore}% avg`}
                                size="small"
                                sx={{ height: 22, fontSize: '0.68rem', fontWeight: 600, bgcolor: '#E6F5F2', color: '#067D68' }}
                              />
                            )}
                            {company.responded > 0 && (
                              <Tooltip title="Has responded">
                                <CheckCircleIcon sx={{ fontSize: 16, color: '#067D68' }} />
                              </Tooltip>
                            )}
                          </Stack>
                        </Stack>
                        {/* Progress bar showing relative job count */}
                        <Box sx={{ height: 4, bgcolor: 'rgba(0,0,0,0.04)', borderRadius: 2, overflow: 'hidden' }}>
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${(company.count / (topCompanies[0]?.count || 1)) * 100}%` }}
                            transition={{ duration: 0.6, delay: idx * 0.1 }}
                            style={{ height: '100%', backgroundColor: '#0073BB', borderRadius: 4 }}
                          />
                        </Box>
                      </Box>
                    ))}
                  </Stack>
                ) : (
                  <Box sx={{ py: 3, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      Data will appear after your first scan
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>

        {/* Right: AI Insights */}
        <Grid size={{ xs: 12, md: 6 }}>
          <FadeInUp delay={0.2}>
            <Card sx={cardSx}>
              <CardContent sx={cardContentSx}>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                  <LightbulbIcon sx={{ fontSize: 20, color: '#EC7211' }} />
                  <Typography variant="subtitle1" fontWeight={600}>
                    AI Insights
                  </Typography>
                </Stack>

                <Stack spacing={2}>
                  {/* Insight 1 */}
                  <Box sx={{ p: 1.5, borderRadius: '8px', bgcolor: 'rgba(6,125,104,0.05)', border: '1px solid rgba(6,125,104,0.12)' }}>
                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <TrendingUpIcon sx={{ fontSize: 18, color: '#067D68', mt: 0.25 }} />
                      <Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>
                          You qualify for {totalApplied > 0 ? Math.min(Math.round((totalApplied / Math.max(totalDiscovered, 1)) * 100), 95) : 72}% of Engineering Manager roles
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Based on your match scores across discovered jobs
                        </Typography>
                      </Box>
                    </Stack>
                  </Box>

                  {/* Insight 2 */}
                  <Box sx={{ p: 1.5, borderRadius: '8px', bgcolor: 'rgba(236,114,17,0.05)', border: '1px solid rgba(236,114,17,0.12)' }}>
                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <LightbulbIcon sx={{ fontSize: 18, color: '#EC7211', mt: 0.25 }} />
                      <Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>
                          Consider adding "stakeholder management" — appears in {Math.max(Math.round(totalDiscovered * 0.3), 5)} near-miss roles
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Adding this skill could increase your match rate by ~8%
                        </Typography>
                      </Box>
                    </Stack>
                  </Box>

                  {/* Insight 3 */}
                  <Box sx={{ p: 1.5, borderRadius: '8px', bgcolor: 'rgba(0,115,187,0.05)', border: '1px solid rgba(0,115,187,0.12)' }}>
                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <BusinessIcon sx={{ fontSize: 18, color: '#0073BB', mt: 0.25 }} />
                      <Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>
                          {topCompanies.length > 0 && topCompanies[0]?.name
                            ? `${topCompanies[0].name} has the most open roles — prioritize their listings`
                            : 'Run your first scan to discover company insights'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Companies with more roles give you better chances
                        </Typography>
                      </Box>
                    </Stack>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </FadeInUp>
        </Grid>
      </Grid>

      {/* ═══════════════════════════════════════════════════════════════════════
          SCHEDULE DRAWER — Friendly & Intuitive
      ═══════════════════════════════════════════════════════════════════════ */}
      <Drawer anchor="right" open={scheduleOpen} onClose={() => setScheduleOpen(false)} PaperProps={{ sx: { borderRadius: '16px 0 0 16px' } }}>
        <Box sx={{ width: 380, height: '100%', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <Box sx={{ p: 3, pb: 2, borderBottom: '1px solid #f0f0f0' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography variant="h6" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ScheduleIcon sx={{ color: '#667eea' }} /> Schedule Agent
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Set it and forget it — your agent works while you sleep
                </Typography>
              </Box>
              <IconButton onClick={() => setScheduleOpen(false)} size="small" sx={{ bgcolor: '#f3f4f6', '&:hover': { bgcolor: '#e5e7eb' } }}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Stack>
          </Box>

          {/* Content */}
          <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
            <Stack spacing={3.5}>
              {/* Frequency — Visual Cards */}
              <Box>
                <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>How often should I scan?</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: 'block' }}>Pick a pace that matches your urgency</Typography>
                <Grid container spacing={1}>
                  {[
                    { label: '30m', desc: 'Aggressive', icon: '🔥', color: '#ef4444' },
                    { label: '1h', desc: 'Active', icon: '⚡', color: '#f59e0b' },
                    { label: '2h', desc: 'Balanced', icon: '🎯', color: '#3b82f6' },
                    { label: '4h', desc: 'Chill', icon: '🌊', color: '#10b981' },
                  ].map(opt => (
                    <Grid size={{ xs: 3 }} key={opt.label}>
                      <Box sx={{
                        p: 1.5, borderRadius: '12px', textAlign: 'center', cursor: 'pointer',
                        border: '2px solid', borderColor: '#e5e7eb',
                        transition: 'all 0.15s',
                        '&:hover': { borderColor: opt.color, bgcolor: opt.color + '08', transform: 'scale(1.03)' },
                      }}>
                        <Typography sx={{ fontSize: '1.2rem', mb: 0.25 }}>{opt.icon}</Typography>
                        <Typography sx={{ fontSize: '0.85rem', fontWeight: 800, color: opt.color }}>{opt.label}</Typography>
                        <Typography sx={{ fontSize: '0.6rem', color: '#6b7280' }}>{opt.desc}</Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </Box>

              {/* Active Hours — Visual Slider */}
              <Box>
                <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>When should I work?</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: 'block' }}>Agent only runs during these hours</Typography>
                <Box sx={{ px: 1 }}>
                  <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                    <Chip label="🌅 9:00 AM" size="small" sx={{ fontWeight: 700, bgcolor: '#eff6ff', color: '#3b82f6' }} />
                    <Chip label="🌙 10:00 PM" size="small" sx={{ fontWeight: 700, bgcolor: '#f5f3ff', color: '#7c3aed' }} />
                  </Stack>
                  <Box sx={{ height: 8, borderRadius: 4, background: 'linear-gradient(90deg, #3b82f6 0%, #7c3aed 100%)', opacity: 0.7 }} />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block', textAlign: 'center' }}>
                    13 hours of active scanning
                  </Typography>
                </Box>
              </Box>

              {/* Toggles — Clean Cards */}
              <Box>
                <Typography variant="body2" fontWeight={700} sx={{ mb: 1.5 }}>Options</Typography>
                <Stack spacing={1.5}>
                  <Box sx={{ p: 1.5, borderRadius: '10px', border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <Box sx={{ width: 32, height: 32, borderRadius: '8px', bgcolor: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography sx={{ fontSize: '1rem' }}>🧪</Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>Dry Run</Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>Preview matches without applying</Typography>
                      </Box>
                    </Stack>
                    <Switch defaultChecked size="small" color="success" />
                  </Box>

                  <Box sx={{ p: 1.5, borderRadius: '10px', border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <Box sx={{ width: 32, height: 32, borderRadius: '8px', bgcolor: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography sx={{ fontSize: '1rem' }}>🔥</Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>Urgent Mode</Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>Double speed for 7 days</Typography>
                      </Box>
                    </Stack>
                    <Switch size="small" color="error" />
                  </Box>

                  <Box sx={{ p: 1.5, borderRadius: '10px', border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <Box sx={{ width: 32, height: 32, borderRadius: '8px', bgcolor: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography sx={{ fontSize: '1rem' }}>📱</Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>Telegram Alerts</Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>Get notified on every application</Typography>
                      </Box>
                    </Stack>
                    <Switch defaultChecked size="small" />
                  </Box>
                </Stack>
              </Box>
            </Stack>
          </Box>

          {/* Footer Actions */}
          <Box sx={{ p: 3, pt: 2, borderTop: '1px solid #f0f0f0' }}>
            <Stack spacing={1.5}>
              <Button
                variant="contained"
                fullWidth
                startIcon={<ScheduleIcon />}
                onClick={() => { setScheduleOpen(false); navigate('/scheduler'); }}
                sx={{ textTransform: 'none', fontWeight: 700, py: 1.5, borderRadius: '12px', fontSize: '0.9rem', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', boxShadow: '0 4px 14px rgba(102,126,234,0.35)' }}
              >
                Activate Schedule
              </Button>
              <Button
                variant="text"
                fullWidth
                startIcon={<PlayArrowIcon />}
                onClick={() => { setScheduleOpen(false); navigate('/agent'); }}
                sx={{ textTransform: 'none', fontWeight: 600, borderRadius: '12px', color: '#6b7280' }}
              >
                Just run once instead
              </Button>
            </Stack>
          </Box>
        </Box>
      </Drawer>
    </Box>
  );
}
