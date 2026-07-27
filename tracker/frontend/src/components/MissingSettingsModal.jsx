import { useState, useEffect } from 'react';
import { AlertTriangle, Eye, EyeOff, Save, X, Shield, Loader2 } from 'lucide-react';
import { updateSettings, fetchFreeModels } from '../api';

export default function MissingSettingsModal({ isOpen, onClose, missingFields, onSaved }) {
  const [values, setValues] = useState({});
  const [visible, setVisible] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  // Load models if AI_MODEL is in missing fields
  useEffect(() => {
    if (!isOpen || !missingFields) return;
    const hasModelField = missingFields.some(f => f.key === 'AI_MODEL');
    if (hasModelField) {
      setModelsLoading(true);
      fetchFreeModels()
        .then(data => setModels(data.models || []))
        .catch(() => {})
        .finally(() => setModelsLoading(false));
    }
  }, [isOpen, missingFields]);

  if (!isOpen || !missingFields || missingFields.length === 0) return null;

  const handleSave = async () => {
    const empty = missingFields.filter(f => !values[f.key]?.trim());
    if (empty.length > 0) {
      setError(`Please fill in: ${empty.map(f => f.label).join(', ')}`);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await updateSettings(values);
      onSaved();
      onClose();
    } catch (e) {
      setError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const renderField = (field) => {
    // AI_MODEL gets a dropdown
    if (field.key === 'AI_MODEL') {
      return (
        <div key={field.key}>
          <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-slate-700">
            <Shield className="h-3.5 w-3.5 text-purple-400" />
            {field.label}
            <span className="text-red-500">*</span>
          </label>
          {modelsLoading ? (
            <div className="flex items-center gap-2 rounded-xl border-2 border-slate-200 bg-slate-50 py-3 px-4 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading available models...
            </div>
          ) : (
            <select
              value={values[field.key] || ''}
              onChange={(e) => setValues(prev => ({ ...prev, [field.key]: e.target.value }))}
              className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 py-2.5 px-4 text-sm outline-none transition-all focus:border-teal-400 focus:bg-white focus:ring-4 focus:ring-teal-400/10"
            >
              <option value="">— Select a model —</option>
              <option value="openrouter/free">🎲 Auto (Free Router — best available)</option>
              {models.map(m => (
                <option key={m.id} value={m.id}>
                  {m.tier === 'high' ? '⚡' : m.tier === 'medium' ? '✦' : '○'} {m.name}
                  {m.context_length ? ` (${Math.round(m.context_length/1000)}k)` : ''}
                </option>
              ))}
            </select>
          )}
          <p className="mt-1 text-[11px] text-slate-400">
            Used for InMail drafting. "Auto" picks the best free model automatically.
          </p>
        </div>
      );
    }

    // Default: password/text input
    return (
      <div key={field.key}>
        <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-slate-700">
          <Shield className="h-3.5 w-3.5 text-slate-400" />
          {field.label}
          <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <input
            type={visible[field.key] ? 'text' : 'password'}
            value={values[field.key] || ''}
            onChange={(e) => setValues(prev => ({ ...prev, [field.key]: e.target.value }))}
            placeholder={field.placeholder}
            autoComplete="off"
            className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 py-2.5 pl-4 pr-10 text-sm font-mono outline-none transition-all focus:border-teal-400 focus:bg-white focus:ring-4 focus:ring-teal-400/10"
          />
          <button
            type="button"
            onClick={() => setVisible(prev => ({ ...prev, [field.key]: !prev[field.key] }))}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            {visible[field.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl mx-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">Configuration Required</h2>
              <p className="text-sm text-slate-500">The agent needs these settings before it can run.</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Fields */}
        <div className="space-y-4 mb-5">
          {missingFields.map(renderField)}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between">
          <p className="text-[11px] text-slate-400">
            Saved securely. Changes apply instantly.
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:shadow-md transition-all disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {saving ? 'Saving...' : 'Save & Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
