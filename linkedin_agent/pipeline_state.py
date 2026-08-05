"""Pipeline state externalization — checkpoint/resume for crash recovery.

Saves pipeline progress to disk (or Redis if available) so that a crashed
scan cycle can resume from the last checkpoint instead of restarting.

Checkpoint data:
- cycle_id: unique cycle identifier
- phase: current pipeline phase (discover, evaluate, apply, notify)
- jobs_processed: list of job_ids already processed
- jobs_remaining: list of job dicts still to process
- started_at: cycle start timestamp
- last_checkpoint_at: when this checkpoint was written
- metadata: any extra state (search params, thresholds, etc.)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = Path.home() / '.linkedin_agent' / 'checkpoints'
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PipelineCheckpoint:
    """Represents a saved pipeline state."""
    cycle_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    phase: str = 'init'  # init, discover, evaluate, apply, notify, complete
    jobs_processed: list[str] = field(default_factory=list)
    jobs_remaining: list[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    last_checkpoint_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    completed: bool = False


class PipelineStateManager:
    """Manages pipeline checkpoints for crash recovery."""

    def __init__(self, checkpoint_dir: Path | None = None):
        self._dir = checkpoint_dir or CHECKPOINT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._current: Optional[PipelineCheckpoint] = None

    def start_cycle(self, metadata: dict | None = None) -> PipelineCheckpoint:
        """Start a new pipeline cycle, creating a fresh checkpoint."""
        self._current = PipelineCheckpoint(
            metadata=metadata or {},
        )
        self._save()
        logger.info(f'Pipeline cycle started: {self._current.cycle_id}')
        return self._current

    def checkpoint(self, phase: str, jobs_processed: list[str] | None = None,
                   jobs_remaining: list[dict] | None = None, **extra) -> None:
        """Save current progress."""
        if not self._current:
            return
        self._current.phase = phase
        self._current.last_checkpoint_at = time.time()
        if jobs_processed is not None:
            self._current.jobs_processed = jobs_processed
        if jobs_remaining is not None:
            self._current.jobs_remaining = jobs_remaining
        if extra:
            self._current.metadata.update(extra)
        self._save()
        logger.debug(f'Checkpoint: phase={phase}, processed={len(self._current.jobs_processed)}')

    def complete_cycle(self) -> None:
        """Mark cycle as complete and clean up checkpoint file."""
        if self._current:
            self._current.completed = True
            self._current.phase = 'complete'
            self._cleanup(self._current.cycle_id)
            logger.info(f'Pipeline cycle completed: {self._current.cycle_id}')
            self._current = None

    def get_resumable(self) -> Optional[PipelineCheckpoint]:
        """Check if there's a crashed cycle that can be resumed."""
        checkpoint_files = sorted(self._dir.glob('checkpoint_*.json'), reverse=True)
        for f in checkpoint_files:
            try:
                data = json.loads(f.read_text())
                if not data.get('completed', False):
                    cp = PipelineCheckpoint(**data)
                    # Only resume if less than 2 hours old
                    if time.time() - cp.last_checkpoint_at < 7200:
                        logger.info(f'Resumable checkpoint found: {cp.cycle_id} (phase: {cp.phase})')
                        return cp
                    else:
                        # Too old, clean up
                        f.unlink()
            except (json.JSONDecodeError, TypeError, OSError):
                f.unlink(missing_ok=True)
        return None

    def resume(self, checkpoint: PipelineCheckpoint) -> None:
        """Resume from a saved checkpoint."""
        self._current = checkpoint
        logger.info(f'Resuming cycle {checkpoint.cycle_id} from phase: {checkpoint.phase}')

    @property
    def current(self) -> Optional[PipelineCheckpoint]:
        return self._current

    def _save(self) -> None:
        if not self._current:
            return
        filepath = self._dir / f'checkpoint_{self._current.cycle_id}.json'
        try:
            data = asdict(self._current)
            tmp = filepath.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, default=str, indent=2))
            tmp.replace(filepath)
        except OSError as e:
            logger.error(f'Failed to save checkpoint: {e}')

    def _cleanup(self, cycle_id: str) -> None:
        filepath = self._dir / f'checkpoint_{cycle_id}.json'
        filepath.unlink(missing_ok=True)


# Module-level singleton
pipeline_state = PipelineStateManager()
