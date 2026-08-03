# ApplyPilot — Graph DB Architecture Specification

## Overview

Transform ApplyPilot from "stateless automation" into "persistent job intelligence" by adding a local graph database that maintains context across runs — recruiter memory, company reputation, job similarity, skill gaps, and application outcome tracking.

---

## 1. Database Selection

| Criteria | Neo4j | KùzuDB | FalkorDB (Lite) |
|----------|-------|--------|-----------------|
| Embedding | Server (Docker) | Embedded (C++) | Embedded (Rust) |
| Python SDK | neo4j-driver | kuzu | falkordb / redis |
| Cypher support | Full | Full | Full (RedisGraph compat) |
| Local-first | ❌ Needs server | ✅ | ✅ |
| Memory footprint | Heavy (~500MB) | Light (~20MB) | Light (~15MB) |
| Maturity | Production | Newer | Production (ex-RedisGraph) |
| macOS ARM support | ✅ | ✅ | ✅ |
| Zero-config setup | ❌ | ✅ | ✅ |

### ✅ Recommendation: **KùzuDB**

**Rationale:**
- Fully embedded (no Docker, no server, no ports)
- Full Cypher query language
- Python-native with pip install
- Sub-millisecond local queries
- Persistent storage (survives restarts)
- Active development, MIT licensed
- Perfect for single-user local app

```bash
pip install kuzu
```

---

## 2. Entity Model (Nodes)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Candidate   │     │     Job      │     │   Company    │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ name         │     │ job_id (PK)  │     │ name (PK)    │
│ email        │     │ title        │     │ industry     │
│ phone        │     │ company      │     │ size         │
│ headline     │     │ location     │     │ reputation   │
│ notice_period│     │ match_score  │     │ response_rate│
│ target_role  │     │ scoring_method│    │ avg_score    │
└──────────────┘     │ status       │     │ jobs_count   │
                     │ is_easy_apply│     │ last_seen    │
┌──────────────┐     │ is_external  │     │ is_target    │
│   Skill      │     │ posted_at    │     │ is_blocked   │
├──────────────┤     │ discovered_at│     │ notes        │
│ name (PK)    │     │ applied_at   │     └──────────────┘
│ category     │     │ response     │
│ proficiency  │     │ jd_summary   │     ┌──────────────┐
└──────────────┘     │ url          │     │  Recruiter   │
                     └──────────────┘     ├──────────────┤
┌──────────────┐                          │ name         │
│     Run      │     ┌──────────────┐     │ company      │
├──────────────┤     │   InMail     │     │ title        │
│ run_id (PK)  │     ├──────────────┤     │ profile_url  │
│ started_at   │     │ id (PK)      │     │ contacted_at │
│ finished_at  │     │ draft_text   │     │ response_rate│
│ mode         │     │ tone         │     │ last_response│
│ jobs_found   │     │ sent_at      │     └──────────────┘
│ jobs_applied │     │ response     │
│ status       │     │ created_at   │
└──────────────┘     └──────────────┘
```

---

## 3. Relationship Model (Edges)

```cypher
// Candidate skills & preferences
(Candidate)-[:HAS_SKILL {proficiency: 'expert|intermediate|basic'}]->(Skill)
(Candidate)-[:TARGETS_ROLE {priority: 1}]->(Job)

// Applications & outcomes
(Candidate)-[:APPLIED_TO {
    timestamp, method: 'easy_apply|external|inmail',
    resume_used, outcome: 'submitted|viewed|rejected|interview',
    response_days
}]->(Job)

// Job relationships
(Job)-[:AT_COMPANY]->(Company)
(Job)-[:REQUIRES_SKILL {level: 'required|preferred'}]->(Skill)
(Job)-[:SIMILAR_TO {score: 0.85, method: 'skill_overlap|title_match'}]->(Job)

// Recruiter network
(Recruiter)-[:WORKS_AT {since}]->(Company)
(Candidate)-[:CONTACTED {
    channel: 'inmail|connection', message_preview,
    sent_at, response: 'replied|ignored|accepted'
}]->(Recruiter)
(InMail)-[:SENT_TO]->(Recruiter)
(InMail)-[:ABOUT_JOB]->(Job)

// Run tracking
(Run)-[:DISCOVERED]->(Job)
(Run)-[:APPLIED]->(Job)
(Run)-[:SKIPPED {reason: 'low_score|external|duplicate'}]->(Job)

// Company intelligence
(Company)-[:POSTED]->(Job)
(Company)-[:HAS_RECRUITER]->(Recruiter)
```

---

## 4. Key Query Patterns

### 4.1 Company Intelligence
```cypher
// Best response rates by company
MATCH (c:Candidate)-[a:APPLIED_TO]->(j:Job)-[:AT_COMPANY]->(co:Company)
WHERE a.outcome IN ['viewed', 'interview']
RETURN co.name, COUNT(a) AS responses, 
       COUNT(a) * 1.0 / COUNT(*) AS rate
