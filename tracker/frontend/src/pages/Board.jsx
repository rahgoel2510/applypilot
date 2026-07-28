import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stack,
  Chip,
  IconButton,
  Menu,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Divider,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import SearchIcon from '@mui/icons-material/Search';
import InputAdornment from '@mui/material/InputAdornment';
import CloseIcon from '@mui/icons-material/Close';
import LaunchIcon from '@mui/icons-material/Launch';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useSnackbar } from 'notistack';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { COLUMNS } from '../columns';
import { fetchJobs, createJob, updateJob, updateJobStage, deleteJob } from '../api';

dayjs.extend(relativeTime);

const STAGE_COLORS = {
  discovered: '#6366f1',
  reached_out: '#8b5cf6',
  saved: '#294A73',
  applied: '#10b981',
  interviewing: '#f59e0b',
  offered: '#059669',
  rejected: '#ef4444',
};

function getScoreColor(score) {
  if (score >= 0.8) return '#16a34a';
  if (score >= 0.6) return '#ca8a04';
  return '#dc2626';
}

function getScoreBg(score) {
  if (score >= 0.8) return 'rgba(22,163,106,0.1)';
  if (score >= 0.6) return 'rgba(202,138,4,0.1)';
  return 'rgba(220,38,38,0.1)';
}

// ═══ Draggable Job Card ═══
function SortableJobCard({ job, onMenuOpen, onCardClick }) {
  const dragActivatedRef = useRef(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: job.id,
    data: { job, stage: job.stage },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const stageColor = STAGE_COLORS[job.stage] || '#6b7280';
  const score = job.match_score ?? job.score;

  const handlePointerDown = () => { dragActivatedRef.current = false; };
  const handlePointerMove = () => { dragActivatedRef.current = true; };
  const handleClick = () => {
    if (!dragActivatedRef.current) onCardClick(job);
  };

  return (
    <Box
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onClick={handleClick}
      sx={{
        mb: '6px',
        p: '6px 8px',
        cursor: 'grab',
        borderLeft: `3px solid ${stageColor}`,
        borderRadius: '4px',
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderLeftColor: stageColor,
        transition: 'box-shadow 0.15s, border-color 0.15s',
        '&:hover': {
          boxShadow: 2,
          borderColor: 'primary.main',
          borderLeftColor: stageColor,
          '& .card-actions': { opacity: 1 },
        },
        '&:active': { cursor: 'grabbing' },
        position: 'relative',
      }}
    >
      <Typography
        noWrap
        sx={{ fontSize: '0.72rem', fontWeight: 600, lineHeight: 1.3 }}
      >
        {job.title || 'Untitled'}
      </Typography>
      <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: '2px' }}>
        <Typography noWrap sx={{ fontSize: '0.65rem', color: 'text.secondary', flex: 1 }}>
          {job.company || '—'}
        </Typography>
        {score != null && (
          <Chip
            label={`${Math.round(score * 100)}%`}
            size="small"
            sx={{
              height: 16,
              fontSize: '0.6rem',
              fontWeight: 700,
              bgcolor: getScoreBg(score),
              color: getScoreColor(score),
              border: 'none',
              minWidth: 24,
              '& .MuiChip-label': { px: '4px' },
            }}
          />
        )}
      </Stack>
      {/* Hover actions */}
      <Stack
        className="card-actions"
        direction="row"
        spacing={0}
        sx={{
          position: 'absolute',
          top: 2,
          right: 2,
          opacity: 0,
          transition: 'opacity 0.15s',
          bgcolor: 'background.paper',
          borderRadius: '4px',
        }}
      >
        {job.url && (
          <IconButton
            size="small"
            onClick={(e) => { e.stopPropagation(); window.open(job.url, '_blank'); }}
            sx={{ p: '2px' }}
          >
            <OpenInNewIcon sx={{ fontSize: 12 }} />
          </IconButton>
        )}
        <IconButton
          size="small"
          onClick={(e) => { e.stopPropagation(); onMenuOpen(e, job); }}
          sx={{ p: '2px' }}
        >
          <MoreVertIcon sx={{ fontSize: 12 }} />
        </IconButton>
      </Stack>
    </Box>
  );
}

