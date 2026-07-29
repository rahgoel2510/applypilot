import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Box, Typography, Button, TextField, Select, MenuItem, FormControl, InputLabel,
  Stack, Chip, IconButton, Menu, Dialog, DialogTitle, DialogContent, DialogActions,
  CircularProgress, Divider, Avatar,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import SearchIcon from '@mui/icons-material/Search';
import InputAdornment from '@mui/material/InputAdornment';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import {
  DndContext, DragOverlay, closestCorners, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useSnackbar } from 'notistack';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { COLUMNS } from '../columns';
import { fetchJobs, createJob, updateJobStage, deleteJob } from '../api';

dayjs.extend(relativeTime);

// Timeline helper
function TimelineItem({ color, title, sub, detail, isLast }) {
  return (
    <Box sx={{ display: 'flex', gap: 1.5 }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: color, flexShrink: 0 }} />
        {!isLast && <Box sx={{ width: 1.5, flex: 1, bgcolor: '#D5DBDB', mt: 0.5 }} />}
      </Box>
      <Box sx={{ pb: isLast ? 0 : 1 }}>
        <Typography variant="body2" fontWeight={600}>{title}</Typography>
        <Typography variant="caption" color="text.secondary">{sub}</Typography>
        {detail && <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{detail}</Typography>}
      </Box>
    </Box>
  );
}

const STAGE_META = {
  discovered: { color: '#0073BB', bg: '#E6F2FA', emoji: '🔍' },
  reached_out: { color: '#6B40B2', bg: '#F3EEFB', emoji: '✉️' },
  saved: { color: '#545B64', bg: '#F2F3F3', emoji: '📌' },
  applied: { color: '#067D68', bg: '#E6F5F2', emoji: '✅' },
  interviewing: { color: '#EC7211', bg: '#FEF3E8', emoji: '🎤' },
  offered: { color: '#067D68', bg: '#E6F5F2', emoji: '🎉' },
  rejected: { color: '#D13212', bg: '#FCECEA', emoji: '❌' },
};

function getScoreStyle(score) {
  if (score >= 0.8) return { color: '#067D68', bg: '#E6F5F2', label: 'Strong' };
  if (score >= 0.6) return { color: '#EC7211', bg: '#FEF3E8', label: 'Fair' };
  return { color: '#D13212', bg: '#FCECEA', label: 'Low' };
}

