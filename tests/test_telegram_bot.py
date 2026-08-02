"""Tests for the Telegram notification module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_agent.telegram_bot import TelegramNotifier


@pytest.fixture
def notifier():
    """Create a TelegramNotifier with test credentials."""
    return TelegramNotifier(
        bot_token="test-token-123",
        chat_id="123456789",
    )


class TestTelegramNotifierInit:
    """Tests for TelegramNotifier initialization."""

    def test_creates_with_token_and_chat(self):
        n = TelegramNotifier(bot_token="tok", chat_id="789")
        assert n._bot_token == "tok"
        assert n._chat_id == "789"

    def test_has_required_interface(self, notifier):
        """Verify all Notifier protocol methods exist."""
        assert hasattr(notifier, "send_notification")
        assert hasattr(notifier, "send_tally_report")
        assert hasattr(notifier, "send_job_applied_notification")
        assert hasattr(notifier, "send_inmail_draft")


class TestTelegramNotifierSendNotification:
    """Tests for the send_notification method."""

    @pytest.mark.asyncio
    async def test_send_notification_calls_bot(self, notifier):
        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            await notifier.send_notification("Hello!")
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Hello!" in str(call_args)

    @pytest.mark.asyncio
    async def test_send_notification_handles_error(self, notifier):
        with patch.object(
            notifier, "_send_message", new_callable=AsyncMock, side_effect=Exception("net err")
        ):
            # send_notification propagates exceptions (caller handles)
            with pytest.raises(Exception, match="net err"):
                await notifier.send_notification("test")


class TestTelegramNotifierTallyReport:
    """Tests for the send_tally_report method."""

    @pytest.mark.asyncio
    async def test_sends_formatted_tally(self, notifier):
        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            tally = {"submitted": 5, "paused": 2, "skipped_threshold": 10, "skipped_external": 3}
            await notifier.send_tally_report(tally)
            mock_send.assert_called()


class TestTelegramNotifierJobApplied:
    """Tests for per-job notification."""

    @pytest.mark.asyncio
    async def test_sends_job_notification(self, notifier):
        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            await notifier.send_job_applied_notification(
                job_title="SWE",
                company="Google",
                location="Bangalore",
                match_score=0.9,
                posting_url="https://linkedin.com/jobs/view/123",
                action="Applied",
            )
            mock_send.assert_called()
            msg = mock_send.call_args[0][0] if mock_send.call_args[0] else mock_send.call_args[1].get("text", "")
            # The message should contain job details
            assert "SWE" in str(mock_send.call_args) or "Google" in str(mock_send.call_args)


class TestTelegramNotifierInMail:
    """Tests for InMail draft notification."""

    @pytest.mark.asyncio
    async def test_sends_inmail_draft(self, notifier):
        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            await notifier.send_inmail_draft(
                job_title="PM",
                company="Meta",
                recruiter="John",
                draft="Dear John...",
            )
            mock_send.assert_called()


class TestTelegramNotifierTallyFormatting:
    """Tests for tally report formatting logic."""

    @pytest.mark.asyncio
    async def test_legacy_tally_format(self, notifier):
        """Legacy 4-bucket format is handled."""
        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            tally = {"submitted": 3, "paused": 1, "skipped_threshold": 5, "skipped_external": 2}
            await notifier.send_tally_report(tally)
            msg = str(mock_send.call_args)
            assert "3" in msg  # submitted count

    @pytest.mark.asyncio
    async def test_enhanced_tally_format(self, notifier):
        """Enhanced format with extra metrics is handled."""
        with patch.object(notifier, "_send_message", new_callable=AsyncMock) as mock_send:
            tally = {
                "submitted": 5,
                "paused": 0,
                "skipped_threshold": 10,
                "skipped_external": 3,
                "total_found": 50,
                "dedup_skipped": 20,
                "new_discovered": 30,
                "errors": 2,
            }
            await notifier.send_tally_report(tally)
            mock_send.assert_called()


class TestTelegramNotifierHumanInput:
    """Tests for human input request functionality."""

    @pytest.mark.asyncio
    async def test_ask_human_input_method_exists(self, notifier):
        """Verify the human input interface exists."""
        assert hasattr(notifier, "ask_human_input") or hasattr(notifier, "request_human_input")
