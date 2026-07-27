import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Plus } from 'lucide-react';
import JobCard from './JobCard';

export default function KanbanColumn({ column, jobs, onAddJob, onDelete, onMoveStage }) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const Icon = column.icon;
  const count = jobs.length;

  return (
    <div className="w-80 flex-shrink-0 rounded-xl bg-[#F6F8FB]">
      {/* Column header */}
      <div className="sticky top-0 z-10 flex items-center justify-between rounded-t-xl bg-[#F6F8FB] px-3 pb-2 pt-4 relative">
        <span
          aria-hidden="true"
          className={`absolute inset-x-3 top-0 h-[3px] rounded-full ${column.barColor}`}
        />
        <div className={`flex items-center gap-2 font-medium ${column.textColor}`}>
          <Icon className="h-4 w-4" />
          <span className="text-sm">{column.label}</span>
          <span
            className={`ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-xs font-semibold ${column.badgeBg} ${column.badgeText}`}
          >
            {count}
          </span>
        </div>
        <button
          onClick={() => onAddJob(column.id)}
          className={`rounded-md p-1 text-[#8291A5] transition-colors ${column.hoverBg} hover:${column.textColor}`}
          title={`Add job to ${column.label}`}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Droppable area */}
      <div
        ref={setNodeRef}
        className={`min-h-[60vh] space-y-3 rounded-b-xl p-3 pt-1 transition-all ${
          isOver ? 'bg-[#DDF7F6] ring-2 ring-inset ring-dashed ring-[#18B8BC]' : 'bg-transparent'
        }`}
      >
        <SortableContext items={jobs.map((j) => j.id)} strategy={verticalListSortingStrategy}>
          {jobs.length > 0 ? (
            jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onDelete={onDelete}
                onMoveStage={onMoveStage}
              />
            ))
          ) : (
            <EmptyState column={column} onAddJob={onAddJob} />
          )}
        </SortableContext>
      </div>
    </div>
  );
}

function EmptyState({ column, onAddJob }) {
  const Icon = column.icon;
  return (
    <div className="flex min-h-[160px] w-full flex-col items-center justify-center rounded-lg px-5 py-6 text-center">
      <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-sm ${column.textColor}`}>
        <Icon className="h-4 w-4" />
      </div>
      <p className="text-sm font-semibold text-[#294A73]">{column.emptyText}</p>
      <p className="mt-1 max-w-[220px] text-xs leading-5 text-[#8291A5]">
        {column.emptyHint}
      </p>
      <button
        type="button"
        onClick={() => onAddJob(column.id)}
        className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-[#117D84] shadow-sm ring-1 ring-inset ring-[#C9E7E6] transition-colors hover:bg-[#ECFAFA]"
      >
        <Plus className="h-3.5 w-3.5" />
        Add job
      </button>
    </div>
  );
}