// ═══ Job Card ═══
function JobCard({ job, onMenuOpen, onCardClick }) {
  const dragRef = useRef(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: job.id, data: { job, stage: job.stage },
  });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.3 : 1 };
  const score = job.match_score ?? job.score;
  const scoreStyle = score != null ? getScoreStyle(score) : null;
  const initial = (job.company || '?')[0].toUpperCase();

  return (
    <Box
      ref={setNodeRef} style={style} {...attributes} {...listeners}
      onPointerDown={() => { dragRef.current = false; }}
      onPointerMove={() => { dragRef.current = true; }}
      onClick={() => { if (!dragRef.current) onCardClick(job); }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      sx={{
        mb: 1, p: 1.5, cursor: 'pointer',
        bgcolor: 'background.paper',
        borderRadius: '8px',
        border: '1px solid', borderColor: 'divider',
        borderLeft: `3px solid ${STAGE_META[job.stage]?.color || '#545B64'}`,
        transition: 'all 0.15s ease',
        overflow: 'hidden',
        '&:hover': {
          borderColor: '#0073BB',
          borderLeftColor: STAGE_META[job.stage]?.color || '#545B64',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          '& .actions': { opacity: 1 },
        },
        '&:active': { cursor: 'grabbing' },
        position: 'relative',
      }}
    >
      {/* Hover Tooltip */}
      {showTooltip && !dragRef.current && (
        <Box sx={{
          position: 'absolute', bottom: '100%', left: 0, right: 0, mb: 1, zIndex: 1000,
          bgcolor: '#232F3E', color: '#fff', borderRadius: '8px', p: 2,
          boxShadow: '0 8px 24px rgba(0,0,0,0.2)', pointerEvents: 'none',
          '&::after': { content: '""', position: 'absolute', top: '100%', left: 20, border: '6px solid transparent', borderTopColor: '#232F3E' },
        }}>
          <Typography sx={{ fontWeight: 700, fontSize: '13px', mb: 0.75 }}>{job.title}</Typography>
          <Typography sx={{ fontSize: '12px', opacity: 0.8, mb: 1 }}>{job.company}{job.location ? ` • ${job.location}` : ''}</Typography>
          <Stack spacing={0.5}>
            <Stack direction="row" justifyContent="space-between">
              <Typography sx={{ fontSize: '11px', opacity: 0.6 }}>Match Score</Typography>
              <Typography sx={{ fontSize: '11px', fontWeight: 700 }}>{score != null ? `${Math.round(score * 100)}%` : 'N/A'}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography sx={{ fontSize: '11px', opacity: 0.6 }}>Stage</Typography>
              <Typography sx={{ fontSize: '11px', fontWeight: 600, textTransform: 'capitalize' }}>{job.stage}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography sx={{ fontSize: '11px', opacity: 0.6 }}>Added</Typography>
              <Typography sx={{ fontSize: '11px' }}>{job.date_added ? dayjs(job.date_added).fromNow() : '—'}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography sx={{ fontSize: '11px', opacity: 0.6 }}>Source</Typography>
              <Typography sx={{ fontSize: '11px', textTransform: 'capitalize' }}>{job.source || 'agent'}</Typography>
            </Stack>
          </Stack>
          <Typography sx={{ fontSize: '10px', opacity: 0.5, mt: 1, textAlign: 'center' }}>Click to view full details</Typography>
        </Box>
      )}

      {/* Actions (top right on hover) */}
      <Stack direction="row" className="actions" sx={{ position: 'absolute', top: 6, right: 6, opacity: 0, transition: 'opacity 0.15s' }}>
        <IconButton size="small" onClick={(e) => { e.stopPropagation(); onMenuOpen(e, job); }}>
          <MoreHorizIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Stack>

      {/* Company avatar + Title */}
      <Stack direction="row" spacing={1.5} alignItems="flex-start" sx={{ overflow: 'hidden' }}>
        <Avatar sx={{ width: 32, height: 32, fontSize: 13, fontWeight: 700, bgcolor: STAGE_META[job.stage]?.bg || '#F2F3F3', color: STAGE_META[job.stage]?.color || '#545B64', flexShrink: 0 }}>
          {initial}
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
          <Typography variant="body2" fontWeight={600} noWrap title={job.title} sx={{ lineHeight: 1.3 }}>
            {job.title || 'Untitled'}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
            {job.company || '—'}
          </Typography>
        </Box>
      </Stack>

      {/* Bottom row */}
      <Stack direction="row" alignItems="center" spacing={0.75} sx={{ mt: 1, overflow: 'hidden', flexWrap: 'nowrap' }}>
        {job.location && (
          <Chip label={job.location} size="small" variant="outlined" sx={{ fontSize: '11px', height: 20, maxWidth: 100, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }} />
        )}
        {scoreStyle && (
          <Chip label={`${Math.round(score * 100)}%`} size="small" sx={{ height: 20, fontWeight: 700, fontSize: '11px', bgcolor: scoreStyle.bg, color: scoreStyle.color, border: 'none' }} />
        )}
        <Box sx={{ flex: 1 }} />
        {job.date_added && (
          <Typography variant="caption" color="text.disabled" noWrap sx={{ fontSize: '11px', flexShrink: 0 }}>
            {dayjs(job.date_added).fromNow()}
          </Typography>
        )}
      </Stack>
    </Box>
  );
}

