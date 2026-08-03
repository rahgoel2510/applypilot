"""Named Cypher query string constants for KùzuDB operations.

All queries are organized by functional category for clarity and
reusability across the GraphStore and analytics modules.

Categories:
    DEDUP       — Duplicate detection and job-seen checks
    DISCOVERY   — Recording newly discovered jobs and runs
    SCORING     — Score adjustments, company context
    INMAIL      — InMail drafting and recruiter lookup
    SIMILARITY  — Job similarity via graph relationships
    PROMPTS     — LLM prompt caching and retrieval
    ANALYTICS   — Aggregate statistics and reporting
"""

from __future__ import annotations


# ===========================================================================
# DEDUP — Duplicate detection
# ===========================================================================

class DEDUP:
    """Queries for deduplication and job existence checks."""

    IS_SEEN = """
        MATCH (j:Job {id: $job_id})
        RETURN j.id, j.status
    """

    IS_APPLIED = """
        MATCH (c:Candidate)-[a:APPLIED_TO]->(j:Job {id: $job_id})
        RETURN a.applied_at, a.method
    """

    GET_STATUS = """
        MATCH (j:Job {id: $job_id})
        RETURN j.status
    """

    MARK_SKIPPED = """
        MATCH (j:Job {id: $job_id})
        SET j.status = 'skipped'
        RETURN j.id
    """


# ===========================================================================
# DISCOVERY — Recording jobs and runs
# ===========================================================================

class DISCOVERY:
    """Queries for recording discovered jobs, companies, and agent runs."""

    CREATE_JOB = """
        CREATE (j:Job {
            id: $job_id,
            title: $title,
            description: $description,
            location: $location,
            posting_url: $posting_url,
            is_easy_apply: $is_easy_apply,
            match_score: $match_score,
            discovered_at: timestamp(),
            status: 'discovered'
        })
        RETURN j.id
    """

    UPSERT_COMPANY = """
        MERGE (c:Company {id: $company_id})
        ON CREATE SET c.name = $name, c.industry = $industry
        RETURN c.id
    """

    LINK_JOB_COMPANY = """
        MATCH (j:Job {id: $job_id}), (c:Company {id: $company_id})
        CREATE (j)-[:AT_COMPANY]->(c)
    """

    CREATE_RUN = """
        CREATE (r:Run {
            id: $run_id,
            started_at: timestamp(),
            mode: $mode,
            dry_run: $dry_run
        })
        RETURN r.id
    """

    LINK_RUN_JOB = """
        MATCH (r:Run {id: $run_id}), (j:Job {id: $job_id})
        CREATE (r)-[:DISCOVERED {discovered_at: timestamp()}]->(j)
    """

    FINISH_RUN = """
        MATCH (r:Run {id: $run_id})
        SET r.ended_at = timestamp(),
            r.jobs_discovered = $discovered,
            r.jobs_applied = $applied,
            r.jobs_skipped = $skipped
        RETURN r.id
    """


# ===========================================================================
# SCORING — Score adjustments and company context
# ===========================================================================

class SCORING:
    """Queries for score computation and company intelligence."""

    GET_COMPANY_ADJUSTMENT = """
        MATCH (c:Company {id: $company_id})
        RETURN c.score_adjustment, c.is_target, c.is_blocklisted
    """

    SET_COMPANY_ADJUSTMENT = """
        MATCH (c:Company {id: $company_id})
        SET c.score_adjustment = $adjustment
        RETURN c.id
    """

    GET_COMPANY_CONTEXT = """
        MATCH (c:Company {name: $company_name})
        OPTIONAL MATCH (j:Job)-[:AT_COMPANY]->(c)
        OPTIONAL MATCH (r:Recruiter)-[:WORKS_AT]->(c)
        RETURN c.name, c.industry, c.is_target, c.is_blocklisted,
               c.score_adjustment,
               collect(DISTINCT j.title) AS past_jobs,
               collect(DISTINCT r.name) AS recruiters
    """

    GET_APPLIED_COMPANIES = """
        MATCH (c:Candidate)-[:APPLIED_TO]->(j:Job)-[:AT_COMPANY]->(co:Company)
        RETURN co.name, count(j) AS application_count
        ORDER BY application_count DESC
        LIMIT $limit
    """

    COMPANY_APPLICATION_HISTORY = """
        MATCH (j:Job)-[:AT_COMPANY]->(c:Company {name: $company_name})
        WHERE j.status = 'applied'
        RETURN j.title, j.match_score, j.discovered_at
        ORDER BY j.discovered_at DESC
        LIMIT $limit
    """


# ===========================================================================
# INMAIL — Recruiter lookup and InMail tracking
# ===========================================================================

class INMAIL:
    """Queries for InMail drafting and recruiter management."""

    UPSERT_RECRUITER = """
        MERGE (r:Recruiter {id: $recruiter_id})
        ON CREATE SET r.name = $name, r.linkedin_url = $linkedin_url, r.title = $title
        RETURN r.id
    """

    LINK_RECRUITER_COMPANY = """
        MATCH (r:Recruiter {id: $recruiter_id}), (c:Company {id: $company_id})
        CREATE (r)-[:WORKS_AT]->(c)
    """

    CREATE_INMAIL = """
        CREATE (im:InMail {
            id: $inmail_id,
            subject: $subject,
            body: $body,
            tone: $tone,
            sent_at: timestamp(),
            status: $status
        })
        RETURN im.id
    """

    LINK_INMAIL_RECRUITER = """
        MATCH (im:InMail {id: $inmail_id}), (r:Recruiter {id: $recruiter_id})
        CREATE (im)-[:SENT_TO]->(r)
    """

    LINK_INMAIL_JOB = """
        MATCH (im:InMail {id: $inmail_id}), (j:Job {id: $job_id})
        CREATE (im)-[:ABOUT_JOB]->(j)
    """

    GET_RECRUITER_HISTORY = """
        MATCH (im:InMail)-[:SENT_TO]->(r:Recruiter {id: $recruiter_id})
        RETURN im.subject, im.status, im.sent_at
        ORDER BY im.sent_at DESC
        LIMIT $limit
    """


