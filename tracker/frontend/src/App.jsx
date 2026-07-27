import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { Plus, LayoutDashboard, Columns3, Activity, Bot } from 'lucide-react';
import { COLUMNS } from './columns';
import KanbanColumn from './components/KanbanColumn';
import JobCard from './components/JobCard';
import AddJobModal from './components/AddJobModal';
import SearchBar from './components/SearchBar';
import Dashboard from './components/Dashboard';
import ActivityFeed from './components/ActivityFeed';
import AgentControlPanel from './components/AgentControlPanel';
import { fetchJobs, createJob, updateJobStage, deleteJob } from './api';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'board', label: 'Board', icon: Columns3 },
  { id: 'activity', label: 'Activity Log', icon: Activity },
];

export default function App() {
  // URL-based tab routing
  const getTabFromHash = () => {
    const hash = window.location.hash.replace('#', '');
    return TABS.find(t => t.id === hash)?.id || 'dashboard';
  };

  const [activeTab, setActiveTab] = useState(getTabFromHash);
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

  // Sync tab with URL hash
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    window.location.hash = tabId;
  };

  useEffect(() => {
    const onHashChange = () => setActiveTab(getTabFromHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Fetch jobs
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

  // Derived data
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

  // Handlers
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

  // DnD
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
    <div className="min-h-screen bg-[#f0f4f8]">
      {/* Top navigation */}
      <header className="sticky top-0 z-40 border-b border-[#DCE5ED] bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#18B8BC] to-[#117D84]">
                <Columns3 className="h-4 w-4 text-white" />
              </div>
              <span className="text-lg font-bold text-[#203A5F]">Job Tracker</span>
            </div>

            {/* Tabs */}
            <nav className="flex items-center gap-1">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => handleTabChange(id)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    activeTab === id
                      ? 'bg-[#ECFAFA] text-[#117D84]'
                      : 'text-[#52677F] hover:bg-[#F6F8FB] hover:text-[#203A5F]'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </nav>
          </div>

          {/* Add job button (always visible) */}
          <button
            onClick={() => openAddModal('saved')}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white shadow-sm hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add Job
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-[1600px] p-6">
        {activeTab === 'dashboard' && <Dashboard />}

        {activeTab === 'agent' && <AgentControlPanel />}

        {activeTab === 'board' && (
          <>
            {/* Search bar */}
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

            {/* Kanban board */}
            {loading ? (
              <div className="flex h-64 items-center justify-center text-[#8291A5]">Loading...</div>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCorners}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragEnd={handleDragEnd}
              >
                <div className="flex gap-4 overflow-x-auto pb-4">
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
                </div>
                <DragOverlay>
                  {activeJob && (
                    <div className="rotate-3 scale-105">
                      <JobCard job={activeJob} onDelete={() => {}} onMoveStage={() => {}} />
                    </div>
                  )}
                </DragOverlay>
              </DndContext>
            )}
          </>
        )}

        {activeTab === 'activity' && <ActivityFeed compact={false} limit={100} />}
      </main>

      {/* Add Job Modal */}
      <AddJobModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleAddJob}
        defaultStage={modalStage}
      />
    </div>
  );
}