// ═══ Column ═══
function KanbanCol({ column, jobs, onMenuOpen, onCardClick, onAddJob }) {
  const jobIds = useMemo(() => jobs.map(j => j.id), [jobs]);
  const meta = STAGE_META[column.id] || { color: '#545B64', bg: '#F2F3F3', emoji: '📋' };

  return (
    <Box sx={{ width: 280, minWidth: 280, display: 'flex', flexDirection: 'column', height: '100%', bgcolor: '#F7F8F9', borderRadius: '8px', border: '1px solid', borderColor: 'divider' }}>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.5, py: 1.25, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography sx={{ fontSize: 16 }}>{meta.emoji}</Typography>
        <Typography variant="body1" fontWeight={600} sx={{ flex: 1 }}>{column.label}</Typography>
        <Chip label={jobs.length} size="small" sx={{ height: 20, fontSize: '11px', fontWeight: 700, bgcolor: meta.bg, color: meta.color }} />
        <IconButton size="small" onClick={() => onAddJob(column.id)} sx={{ opacity: 0.4, '&:hover': { opacity: 1 } }}>
          <AddIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Stack>

      {/* Cards area */}
      <Box sx={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden', p: 1,
        '&::-webkit-scrollbar': { width: 4 },
        '&::-webkit-scrollbar-thumb': { bgcolor: '#D5DBDB', borderRadius: 4 },
      }}>
        <SortableContext items={jobIds} strategy={verticalListSortingStrategy}>
          {jobs.map(job => <JobCard key={job.id} job={job} onMenuOpen={onMenuOpen} onCardClick={onCardClick} />)}
        </SortableContext>
        {jobs.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 4, opacity: 0.35 }}>
            <Typography variant="body2" color="text.secondary">No jobs</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

