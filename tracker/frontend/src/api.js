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
