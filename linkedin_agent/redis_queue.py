"""Redis-backed retry queue with automatic fallback to file-based persistence.

Uses Redis Sorted Sets (ZSET) for the retry schedule (score = next_retry_at timestamp)
and Redis Hashes for job metadata. Falls back to the existing file-based RetryQueue
if Redis is not available.

Configuration via environment:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    RETRY_QUEUE_BACKEND: 'redis' | 'file' | 'auto' (default: 'auto')
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [5 * 60, 15 * 60, 45 * 60]  # 5min, 15min, 45min

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
RETRY_QUEUE_BACKEND = os.environ.get('RETRY_QUEUE_BACKEND', 'auto')

_KEY_PREFIX = 'applypilot:retry:'
_SCHEDULE_KEY = f'{_KEY_PREFIX}schedule'  # ZSET: job_id -> next_retry_at
_META_KEY = f'{_KEY_PREFIX}meta:'  # HASH per job: job_id -> {job, attempts, ...}
_FAILED_KEY = f'{_KEY_PREFIX}permanent_failures'  # SET of permanently failed job_ids


def _get_redis():
    """Try to connect to Redis. Returns client or None."""
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


class RedisRetryQueue:
    """Redis-backed retry queue using Sorted Sets for scheduling."""

    def __init__(self):
        self._redis = _get_redis()
        if self._redis:
            logger.info('Redis retry queue connected')
        else:
            logger.warning('Redis not available for retry queue')

    @property
    def available(self) -> bool:
        return self._redis is not None

    def add(self, job: dict, error: str, max_retries: int = 3) -> None:
        job_id = job.get('job_id') or job.get('id') or ''
        if not job_id or not self._redis:
            return

        meta_key = f'{_META_KEY}{job_id}'
        existing = self._redis.hgetall(meta_key)

        if existing:
            attempts = int(existing.get('attempts', '0')) + 1
            if attempts >= max_retries:
                self._redis.sadd(_FAILED_KEY, job_id)
                self._redis.zrem(_SCHEDULE_KEY, job_id)
                self._redis.hset(meta_key, mapping={'status': 'permanent_failure', 'attempts': str(attempts)})
                logger.info(f'Job {job_id} exceeded max retries ({max_retries}), permanent failure')
                return
            backoff_idx = min(attempts - 1, len(BACKOFF_SECONDS) - 1)
            next_retry = time.time() + BACKOFF_SECONDS[backoff_idx]
            self._redis.hset(meta_key, mapping={
                'attempts': str(attempts),
                'last_error': error[:500],
                'next_retry_at': str(next_retry),
                'status': 'pending',
            })
            self._redis.zadd(_SCHEDULE_KEY, {job_id: next_retry})
            logger.info(f'Job {job_id} retry #{attempts} in {BACKOFF_SECONDS[backoff_idx]//60}min')
        else:
            next_retry = time.time() + BACKOFF_SECONDS[0]
            self._redis.hset(meta_key, mapping={
                'job': json.dumps(job),
                'job_id': job_id,
                'attempts': '1',
                'max_retries': str(max_retries),
                'last_error': error[:500],
                'next_retry_at': str(next_retry),
                'added_at': str(time.time()),
                'status': 'pending',
            })
            self._redis.zadd(_SCHEDULE_KEY, {job_id: next_retry})
            logger.info(f'Job {job_id} added to Redis retry queue, first retry in 5min')

    def get_due(self) -> list[dict]:
        if not self._redis:
            return []
        now = time.time()
        due_ids = self._redis.zrangebyscore(_SCHEDULE_KEY, '-inf', str(now))
        jobs = []
        for job_id in due_ids:
            meta = self._redis.hgetall(f'{_META_KEY}{job_id}')
            if meta and meta.get('status') == 'pending' and 'job' in meta:
                try:
                    jobs.append(json.loads(meta['job']))
                except json.JSONDecodeError:
                    pass
        return jobs

    def mark_success(self, job_id: str) -> None:
        if not self._redis:
            return
        self._redis.zrem(_SCHEDULE_KEY, job_id)
        self._redis.delete(f'{_META_KEY}{job_id}')
        logger.info(f'Job {job_id} retry succeeded, removed from Redis queue')

    def mark_permanent_failure(self, job_id: str) -> None:
        if not self._redis:
            return
        self._redis.zrem(_SCHEDULE_KEY, job_id)
        self._redis.sadd(_FAILED_KEY, job_id)
        self._redis.hset(f'{_META_KEY}{job_id}', 'status', 'permanent_failure')
        logger.info(f'Job {job_id} marked as permanent failure in Redis')

    @property
    def pending_count(self) -> int:
        if not self._redis:
            return 0
        return self._redis.zcard(_SCHEDULE_KEY)

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        if not self._redis:
            return 0
        cutoff = time.time() - (max_age_hours * 3600)
        # Get all job IDs and check added_at
        all_ids = self._redis.zrange(_SCHEDULE_KEY, 0, -1)
        removed = 0
        for job_id in all_ids:
            meta = self._redis.hgetall(f'{_META_KEY}{job_id}')
            added_at = float(meta.get('added_at', '0'))
            if added_at < cutoff:
                self._redis.zrem(_SCHEDULE_KEY, job_id)
                self._redis.delete(f'{_META_KEY}{job_id}')
                removed += 1
        if removed:
            logger.info(f'Cleaned up {removed} stale Redis retry entries')
        return removed

    def get_stats(self) -> dict[str, int]:
        if not self._redis:
            return {'pending': 0, 'permanent_failures': 0, 'total': 0}
        pending = self._redis.zcard(_SCHEDULE_KEY)
        permanent = self._redis.scard(_FAILED_KEY)
        return {'pending': pending, 'permanent_failures': permanent, 'total': pending + permanent}


class HybridRetryQueue:
    """Auto-selects Redis or file-based queue based on availability."""

    def __init__(self):
        self._redis_queue: RedisRetryQueue | None = None
        self._file_queue = None
        self._backend = RETRY_QUEUE_BACKEND

        if self._backend in ('redis', 'auto'):
            self._redis_queue = RedisRetryQueue()
            if self._redis_queue.available:
                logger.info('Using Redis-backed retry queue')
                return

        # Fallback to file-based
        from linkedin_agent.retry_queue import RetryQueue
        self._file_queue = RetryQueue()
        self._redis_queue = None
        logger.info('Using file-based retry queue (Redis unavailable)')

    @property
    def _active(self):
        return self._redis_queue if self._redis_queue and self._redis_queue.available else self._file_queue

    def add(self, job: dict, error: str, max_retries: int = 3) -> None:
        self._active.add(job, error, max_retries)

    def get_due(self) -> list[dict]:
        return self._active.get_due()

    def mark_success(self, job_id: str) -> None:
        self._active.mark_success(job_id)

    def mark_permanent_failure(self, job_id: str) -> None:
        self._active.mark_permanent_failure(job_id)

    @property
    def pending_count(self) -> int:
        return self._active.pending_count

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        return self._active.cleanup_old(max_age_hours)

    def get_stats(self) -> dict[str, int]:
        return self._active.get_stats()


# Module-level instance
retry_queue = HybridRetryQueue()
