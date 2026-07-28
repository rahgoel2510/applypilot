"""Telegram Bot module for LinkedIn Job Agent.

Provides async notification, tally reporting, human-input collection,
and InMail draft review via Telegram using python-telegram-bot v20+.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from linkedin_agent.config import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds (exponential backoff base)
DEFAULT_HUMAN_TIMEOUT = 300  # 5 minutes

# Emojis for message formatting
EMOJI = {
    "submitted": "✅",
    "paused": "⏸️",
    "skipped_threshold": "⚠️",
    "skipped_external": "🚫",
    "info": "ℹ️",
    "robot": "🤖",
    "briefcase": "💼",
    "envelope": "✉️",
    "question": "❓",
    "clock": "⏳",
    "report": "📊",
    "rocket": "🚀",
    "warning": "⚠️",
}


# ---------------------------------------------------------------------------
# Retry decorator for network resilience
# ---------------------------------------------------------------------------


async def _retry_send(coro_factory, max_retries: int = MAX_RETRIES) -> Any:
    """Execute an async callable with exponential backoff on network errors.

    Args:
        coro_factory: A zero-arg callable that returns an awaitable.
        max_retries: Maximum number of retry attempts.

    Returns:
        The result of the awaitable on success.

    Raises:
        The last exception encountered after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except RetryAfter as exc:
            # Telegram rate-limiting — respect the retry_after header
            wait = exc.retry_after
            logger.warning("Rate limited by Telegram. Retrying after %s seconds.", wait)
            await asyncio.sleep(wait)
            last_exc = exc
        except (NetworkError, TimedOut) as exc:
            delay = RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "Network error (attempt %d/%d): %s. Retrying in %.1fs.",
                attempt + 1,
                max_retries + 1,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            last_exc = exc
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TelegramNotifier class
# ---------------------------------------------------------------------------


