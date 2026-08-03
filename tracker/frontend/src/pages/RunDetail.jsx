import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Stack,
  Chip,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Tooltip,
  LinearProgress,
  Collapse,
  Avatar,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import BugReportIcon from '@mui/icons-material/BugReport';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import WorkIcon from '@mui/icons-material/Work';
import BusinessIcon from '@mui/icons-material/Business';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SchoolIcon from '@mui/icons-material/School';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import TerminalIcon from '@mui/icons-material/Terminal';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import { useSnackbar } from 'notistack';
import { motion } from 'framer-motion';
import { getRunAnalysis, diagnoseRun, getAgentOutput, getAgentStatus } from '../api';

dayjs.extend(duration);

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatDuration(secs) {
  if (!secs) return '—';
  const s = parseInt(secs);
  if (s >= 3600) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ${s % 60}s`;
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${s}s`;
}

function decisionIcon(decision) {
  switch (decision) {
    case 'applied': case 'would_apply': return <CheckCircleIcon sx={{ color: '#10b981', fontSize: 20 }} />;
    case 'skipped': return <CancelIcon sx={{ color: '#f59e0b', fontSize: 20 }} />;
    case 'external': return <OpenInNewIcon sx={{ color: '#6366f1', fontSize: 20 }} />;
    case 'paused': return <PauseCircleIcon sx={{ color: '#8b5cf6', fontSize: 20 }} />;
    case 'error': return <CancelIcon sx={{ color: '#ef4444', fontSize: 20 }} />;
    default: return <WorkIcon sx={{ color: '#6b7280', fontSize: 20 }} />;
  }
}

function decisionLabel(decision) {
  switch (decision) {
    case 'applied': return 'Applied';
    case 'would_apply': return 'Would Apply';
    case 'skipped': return 'Skipped';
    case 'external': return 'External';
    case 'paused': return 'Paused';
    case 'error': return 'Error';
    default: return 'Evaluating';
  }
}

function decisionColor(decision) {
  switch (decision) {
    case 'applied': case 'would_apply': return '#10b981';
    case 'skipped': return '#f59e0b';
    case 'external': return '#6366f1';
    case 'paused': return '#8b5cf6';
    case 'error': return '#ef4444';
    default: return '#6b7280';
  }
}

function scoreGrade(score) {
  if (score >= 90) return { label: 'Excellent', color: '#10b981' };
  if (score >= 80) return { label: 'Strong', color: '#059669' };
  if (score >= 70) return { label: 'Good', color: '#0891b2' };
  if (score >= 60) return { label: 'Fair', color: '#f59e0b' };
  return { label: 'Low', color: '#ef4444' };
}

function getLogLineColor(line) {
  if (line.match(/error|fail|exception|traceback/i)) return '#f87171';
  if (line.match(/warn/i)) return '#fbbf24';
  if (line.match(/success|applied|done|complete|submitted/i)) return '#4ade80';
  if (line.match(/skip/i)) return '#fb923c';
  if (line.match(/info|scan|score|discover/i)) return '#93c5fd';
  if (line.match(/^\s*─|═|┌|┐|└|┘|│|├|┤/)) return '#6b7280';
  return '#e2e8f0';
}

