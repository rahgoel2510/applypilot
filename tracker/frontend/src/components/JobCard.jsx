import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { MapPin, Calendar, ExternalLink, Ellipsis, Zap, Trash2, ArrowRight } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { COLUMNS } from '../columns';

export default function JobCard({ job, onDelete, onMoveStage }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: job.id, data: { job } });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  const initial = (job.company || '?')[0].toUpperCase();
  const dateStr = job.date_added
    ? new Date(job.date_added).toLocaleDateString('en-US')
    : '';

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="group cursor-grab rounded-lg border border-[#DCE5ED] bg-white p-3 shadow-sm transition-[box-shadow,transform] active:cursor-grabbing hover:-translate-y-0.5 hover:shadow-md"
    >
      {/* Header: avatar + title + menu */}
      <div className="flex items-start gap-2.5">
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#E9F3F7] text-xs font-semibold uppercase text-[#294A73]">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <p
            className="line-clamp-2 text-[15px] font-semibold leading-5 text-[#203A5F]"
            title={job.title}
          >
            {job.title}
          </p>
          <p className="mt-0.5 truncate text-sm text-[#52677F]" title={job.company}>
            {job.company}
          </p>
        </div>
        {/* More menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen(!menuOpen);
            }}
            onPointerDown={(e) => e.stopPropagation()}
            className="rounded-md p-1.5 text-[#8291A5] opacity-0 transition-opacity hover:bg-[#ECFAFA] hover:text-[#117D84] group-hover:opacity-100 focus:opacity-100"
            title="More"
          >
            <Ellipsis className="h-5 w-5" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-8 z-50 w-44 rounded-lg border border-[#DCE5ED] bg-white py-1 shadow-lg">
              {COLUMNS.filter((c) => c.id !== job.stage).map((col) => (
                <button
                  key={col.id}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[#52677F] hover:bg-[#F6F8FB]"
                  onClick={(e) => {
                    e.stopPropagation();
                    onMoveStage(job.id, col.id);
                    setMenuOpen(false);
                  }}
                  onPointerDown={(e) => e.stopPropagation()}
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                  Move to {col.label}
                </button>
              ))}
              <hr className="my-1 border-[#EDF1F5]" />
              <button
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(job.id);
                  setMenuOpen(false);
                }}
                onPointerDown={(e) => e.stopPropagation()}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Meta: location + date */}
      <div className="mt-3 flex min-w-0 items-center gap-3 text-xs text-[#8291A5]">
        {job.location && (
          <span className="flex min-w-0 items-center gap-1">
            <MapPin className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{job.location}</span>
          </span>
        )}
        {dateStr && (
          <span className="ml-auto flex flex-shrink-0 items-center gap-1">
            <Calendar className="h-3 w-3" />
            {dateStr}
          </span>
        )}
      </div>

      {/* Footer: match score + link */}
      <div className="mt-3 flex items-center justify-between border-t border-[#EDF1F5] pt-2.5">
        {job.match_score ? (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-[#EAF4FF] px-2.5 py-1.5 text-xs font-semibold text-[#2F6EA5] ring-1 ring-inset ring-[#CFE3F5]">
            <Zap className="h-3.5 w-3.5" />
            {Math.round(job.match_score * 100)}% match
          </span>
        ) : (
          <span />
        )}
        {job.posting_url && (
          <a
            href={job.posting_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-[#60758D] transition-colors hover:text-[#294A73]"
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
          >
            View posting
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}