// ═══ Column ═══
function KanbanColumn({ column, jobs, onMenuOpen, onCardClick }) {
  const jobIds = useMemo(() => jobs.map((j) => j.id), [jobs]);
  const stageColor = STAGE_COLORS[column.id] || '#6b7280';

  return (
    <Box
      sx={{
        width: 180,
        minWidth: 180,
        flex: '0 0 180px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* Column Header */}
      <Box sx={{ borderTop: `3px solid ${stageColor}`, borderRadius: '4px 4px 0 0', mb: 0.5 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 0.75, py: 0.5 }}>
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {column.label}
          </Typography>
          <Chip
            label={jobs.length}
            size="small"
            sx={{
              height: 16,
              minWidth: 20,
              fontSize: '0.6rem',
              fontWeight: 700,
              bgcolor: stageColor,
              color: '#fff',
              '& .MuiChip-label': { px: '4px' },
            }}
          />
        </Stack>
      </Box>

      {/* Scrollable card list */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          px: 0.25,
          pb: 0.5,
          '&::-webkit-scrollbar': { width: 3 },
          '&::-webkit-scrollbar-thumb': { bgcolor: 'divider', borderRadius: 2 },
        }}
      >
        <SortableContext items={jobIds} strategy={verticalListSortingStrategy}>
          {jobs.map((job) => (
            <SortableJobCard key={job.id} job={job} onMenuOpen={onMenuOpen} onCardClick={onCardClick} />
          ))}
        </SortableContext>
        {jobs.length === 0 && (
          <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', textAlign: 'center', py: 2 }}>
            Empty
          </Typography>
        )}
      </Box>
    </Box>
  );
}

// ═══ Drag Overlay ═══
function DragOverlayCard({ job }) {
  if (!job) return null;
  const stageColor = STAGE_COLORS[job.stage] || '#6b7280';
  return (
    <Box sx={{ width: 180, p: '6px 8px', borderLeft: `3px solid ${stageColor}`, bgcolor: 'background.paper', borderRadius: '4px', boxShadow: 6, opacity: 0.92 }}>
      <Typography noWrap sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{job.title || 'Untitled'}</Typography>
      <Typography noWrap sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{job.company || '—'}</Typography>
    </Box>
  );
}

// ═══ Job Detail Modal ═══
function JobDetailDialog({ job, open, onClose, onUpdate, onDelete, columns }) {
  const [stage, setStage] = useState(job?.stage || 'discovered');
  const [notes, setNotes] = useState(job?.notes || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (job) {
      setStage(job.stage || 'discovered');
      setNotes(job.notes || '');
    }
  }, [job]);

  if (!job) return null;

  const score = job.match_score ?? job.score ?? 0;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(job.id, { stage, notes });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 0.5, pr: 6 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ lineHeight: 1.3 }}>
          {job.title || 'Untitled'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {job.company || '—'}{job.location ? ` · ${job.location}` : ''}
        </Typography>
        <IconButton onClick={onClose} sx={{ position: 'absolute', right: 8, top: 8 }} size="small">
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ py: 2 }}>
        {/* Score circle */}
        <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
          <Box sx={{ position: 'relative', display: 'inline-flex' }}>
            <CircularProgress
              variant="determinate"
              value={score * 100}
              size={56}
              thickness={5}
              sx={{ color: getScoreColor(score) }}
            />
            <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography sx={{ fontWeight: 800, fontSize: '0.85rem', color: getScoreColor(score) }}>
                {Math.round(score * 100)}%
              </Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="body2" fontWeight={600}>Match Score</Typography>
            <Typography variant="caption" color="text.secondary">
              {score >= 0.8 ? 'Excellent' : score >= 0.6 ? 'Good' : 'Low'} match
            </Typography>
          </Box>
          {job.url && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<LaunchIcon sx={{ fontSize: 14 }} />}
              href={job.url}
              target="_blank"
              rel="noopener"
              sx={{ textTransform: 'none', fontSize: '0.75rem' }}
            >
              LinkedIn
            </Button>
          )}
        </Stack>

        {/* Stage selector */}
        <FormControl size="small" fullWidth sx={{ mb: 2 }}>
          <InputLabel sx={{ fontSize: '0.8rem' }}>Stage</InputLabel>
          <Select value={stage} label="Stage" onChange={(e) => setStage(e.target.value)} sx={{ fontSize: '0.85rem' }}>
            {columns.map((col) => (
              <MenuItem key={col.id} value={col.id} sx={{ fontSize: '0.85rem' }}>{col.label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Notes */}
        <TextField
          label="Notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          multiline
          rows={3}
          fullWidth
          size="small"
          sx={{ mb: 2 }}
        />

        {/* Mini timeline */}
        <Divider sx={{ mb: 1 }} />
        <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: 0.5, mb: 0.5, display: 'block' }}>
          Timeline
        </Typography>
        <Stack spacing={0.25}>
          {job.discovered_at && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
              📡 Discovered {dayjs(job.discovered_at).fromNow()}
            </Typography>
          )}
          {job.scored_at && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
              📊 Scored {dayjs(job.scored_at).fromNow()}
            </Typography>
          )}
          {job.applied_at && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
              ✅ Applied {dayjs(job.applied_at).fromNow()}
            </Typography>
          )}
          {job.created_at && !job.discovered_at && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
              ➕ Added {dayjs(job.created_at).fromNow()}
            </Typography>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 2, py: 1, justifyContent: 'space-between' }}>
        <Button size="small" color="error" startIcon={<DeleteIcon sx={{ fontSize: 14 }} />} onClick={() => { onDelete(job.id); onClose(); }} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
          Delete
        </Button>
        <Stack direction="row" spacing={1}>
          {job.url && (
            <Button size="small" variant="outlined" href={job.url} target="_blank" rel="noopener" sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
              Apply Manually
            </Button>
          )}
          <Button size="small" variant="contained" onClick={handleSave} disabled={saving} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </Stack>
      </DialogActions>
    </Dialog>
  );
}