export default function RunDetail() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pipeline');
  const [expandedJob, setExpandedJob] = useState(null);
  const [showRawLog, setShowRawLog] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosis, setDiagnosis] = useState(null);
  const [liveOutput, setLiveOutput] = useState([]);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await getRunAnalysis(runId);
        setAnalysis(data);
        // If run is still running, switch to live mode
        if (data.status === 'running') {
          setIsLive(true);
          setActiveTab('log'); // Show live log by default for running jobs
        }
      } catch (err) {
        enqueueSnackbar('Failed to load run analysis', { variant: 'error' });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [runId, enqueueSnackbar]);

  // Poll live output when run is still active
  useEffect(() => {
    if (!isLive) return;
    const fetchLive = async () => {
      try {
        const outputData = await getAgentOutput(500);
        const lines = outputData.lines || outputData.output || [];
        setLiveOutput(lines);
        // Also refresh analysis data periodically
        const data = await getRunAnalysis(runId);
        setAnalysis(data);
        if (data.status !== 'running') {
          setIsLive(false); // Run finished, stop polling
        }
      } catch (e) { /* ignore */ }
    };
    fetchLive();
    const iv = setInterval(fetchLive, 2000);
    return () => clearInterval(iv);
  }, [isLive, runId]);

  const handleDiagnose = async () => {
    setDiagnosing(true);
    try {
      const result = await diagnoseRun(runId);
      setDiagnosis(result);
    } catch (err) {
      enqueueSnackbar('Diagnosis failed', { variant: 'error' });
    } finally {
      setDiagnosing(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', p: 4, gap: 2 }}>
        <CircularProgress size={48} />
        <Typography color="text.secondary">Analyzing your run...</Typography>
      </Box>
    );
  }

  if (!analysis) {
    return (
      <Box sx={{ p: 4 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/agent')}>Back to Agent Control</Button>
        <Typography sx={{ mt: 2 }}>Run not found.</Typography>
      </Box>
    );
  }

  const { summary, jobs, companies, sources, phases } = analysis;
  const isDryRun = analysis.dry_run === 'True' || analysis.dry_run === true || analysis.dry_run === 'true';
  const hasJobs = jobs && jobs.length > 0;

  // Use live output when running, fallback to stored log
  const logLines = isLive && liveOutput.length > 0
    ? liveOutput.map(l => typeof l === 'string' ? l : l.text || l.message || JSON.stringify(l)).filter(l => l.trim())
    : (analysis.output_log || '').split('\n').filter(l => l.trim());

  // Generate smart insights
  const insights = generateInsights(analysis);

  const tabs = [
    { id: 'pipeline', label: '🎬 Pipeline' },
    { id: 'overview', label: '📊 Overview' },
    { id: 'jobs', label: `💼 Jobs (${jobs?.length || 0})` },
    { id: 'insights', label: '💡 Insights' },
    { id: 'log', label: isLive ? '🔴 Live Log' : '🖥️ Raw Log' },
  ];

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      {/* Header */}
      <HeaderSection analysis={analysis} isDryRun={isDryRun} navigate={navigate} />

      {/* Live Banner */}
      {isLive && (
        <Box sx={{
          mb: 2, p: 2, borderRadius: '12px',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: '#fff', display: 'flex', alignItems: 'center', gap: 2,
          animation: 'pulse 2s ease-in-out infinite',
          '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.85 } },
        }}>
          <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#ff4444', boxShadow: '0 0 8px #ff4444', animation: 'blink 1s step-end infinite', '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } } }} />
          <Typography variant="body2" fontWeight={700}>
            ⚡ This run is LIVE — output is streaming in real-time
          </Typography>
          <Typography variant="caption" sx={{ ml: 'auto', opacity: 0.8 }}>
            {logLines.length} lines captured
          </Typography>
        </Box>
      )}

      {/* Tab Navigation */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <Chip
            key={t.id}
            label={t.label}
            clickable
            onClick={() => setActiveTab(t.id)}
            sx={{
              fontWeight: 600, fontSize: '0.9rem', height: 36, px: 1.5,
              bgcolor: activeTab === t.id ? 'primary.main' : 'transparent',
              color: activeTab === t.id ? '#fff' : 'text.secondary',
              border: activeTab === t.id ? 'none' : '1px solid',
              borderColor: 'divider',
              '&:hover': { bgcolor: activeTab === t.id ? 'primary.dark' : 'action.hover' },
            }}
          />
        ))}
      </Box>

      {/* Tab Content */}
      {activeTab === 'pipeline' && (
        <PipelineTab steps={analysis.steps || []} analysis={analysis} />
      )}

      {activeTab === 'overview' && (
        <OverviewTab
          analysis={analysis}
          summary={summary}
          companies={companies}
          sources={sources}
          phases={phases}
          isDryRun={isDryRun}
          insights={insights}
        />
      )}

      {activeTab === 'jobs' && (
        <JobsTab
          jobs={jobs}
          hasJobs={hasJobs}
          expandedJob={expandedJob}
          setExpandedJob={setExpandedJob}
          threshold={analysis.match_threshold}
        />
      )}

      {activeTab === 'insights' && (
        <InsightsTab
          insights={insights}
          analysis={analysis}
          diagnosis={diagnosis}
          diagnosing={diagnosing}
          handleDiagnose={handleDiagnose}
        />
      )}

      {activeTab === 'log' && (
        <LogTab logLines={logLines} output_log={analysis.output_log} enqueueSnackbar={enqueueSnackbar} isLive={isLive} />
      )}
    </Box>
  );
}


// ─── Header Section ─────────────────────────────────────────────────────────