class TelegramNotifier:
    """Async Telegram bot for notifications and human interaction.

    Uses python-telegram-bot v20+ Application pattern. Supports:
    - Sending notifications and tally reports
    - Requesting human input with timeout
    - Sending InMail drafts for review
    - Listener mode for receiving callback responses
    """

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None) -> None:
        """Initialize the notifier.

        If bot_token/chat_id are not provided, they are read from config.
        """
        if bot_token is None or chat_id is None:
            cfg = get_config(validate=False)
            bot_token = bot_token or cfg.telegram.bot_token
            chat_id = chat_id or cfg.telegram.chat_id

        self._bot_token = bot_token
        self._chat_id = chat_id
        self._bot = Bot(token=self._bot_token)

        # Application for listener mode
        self._app: Application | None = None
        self._listener_running = False

        # Pending human-input futures keyed by chat_id
        self._pending_responses: dict[str, asyncio.Future[str]] = {}

    # ------------------------------------------------------------------
    # Core send helper
    # ------------------------------------------------------------------

    async def _send_message(self, text: str, parse_mode: str = ParseMode.HTML) -> None:
        """Send a message to the configured chat with retry logic."""
        await _retry_send(
            lambda: self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=parse_mode,
            )
        )

    # ------------------------------------------------------------------
    # Public API: send_notification
    # ------------------------------------------------------------------

    async def send_notification(self, message: str) -> None:
        """Send a plain notification message to the configured chat.

        Args:
            message: Text to send. Supports HTML formatting.
        """
        formatted = f"{EMOJI['info']} <b>LinkedIn Agent</b>\n\n{message}"
        await self._send_message(formatted)
        logger.info("Notification sent: %s", message[:80])

    # ------------------------------------------------------------------
    # Public API: send_tally_report
    # ------------------------------------------------------------------

    async def send_tally_report(self, tally: dict[str, int]) -> None:
        """Format and send a funnel tally report.

        Supports both the legacy 4-bucket format and the expanded funnel format.

        Args:
            tally: Dictionary with keys. Expanded funnel keys:
                - total_found: Total jobs found in scan
                - dedup_skipped: Jobs skipped (already seen)
                - new_discovered: New jobs discovered this cycle
                - applied: Applications submitted
                - external_manual: External apply (user handles manually)
                - skipped_low_score: Skipped due to low match score
                - paused: Paused for human review
                - errors: Errors during processing
              Legacy keys (backwards compatible):
                - submitted, paused, skipped_threshold, skipped_external
        """
        # Detect expanded format by checking for new keys
        is_expanded = any(
            k in tally for k in ("total_found", "new_discovered", "dedup_skipped")
        )

        if is_expanded:
            total_found = tally.get("total_found", 0)
            dedup_skipped = tally.get("dedup_skipped", 0)
            new_discovered = tally.get("new_discovered", 0)
            applied = tally.get("applied", 0)
            external_manual = tally.get("external_manual", 0)
            skipped_low_score = tally.get("skipped_low_score", 0)
            paused = tally.get("paused", 0)
            errors = tally.get("errors", 0)

            report = (
                f"{EMOJI['report']} <b>Scan Cycle Funnel Report</b>\n"
                f"{'─' * 28}\n"
                f"🔍 Total found: <b>{total_found}</b>\n"
                f"♻️ Already seen (dedup): <b>{dedup_skipped}</b>\n"
                f"🆕 New discovered: <b>{new_discovered}</b>\n"
                f"{'─' * 28}\n"
                f"✅ Applied: <b>{applied}</b>\n"
                f"🔗 External (manual): <b>{external_manual}</b>\n"
                f"⚠️ Skipped (low score): <b>{skipped_low_score}</b>\n"
                f"⏸️ Paused (review): <b>{paused}</b>\n"
                f"❌ Errors: <b>{errors}</b>\n"
                f"{'─' * 28}\n"
                f"{EMOJI['rocket']} Cycle complete!"
            )
        else:
            # Legacy 4-bucket format for backwards compatibility
            submitted = tally.get("submitted", 0)
            paused = tally.get("paused", 0)
            skipped_threshold = tally.get("skipped_threshold", 0)
            skipped_external = tally.get("skipped_external", 0)
            total = submitted + paused + skipped_threshold + skipped_external

            report = (
                f"{EMOJI['report']} <b>Run Tally Report</b>\n"
                f"{'─' * 28}\n"
                f"{EMOJI['submitted']} Submitted: <b>{submitted}</b>\n"
                f"{EMOJI['paused']} Paused (review needed): <b>{paused}</b>\n"
                f"{EMOJI['skipped_threshold']} Skipped (low match): <b>{skipped_threshold}</b>\n"
                f"{EMOJI['skipped_external']} Skipped (external apply): <b>{skipped_external}</b>\n"
                f"{'─' * 28}\n"
                f"{EMOJI['briefcase']} Total processed: <b>{total}</b>"
            )

        await self._send_message(report)
        logger.info("Tally report sent: %s", tally)

    # ------------------------------------------------------------------
    # Public API: send_job_applied_notification
    # ------------------------------------------------------------------

    async def send_job_applied_notification(
        self,
        job_title: str,
        company: str,
        location: str,
        match_score: float,
        posting_url: str,
        action: str,
    ) -> None:
        """Send a rich per-job notification with clickable job URL.

        Args:
            job_title: The job title.
            company: The company name.
            location: Job location.
            match_score: Match score (0.0 to 1.0).
            posting_url: URL to the job posting on LinkedIn.
            action: The action taken (e.g., 'Applied', 'Paused', 'Skipped').
        """
        # Determine emoji based on action
        action_lower = action.lower()
        if action_lower in ("applied", "submitted"):
            action_emoji = "✅"
        elif action_lower == "paused":
            action_emoji = "⏸️"
        elif action_lower == "skipped":
            action_emoji = "⚠️"
        else:
            action_emoji = "ℹ️"

        score_pct = f"{match_score:.0%}" if match_score is not None else "N/A"

        message = (
            f"{action_emoji} <b>{action}</b>\n\n"
            f"💼 <b>{job_title}</b>\n"
            f"🏢 {company}\n"
            f"📍 {location}\n"
            f"📊 Match: <b>{score_pct}</b>\n\n"
            f'🔗 <a href="{posting_url}">View Job</a>'
        )
        await self._send_message(message)
        logger.info(
            "Job applied notification sent: %s @ %s (%s)", job_title, company, action
        )

    # ------------------------------------------------------------------
    # Public API: ask_human_input
    # ------------------------------------------------------------------

    async def ask_human_input(
        self,
        job_title: str,
        company: str,
        fields: list[str],
        timeout: float = DEFAULT_HUMAN_TIMEOUT,
    ) -> str:
        """Send a prompt asking for human input on sensitive fields and wait for reply.

        Args:
            job_title: The job title being applied to.
            company: The company name.
            fields: List of field names that need human input.
            timeout: Seconds to wait for a reply (default 5 minutes).

        Returns:
            The human's reply text, or empty string if timed out.
        """
        fields_formatted = "\n".join(f"  • {f}" for f in fields)
        prompt = (
            f"{EMOJI['question']} <b>Human Input Needed</b>\n\n"
            f"{EMOJI['briefcase']} <b>{job_title}</b> @ {company}\n\n"
            f"The following fields require your input:\n"
            f"{fields_formatted}\n\n"
            f"{EMOJI['clock']} Please reply within {int(timeout // 60)} minutes.\n"
            f"Reply with your answers (one per line, matching the order above)."
        )
        await self._send_message(prompt)
        logger.info("Human input requested for %s @ %s, fields: %s", job_title, company, fields)

        # If listener is running, wait for response via the message handler
        if self._listener_running:
            return await self._wait_for_response(timeout)

        # If no listener, use a polling approach to get updates
        return await self._poll_for_response(timeout)

    async def _wait_for_response(self, timeout: float) -> str:
        """Wait for a response via the listener's message handler."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_responses[self._chat_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning("Human input timed out after %.0f seconds.", timeout)
            await self._send_message(
                f"{EMOJI['warning']} Input timed out. Skipping this application."
            )
            return ""
        finally:
            self._pending_responses.pop(self._chat_id, None)

    async def _poll_for_response(self, timeout: float) -> str:
        """Poll for a response using getUpdates (fallback without listener)."""
        deadline = asyncio.get_event_loop().time() + timeout
        last_update_id: int | None = None

        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            poll_timeout = min(30.0, remaining)  # Long-poll up to 30s

            try:
                updates = await _retry_send(
                    lambda: self._bot.get_updates(
                        offset=last_update_id,
                        timeout=int(poll_timeout),
                        allowed_updates=["message"],
                    )
                )
            except Exception as exc:
                logger.error("Error polling for updates: %s", exc)
                await asyncio.sleep(2)
                continue

            for update in updates:
                last_update_id = update.update_id + 1
                if (
                    update.message
                    and str(update.message.chat_id) == str(self._chat_id)
                    and update.message.text
                ):
                    logger.info("Received human input: %s", update.message.text[:80])
                    return update.message.text

            if not updates:
                await asyncio.sleep(1)

        logger.warning("Human input timed out after %.0f seconds.", timeout)
        await self._send_message(
            f"{EMOJI['warning']} Input timed out. Skipping this application."
        )
        return ""

    # ------------------------------------------------------------------
    # Public API: send_inmail_draft
    # ------------------------------------------------------------------

    async def send_inmail_draft(
        self, job_title: str, company: str, recruiter: str, draft: str
    ) -> None:
        """Send a drafted InMail message for human review.

        Args:
            job_title: The target job title.
            company: The company name.
            recruiter: The recruiter's name.
            draft: The generated InMail draft text.
        """
        message = (
            f"{EMOJI['envelope']} <b>InMail Draft for Review</b>\n\n"
            f"{EMOJI['briefcase']} <b>Position:</b> {job_title}\n"
            f"🏢 <b>Company:</b> {company}\n"
            f"👤 <b>Recruiter:</b> {recruiter}\n\n"
            f"{'─' * 28}\n"
            f"{draft}\n"
            f"{'─' * 28}\n\n"
            f"Reply <b>SEND</b> to send, <b>EDIT</b> to modify, or <b>SKIP</b> to discard."
        )
        await self._send_message(message)
        logger.info("InMail draft sent for review: %s @ %s to %s", job_title, company, recruiter)

    # ------------------------------------------------------------------
    # Listener mode
    # ------------------------------------------------------------------

    async def start_listener(self) -> None:
        """Start the Telegram bot listener to receive callback responses.

        Runs the Application in polling mode to handle incoming messages.
        This is non-blocking — it starts the polling loop as a background task.
        """
        if self._listener_running:
            logger.warning("Listener is already running.")
            return

        self._app = (
            Application.builder()
            .token(self._bot_token)
            .build()
        )

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("status", self._handle_status))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Initialize and start polling
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        self._listener_running = True
        logger.info("Telegram listener started.")

    async def stop_listener(self) -> None:
        """Stop the Telegram bot listener gracefully."""
        if not self._listener_running or self._app is None:
            return

        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()
        self._listener_running = False
        logger.info("Telegram listener stopped.")

    # ------------------------------------------------------------------
    # Listener handlers
    # ------------------------------------------------------------------

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if update.message:
            await update.message.reply_html(
                f"{EMOJI['robot']} <b>LinkedIn Job Agent Bot</b>\n\n"
                f"I'll send you notifications about job applications.\n"
                f"Use /status to check the agent's current state."
            )

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if update.message:
            await update.message.reply_html(
                f"{EMOJI['rocket']} Agent is running and listening for commands."
            )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages — resolve pending futures."""
        if not update.message or not update.message.text:
            return

        chat_id = str(update.message.chat_id)
        text = update.message.text

        # Check if there's a pending response future for this chat
        if chat_id in self._pending_responses:
            future = self._pending_responses[chat_id]
            if not future.done():
                future.set_result(text)
                logger.info("Resolved pending response for chat %s", chat_id)
        else:
            # No pending request — acknowledge
            if update.message:
                await update.message.reply_html(
                    f"{EMOJI['info']} No pending input request. "
                    f"I'll let you know when I need your help!"
                )


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_default_notifier: TelegramNotifier | None = None


