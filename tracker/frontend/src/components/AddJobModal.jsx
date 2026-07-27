import { useState } from 'react';
import { X } from 'lucide-react';
import { COLUMNS } from '../columns';

export default function AddJobModal({ isOpen, onClose, onSubmit, defaultStage }) {
  const [form, setForm] = useState({
    title: '',
    company: '',
    location: '',
    stage: defaultStage || 'saved',
    posting_url: '',
    match_score: '',
    notes: '',
  });

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.company.trim()) return;
    onSubmit({
      ...form,
      match_score: form.match_score ? parseFloat(form.match_score) / 100 : null,
      posting_url: form.posting_url || null,
      notes: form.notes || null,
      location: form.location || null,
    });
    setForm({
      title: '',
      company: '',
      location: '',
      stage: defaultStage || 'saved',
      posting_url: '',
      match_score: '',
      notes: '',
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[#203A5F]">Add Job</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-[#8291A5] hover:bg-[#F6F8FB] hover:text-[#203A5F]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-[#52677F] mb-1">
              Job Title *
            </label>
            <input
              type="text"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
              placeholder="e.g. Senior Backend Engineer"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#52677F] mb-1">
              Company *
            </label>
            <input
              type="text"
              required
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
              className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
              placeholder="e.g. TechCorp"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[#52677F] mb-1">
                Location
              </label>
              <input
                type="text"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
                placeholder="e.g. Bangalore"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#52677F] mb-1">
                Stage
              </label>
              <select
                value={form.stage}
                onChange={(e) => setForm({ ...form, stage: e.target.value })}
                className="w-full rounded-lg border border-[#DCE5ED] bg-white px-3 py-2 text-sm text-[#52677F] outline-none focus:border-[#18B8BC] focus:ring-2 focus:ring-[#CEF2F1]"
              >
                {COLUMNS.map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[#52677F] mb-1">
                Match Score (%)
              </label>
              <input
                type="number"
                min="0"
                max="100"
                value={form.match_score}
                onChange={(e) => setForm({ ...form, match_score: e.target.value })}
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
                placeholder="85"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#52677F] mb-1">
                Posting URL
              </label>
              <input
                type="url"
                value={form.posting_url}
                onChange={(e) => setForm({ ...form, posting_url: e.target.value })}
                className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
                placeholder="https://..."
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#52677F] mb-1">
              Notes
            </label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={2}
              className="w-full rounded-lg border border-[#DCE5ED] bg-[#F8FAFC] px-3 py-2 text-sm text-[#203A5F] outline-none focus:border-[#18B8BC] focus:bg-white focus:ring-2 focus:ring-[#CEF2F1]"
              placeholder="Any notes about this job..."
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[#DCE5ED] px-4 py-2 text-sm text-[#52677F] hover:bg-[#F6F8FB]"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 shadow-sm"
            >
              Add Job
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