ORDER BY rate DESC LIMIT 10
```

### 4.2 Similar Jobs (for recommendations)
```cypher
// Jobs similar to ones I got interviews for
MATCH (c:Candidate)-[a:APPLIED_TO {outcome: 'interview'}]->(j:Job)
MATCH (j)-[:SIMILAR_TO]->(similar:Job)
WHERE NOT EXISTS((c)-[:APPLIED_TO]->(similar))
RETURN similar.title, similar.company, similar.match_score
ORDER BY similar.match_score DESC
```

### 4.3 Skill Gap Analysis
```cypher
// Skills I'm missing for high-scoring roles
MATCH (j:Job)-[:REQUIRES_SKILL]->(s:Skill)
WHERE j.match_score >= 0.6 AND j.match_score < 0.8
AND NOT EXISTS((:Candidate)-[:HAS_SKILL]->(s))
RETURN s.name, COUNT(j) AS demanded_by
ORDER BY demanded_by DESC
```

### 4.4 Recruiter Strategy
```cypher
// Recruiters to InMail based on past success
MATCH (r:Recruiter)-[:WORKS_AT]->(co:Company)
MATCH (co)<-[:AT_COMPANY]-(j:Job)
WHERE j.match_score >= 0.8
AND NOT EXISTS((:Candidate)-[:CONTACTED]->(r))
RETURN r.name, co.name, COUNT(j) AS open_roles
ORDER BY open_roles DESC
```

### 4.5 Application Funnel (30 days)
```cypher
MATCH (c:Candidate)-[a:APPLIED_TO]->(j:Job)
WHERE a.timestamp > datetime() - duration('P30D')
RETURN a.outcome, COUNT(*) AS count
```

### 4.6 Token-Saving Context Lookup
```cypher
// Get cached company context for InMail
MATCH (co:Company {name: $company})
OPTIONAL MATCH (co)<-[:WORKS_AT]-(r:Recruiter)
OPTIONAL MATCH (c:Candidate)-[prev:APPLIED_TO]->(pj:Job)-[:AT_COMPANY]->(co)
RETURN co.industry, co.size, co.notes,
       COLLECT(DISTINCT r.name) AS recruiters,
       COLLECT(DISTINCT {title: pj.title, outcome: prev.outcome}) AS history
```

---

## 5. Integration Points

| Pipeline Stage | Graph Write | Graph Read |
|---|---|---|
| Discovery | CREATE Job, Company, DISCOVERED edge | Dedup: `is_seen(job_id)` |
| Scoring | SET match_score, skill extraction | Company reputation adjustment |
| Apply decision | - | Resume selection by skill overlap |
| Easy Apply | CREATE APPLIED_TO edge | - |
| InMail draft | CREATE InMail node | Company context, recruiter history |
| Response check | UPDATE outcome on APPLIED_TO | - |
| Self-learning | UPDATE company reputation | Score adjustments |
| Run end | Compute SIMILAR_TO edges | - |

---

## 6. Token Savings

| Optimization | Tokens Saved | Mechanism |
|---|---|---|
| JD summary caching | ~1850/job | Store 2-sentence summary at discovery, reuse for InMail |
| Company context cache | ~2000/repeat | Cache research for 7 days, reuse across jobs |
| InMail template reuse | ~600/message | Adapt successful templates instead of generating fresh |
| Skill-based resume pick | ~500/job | Graph query vs LLM reasoning |
| **Total per 100-job run** | **~50,000-90,000** | ~60% reduction in API calls |

---

## 7. Migration Path

| Phase | Timeline | What Changes | Risk |
|---|---|---|---|
| **1. Shadow Mode** | Week 1-2 | Graph mirrors events (fire-and-forget). No decisions from graph. | Zero — graph failures silently ignored |
| **2. Write Mode** | Week 3-4 | Pipeline writes to graph as primary. Skill extraction added. | Low — dual-write to SQLite continues |
| **3. Read Mode** | Week 5-6 | Scoring, InMail, resume selection read from graph. | Medium — test thoroughly |
| **4. Replace Dedup** | Week 7-8 | Graph replaces Turso for dedup. Remove cloud dependency. | Low — graph dedup is faster |

---

## 8. File Structure

```
linkedin_agent/
├── graph/
│   ├── __init__.py          # get_graph_store() factory
│   ├── store.py             # GraphStore class (main interface)
│   ├── schema.py            # CREATE NODE TABLE / REL TABLE DDL
│   ├── queries.py           # Named Cypher query constants
│   ├── enrichment.py        # Skill extraction, similarity computation
│   └── migrations.py        # migrate_to_graph() from Turso/SQLite
```

### Dependencies
```
kuzu>=0.4.0
```

### Config Addition (config.yaml)
```yaml
graph:
  enabled: true
  db_path: "~/.linkedin_agent/graph_db"
  auto_similarity: true
  similarity_threshold: 0.6
  skill_extraction: true
  cache_company_days: 7
```

---

## 9. Implementation Priority

1. **Schema + Store** — KùzuDB setup, schema creation, basic CRUD
2. **Shadow writes** — Mirror pipeline events without affecting flow
3. **Company context** — Cache company research (immediate token savings)
4. **Similarity engine** — Compute SIMILAR_TO edges based on skill overlap
5. **Smart scoring** — Graph-informed score adjustments
6. **Dashboard widget** — "Graph Intelligence" panel showing insights
7. **Replace dedup** — Full migration from Turso to local graph

---

## 10. Expected Outcomes

After full implementation:
- **50-60% reduction** in LLM API token usage
- **Sub-1ms dedup** (local graph vs cloud Turso)
- **Cross-run learning** — agent gets smarter every cycle
- **Recruiter memory** — never re-contact someone who ignored you
- **Skill gap insights** — know exactly what to add to your profile
- **Zero cloud dependencies** — fully local, fully private
