import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { Box, Button, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { COLUMNS } from '../columns';
import KanbanColumn from './KanbanColumn';
import JobCard from './JobCard';
import AddJobModal from './AddJobModal';
import SearchBar from './SearchBar';
import { fetchJobs, createJob, updateJobStage, deleteJob } from '../api';

export default function Board() {
  const [jobs, setJobs] = useState([]);
  const [search, setSearch] = useState('');
  const [companyFilter, setCompanyFilter] = useState('all');
  const [sort, setSort] = useState('newest');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalStage, setModalStage] = useState('saved');
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(true);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const loadJobs = useCallback(async () => {
    try {
      const data = await fetchJobs({ company: companyFilter, search, sort });
      setJobs(data);
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  }, [companyFilter, search, sort]);

  useEffect(() => { loadJobs(); }, [loadJobs]);
  useEffect(() => {
    const interval = setInterval(loadJobs, 10000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  const companies = useMemo(() => [...new Set(jobs.map((j) => j.company))].sort(), [jobs]);

  const filteredJobs = useMemo(() => {
    let result = jobs;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) => j.title.toLowerCase().includes(q) || j.company.toLowerCase().includes(q) || (j.location && j.location.toLowerCase().includes(q))
      );
    }
    if (companyFilter !== 'all') {
      result = result.filter((j) => j.company === companyFilter);
    }
    return result;
  }, [jobs, search, companyFilter]);

  const jobsByStage = useMemo(() => {
    const map = {};
    COLUMNS.forEach((col) => (map[col.id] = []));
    filteredJobs.forEach((j) => { if (map[j.stage]) map[j.stage].push(j); });
    return map;
  }, [filteredJobs]);

  const handleAddJob = async (jobData) => {
    try {
      const created = await createJob(jobData);
      setJobs((prev) => [created, ...prev]);
    } catch (err) { console.error('Failed to create job:', err); }
  };

  const handleDeleteJob = async (id) => {
    try {
      await deleteJob(id);
      setJobs((prev) => prev.filter((j) => j.id !== id));
    } catch (err) { console.error('Failed to delete job:', err); }
  };

  const handleMoveStage = async (id, newStage) => {
    try {
      const updated = await updateJobStage(id, newStage);
      setJobs((prev) => prev.map((j) => (j.id === id ? updated : j)));
    } catch (err) { console.error('Failed to move job:', err); }
  };

  const handleDragStart = (event) => setActiveId(event.active.id);
  const handleDragEnd = async (event) => {
    const { active, over } = event;
    setActiveId(null);
    if (!over) return;
    const targetColumnId = over.id;
    if (COLUMNS.some((c) => c.id === targetColumnId)) {
      const job = jobs.find((j) => j.id === active.id);
      if (job && job.stage !== targetColumnId) handleMoveStage(active.id, targetColumnId);
    }
  };
  const handleDragOver = (event) => {
    const { active, over } = event;
    if (!over) return;
    const targetColumnId = over.id;
    if (COLUMNS.some((c) => c.id === targetColumnId)) {
      const job = jobs.find((j) => j.id === active.id);
      if (job && job.stage !== targetColumnId) {
        setJobs((prev) => prev.map((j) => (j.id === active.id ? { ...j, stage: targetColumnId } : j)));
      }
    }
  };

  const activeJob = activeId ? jobs.find((j) => j.id === activeId) : null;
  const openAddModal = (stage) => { setModalStage(stage); setModalOpen(true); };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4">Board</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => openAddModal('saved')}>
          Add Job
        </Button>
      </Box>

      <SearchBar
        search={search}
        onSearchChange={setSearch}
        company={companyFilter}
        onCompanyChange={setCompanyFilter}
        sort={sort}
        onSortChange={setSort}
        companies={companies}
        totalJobs={jobs.length}
        filteredJobs={filteredJobs.length}
      />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <Typography color="text.secondary">Loading...</Typography>
        </Box>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 2 }}>
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.id}
                column={col}
                jobs={jobsByStage[col.id] || []}
                onAddJob={openAddModal}
                onDelete={handleDeleteJob}
                onMoveStage={handleMoveStage}
              />
            ))}
          </Box>
          <DragOverlay>
            {activeJob && (
              <div style={{ transform: 'rotate(3deg) scale(1.05)' }}>
                <JobCard job={activeJob} onDelete={() => {}} onMoveStage={() => {}} />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      <AddJobModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleAddJob}
        defaultStage={modalStage}
      />
    </Box>
  );
}