def _get_notifier() -> TelegramNotifier:
    """Get or create the default TelegramNotifier singleton."""
    global _default_notifier  # noqa: PLW0603
    if _default_notifier is None:
        _default_notifier = TelegramNotifier()
    return _default_notifier


def reset_notifier() -> None:
    """Reset the default notifier singleton (for testing)."""
    global _default_notifier  # noqa: PLW0603
    _default_notifier = None


async def send_notification(message: str) -> None:
    """Send a notification message using the default notifier.

    Args:
        message: Text to send.
    """
    notifier = _get_notifier()
    await notifier.send_notification(message)


async def send_tally_report(tally: dict[str, int]) -> None:
    """Send a tally report using the default notifier.

    Args:
        tally: Tally dictionary with 4 buckets.
    """
    notifier = _get_notifier()
    await notifier.send_tally_report(tally)


async def ask_human_input(
    job_title: str,
    company: str,
    fields: list[str],
    timeout: float = DEFAULT_HUMAN_TIMEOUT,
) -> str:
    """Ask for human input using the default notifier.

    Args:
        job_title: The job title.
        company: The company name.
        fields: Fields needing input.
        timeout: Reply timeout in seconds.

    Returns:
        Human's reply text, or empty string on timeout.
    """
    notifier = _get_notifier()
    return await notifier.ask_human_input(job_title, company, fields, timeout)


async def send_job_applied_notification(
    job_title: str,
    company: str,
    location: str,
    match_score: float,
    posting_url: str,
    action: str,
) -> None:
    """Send a rich per-job notification using the default notifier.

    Args:
        job_title: The job title.
        company: The company name.
        location: Job location.
        match_score: Match score (0.0 to 1.0).
        posting_url: URL to the job posting.
        action: The action taken.
    """
    notifier = _get_notifier()
    await notifier.send_job_applied_notification(
        job_title, company, location, match_score, posting_url, action
    )


async def send_inmail_draft(
    job_title: str, company: str, recruiter: str, draft: str
) -> None:
    """Send an InMail draft for review using the default notifier.

    Args:
        job_title: Target position.
        company: Company name.
        recruiter: Recruiter name.
        draft: The InMail draft body.
    """
    notifier = _get_notifier()
    await notifier.send_inmail_draft(job_title, company, recruiter, draft)
