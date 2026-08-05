"""Alert manager for ApplyPilot agent failures.

Monitors consecutive failures and sends Telegram alerts when thresholds are breached.
Designed to be called from the orchestrator after each job processing attempt.
"""

import os
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    WARNING = 'warning'
    CRITICAL = 'critical'
    RECOVERY = 'recovery'


@dataclass
class AlertRule:
    """Defines when to fire an alert."""
    name: str
    consecutive_failures_threshold: int  # Fire after N consecutive failures
    cooldown_seconds: int = 300  # Don't re-fire within this window
    last_fired_at: float = 0.0
    
    def can_fire(self) -> bool:
        return (time.time() - self.last_fired_at) > self.cooldown_seconds


@dataclass 
class AlertState:
    """Tracks current failure/success state."""
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    is_alerting: bool = False


class AlertManager:
    """Monitors agent health and fires alerts on failure patterns."""
    
    def __init__(self):
        self.state = AlertState()
        self.rules: list[AlertRule] = [
            AlertRule(name='consecutive_failures', consecutive_failures_threshold=3, cooldown_seconds=300),
            AlertRule(name='critical_failures', consecutive_failures_threshold=5, cooldown_seconds=600),
        ]
        self._telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        self._telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    
    def record_success(self):
        """Record a successful job processing."""
        was_alerting = self.state.is_alerting
        self.state.consecutive_failures = 0
        self.state.total_successes += 1
        
        if was_alerting:
            self.state.is_alerting = False
            self._fire_alert(AlertSeverity.RECOVERY, 'Agent recovered — processing normally again.')
    
    def record_failure(self, error: str):
        """Record a failed job processing attempt."""
        self.state.consecutive_failures += 1
        self.state.total_failures += 1
        self.state.last_error = error
        self.state.last_error_time = time.time()
        
        # Check each rule
        for rule in self.rules:
            if self.state.consecutive_failures >= rule.consecutive_failures_threshold:
                if rule.can_fire():
                    severity = AlertSeverity.CRITICAL if rule.consecutive_failures_threshold >= 5 else AlertSeverity.WARNING
                    self._fire_alert(
                        severity,
                        f'{self.state.consecutive_failures} consecutive failures. Last error: {error[:200]}'
                    )
                    rule.last_fired_at = time.time()
                    self.state.is_alerting = True
    
    def _fire_alert(self, severity: AlertSeverity, message: str):
        """Send alert via Telegram."""
        emoji = {'warning': '\u26a0\ufe0f', 'critical': '\U0001f6a8', 'recovery': '\u2705'}[severity.value]
        text = f"{emoji} ApplyPilot Alert [{severity.value.upper()}]\n\n{message}\n\nStats: {self.state.total_successes} ok / {self.state.total_failures} failed"
        
        if self._telegram_token and self._telegram_chat_id:
            self._send_telegram(text)
        else:
            logger.warning(f'Alert (no Telegram configured): {text}')
    
    def _send_telegram(self, text: str):
        """Send message via Telegram Bot API (sync, best-effort)."""
        try:
            import httpx
            url = f'https://api.telegram.org/bot{self._telegram_token}/sendMessage'
            httpx.post(url, json={'chat_id': self._telegram_chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        except Exception as e:
            logger.error(f'Failed to send Telegram alert: {e}')
    
    def get_status(self) -> dict:
        """Return current alert manager status."""
        return {
            'consecutive_failures': self.state.consecutive_failures,
            'total_failures': self.state.total_failures,
            'total_successes': self.state.total_successes,
            'is_alerting': self.state.is_alerting,
            'last_error': self.state.last_error,
            'last_error_time': self.state.last_error_time,
        }


# Module-level singleton
alert_manager = AlertManager()
