const BASE_URL = '/api';

export async function fetchJobs({ stage, company, search, sort } = {}) {
  const params = new URLSearchParams();
  if (stage && stage !== 'all') params.append('stage', stage);
  if (company && company !== 'all') params.append('company', company);
  if (search) params.append('search', search);
  if (sort) params.append('sort', sort);

  const res = await fetch(`${BASE_URL}/jobs?${params}`);
  if (!res.ok) throw new Error('Failed to fetch jobs');
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${BASE_URL}/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function createJob(job) {
  const res = await fetch(`${BASE_URL}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(job),
  });
  if (!res.ok) throw new Error('Failed to create job');
  return res.json();
}

export async function updateJob(id, job) {
  const res = await fetch(`${BASE_URL}/jobs/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(job),
  });
  if (!res.ok) throw new Error('Failed to update job');
  return res.json();
}

export async function updateJobStage(id, stage) {
  const res = await fetch(`${BASE_URL}/jobs/${id}/stage`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage }),
  });
  if (!res.ok) throw new Error('Failed to update stage');
  return res.json();
}

export async function deleteJob(id) {
  const res = await fetch(`${BASE_URL}/jobs/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete job');
}

export async function fetchLogs({ page = 1, pageSize = 50, eventType, severity, search } = {}) {
  const params = new URLSearchParams();
  params.append('page', page);
  params.append('page_size', pageSize);
  if (eventType) params.append('event_type', eventType);
  if (severity) params.append('severity', severity);
  if (search) params.append('search', search);

  const res = await fetch(`${BASE_URL}/logs?${params}`);
  if (!res.ok) throw new Error('Failed to fetch logs');
  return res.json();
}

// Agent Control API
export async function triggerAgent({ mode = 'single', dryRun = true, limit = null, matchThreshold = null, collection = 'Recommended' } = {}) {
  const res = await fetch(`${BASE_URL}/agent/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode,
      dry_run: dryRun,
      limit,
      match_threshold: matchThreshold,
      collection,
    }),
  });
  if (!res.ok) throw new Error('Failed to trigger agent');
  return res.json();
}

export async function stopAgent() {
  const res = await fetch(`${BASE_URL}/agent/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop agent');
  return res.json();
}

export async function getAgentStatus() {
  const res = await fetch(`${BASE_URL}/agent/status`);
  if (!res.ok) throw new Error('Failed to get agent status');
  return res.json();
}

export async function getAgentOutput(tail = 100) {
  const res = await fetch(`${BASE_URL}/agent/output?tail=${tail}`);
  if (!res.ok) throw new Error('Failed to get agent output');
  return res.json();
}

export async function getAgentRuns(limit = 20) {
  const res = await fetch(`${BASE_URL}/agent/runs?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to get agent runs');
  return res.json();
}

export async function getAgentRunDetail(runId) {
  const res = await fetch(`${BASE_URL}/agent/runs/${runId}`);
  if (!res.ok) throw new Error('Failed to get run detail');
  return res.json();
}

export async function diagnoseRun(runId) {
  const res = await fetch(`${BASE_URL}/agent/diagnose/${runId}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to diagnose');
  return res.json();
}

export async function autoRepair() {
  const res = await fetch(`${BASE_URL}/agent/repair`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to auto-repair');
  return res.json();
}

// Settings API
export async function getSettings() {
  const res = await fetch(`${BASE_URL}/settings`);
  if (!res.ok) throw new Error('Failed to get settings');
  return res.json();
}

export async function updateSettings(values) {
  const res = await fetch(`${BASE_URL}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  });
  if (!res.ok) throw new Error('Failed to update settings');
  return res.json();
}

export async function testConnection(service) {
  const res = await fetch(`${BASE_URL}/settings/test/${service}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to test connection');
  return res.json();
}

export async function fetchFreeModels() {
  const res = await fetch(`${BASE_URL}/settings/models`);
  if (!res.ok) throw new Error('Failed to fetch models');
  return res.json();
}

// ===========================================================================
// Scheduler API
// ===========================================================================

export async function getSchedule() {
  const res = await fetch(`${BASE_URL}/scheduler`);
  if (!res.ok) throw new Error('Failed to get schedule');
  return res.json();
}

export async function updateSchedule(config) {
  const res = await fetch(`${BASE_URL}/scheduler`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to update schedule');
  return res.json();
}

export async function getNextRuns() {
  const res = await fetch(`${BASE_URL}/scheduler/next-runs`);
  if (!res.ok) throw new Error('Failed to get next runs');
  return res.json();
}

// ===========================================================================
// Service API
// ===========================================================================

export async function getServiceStatus() {
  const res = await fetch(`${BASE_URL}/service/status`);
  if (!res.ok) throw new Error('Failed to get service status');
  return res.json();
}

export async function startService() {
  const res = await fetch(`${BASE_URL}/service/start`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start service');
  return res.json();
}

export async function stopService() {
  const res = await fetch(`${BASE_URL}/service/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop service');
  return res.json();
}

export async function setAutoStart(enabled) {
  const res = await fetch(`${BASE_URL}/service/auto-start`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error('Failed to set auto-start');
  return res.json();
}

// ===========================================================================
// Agents API
// ===========================================================================

export async function getAgentTypes() {
  const res = await fetch(`${BASE_URL}/agents`);
  if (!res.ok) throw new Error('Failed to get agent types');
  return res.json();
}

export async function updateAgentConfig(agentId, config) {
  const res = await fetch(`${BASE_URL}/agents/${agentId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config }),
  });
  if (!res.ok) throw new Error('Failed to update agent config');
  return res.json();
}

export async function toggleAgent(agentId, enabled) {
  const res = await fetch(`${BASE_URL}/agents/${agentId}/toggle`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error('Failed to toggle agent');
  return res.json();
}

// ===========================================================================
// Feedback / Learning API
// ===========================================================================

export async function getFeedbackSummary() {
  const res = await fetch(`${BASE_URL}/feedback/summary`);
  if (!res.ok) throw new Error('Failed to get feedback summary');
  return res.json();
}

// ===========================================================================
// Config YAML API (for Settings page)
// ===========================================================================

export async function getConfigYaml() {
  const res = await fetch(`${BASE_URL}/settings/config`);
  if (!res.ok) throw new Error('Failed to get config');
  return res.json();
}

export async function updateConfigYaml(config) {
  const res = await fetch(`${BASE_URL}/settings/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to update config');
  return res.json();
}