function HeaderSection({ analysis, isDryRun, navigate }) {
  const statusColors = { completed: '#10b981', failed: '#ef4444', running: '#3b82f6', stopped: '#f59e0b' };
  const statusBg = { completed: '#ecfdf5', failed: '#fef2f2', running: '#eff6ff', stopped: '#fffbeb' };

  return (
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <Box sx={{ mb: 3 }}>
        {/* Breadcrumb back navigation */}
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/agent')}
            sx={{ textTransform: 'none', fontWeight: 600, color: 'text.secondary', px: 1.5, borderRadius: '8px', '&:hover': { bgcolor: '#f3f4f6' } }}
          >
            Agent Control
          </Button>
          <Typography color="text.secondary" sx={{ fontSize: '0.9rem' }}>/</Typography>
          <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>Run Analysis</Typography>
        </Box>

        <Stack direction="row" alignItems="center" spacing={2}>
          <Box sx={{ flex: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <RocketLaunchIcon sx={{ color: 'primary.main', fontSize: 28 }} />
              <Typography variant="h4" sx={{ fontWeight: 800, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Run Analysis
              </Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {analysis.started_at ? dayjs(analysis.started_at).format('MMMM D, YYYY [at] h:mm A') : '—'}
              {analysis.duration_seconds ? ` · ${formatDuration(analysis.duration_seconds)}` : ''}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Chip
              label={analysis.status || 'unknown'}
              sx={{ fontWeight: 700, bgcolor: statusBg[analysis.status] || '#f3f4f6', color: statusColors[analysis.status] || '#6b7280', border: `1px solid ${statusColors[analysis.status] || '#d1d5db'}` }}
            />
            {isDryRun && <Chip label="🧪 Dry Run" sx={{ fontWeight: 600, bgcolor: '#eff6ff', color: '#3b82f6', border: '1px solid #93c5fd' }} />}
            <Chip label={analysis.mode || 'single'} variant="outlined" sx={{ fontWeight: 600, textTransform: 'capitalize' }} />
          </Stack>
        </Stack>
      </Box>
    </motion.div>
  );
}

// ─── Overview Tab ───────────────────────────────────────────────────────────

function OverviewTab({ analysis, summary, companies, sources, phases, isDryRun, insights }) {
  const companyList = Object.entries(companies || {}).sort((a, b) => b[1].total - a[1].total).slice(0, 8);

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      {/* Executive Summary Banner */}
      <Card sx={{ mb: 3, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: '#fff', border: 'none' }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>
            {summary?.jobs_evaluated === 0
              ? "🔍 No jobs were evaluated in this run"
              : isDryRun
                ? `🧪 Preview: ${summary?.applied || 0} job${summary?.applied !== 1 ? 's' : ''} would be applied to`
                : `✅ ${summary?.applied || 0} application${summary?.applied !== 1 ? 's' : ''} submitted this run`
            }
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.9 }}>
            {summary?.total_discovered > 0
              ? `Discovered ${summary.total_discovered} jobs → Evaluated ${summary.jobs_evaluated} → ${summary.applied || 0} qualified`
              : "The agent completed its scan cycle. Check your settings if no jobs were found."
            }
          </Typography>
          {summary?.avg_score && (
            <Typography variant="body2" sx={{ mt: 1, opacity: 0.85 }}>
              Average match score: {summary.avg_score}% · Top score: {summary.top_score}%
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Key Metrics */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { label: 'Discovered', value: summary?.total_discovered || 0, icon: '🔍', color: '#6366f1', desc: 'Jobs found on LinkedIn' },
          { label: isDryRun ? 'Would Apply' : 'Applied', value: summary?.applied || 0, icon: '✅', color: '#10b981', desc: isDryRun ? 'Meets your criteria' : 'Applications sent' },
          { label: 'Skipped', value: summary?.skipped || 0, icon: '⏭️', color: '#f59e0b', desc: 'Below your threshold' },
          { label: 'External', value: summary?.external || 0, icon: '🔗', color: '#8b5cf6', desc: 'Needs manual apply' },
        ].map((metric, idx) => (
          <Grid item xs={6} md={3} key={idx}>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.05 }}>
              <Card variant="outlined" sx={{ height: '100%', borderLeft: `4px solid ${metric.color}` }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Typography sx={{ fontSize: '1.5rem', mb: 0.5 }}>{metric.icon}</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: metric.color }}>{metric.value}</Typography>
                  <Typography variant="body2" fontWeight={600}>{metric.label}</Typography>
                  <Typography variant="caption" color="text.secondary">{metric.desc}</Typography>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
        ))}
      </Grid>

      {/* Pipeline Timeline + Companies side by side */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {/* Pipeline Phases */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <RocketLaunchIcon sx={{ fontSize: 18, color: 'primary.main' }} /> Pipeline Timeline
              </Typography>
              {phases && phases.length > 0 ? (
                <Stack spacing={1}>
                  {phases.map((phase, idx) => (
                    <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#10b981', flexShrink: 0 }} />
                      <Box sx={{ flex: 1, borderBottom: '1px dashed', borderColor: 'divider', pb: 0.5 }}>
                        <Typography variant="body2" fontWeight={600}>{phase.label}</Typography>
                        {phase.detail && <Typography variant="caption" color="text.secondary">{phase.detail}</Typography>}
                      </Box>
                    </Box>
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary">No pipeline phases detected</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Companies Breakdown */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <BusinessIcon sx={{ fontSize: 18, color: '#6366f1' }} /> Companies
              </Typography>
              {companyList.length > 0 ? (
                <Stack spacing={1}>
                  {companyList.map(([name, data], idx) => (
                    <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <Avatar sx={{ width: 28, height: 28, fontSize: '0.7rem', bgcolor: `hsl(${idx * 40}, 60%, 50%)` }}>
                        {name.charAt(0)}
                      </Avatar>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" fontWeight={600} noWrap>{name}</Typography>
                      </Box>
                      <Stack direction="row" spacing={0.5}>
                        {data.applied > 0 && <Chip label={`${data.applied} ✓`} size="small" sx={{ height: 20, fontSize: '0.7rem', bgcolor: '#ecfdf5', color: '#059669' }} />}
                        {data.skipped > 0 && <Chip label={`${data.skipped} ✗`} size="small" sx={{ height: 20, fontSize: '0.7rem', bgcolor: '#fffbeb', color: '#d97706' }} />}
                        {data.external > 0 && <Chip label={`${data.external} 🔗`} size="small" sx={{ height: 20, fontSize: '0.7rem', bgcolor: '#f5f3ff', color: '#7c3aed' }} />}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary">No companies processed yet</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Search Sources */}
      {sources && sources.length > 0 && (
        <Card variant="outlined" sx={{ mb: 3 }}>
          <CardContent sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>🌐 Search Sources</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {sources.map((s, idx) => (
                <Chip key={idx} label={`${s.source}: ${s.count} jobs`} size="small" variant="outlined" sx={{ fontWeight: 500 }} />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      {/* Quick Insight */}
      {insights.length > 0 && (
        <Card sx={{ bgcolor: '#fffbeb', border: '1px solid #fde68a' }}>
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <TipsAndUpdatesIcon sx={{ color: '#f59e0b', mt: 0.25 }} />
              <Box>
                <Typography variant="body2" fontWeight={700}>Quick Insight</Typography>
                <Typography variant="body2" color="text.secondary">{insights[0]?.message}</Typography>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}

// ─── Jobs Tab ───────────────────────────────────────────────────────────────

function JobsTab({ jobs, hasJobs, expandedJob, setExpandedJob, threshold }) {
  if (!hasJobs) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Card variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <WorkIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
          <Typography variant="h6" color="text.secondary">No Jobs Evaluated</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            This run didn't evaluate individual jobs. This could happen if no jobs matched your search criteria, or the run was stopped early.
          </Typography>
        </Card>
      </motion.div>
    );
  }

  const applied = jobs.filter(j => j.decision === 'applied' || j.decision === 'would_apply');
  const skipped = jobs.filter(j => j.decision === 'skipped');
  const others = jobs.filter(j => !['applied', 'would_apply', 'skipped'].includes(j.decision));

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Summary bar */}
      <Box sx={{ mb: 2, p: 2, borderRadius: '12px', bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
        <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="body2" fontWeight={600}>{jobs.length} jobs evaluated</Typography>
          <Chip label={`${applied.length} qualified`} size="small" sx={{ bgcolor: '#ecfdf5', color: '#059669', fontWeight: 600 }} />
          <Chip label={`${skipped.length} skipped`} size="small" sx={{ bgcolor: '#fffbeb', color: '#d97706', fontWeight: 600 }} />
          {others.length > 0 && <Chip label={`${others.length} other`} size="small" variant="outlined" sx={{ fontWeight: 600 }} />}
        </Stack>
      </Box>

      {/* Job Cards */}
      <Stack spacing={1}>
        {jobs.map((job, idx) => {
          const isExpanded = expandedJob === idx;
          const scorePercent = job.score !== null ? Math.round(job.score * 100) : null;
          const grade = scorePercent !== null ? scoreGrade(scorePercent) : null;

          return (
            <motion.div key={idx} initial={{ opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.02 }}>
              <Card
                variant="outlined"
                onClick={() => setExpandedJob(isExpanded ? null : idx)}
                sx={{
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  borderLeft: `4px solid ${decisionColor(job.decision)}`,
                  '&:hover': { boxShadow: '0 2px 8px rgba(0,0,0,0.08)', transform: 'translateX(2px)' },
                }}
              >
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Stack direction="row" alignItems="center" spacing={1.5}>
                    {decisionIcon(job.decision)}
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" fontWeight={700} noWrap>{job.title}</Typography>
                      <Typography variant="caption" color="text.secondary">{job.company}</Typography>
                    </Box>
                    {scorePercent !== null && (
                      <Tooltip title={`Match: ${scorePercent}% ${grade ? `(${grade.label})` : ''}`}>
                        <Chip
                          label={`${scorePercent}%`}
                          size="small"
                          sx={{ fontWeight: 700, fontFamily: 'monospace', bgcolor: `${grade?.color}15`, color: grade?.color, border: `1px solid ${grade?.color}40` }}
                        />
                      </Tooltip>
                    )}
                    <Chip label={decisionLabel(job.decision)} size="small" sx={{ fontWeight: 600, bgcolor: `${decisionColor(job.decision)}15`, color: decisionColor(job.decision), fontSize: '0.7rem' }} />
                    <ExpandMoreIcon sx={{ fontSize: 18, transform: isExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s', color: 'text.secondary' }} />
                  </Stack>

                  <Collapse in={isExpanded}>
                    <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                      {job.reason && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          <strong>Reason:</strong> {job.reason}
                        </Typography>
                      )}
                      {job.score_method && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          <strong>Scoring:</strong> {job.score_method === 'premium' ? 'LinkedIn Premium AI' : 'Keyword Matching (Fallback)'}
                        </Typography>
                      )}
                      {job.external_url && (
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          <strong>Apply Link:</strong>{' '}
                          <a href={job.external_url} target="_blank" rel="noopener noreferrer" style={{ color: '#6366f1' }}>
                            {job.external_url.length > 60 ? job.external_url.slice(0, 60) + '...' : job.external_url}
                          </a>
                        </Typography>
                      )}
                      {job.events && job.events.length > 0 && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption" fontWeight={600} color="text.secondary">Event Timeline:</Typography>
                          <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                            {job.events.map((ev, evIdx) => (
                              <Typography key={evIdx} variant="caption" sx={{ pl: 1, borderLeft: '2px solid', borderColor: 'divider', color: 'text.secondary' }}>
                                {ev.detail}
                              </Typography>
                            ))}
                          </Stack>
                        </Box>
                      )}
                    </Box>
                  </Collapse>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </Stack>
    </motion.div>
  );
}

// ─── Insights Tab ───────────────────────────────────────────────────────────

function InsightsTab({ insights, analysis, diagnosis, diagnosing, handleDiagnose }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* AI Insights */}
      <Card sx={{ mb: 3, border: '1px solid', borderColor: '#fde68a', bgcolor: '#fffdf5' }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
            <TipsAndUpdatesIcon sx={{ color: '#f59e0b', fontSize: 24 }} />
            <Typography variant="h6" fontWeight={700}>Smart Insights</Typography>
          </Stack>
          {insights.length > 0 ? (
            <Stack spacing={2}>
              {insights.map((insight, idx) => (
                <motion.div key={idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.1 }}>
                  <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                    <Typography sx={{ fontSize: '1.2rem' }}>{insight.icon}</Typography>
                    <Box>
                      <Typography variant="body2" fontWeight={700}>{insight.title}</Typography>
                      <Typography variant="body2" color="text.secondary">{insight.message}</Typography>
                    </Box>
                  </Box>
                </motion.div>
              ))}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">Run more jobs to unlock insights about your job search patterns.</Typography>
          )}
        </CardContent>
      </Card>

      {/* Actionable Next Steps */}
      <Card sx={{ mb: 3, border: '1px solid', borderColor: '#a5f3fc', bgcolor: '#f0fdfa' }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
            <SchoolIcon sx={{ color: '#0891b2', fontSize: 24 }} />
            <Typography variant="h6" fontWeight={700}>Recommended Actions</Typography>
          </Stack>
          <Stack spacing={1.5}>
            {generateActions(analysis).map((action, idx) => (
              <Box key={idx} sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                <Box sx={{ width: 24, height: 24, borderRadius: '50%', bgcolor: '#0891b2', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0 }}>
                  {idx + 1}
                </Box>
                <Typography variant="body2">{action}</Typography>
              </Box>
            ))}
          </Stack>
        </CardContent>
      </Card>

      {/* Error Diagnosis */}
      {analysis.error_message && (
        <Card sx={{ mb: 3, border: '1px solid', borderColor: '#fca5a5', bgcolor: '#fef2f2' }}>
          <CardContent sx={{ p: 3 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <BugReportIcon sx={{ color: '#ef4444' }} />
                <Typography variant="h6" fontWeight={700} color="error">Error Detected</Typography>
              </Stack>
              <Button
                size="small"
                variant="outlined"
                color="error"
                startIcon={diagnosing ? <CircularProgress size={14} /> : <BugReportIcon />}
                onClick={handleDiagnose}
                disabled={diagnosing}
              >
                AI Diagnose
              </Button>
            </Stack>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', color: '#991b1b', whiteSpace: 'pre-wrap' }}>
              {analysis.error_message}
            </Typography>
          </CardContent>
        </Card>
      )}

      {diagnosis && diagnosis.diagnosed && (
        <Card sx={{ border: '1px solid', borderColor: '#93c5fd', bgcolor: '#eff6ff' }}>
          <CardContent sx={{ p: 3 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
              <TipsAndUpdatesIcon sx={{ color: '#3b82f6' }} />
              <Typography variant="h6" fontWeight={700}>AI Diagnosis</Typography>
            </Stack>
            {diagnosis.diagnosis?.root_cause && (
              <Box sx={{ mb: 1.5 }}>
                <Typography variant="body2" fontWeight={600}>Root Cause:</Typography>
                <Typography variant="body2">{diagnosis.diagnosis.root_cause}</Typography>
              </Box>
            )}
            {diagnosis.diagnosis?.suggestion && (
              <Box>
                <Typography variant="body2" fontWeight={600}>Fix:</Typography>
                <Typography variant="body2">{diagnosis.diagnosis.suggestion}</Typography>
              </Box>
            )}
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}

// ─── Log Tab ────────────────────────────────────────────────────────────────

function LogTab({ logLines, output_log, enqueueSnackbar, isLive }) {
  const handleCopy = () => {
    const text = logLines.join('\n') || output_log || '';
    if (text) {
      navigator.clipboard.writeText(text);
      enqueueSnackbar('Log copied to clipboard', { variant: 'success' });
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <Card variant="outlined">
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <TerminalIcon sx={{ fontSize: 18, color: isLive ? '#ef4444' : 'text.secondary' }} />
              <Typography variant="body2" fontWeight={600} color={isLive ? 'error.main' : 'text.secondary'}>
                {isLive ? '🔴 Live Output' : 'Output Log'} ({logLines.length} lines)
              </Typography>
              {isLive && (
                <Chip label="STREAMING" size="small" sx={{ height: 20, fontSize: '0.65rem', fontWeight: 700, bgcolor: '#fef2f2', color: '#ef4444', animation: 'pulse 1.5s infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } } }} />
              )}
            </Stack>
            <Tooltip title="Copy to clipboard">
              <IconButton size="small" onClick={handleCopy} disabled={logLines.length === 0}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
          <Box sx={{
            bgcolor: '#0d1117',
            p: 2,
            maxHeight: 600,
            overflow: 'auto',
            fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", monospace',
            fontSize: '0.78rem',
            lineHeight: 1.7,
          }}>
            {logLines.length === 0 ? (
              <Typography sx={{ color: '#484f58', fontFamily: 'inherit', fontSize: '0.85rem' }}>
                {isLive ? '⏳ Waiting for agent output... The agent is starting up.' : 'No output captured for this run.'}
              </Typography>
            ) : (
              logLines.map((line, idx) => (
                <Box key={idx} component="div" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: getLogLineColor(line), '&:hover': { bgcolor: '#161b22' } }}>
                  <Box component="span" sx={{ color: '#484f58', mr: 1.5, userSelect: 'none', display: 'inline-block', minWidth: 36, textAlign: 'right' }}>{idx + 1}</Box>
                  {line}
                </Box>
              ))
            )}
            {isLive && logLines.length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Box component="span" sx={{ display: 'inline-block', width: 8, height: 16, bgcolor: '#4ade80', animation: 'blink 1s step-end infinite', '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } } }} />
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ─── Pipeline Tab (GitHub Actions style) ────────────────────────────────────

function PipelineTab({ steps, analysis }) {
  const [collapsedSteps, setCollapsedSteps] = useState({});

  const formatDur = (secs) => {
    if (secs == null) return '';
    if (secs >= 60) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
    return `${secs}s`;
  };

  const statusIcon = (s) => s === 'success' ? '✅' : s === 'warning' ? '⚠️' : s === 'error' ? '❌' : '⬜';
  const statusColor = (s) => s === 'success' ? '#10b981' : s === 'warning' ? '#f59e0b' : s === 'error' ? '#ef4444' : '#d1d5db';
  const totalDur = analysis.duration_seconds ? formatDur(parseInt(analysis.duration_seconds)) : '—';
  const isDryRun = analysis.dry_run === 'True' || analysis.dry_run === true || analysis.dry_run === 'true';

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Run Banner */}
      <Card sx={{ mb: 2, border: '1px solid', borderColor: analysis.status === 'completed' ? '#a7f3d0' : '#fca5a5', borderRadius: '12px', overflow: 'hidden' }}>
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, bgcolor: analysis.status === 'completed' ? '#ecfdf5' : '#fef2f2' }}>
          <Box sx={{ width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: analysis.status === 'completed' ? '#10b981' : '#ef4444', color: '#fff', fontWeight: 700 }}>
            {analysis.status === 'completed' ? '✓' : '✗'}
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle1" fontWeight={800}>🎬 ApplyPilot Pipeline #{analysis.run_id?.slice(0, 8)}</Typography>
            <Typography variant="caption" color="text.secondary">
              {analysis.started_at ? dayjs(analysis.started_at).format('MMM D, h:mm:ss A') : ''} · {totalDur} · {analysis.mode}{isDryRun ? ' (Dry Run)' : ''}
            </Typography>
          </Box>
          <Chip label={analysis.status} size="small" sx={{ fontWeight: 700, textTransform: 'capitalize', bgcolor: analysis.status === 'completed' ? '#d1fae5' : '#fee2e2', color: analysis.status === 'completed' ? '#065f46' : '#991b1b' }} />
        </Box>
      </Card>

      {/* Steps */}
      {/* Copy All Logs button */}
      {steps.length > 0 && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
          <Button
            size="small"
            startIcon={<ContentCopyIcon />}
            onClick={() => {
              const allText = steps.map(s =>
                `── ${s.icon} ${s.name} (${s.duration_seconds != null ? s.duration_seconds + 's' : ''}) ──\n` +
                (s.sub_steps || []).map(ss => `${ss.timestamp || ''} ${ss.text}`).join('\n')
              ).join('\n\n');
              navigator.clipboard.writeText(allText);
            }}
            sx={{ textTransform: 'none', fontWeight: 600, fontSize: '0.8rem' }}
          >
            Copy All Logs
          </Button>
        </Box>
      )}

      {steps.length === 0 ? (
        <Card variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">No pipeline steps recorded.</Typography>
        </Card>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {steps.map((s, idx) => {
            const isExpanded = !collapsedSteps[idx];
            return (
              <Box key={s.id + idx}>
                {/* Step Header Row */}
                <Box
                  onClick={() => setCollapsedSteps(prev => ({ ...prev, [idx]: !prev[idx] }))}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1.5,
                    p: '10px 12px', cursor: 'pointer', borderRadius: '8px',
                    borderLeft: `3px solid ${statusColor(s.status)}`,
                    ml: 1, transition: 'all 0.15s',
                    bgcolor: isExpanded ? '#f8fafc' : 'transparent',
                    '&:hover': { bgcolor: '#f8fafc' },
                  }}
                >
                  <Typography sx={{ fontSize: '0.95rem' }}>{statusIcon(s.status)}</Typography>
                  <Typography sx={{ fontSize: '1rem' }}>{s.icon}</Typography>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="body2" fontWeight={700}>{s.name}</Typography>
                    {s.start_time && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                        {s.start_time}{s.end_time ? ` → ${s.end_time}` : ''}
                      </Typography>
                    )}
                  </Box>
                  {s.log_count > 0 && (
                    <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                      {s.log_count} lines
                    </Typography>
                  )}
                  {s.duration_seconds != null && (
                    <Chip label={formatDur(s.duration_seconds)} size="small" sx={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.7rem', height: 22, bgcolor: '#f3f4f6' }} />
                  )}
                  <ExpandMoreIcon sx={{ fontSize: 16, transform: isExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s', color: '#9ca3af' }} />
                </Box>

                {/* Expanded Sub-steps */}
                <Collapse in={isExpanded}>
                  <Box sx={{ ml: 5, mr: 1, my: 1, borderRadius: '8px', border: '1px solid #1e293b', overflow: 'hidden' }}>
                    {/* Sub-step header */}
                    <Box sx={{ px: 1.5, py: 0.75, bgcolor: '#161b22', display: 'flex', alignItems: 'center', borderBottom: '1px solid #30363d' }}>
                      <Typography variant="caption" sx={{ color: '#8b949e', fontFamily: 'monospace', fontWeight: 600, flex: 1 }}>
                        {s.name} — {s.log_count} entries
                      </Typography>
                      <Tooltip title="Copy step logs">
                        <IconButton size="small" onClick={(e) => {
                          e.stopPropagation();
                          const text = (s.sub_steps || []).map(ss => `${ss.timestamp || ''} ${ss.text}`).join('\n');
                          navigator.clipboard.writeText(text);
                        }} sx={{ color: '#8b949e', p: 0.5, '&:hover': { color: '#e2e8f0' } }}>
                          <ContentCopyIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                      </Tooltip>
                    </Box>
                    {/* Sub-step lines */}
                    <Box sx={{ bgcolor: '#0d1117', maxHeight: 350, overflow: 'auto', py: 0.5, userSelect: 'text' }}>
                      {s.sub_steps && s.sub_steps.map((ss, ssIdx) => (
                        <Box key={ssIdx} sx={{
                          display: 'flex', alignItems: 'flex-start', gap: 1,
                          px: 1.5, py: '3px',
                          '&:hover': { bgcolor: '#161b22' },
                          fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                          fontSize: '0.72rem', lineHeight: 1.6,
                        }}>
                          {/* Timestamp */}
                          <Box component="span" sx={{ color: '#484f58', minWidth: 55, flexShrink: 0 }}>
                            {ss.timestamp || ''}
                          </Box>
                          {/* Duration badge */}
                          <Box component="span" sx={{ color: '#6e7681', minWidth: 30, flexShrink: 0, textAlign: 'right' }}>
                            {ss.duration_seconds != null && ss.duration_seconds > 0 ? `${ss.duration_seconds}s` : ''}
                          </Box>
                          {/* Log text */}
                          <Box component="span" sx={{
                            color: ss.status === 'error' ? '#f87171' : ss.status === 'warning' ? '#fbbf24' :
                                   ss.text.match(/✅|✓|success|connected|found|ready/i) ? '#4ade80' :
                                   ss.text.match(/scanning|searching|checking/i) ? '#93c5fd' : '#e2e8f0',
                            flex: 1, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                          }}>
                            {ss.text}
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                </Collapse>

                {/* Connector */}
                {idx < steps.length - 1 && (
                  <Box sx={{ ml: 2.8, width: 2, height: 6, bgcolor: statusColor(steps[idx + 1]?.status || 'default'), borderRadius: 1 }} />
                )}
              </Box>
            );
          })}
        </Box>
      )}
    </motion.div>
  );
}

// ─── Intelligence Generators ────────────────────────────────────────────────

function generateInsights(analysis) {
  const { summary, jobs, companies } = analysis;
  const insights = [];

  if (!summary || summary.jobs_evaluated === 0) {
    insights.push({
      icon: '🔍',
      title: 'No jobs evaluated',
      message: 'The agent completed but didn\'t evaluate any jobs. This could mean no new jobs matched your keywords, or all found jobs were already in your dedup database.',
    });
    return insights;
  }

  // Success rate insight
  const successRate = summary.jobs_evaluated > 0 ? (summary.applied / summary.jobs_evaluated) * 100 : 0;
  if (successRate >= 50) {
    insights.push({ icon: '🎯', title: 'High match rate!', message: `${Math.round(successRate)}% of evaluated jobs met your criteria. Your search settings are well-tuned.` });
  } else if (successRate >= 20) {
    insights.push({ icon: '📊', title: 'Moderate match rate', message: `${Math.round(successRate)}% of jobs qualified. Consider adjusting your threshold if you want more applications.` });
  } else if (successRate > 0) {
    insights.push({ icon: '⚠️', title: 'Low match rate', message: `Only ${Math.round(successRate)}% of jobs qualified. Your threshold might be too high, or your keywords could be broadened.` });
  } else {
    insights.push({ icon: '❌', title: 'No matches found', message: 'None of the evaluated jobs met your threshold. Consider lowering it from the Agent Control panel.' });
  }

  // Score insight
  if (summary.avg_score) {
    if (summary.avg_score >= 80) {
      insights.push({ icon: '⭐', title: 'Strong profile match', message: `Average score of ${summary.avg_score}% means LinkedIn sees you as a great fit for these roles.` });
    } else if (summary.avg_score >= 60) {
      insights.push({ icon: '📈', title: 'Decent match potential', message: `Average score of ${summary.avg_score}%. Tip: Optimize your LinkedIn headline and skills to boost your match score.` });
    }
  }

  // External jobs insight
  if (summary.external > 0) {
    const extRate = Math.round((summary.external / summary.jobs_evaluated) * 100);
    insights.push({ icon: '🔗', title: `${summary.external} external applications`, message: `${extRate}% of jobs require applying on company websites. These links have been captured for you.` });
  }

  // Company diversity
  const companyCount = Object.keys(companies || {}).length;
  if (companyCount >= 5) {
    insights.push({ icon: '🏢', title: 'Good company diversity', message: `Jobs from ${companyCount} different companies. You're casting a wide net across the market.` });
  }

  // Dedup effectiveness
  if (summary.dedup_database_size > 100) {
    insights.push({ icon: '🧠', title: 'Smart dedup working', message: `${summary.dedup_database_size} jobs in your memory — the agent is getting faster by skipping already-seen listings.` });
  }

  return insights;
}

function generateActions(analysis) {
  const { summary, jobs } = analysis;
  const actions = [];

  if (!summary || summary.jobs_evaluated === 0) {
    actions.push('Run the agent again with broader keywords or lower threshold to find more matches.');
    actions.push('Check that your LinkedIn session is active — go to Settings → Test LinkedIn.');
    actions.push('Verify your search keywords match actual LinkedIn job titles in your target locations.');
    return actions;
  }

  const isDryRun = analysis.dry_run === 'True' || analysis.dry_run === true || analysis.dry_run === 'true';

  if (isDryRun && summary.applied > 0) {
    actions.push(`🚀 Turn off Dry Run to actually submit your ${summary.applied} qualified application${summary.applied > 1 ? 's' : ''}!`);
  }

  if (summary.skipped > summary.applied && summary.applied > 0) {
    actions.push(`Consider lowering your match threshold from ${analysis.match_threshold || 80}% to capture more opportunities.`);
  }

  if (summary.external > 0) {
    actions.push(`Review the ${summary.external} external job link${summary.external > 1 ? 's' : ''} — these are high-quality matches that need manual apply.`);
  }

  if (summary.avg_score && summary.avg_score < 70) {
    actions.push('Boost your match scores by updating your LinkedIn profile: add more skills, optimize your headline, and match keywords from job descriptions.');
  }

  if (summary.errors > 0) {
    actions.push(`${summary.errors} error${summary.errors > 1 ? 's' : ''} occurred — use the AI Diagnose button above to understand what went wrong.`);
  }

  if (summary.total_discovered === 0) {
    actions.push('Add more search keywords or expand your target locations to discover more opportunities.');
  }

  if (actions.length === 0) {
    actions.push('Great run! Keep your agent running on schedule to catch new postings daily.');
    actions.push('Review your Board to track application responses and move jobs through your pipeline.');
  }

  return actions;
}
