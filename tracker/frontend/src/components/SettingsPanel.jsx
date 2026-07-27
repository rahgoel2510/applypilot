import { useState, useEffect } from 'react';
import {
  Settings, Shield, Eye, EyeOff, Save, Check, AlertCircle,
  Key, Bot, Brain, Globe, Lock, RefreshCw, Plug, Loader2, X,
} from 'lucide-react';
import { getSettings, updateSettings, testConnection, fetchFreeModels } from '../api';

const GROUP_ICONS = {
  Telegram: Bot,
  'AI (OpenRouter)': Brain,
  LinkedIn: Globe,
};

const GROUP_COLORS = {
  Telegram: { bg: 'bg-sky-50', border: 'border-sky-200', icon: 'text-sky-600', badge: 'bg-sky-100 text-sky-700' },
  'AI (OpenRouter)': { bg: 'bg-purple-50', border: 'border-purple-200', icon: 'text-purple-600', badge: 'bg-purple-100 text-purple-700' },
  LinkedIn: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'text-blue-600', badge: 'bg-blue-100 text-blue-700' },
};

export default function SettingsPanel() {
  const [settings, setSettings] = useState([]);
  const [configured, setConfigured] = useState(0);
  const [total, setTotal] = useState(0);
  const [editValues, setEditValues] = useState({});
  const [visibleFields, setVisibleFields] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testResults, setTestResults] = useState({});
  const [testing, setTesting] = useState({});
  const [freeModels, setFreeModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  const loadSettings = async () => {
    try {
      const data = await getSettings();
      setSettings(data.settings);
      setConfigured(data.configured);
      setTotal(data.total);
      setEditValues({});
    } catch (e) {
      console.error('Failed to load settings:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSettings(); }, []);

  const handleSave = async () => {
    // Only send non-empty values
    const nonEmpty = Object.fromEntries(
      Object.entries(editValues).filter(([_, v]) => v.trim().length > 0)
    );
    if (Object.keys(nonEmpty).length === 0) {
      setMessage({ type: 'info', text: 'No changes to save.' });
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      const result = await updateSettings(nonEmpty);
      setMessage({ type: 'success', text: result.message });
      setEditValues({});
      await loadSettings();
    } catch (e) {
      setMessage({ type: 'error', text: 'Failed to save settings.' });
    } finally {
      setSaving(false);
    }
  };

  const toggleVisibility = (key) => {
    setVisibleFields(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const hasChanges = Object.values(editValues).some(v => v.trim().length > 0);
  const currentAiModel = settings.find(s => s.key === 'AI_MODEL')?.masked_value || '';

  const handleTestConnection = async (group) => {
    const serviceMap = { Telegram: 'telegram', 'AI (OpenRouter)': 'openai', LinkedIn: 'linkedin' };
    const service = serviceMap[group];
    if (!service) return;

    setTesting(prev => ({ ...prev, [group]: true }));
    setTestResults(prev => ({ ...prev, [group]: null }));
    try {
      const result = await testConnection(service);
      setTestResults(prev => ({ ...prev, [group]: result }));

      // If AI test succeeded, fetch available free models
      if (group === 'AI (OpenRouter)' && result.success) {
        setModelsLoading(true);
        try {
          const modelsData = await fetchFreeModels();
          setFreeModels(modelsData.models || []);
        } catch (e) { /* ignore */ }
        finally { setModelsLoading(false); }
      }
    } catch (e) {
      setTestResults(prev => ({ ...prev, [group]: { success: false, message: 'Request failed' } }));
    } finally {
      setTesting(prev => ({ ...prev, [group]: false }));
    }
  };

  // Group settings
  const groups = {};
  settings.forEach(s => {
    if (!groups[s.group]) groups[s.group] = [];
    groups[s.group].push(s);
  });

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-[#8291A5]">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading settings...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-slate-700 to-slate-900 shadow-md">
            <Settings className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-[#203A5F]">Settings</h1>
            <p className="text-sm text-[#708198]">
              Configure API keys and credentials · <span className="text-teal-600 font-medium">{configured}/{total} configured</span>
            </p>
          </div>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold shadow-sm transition-all ${
            hasChanges
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:shadow-md hover:-translate-y-0.5'
              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
          }`}
        >
          {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save Changes
        </button>
      </div>

      {/* Security notice */}
      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <Shield className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-amber-900">Secrets are stored securely</p>
          <p className="mt-0.5 text-xs text-amber-700">
            Values are saved to your local <code className="rounded bg-amber-100 px-1">.env</code> file. 
            They are never exposed in full to the browser — only masked previews are shown.
            Restart the agent after making changes.
          </p>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${
          message.type === 'success' ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' :
          message.type === 'error' ? 'bg-red-50 border border-red-200 text-red-700' :
          'bg-blue-50 border border-blue-200 text-blue-700'
        }`}>
          {message.type === 'success' ? <Check className="h-4 w-4" /> :
           message.type === 'error' ? <AlertCircle className="h-4 w-4" /> :
           <AlertCircle className="h-4 w-4" />}
          {message.text}
        </div>
      )}

      {/* Settings groups */}
      {Object.entries(groups).map(([groupName, fields]) => {
        const GroupIcon = GROUP_ICONS[groupName] || Key;
        const colors = GROUP_COLORS[groupName] || GROUP_COLORS.LinkedIn;

        return (
          <div key={groupName} className={`rounded-2xl border ${colors.border} ${colors.bg} p-5`}>
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GroupIcon className={`h-5 w-5 ${colors.icon}`} />
                <h3 className="text-base font-semibold text-[#0f172a]">{groupName}</h3>
                <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold ${colors.badge}`}>
                  {fields.filter(f => f.is_set).length}/{fields.length}
                </span>
              </div>
              <button
                onClick={() => handleTestConnection(groupName)}
                disabled={testing[groupName] || !fields.some(f => f.is_set)}
                className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-all hover:bg-slate-50 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {testing[groupName] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />}
                Test Connection
              </button>
            </div>

            {/* Test result */}
            {testResults[groupName] && (
              <div className={`mb-4 flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm ${
                testResults[groupName].success
                  ? 'bg-emerald-100 border border-emerald-200 text-emerald-800'
                  : 'bg-red-100 border border-red-200 text-red-800'
              }`}>
                {testResults[groupName].success ? <Check className="h-4 w-4 flex-shrink-0" /> : <AlertCircle className="h-4 w-4 flex-shrink-0" />}
                <span className="flex-1">{testResults[groupName].message}</span>
                <button onClick={() => setTestResults(prev => ({ ...prev, [groupName]: null }))} className="p-0.5 hover:opacity-70">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            {/* Model selector — shown after successful AI test */}
            {groupName === 'AI (OpenRouter)' && testResults[groupName]?.success && freeModels.length > 0 && (
              <div className="mb-4 rounded-xl border border-purple-200 bg-purple-50/50 p-4">
                <label className="mb-3 flex items-center gap-2 text-sm font-semibold text-purple-800">
                  <Brain className="h-4 w-4" />
                  Choose a Model ({freeModels.length} free models available)
                </label>
                <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                  {/* Auto option */}
                  <ModelOption
                    model={{ id: 'openrouter/free', name: 'Auto (Free Router)', tier: 'standard', context_length: 0, capabilities: ['auto-select'], description: 'Automatically picks the best available free model for each request.' }}
                    selected={(!editValues['AI_MODEL'] && !currentAiModel) || editValues['AI_MODEL'] === 'openrouter/free'}
                    onSelect={() => setEditValues(prev => ({ ...prev, AI_MODEL: 'openrouter/free' }))}
                  />
                  {freeModels.map(m => (
                    <ModelOption
                      key={m.id}
                      model={m}
                      selected={editValues['AI_MODEL'] === m.id}
                      onSelect={() => setEditValues(prev => ({ ...prev, AI_MODEL: m.id }))}
                    />
                  ))}
                </div>
                <p className="mt-3 text-[11px] text-purple-600">
                  Selected model is used for InMail drafting. Higher-tier models write better messages.
                </p>
                {modelsLoading && <p className="mt-1 text-xs text-purple-500 animate-pulse">Loading models...</p>}
              </div>
            )}

            <div className="space-y-4">
              {fields.map(field => (
                <SettingField
                  key={field.key}
                  field={field}
                  editValue={editValues[field.key] || ''}
                  onEditChange={(val) => setEditValues(prev => ({ ...prev, [field.key]: val }))}
                  visible={visibleFields[field.key]}
                  onToggleVisibility={() => toggleVisibility(field.key)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SettingField({ field, editValue, onEditChange, visible, onToggleVisibility }) {
  const isEditing = editValue.length > 0;

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Lock className="h-3.5 w-3.5 text-slate-400" />
          <label className="text-sm font-medium text-slate-800">{field.label}</label>
        </div>
        <div className="flex items-center gap-2">
          {field.is_set && !isEditing && (
            <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
              <Check className="h-2.5 w-2.5" /> Set
            </span>
          )}
          {isEditing && (
            <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
              Modified
            </span>
          )}
        </div>
      </div>

      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={editValue || ''}
          onChange={(e) => onEditChange(e.target.value)}
          placeholder={field.is_set ? field.masked_value : field.placeholder}
          autoComplete="off"
          spellCheck="false"
          className={`w-full rounded-lg border-2 py-2.5 pl-4 pr-10 text-sm font-mono outline-none transition-all ${
            isEditing
              ? 'border-amber-300 bg-amber-50/50 text-slate-800 ring-2 ring-amber-100'
              : 'border-slate-200 bg-slate-50 text-slate-600 placeholder:text-slate-400 focus:border-teal-400 focus:bg-white focus:ring-2 focus:ring-teal-100'
          }`}
        />
        <button
          type="button"
          onClick={onToggleVisibility}
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:text-slate-600"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>

      {field.is_set && !isEditing && (
        <p className="mt-1.5 text-[11px] text-slate-400">
          Leave empty to keep current value. Enter a new value to update.
        </p>
      )}
    </div>
  );
}

function ModelOption({ model, selected, onSelect }) {
  const tierColors = {
    high: 'border-amber-300 bg-amber-50',
    medium: 'border-purple-200 bg-purple-50/50',
    standard: 'border-slate-200 bg-white',
  };
  const tierLabels = {
    high: { text: '⚡ Best', className: 'bg-amber-100 text-amber-800' },
    medium: { text: '✦ Good', className: 'bg-purple-100 text-purple-800' },
    standard: { text: '○ Basic', className: 'bg-slate-100 text-slate-600' },
  };
  const capabilityIcons = {
    'long-context': '📚',
    'code': '💻',
    'text': '📝',
    'tools': '🔧',
    'auto-select': '🎲',
  };

  const tier = tierLabels[model.tier] || tierLabels.standard;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-xl border-2 p-3 text-left transition-all ${
        selected
          ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-500/20'
          : `${tierColors[model.tier] || tierColors.standard} hover:border-purple-300 hover:shadow-sm`
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {selected && <span className="flex h-4 w-4 items-center justify-center rounded-full bg-purple-600 text-[9px] text-white">✓</span>}
          <span className="text-sm font-semibold text-slate-800">{model.name}</span>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${tier.className}`}>
          {tier.text}
        </span>
      </div>
      {model.description && (
        <p className="mt-1 text-[11px] text-slate-500 line-clamp-1">{model.description}</p>
      )}
      <div className="mt-1.5 flex items-center gap-2 flex-wrap">
        {model.context_length > 0 && (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
            {Math.round(model.context_length / 1000)}k context
          </span>
        )}
        {(model.capabilities || []).map(cap => (
          <span key={cap} className="text-[10px]">{capabilityIcons[cap] || '•'} {cap}</span>
        ))}
      </div>
    </button>
  );
}