// ═══ MAIN BOARD ═══
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
  const [detailOpen, setDetailOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [newJob, setNewJob] = useState({ title: '', company: '', location: '', url: '', stage: 'discovered', notes: '' });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const loadJobs = useCallback(async () => {
    try {
      const data = await fetchJobs({ search, company: companyFilter, sort });
      setJobs(data.jobs || data || []);
    } catch (err) {
      console.error('Jobs fetch error', err);
    } finally {
      setLoading(false);
    }
  }, [search, companyFilter, sort]);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  const companies = useMemo(() => {
    const set = new Set(jobs.map((j) => j.company).filter(Boolean));
    return ['all', ...Array.from(set).sort()];
  }, [jobs]);

  const jobsByStage = useMemo(() => {
    const map = {};
    COLUMNS.forEach((col) => (map[col.id] = []));
    jobs.forEach((job) => {
      const stage = job.stage || 'discovered';
      if (map[stage]) map[stage].push(job);
      else map.discovered.push(job);
    });
    return map;
  }, [jobs]);

  const handleDragStart = (event) => {
    const job = jobs.find((j) => j.id === event.active.id);
    setActiveJob(job || null);
  };

  const handleDragEnd = async (event) => {
    setActiveJob(null);
    const { active, over } = event;
    if (!over) return;
    const jobId = active.id;
    const job = jobs.find((j) => j.id === jobId);
    if (!job) return;

    let targetStage = null;
    if (COLUMNS.find((c) => c.id === over.id)) {
      targetStage = over.id;
    } else {
      const overJob = jobs.find((j) => j.id === over.id);
      if (overJob) targetStage = overJob.stage;
    }
    if (!targetStage || targetStage === job.stage) return;

    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, stage: targetStage } : j)));
    try {
      await updateJobStage(jobId, targetStage);
    } catch (err) {
      enqueueSnackbar('Failed to move job', { variant: 'error' });
      loadJobs();
    }
  };

  const handleMenuOpen = (event, job) => { setMenuAnchor(event.currentTarget); setMenuJob(job); };
  const handleMenuClose = () => { setMenuAnchor(null); setMenuJob(null); };

  const handleMoveToStage = async (stage) => {
    if (!menuJob) return;
    handleMenuClose();
    setJobs((prev) => prev.map((j) => (j.id === menuJob.id ? { ...j, stage } : j)));
    try {
      await updateJobStage(menuJob.id, stage);
    } catch (err) {
      enqueueSnackbar('Failed to move job', { variant: 'error' });
      loadJobs();
    }
  };

  const handleDeleteJob = async (id) => {
    const jobId = id || menuJob?.id;
    if (!jobId) return;
    handleMenuClose();
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
    try {
      await deleteJob(jobId);
      enqueueSnackbar('Job deleted', { variant: 'info' });
    } catch (err) {
      enqueueSnackbar('Failed to delete job', { variant: 'error' });
      loadJobs();
    }
  };

  const handleCardClick = (job) => { setDetailJob(job); setDetailOpen(true); };

  const handleDetailUpdate = async (id, updates) => {
    try {
      await updateJob(id, updates);
      setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...updates } : j)));
      enqueueSnackbar('Job updated', { variant: 'success' });
      setDetailOpen(false);
    } catch (err) {
      enqueueSnackbar('Failed to update job', { variant: 'error' });
    }
  };

  const handleAddJob = async () => {
    try {
      await createJob(newJob);
      enqueueSnackbar('Job added', { variant: 'success' });
      setAddOpen(false);
      setNewJob({ title: '', company: '', location: '', url: '', stage: 'discovered', notes: '' });
      loadJobs();
    } catch (err) {
      enqueueSnackbar(err.message, { variant: 'error' });
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* ═══ TOP BAR ═══ */}
      <Box
        sx={{
          height: 44,
          minHeight: 44,
          display: 'flex',
          alignItems: 'center',
          px: 1.5,
          gap: 1,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <TextField
          size="small"
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{
            width: 180,
            '& .MuiOutlinedInput-root': { height: 30, fontSize: '0.75rem' },
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 16 }} />
              </InputAdornment>
            ),
          }}
        />
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <Select
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            displayEmpty
            sx={{ height: 30, fontSize: '0.72rem' }}
          >
            {companies.map((c) => (
              <MenuItem key={c} value={c} sx={{ fontSize: '0.75rem' }}>
                {c === 'all' ? 'All Companies' : c}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 100 }}>
          <Select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            displayEmpty
            sx={{ height: 30, fontSize: '0.72rem' }}
          >
            <MenuItem value="newest" sx={{ fontSize: '0.75rem' }}>Newest</MenuItem>
            <MenuItem value="oldest" sx={{ fontSize: '0.75rem' }}>Oldest</MenuItem>
            <MenuItem value="score_desc" sx={{ fontSize: '0.75rem' }}>Score ↓</MenuItem>
            <MenuItem value="score_asc" sx={{ fontSize: '0.75rem' }}>Score ↑</MenuItem>
          </Select>
        </FormControl>
        <Chip
          label={`${jobs.length} jobs`}
          size="small"
          sx={{ height: 20, fontSize: '0.65rem', fontWeight: 700 }}
        />
        <Box sx={{ flex: 1 }} />
        <Button
          size="small"
          variant="contained"
          startIcon={<AddIcon sx={{ fontSize: 14 }} />}
          onClick={() => setAddOpen(true)}
          sx={{ textTransform: 'none', fontSize: '0.72rem', height: 28, px: 1.5, boxShadow: 'none' }}
        >
          Add Job
        </Button>
      </Box>

      {/* ═══ KANBAN AREA ═══ */}
      <Box sx={{ flex: 1, overflow: 'hidden', p: 1 }}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <Box
            sx={{
              display: 'flex',
              gap: '8px',
              height: '100%',
              overflowX: 'auto',
              '&::-webkit-scrollbar': { height: 5 },
              '&::-webkit-scrollbar-thumb': { bgcolor: 'divider', borderRadius: 3 },
            }}
          >
            {COLUMNS.map((col) => (
              <SortableContext
                key={col.id}
                id={col.id}
                items={(jobsByStage[col.id] || []).map((j) => j.id)}
                strategy={verticalListSortingStrategy}
              >
                <KanbanColumn
                  column={col}
                  jobs={jobsByStage[col.id] || []}
                  onMenuOpen={handleMenuOpen}
                  onCardClick={handleCardClick}
                />
              </SortableContext>
            ))}
          </Box>
          <DragOverlay>
            <DragOverlayCard job={activeJob} />
          </DragOverlay>
        </DndContext>
      </Box>

      {/* Context Menu */}
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={handleMenuClose}
        slotProps={{ paper: { sx: { minWidth: 130 } } }}
      >
        {COLUMNS.filter((c) => c.id !== menuJob?.stage).map((col) => (
          <MenuItem key={col.id} onClick={() => handleMoveToStage(col.id)} sx={{ fontSize: '0.75rem', py: 0.5 }}>
            Move → {col.label}
          </MenuItem>
        ))}
        <Divider />
        <MenuItem onClick={() => handleDeleteJob()} sx={{ fontSize: '0.75rem', py: 0.5, color: 'error.main' }}>
          Delete
        </MenuItem>
      </Menu>

      {/* Job Detail Modal */}
      <JobDetailDialog
        job={detailJob}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        onUpdate={handleDetailUpdate}
        onDelete={handleDeleteJob}
        columns={COLUMNS}
      />

      {/* Add Job Dialog */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ pb: 0.5, fontSize: '0.95rem' }}>Add Job</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <Stack spacing={1.5} sx={{ mt: 0.5 }}>
            <TextField size="small" label="Job Title" value={newJob.title} onChange={(e) => setNewJob((p) => ({ ...p, title: e.target.value }))} fullWidth required />
            <TextField size="small" label="Company" value={newJob.company} onChange={(e) => setNewJob((p) => ({ ...p, company: e.target.value }))} fullWidth />
            <TextField size="small" label="Location" value={newJob.location} onChange={(e) => setNewJob((p) => ({ ...p, location: e.target.value }))} fullWidth />
            <TextField size="small" label="URL" value={newJob.url} onChange={(e) => setNewJob((p) => ({ ...p, url: e.target.value }))} fullWidth />
            <FormControl size="small" fullWidth>
              <InputLabel>Stage</InputLabel>
              <Select value={newJob.stage} label="Stage" onChange={(e) => setNewJob((p) => ({ ...p, stage: e.target.value }))}>
                {COLUMNS.map((col) => (<MenuItem key={col.id} value={col.id}>{col.label}</MenuItem>))}
              </Select>
            </FormControl>
            <TextField size="small" label="Notes" value={newJob.notes} onChange={(e) => setNewJob((p) => ({ ...p, notes: e.target.value }))} fullWidth multiline rows={2} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 1.5 }}>
          <Button size="small" onClick={() => setAddOpen(false)} sx={{ textTransform: 'none' }}>Cancel</Button>
          <Button size="small" variant="contained" onClick={handleAddJob} disabled={!newJob.title} sx={{ textTransform: 'none' }}>Add</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