# ===========================================================================
# SIMILARITY — Job similarity via graph relationships and embeddings
# ===========================================================================

class SIMILARITY:
    """Queries for computing and retrieving job similarity."""

    GET_SIMILAR_JOBS = """
        MATCH (j:Job {id: $job_id})-[s:SIMILAR_TO]->(other:Job)
        RETURN other.id, other.title, other.location, s.similarity_score
        ORDER BY s.similarity_score DESC
        LIMIT $limit
    """

    CREATE_SIMILARITY_EDGE = """
        MATCH (a:Job {id: $job_a_id}), (b:Job {id: $job_b_id})
        CREATE (a)-[:SIMILAR_TO {similarity_score: $score}]->(b)
    """

    GET_JOBS_SHARING_SKILLS = """
        MATCH (j:Job {id: $job_id})-[:REQUIRES_SKILL]->(s:Skill)<-[:REQUIRES_SKILL]-(other:Job)
        WHERE other.id <> $job_id
        RETURN other.id, other.title, count(s) AS shared_skills
        ORDER BY shared_skills DESC
        LIMIT $limit
    """

    STORE_EMBEDDING = """
        MATCH (n:{node_type} {{id: $node_id}})
        SET n.embedding = $embedding
        RETURN n.id
    """

    GET_EMBEDDING = """
        MATCH (n:{node_type} {{id: $node_id}})
        RETURN n.embedding
    """

    LINK_JOB_SKILL = """
        MATCH (j:Job {id: $job_id}), (s:Skill {id: $skill_id})
        CREATE (j)-[:REQUIRES_SKILL {importance: $importance}]->(s)
    """

    UPSERT_SKILL = """
        MERGE (s:Skill {id: $skill_id})
        ON CREATE SET s.name = $name, s.category = $category
        RETURN s.id
    """


# ===========================================================================
# PROMPTS — LLM prompt caching and retrieval
# ===========================================================================

class PROMPTS:
    """Queries for storing and retrieving LLM prompt/response pairs."""

    STORE_PROMPT = """
        CREATE (p:Prompt {
            id: $prompt_id,
            prompt_type: $prompt_type,
            input_text: $input_text,
            input_hash: $input_hash,
            output_text: $output_text,
            model: $model,
            tokens_used: $tokens_used,
            created_at: timestamp()
        })
        RETURN p.id
    """

    GET_CACHED_PROMPT = """
        MATCH (p:Prompt {prompt_type: $prompt_type, input_hash: $input_hash})
        RETURN p.output_text, p.model, p.created_at
        ORDER BY p.created_at DESC
        LIMIT 1
    """

    LINK_APPLICATION_PROMPT = """
        MATCH (a:Application {id: $application_id}), (p:Prompt {id: $prompt_id})
        CREATE (a)-[:USED_PROMPT]->(p)
    """

    LINK_INMAIL_PROMPT = """
        MATCH (im:InMail {id: $inmail_id}), (p:Prompt {id: $prompt_id})
        CREATE (im)-[:GENERATED_BY]->(p)
    """

    GET_PROMPT_STATS = """
        MATCH (p:Prompt)
        RETURN p.prompt_type, count(p) AS count, sum(p.tokens_used) AS total_tokens
        ORDER BY total_tokens DESC
    """


# ===========================================================================
# ANALYTICS — Aggregate statistics and reporting
# ===========================================================================

class ANALYTICS:
    """Queries for dashboard analytics and reporting."""

    TOTAL_JOBS_BY_STATUS = """
        MATCH (j:Job)
        RETURN j.status, count(j) AS count
        ORDER BY count DESC
    """

    APPLICATIONS_PER_DAY = """
        MATCH (c:Candidate)-[a:APPLIED_TO]->(j:Job)
        RETURN date(a.applied_at) AS day, count(j) AS applications
        ORDER BY day DESC
        LIMIT $limit
    """

    TOP_COMPANIES = """
        MATCH (j:Job)-[:AT_COMPANY]->(c:Company)
        WHERE j.status = 'applied'
        RETURN c.name, count(j) AS applications, c.is_target
        ORDER BY applications DESC
        LIMIT $limit
    """

    SKILL_DEMAND = """
        MATCH (j:Job)-[:REQUIRES_SKILL]->(s:Skill)
        RETURN s.name, count(j) AS demand
        ORDER BY demand DESC
        LIMIT $limit
    """

    RUN_HISTORY = """
        MATCH (r:Run)
        RETURN r.id, r.started_at, r.ended_at, r.mode, r.dry_run,
               r.jobs_discovered, r.jobs_applied, r.jobs_skipped
        ORDER BY r.started_at DESC
        LIMIT $limit
    """

    AVERAGE_MATCH_SCORE = """
        MATCH (j:Job)
        WHERE j.match_score > 0
        RETURN avg(j.match_score) AS avg_score,
               min(j.match_score) AS min_score,
               max(j.match_score) AS max_score,
               count(j) AS total_scored
    """

    PROMPT_USAGE_SUMMARY = """
        MATCH (p:Prompt)
        RETURN p.model, p.prompt_type, count(p) AS invocations,
               sum(p.tokens_used) AS total_tokens
        ORDER BY total_tokens DESC
    """
