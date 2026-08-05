"""Async pipeline with bounded queues and backpressure.

Implements a staged pipeline pattern:
  Discovery -> Evaluation -> Application -> Notification

Each stage has a bounded asyncio.Queue. When a downstream queue is full,
the upstream producer blocks (backpressure), preventing memory exhaustion.

Usage:
    pipeline = Pipeline()
    pipeline.add_stage('discover', discover_handler, max_queue=50)
    pipeline.add_stage('evaluate', evaluate_handler, max_queue=20)
    pipeline.add_stage('apply', apply_handler, max_queue=10)
    pipeline.add_stage('notify', notify_handler, max_queue=30)

    await pipeline.start()
    await pipeline.submit('discover', job_data)  # Will block if queue full
    await pipeline.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

_SENTINEL = object()  # Signals shutdown to workers


@dataclass
class StageMetrics:
    """Per-stage processing metrics."""

    items_received: int = 0
    items_processed: int = 0
    items_failed: int = 0
    total_processing_time: float = 0.0
    last_processed_at: Optional[float] = None
    backpressure_events: int = 0  # Times producer had to wait

    @property
    def avg_processing_time(self) -> float:
        if self.items_processed == 0:
            return 0.0
        return self.total_processing_time / self.items_processed


@dataclass
class Stage:
    """A pipeline stage with its queue and handler."""

    name: str
    handler: Callable[[Any], Coroutine]
    queue: asyncio.Queue
    next_stage: Optional[str] = None
    concurrency: int = 1
    metrics: StageMetrics = field(default_factory=StageMetrics)
    _workers: list[asyncio.Task] = field(default_factory=list)


class Pipeline:
    """Multi-stage async pipeline with bounded queues and backpressure."""

    def __init__(self):
        self._stages: dict[str, Stage] = {}
        self._stage_order: list[str] = []
        self._running = False

    def add_stage(
        self,
        name: str,
        handler: Callable[[Any], Coroutine],
        max_queue: int = 50,
        concurrency: int = 1,
        next_stage: Optional[str] = None,
    ) -> "Pipeline":
        """Add a stage to the pipeline.

        Args:
            name: Stage identifier
            handler: Async function that processes items. Should return the item
                     to pass to next stage, or None to drop it.
            max_queue: Maximum items in this stage's queue (backpressure threshold)
            concurrency: Number of concurrent workers for this stage
            next_stage: Name of the stage to forward processed items to.
                        If None, auto-links to the next added stage.
        """
        stage = Stage(
            name=name,
            handler=handler,
            queue=asyncio.Queue(maxsize=max_queue),
            next_stage=next_stage,
            concurrency=concurrency,
        )

        # Auto-link: if there's a previous stage without explicit next_stage, link it
        if self._stage_order and not next_stage:
            prev = self._stages[self._stage_order[-1]]
            if prev.next_stage is None:
                prev.next_stage = name

        self._stages[name] = stage
        self._stage_order.append(name)
        return self

    async def start(self) -> None:
        """Start all stage workers."""
        if self._running:
            return
        self._running = True

        for stage in self._stages.values():
            for i in range(stage.concurrency):
                task = asyncio.create_task(
                    self._worker(stage), name=f"pipeline-{stage.name}-{i}"
                )
                stage._workers.append(task)

        logger.info(f'Pipeline started: {" -> ".join(self._stage_order)}')

    async def submit(self, stage_name: str, item: Any, timeout: float = 30.0) -> bool:
        """Submit an item to a stage's queue.

        Blocks if the queue is full (backpressure).
        Returns False if timeout exceeded.
        """
        stage = self._stages.get(stage_name)
        if not stage:
            logger.error(f"Unknown stage: {stage_name}")
            return False

        try:
            start = time.time()
            await asyncio.wait_for(stage.queue.put(item), timeout=timeout)
            wait_time = time.time() - start
            stage.metrics.items_received += 1
            if wait_time > 0.1:  # Waited more than 100ms = backpressure
                stage.metrics.backpressure_events += 1
                logger.debug(f"Backpressure on {stage_name}: waited {wait_time:.1f}s")
            return True
        except asyncio.TimeoutError:
            logger.warning(
                f"Queue full for {stage_name}, item dropped (timeout={timeout}s)"
            )
            return False

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shut down the pipeline.

        Sends sentinel to all workers and waits for completion.
        """
        if not self._running:
            return
        self._running = False

        # Send sentinels to all stages
        for stage in self._stages.values():
            for _ in range(stage.concurrency):
                await stage.queue.put(_SENTINEL)

        # Wait for all workers to finish
        all_workers = [w for s in self._stages.values() for w in s._workers]
        if all_workers:
            done, pending = await asyncio.wait(all_workers, timeout=timeout)
            for task in pending:
                task.cancel()

        logger.info("Pipeline shut down")

    def get_metrics(self) -> dict[str, dict]:
        """Get metrics for all stages."""
        return {
            name: {
                "queue_size": stage.queue.qsize(),
                "queue_max": stage.queue.maxsize,
                "items_received": stage.metrics.items_received,
                "items_processed": stage.metrics.items_processed,
                "items_failed": stage.metrics.items_failed,
                "avg_processing_time_ms": round(
                    stage.metrics.avg_processing_time * 1000, 1
                ),
                "backpressure_events": stage.metrics.backpressure_events,
            }
            for name, stage in self._stages.items()
        }

    @property
    def is_running(self) -> bool:
        return self._running

    async def _worker(self, stage: Stage) -> None:
        """Worker loop for a single stage."""
        while True:
            item = await stage.queue.get()

            if item is _SENTINEL:
                stage.queue.task_done()
                break

            start = time.time()
            try:
                result = await stage.handler(item)
                duration = time.time() - start
                stage.metrics.items_processed += 1
                stage.metrics.total_processing_time += duration
                stage.metrics.last_processed_at = time.time()

                # Forward to next stage if result is not None
                if result is not None and stage.next_stage:
                    next_s = self._stages.get(stage.next_stage)
                    if next_s:
                        await next_s.queue.put(result)
                        next_s.metrics.items_received += 1
            except Exception as e:
                stage.metrics.items_failed += 1
                logger.error(f"Stage {stage.name} error: {e}", exc_info=True)
            finally:
                stage.queue.task_done()