// ═══ Main ═══
export default function Board() {
  const { enqueueSnackbar } = useSnackbar();
  const [jobs, setJobs] = useState([]);
  const [search, setSearch] = useState('');
  const [companyFilter, setCompanyFilter] = useState('all');
  const [sort, setSort] = useState('newest');
  const [loading, setLoading] = useState(true);
  const [activeJob, setActiveJob] = useState(null);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [menuJob, setMenuJob] = useState(null);
  const [detailJob, setDetailJob] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addStage, setAddStage] = useState('discovered');
  const [newJob, setNewJob] = useState({ title: '', company: '', location: '', posting_url: '', notes: '' });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const loadJobs = useCallback(async () => {
    try { const d = await fetchJobs({ search, company: companyFilter, sort }); setJobs(d.jobs || d || []); }
    catch (err) { console.error(err); } finally { setLoading(false); }
  }, [search, companyFilter, sort]);
  useEffect(() => { loadJobs(); }, [loadJobs]);

  const companies = useMemo(() => ['all', ...new Set(jobs.map(j => j.company).filter(Boolean))].sort(), [jobs]);
  const jobsByStage = useMemo(() => {
    const map = {}; COLUMNS.forEach(col => (map[col.id] = []));
    jobs.forEach(job => { const s = job.stage || 'discovered'; if (map[s]) map[s].push(job); });
    return map;
  }, [jobs]);

  const handleDragStart = (e) => setActiveJob(jobs.find(j => j.id === e.active.id) || null);
  const handleDragEnd = async (e) => {
    setActiveJob(null); const { active, over } = e; if (!over) return;
    const job = jobs.find(j => j.id === active.id); if (!job) return;
    let target = COLUMNS.find(c => c.id === over.id) ? over.id : jobs.find(j => j.id === over.id)?.stage;
    if (!target || target === job.stage) return;
    setJobs(prev => prev.map(j => j.id === active.id ? { ...j, stage: target } : j));
    try { await updateJobStage(active.id, target); } catch { enqueueSnackbar('Failed', { variant: 'error' }); loadJobs(); }
  };

  const handleMenuOpen = (e, job) => { setMenuAnchor(e.currentTarget); setMenuJob(job); };
  const handleMenuClose = () => { setMenuAnchor(null); setMenuJob(null); };
  const handleMove = async (stage) => { if (!menuJob) return; handleMenuClose(); setJobs(p => p.map(j => j.id === menuJob.id ? { ...j, stage } : j)); try { await updateJobStage(menuJob.id, stage); } catch { loadJobs(); } };
  const handleDelete = async () => { if (!menuJob) return; const id = menuJob.id; handleMenuClose(); setJobs(p => p.filter(j => j.id !== id)); try { await deleteJob(id); } catch { loadJobs(); } };
  const handleAdd = async () => {
    try { await createJob({ ...newJob, stage: addStage }); enqueueSnackbar('Added', { variant: 'success' }); setAddOpen(false); setNewJob({ title: '', company: '', location: '', posting_url: '', notes: '' }); loadJobs(); }
    catch (err) { enqueueSnackbar(err.message, { variant: 'error' }); }
  };
  const openAdd = (stage) => { setAddStage(stage); setAddOpen(true); };

  const score = detailJob?.match_score ?? detailJob?.score;
  const scoreStyle = score != null ? getScoreStyle(score) : null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2 }}>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
        <Typography variant="h3">Job Board</Typography>
        <Chip label={`${jobs.length} jobs`} size="small" sx={{ fontWeight: 600 }} />
        <Box sx={{ flex: 1 }} />
        <TextField
          placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} size="small"
          sx={{ width: 180 }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" color="action" /></InputAdornment> }}
        />
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <Select value={companyFilter} displayEmpty onChange={(e) => setCompanyFilter(e.target.value)} size="small">
            <MenuItem value="all">All companies</MenuItem>
            {companies.filter(c => c !== 'all').map(c => <MenuItem key={c} value={c}>{c}</MenuItem>)}
          </Select>
        </FormControl>
        <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => openAdd('discovered')}>Add Job</Button>
      </Stack>

      {/* Board */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}><CircularProgress /></Box>
      ) : (
        <Box sx={{ flex: 1, overflow: 'hidden' }}>
          <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
            <Box sx={{ display: 'flex', gap: 2, height: '100%', overflowX: 'auto', pb: 1 }}>
              {COLUMNS.map(col => (
                <SortableContext key={col.id} id={col.id} items={(jobsByStage[col.id] || []).map(j => j.id)} strategy={verticalListSortingStrategy}>
                  <KanbanCol column={col} jobs={jobsByStage[col.id] || []} onMenuOpen={handleMenuOpen} onCardClick={setDetailJob} onAddJob={openAdd} />
                </SortableContext>
              ))}
            </Box>
            <DragOverlay>
              {activeJob && (
                <Box sx={{ width: 280, p: 2, bgcolor: 'background.paper', borderRadius: '10px', boxShadow: 8, opacity: 0.95, border: '1px solid', borderColor: 'primary.main' }}>
                  <Typography fontWeight={600}>{activeJob.title}</Typography>
                  <Typography variant="body2" color="text.secondary">{activeJob.company}</Typography>
                </Box>
              )}
            </DragOverlay>
          </DndContext>
        </Box>
      )}

      {/* Context Menu */}
      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={handleMenuClose} slotProps={{ paper: { sx: { minWidth: 160, borderRadius: 2 } } }}>
        <Typography variant="overline" sx={{ px: 2, py: 0.5, display: 'block' }}>Move to</Typography>
        {COLUMNS.filter(c => c.id !== menuJob?.stage).map(col => (
          <MenuItem key={col.id} onClick={() => handleMove(col.id)} sx={{ gap: 1 }}>
            <Typography sx={{ fontSize: 16 }}>{STAGE_META[col.id]?.emoji}</Typography>
            {col.label}
          </MenuItem>
        ))}
        <Divider sx={{ my: 0.5 }} />
        <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}><DeleteOutlineIcon fontSize="small" sx={{ mr: 1 }} />Delete</MenuItem>
      </Menu>

      {/* Detail Dialog */}
      <Dialog open={Boolean(detailJob)} onClose={() => setDetailJob(null)} maxWidth="md" fullWidth
        PaperProps={{ sx: { borderRadius: 3, overflow: 'hidden' } }}
      >
        {detailJob && (() => {
          const dScore = detailJob.match_score ?? detailJob.score;
          const dStyle = dScore != null ? getScoreStyle(dScore) : null;
          return (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 3, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Stack direction="row" spacing={2} alignItems="center">
                <Avatar sx={{ width: 44, height: 44, bgcolor: STAGE_META[detailJob.stage]?.bg, color: STAGE_META[detailJob.stage]?.color, fontWeight: 700, fontSize: 16 }}>
                  {(detailJob.company || '?')[0]}
                </Avatar>
                <Box>
                  <Typography variant="h4" sx={{ lineHeight: 1.3 }}>{detailJob.title}</Typography>
                  <Typography variant="body2" color="text.secondary">{detailJob.company}{detailJob.location ? ` • ${detailJob.location}` : ''}</Typography>
                </Box>
              </Stack>
              <IconButton onClick={() => setDetailJob(null)} size="small" sx={{ bgcolor: '#F2F3F3', '&:hover': { bgcolor: '#EAEDED' } }}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
            <DialogContent sx={{ p: 0 }}>
              <Stack direction="row">
                {/* Left Panel */}
                <Box sx={{ flex: 1, p: 3 }}>
                  {/* Score + Stage */}
                  <Stack direction="row" spacing={3} alignItems="center" sx={{ mb: 3 }}>
                    {dStyle && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                          <CircularProgress variant="determinate" value={dScore * 100} size={72} thickness={5} sx={{ color: dStyle.color }} />
                          <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Typography variant="h4" fontWeight={700} sx={{ color: dStyle.color }}>{Math.round(dScore * 100)}%</Typography>
                          </Box>
                        </Box>
                        <Box>
                          <Typography fontWeight={600}>{dStyle.label} Match</Typography>
                          <Typography variant="caption" color="text.secondary">LinkedIn Premium score</Typography>
                        </Box>
                      </Box>
                    )}
                    <Chip label={detailJob.stage} icon={<span style={{ fontSize: 14 }}>{STAGE_META[detailJob.stage]?.emoji}</span>} sx={{ fontWeight: 600, textTransform: 'capitalize', bgcolor: STAGE_META[detailJob.stage]?.bg, color: STAGE_META[detailJob.stage]?.color, height: 30, fontSize: '13px' }} />
                  </Stack>

                  {/* Job URL */}
                  {(detailJob.posting_url || detailJob.url) && (
                    <Button variant="outlined" fullWidth startIcon={<OpenInNewIcon />} href={detailJob.posting_url || detailJob.url} target="_blank" sx={{ mb: 3, py: 1.25 }}>
                      View Job Posting on LinkedIn
                    </Button>
                  )}

                  {/* Analysis */}
                  <Typography variant="h4" sx={{ mb: 1.5 }}>📊 Agent Analysis</Typography>
                  <Box sx={{ bgcolor: '#F7F8F9', borderRadius: 2, p: 2, border: '1px solid', borderColor: 'divider', mb: 3 }}>
                    <Stack spacing={1.5}>
                      <Stack direction="row" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Match Score</Typography>
                        <Typography variant="body2" fontWeight={700} sx={{ color: dStyle?.color || 'text.primary' }}>
                          {dScore != null ? `${Math.round(dScore * 100)}% — ${dStyle?.label}` : 'Not scored'}
                        </Typography>
                      </Stack>
                      <Divider />
                      <Stack direction="row" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Application Type</Typography>
                        <Typography variant="body2" fontWeight={500}>Easy Apply</Typography>
                      </Stack>
                      <Divider />
                      <Stack direction="row" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Source</Typography>
                        <Typography variant="body2" fontWeight={500} sx={{ textTransform: 'capitalize' }}>{detailJob.source || 'Agent'}</Typography>
                      </Stack>
                      <Divider />
                      <Stack direction="row" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Discovered</Typography>
                        <Typography variant="body2">{detailJob.date_added ? dayjs(detailJob.date_added).format('MMM D, YYYY HH:mm') : '—'}</Typography>
                      </Stack>
                      {dScore != null && dScore >= 0.7 && (<><Divider /><Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Recommendation</Typography><Typography variant="body2" fontWeight={600} sx={{ color: '#067D68' }}>✓ Worth applying</Typography></Stack></>)}
                      {dScore != null && dScore < 0.5 && (<><Divider /><Stack direction="row" justifyContent="space-between"><Typography variant="body2" color="text.secondary">Recommendation</Typography><Typography variant="body2" fontWeight={600} sx={{ color: '#D13212' }}>✗ Below threshold</Typography></Stack></>)}
                    </Stack>
                  </Box>

                  {detailJob.notes && (<><Typography variant="h4" sx={{ mb: 1 }}>📝 Notes</Typography><Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>{detailJob.notes}</Typography></>)}
                </Box>

                {/* Right Panel — Timeline */}
                <Box sx={{ width: 260, minWidth: 260, p: 2.5, bgcolor: '#FAFBFC', borderLeft: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="h4" sx={{ mb: 2 }}>📅 Timeline</Typography>
                  <Stack spacing={2}>
                    <TimelineItem color="#0073BB" title="Discovered" sub={detailJob.date_added ? dayjs(detailJob.date_added).format('MMM D, HH:mm') : '—'} detail={`Found via ${detailJob.source || 'agent'} scan`} />
                    {dScore != null && <TimelineItem color="#6B40B2" title="Scored" sub={`Match: ${Math.round(dScore * 100)}%`} />}
                    {(detailJob.stage === 'reached_out') && <TimelineItem color="#6B40B2" title="InMail Sent" sub="Warm outreach to recruiter" />}
                    {(['applied', 'interviewing', 'offered'].includes(detailJob.stage)) && <TimelineItem color="#067D68" title="Applied" sub="Application submitted" />}
                    {detailJob.stage === 'interviewing' && <TimelineItem color="#EC7211" title="Interviewing" sub="In progress" />}
                    {detailJob.stage === 'offered' && <TimelineItem color="#067D68" title="Offered! 🎉" sub="Congratulations" />}
                    {detailJob.stage === 'rejected' && <TimelineItem color="#D13212" title="Rejected" sub="Not selected" isLast />}
                    <TimelineItem color={STAGE_META[detailJob.stage]?.color || '#545B64'} title={`Current: ${detailJob.stage}`} sub="Now" isLast />
                  </Stack>

                  <Divider sx={{ my: 2 }} />
                  <Typography variant="h6" sx={{ mb: 1 }}>Quick Info</Typography>
                  <Stack spacing={0.75}>
                    {detailJob.location && <Stack direction="row" justifyContent="space-between"><Typography variant="caption" color="text.secondary">Location</Typography><Typography variant="body2">{detailJob.location}</Typography></Stack>}
                    <Stack direction="row" justifyContent="space-between"><Typography variant="caption" color="text.secondary">ID</Typography><Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{detailJob.id?.slice(0, 8)}</Typography></Stack>
                  </Stack>
                </Box>
              </Stack>
            </DialogContent>
            <Box sx={{ display: 'flex', alignItems: 'center', px: 3, py: 1.5, borderTop: '1px solid', borderColor: 'divider', bgcolor: '#FAFBFC' }}>
              <Button color="error" size="small" startIcon={<DeleteOutlineIcon />} onClick={() => { handleDelete(); setDetailJob(null); }}>Delete</Button>
              <Box sx={{ flex: 1 }} />
              {(detailJob.posting_url || detailJob.url) && <Button variant="contained" size="small" startIcon={<OpenInNewIcon />} href={detailJob.posting_url || detailJob.url} target="_blank">Apply Manually</Button>}
            </Box>
          </>
          );
        })()}
      </Dialog>

      {/* Add Dialog */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Add Job to {COLUMNS.find(c => c.id === addStage)?.label || 'Board'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Job Title" value={newJob.title} onChange={(e) => setNewJob(p => ({ ...p, title: e.target.value }))} fullWidth required autoFocus />
            <TextField label="Company" value={newJob.company} onChange={(e) => setNewJob(p => ({ ...p, company: e.target.value }))} fullWidth />
            <TextField label="Location" value={newJob.location} onChange={(e) => setNewJob(p => ({ ...p, location: e.target.value }))} fullWidth />
            <TextField label="Job URL" value={newJob.posting_url} onChange={(e) => setNewJob(p => ({ ...p, posting_url: e.target.value }))} fullWidth placeholder="https://linkedin.com/jobs/view/..." />
            <TextField label="Notes" value={newJob.notes} onChange={(e) => setNewJob(p => ({ ...p, notes: e.target.value }))} fullWidth multiline rows={2} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleAdd} disabled={!newJob.title}>Add Job</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
