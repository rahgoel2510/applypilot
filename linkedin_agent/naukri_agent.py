"""Naukri.com Profile Freshener Agent — COMPLETELY INDEPENDENT from the LinkedIn agent.

Refreshes your Naukri profile by toggling the profile summary and re-uploading
your resume. This keeps your profile "active" in recruiter searches.

Uses its own browser data directory, its own error handling, and its own state.
No shared sessions or state with the LinkedIn agent.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir
from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    TimeoutError as PlaywrightTimeout,
)

from linkedin_agent.stealth import STEALTH_ARGS, get_random_ua, get_stealth_scripts
from linkedin_agent.tracker_client import TrackerClient

# ---------------------------------------------------------------------------
# Logger — own namespace, completely independent
# ---------------------------------------------------------------------------

logger = logging.getLogger("naukri_agent")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAUKRI_BASE = "https://www.naukri.com"
NAUKRI_LOGIN_URL = f"{NAUKRI_BASE}/nlogin/login"
NAUKRI_PROFILE_URL = f"{NAUKRI_BASE}/mnjuser/profile"

# Independent browser data directory (no overlap with LinkedIn agent)
BROWSER_DATA_DIR = Path(user_data_dir("naukri_agent", "applypilot")) / "browser_data"
SCREENSHOT_DIR = Path(user_data_dir("naukri_agent", "applypilot")) / "screenshots"

# Timing
DELAY_MIN = 1.5
DELAY_MAX = 3.5
PAGE_LOAD_TIMEOUT = 30_000  # 30s
ACTION_TIMEOUT = 15_000  # 15s

# Selectors for Naukri.com
SELECTORS = {
    # Login page
    "email_field": "input[type='text'], #usernameField",
    "password_field": "input[type='password'], #passwordField",
    "login_button": "button[type='submit'], .loginButton",
    "login_success": ".nI-gNb-drawer, .view-profile-icon, .nI-gNb-header__right",

    # Profile page — Resume headline / summary
    "summary_widget": ".widgetHead",
    "summary_edit_icon": ".widgetHead .edit-icon, .widgetHead .icon, "
                         "[class*='editIcon'], .widgetHead button",
    "summary_textarea": "textarea",
    "summary_save_button": "button[type='submit'], button:has-text('Save'), "
                           ".modal-footer button.btn-dark",

    # Resume upload
    "resume_upload_input": "input[type='file']",
    "resume_update_button": "#attachCV, .uploadResume, "
                            "input[name='attachCV'], [id*='attachCV']",
    "upload_success": ".toast-message, .success-message, "
                      "[class*='success'], [class*='toast']",
}



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _human_delay(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX) -> None:
    """Sleep for a randomized duration to mimic human behavior."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _safe_click(page: Page, selector: str, timeout: int = ACTION_TIMEOUT) -> bool:
    """Attempt to click a selector, trying each comma-separated alternative."""
    alternatives = [s.strip() for s in selector.split(",")]
    for alt in alternatives:
        try:
            locator = page.locator(alt).first
            if await locator.is_visible(timeout=timeout):
                await locator.click(timeout=timeout)
                return True
        except (PlaywrightTimeout, Exception):
            continue
    return False


async def _safe_fill(page: Page, selector: str, value: str, timeout: int = ACTION_TIMEOUT) -> bool:
    """Attempt to fill a field, trying each comma-separated alternative."""
    alternatives = [s.strip() for s in selector.split(",")]
    for alt in alternatives:
        try:
            locator = page.locator(alt).first
            if await locator.is_visible(timeout=timeout):
                await locator.click(timeout=timeout)
                await locator.fill(value, timeout=timeout)
                return True
        except (PlaywrightTimeout, Exception):
            continue
    return False



# ---------------------------------------------------------------------------
# NaukriFreshener Agent
# ---------------------------------------------------------------------------


class NaukriFreshener:
    """Autonomous Naukri.com profile freshener.

    Keeps your Naukri profile active by:
      1. Logging in with your credentials
      2. Toggling the profile summary (append/remove a '.' character)
      3. Re-uploading your resume

    Completely independent from the LinkedIn agent — own browser data,
    own state, own error handling.

    Usage:
        agent = NaukriFreshener()
        result = await agent.run()
        print(result)  # {'success': True, 'actions': [...], 'error': None}
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize with optional config overrides.

        Config keys (all optional — falls back to env vars):
            - naukri_email: Naukri login email
            - naukri_password: Naukri login password
            - resume_path: Path to resume file for upload
            - headless: Run browser in headless mode (default False)
            - tracker_url: Tracker API base URL
        """
        self._config = config or {}

        # Credentials from config or env
        self._email = self._config.get("naukri_email") or os.environ.get("NAUKRI_EMAIL", "")
        self._password = self._config.get("naukri_password") or os.environ.get("NAUKRI_PASSWORD", "")
        self._resume_path = self._config.get("resume_path") or os.environ.get("NAUKRI_RESUME_PATH", "")
        self._headless = self._config.get("headless", False)

        # Browser state — completely independent
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        # State tracking
        self._launched = False
        self._logged_in = False
        self._last_run: datetime | None = None
        self._last_error: str | None = None
        self._actions: list[str] = []

        # Tracker client (own instance, fire-and-forget)
        tracker_url = self._config.get("tracker_url", "http://127.0.0.1:8000/api")
        self._tracker = TrackerClient(base_url=tracker_url)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def launch(self) -> None:
        """Launch a stealth Chromium browser with independent persistent context.

        Uses its own user data directory — completely isolated from LinkedIn agent.
        """
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        user_agent = get_random_ua()
        logger.info("Launching browser with UA: %s", user_agent[:60])

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=self._headless,
            viewport={"width": 1280, "height": 900},
            user_agent=user_agent,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            args=STEALTH_ARGS,
        )

        # Get or create the page
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        # Inject stealth scripts
        stealth_js = get_stealth_scripts()
        await self._context.add_init_script(stealth_js)
        await self._page.add_init_script(stealth_js)

        self._launched = True
        logger.info("Browser launched successfully (data dir: %s)", BROWSER_DATA_DIR)

    async def close(self) -> None:
        """Close browser and clean up resources."""
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            logger.warning("Error during browser cleanup: %s", exc)
        finally:
            self._context = None
            self._page = None
            self._playwright = None
            self._launched = False
            self._logged_in = False
            logger.info("Browser closed.")

    def health_check(self) -> dict[str, Any]:
        """Return current health status of the Naukri agent.

        Returns:
            Dict with keys: status, launched, logged_in, last_run, last_error,
            has_credentials, has_resume.
        """
        has_creds = bool(self._email and self._password)
        has_resume = bool(self._resume_path and Path(self._resume_path).is_file())

        if not has_creds:
            status = "misconfigured"
        elif self._last_error:
            status = "error"
        elif self._launched:
            status = "running"
        else:
            status = "idle"

        return {
            "status": status,
            "launched": self._launched,
            "logged_in": self._logged_in,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_error": self._last_error,
            "has_credentials": has_creds,
            "has_resume": has_resume,
            "browser_data_dir": str(BROWSER_DATA_DIR),
        }


    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(self) -> bool:
        """Login to Naukri.com using credentials from env or config.

        Returns:
            True if login succeeded, False otherwise.
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        if not self._email or not self._password:
            logger.error("Missing Naukri credentials. Set NAUKRI_EMAIL and NAUKRI_PASSWORD.")
            return False

        logger.info("Navigating to Naukri login page...")
        try:
            await self._page.goto(NAUKRI_LOGIN_URL, wait_until="domcontentloaded",
                                  timeout=PAGE_LOAD_TIMEOUT)
            await _human_delay()

            # Check if already logged in (session cookie persisted)
            if await self._is_logged_in():
                logger.info("Already logged in via persistent session.")
                self._logged_in = True
                self._actions.append("login:session_reused")
                return True

            # Fill email
            logger.info("Filling login credentials...")
            filled_email = await _safe_fill(self._page, SELECTORS["email_field"], self._email)
            if not filled_email:
                logger.error("Could not find email field on login page.")
                await self._capture_screenshot("login_email_fail")
                return False

            await _human_delay(0.5, 1.5)

            # Fill password
            filled_pw = await _safe_fill(self._page, SELECTORS["password_field"], self._password)
            if not filled_pw:
                logger.error("Could not find password field on login page.")
                await self._capture_screenshot("login_password_fail")
                return False

            await _human_delay(0.5, 1.0)

            # Click login
            clicked = await _safe_click(self._page, SELECTORS["login_button"])
            if not clicked:
                logger.error("Could not find/click login button.")
                await self._capture_screenshot("login_button_fail")
                return False

            # Wait for navigation / login to complete
            await _human_delay(3.0, 5.0)

            # Verify login succeeded
            if await self._is_logged_in():
                logger.info("Login successful.")
                self._logged_in = True
                self._actions.append("login:success")
                await self._tracker.log(
                    "naukri_login", "success", "Logged in to Naukri.com"
                )
                return True
            else:
                logger.error("Login appears to have failed — no session indicator found.")
                await self._capture_screenshot("login_verify_fail")
                self._actions.append("login:failed")
                return False

        except PlaywrightTimeout as exc:
            logger.error("Login timed out: %s", exc)
            await self._capture_screenshot("login_timeout")
            return False
        except Exception as exc:
            logger.error("Unexpected error during login: %s", exc)
            await self._capture_screenshot("login_error")
            return False

    async def _is_logged_in(self) -> bool:
        """Check if the current page indicates a logged-in state."""
        if not self._page:
            return False
        try:
            # Check for profile-related elements that only appear when logged in
            alternatives = [s.strip() for s in SELECTORS["login_success"].split(",")]
            for alt in alternatives:
                locator = self._page.locator(alt).first
                if await locator.is_visible(timeout=3000):
                    return True
            # Also check URL — if redirected away from login page
            url = self._page.url
            if "/nlogin" not in url and "/login" not in url and "naukri.com" in url:
                return True
        except (PlaywrightTimeout, Exception):
            pass
        return False


    # ------------------------------------------------------------------
    # Toggle Profile Summary
    # ------------------------------------------------------------------

    async def toggle_summary(self) -> bool:
        """Navigate to profile and toggle a '.' at the end of the summary.

        This triggers Naukri's "profile updated" signal which boosts visibility
        in recruiter searches.

        Returns:
            True if the summary was toggled successfully.
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        logger.info("Navigating to profile page to toggle summary...")
        try:
            await self._page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded",
                                  timeout=PAGE_LOAD_TIMEOUT)
            await _human_delay(2.0, 4.0)

            # Find and click the edit icon on the summary/headline widget
            # Look for the resume headline section specifically
            edit_clicked = False

            # Try clicking the pencil/edit icon near the summary section
            edit_selectors = [
                ".widgetHead .edit-icon",
                ".widgetHead .icon",
                "[class*='editIcon']",
                ".widgetHead button",
                "span[class*='edit']",
                ".resumeHeadline .edit-icon",
                ".resumeHeadline [class*='edit']",
            ]

            for selector in edit_selectors:
                try:
                    locator = self._page.locator(selector).first
                    if await locator.is_visible(timeout=3000):
                        await locator.click(timeout=ACTION_TIMEOUT)
                        edit_clicked = True
                        logger.info("Clicked edit icon using selector: %s", selector)
                        break
                except (PlaywrightTimeout, Exception):
                    continue

            if not edit_clicked:
                logger.error("Could not find edit icon for profile summary.")
                await self._capture_screenshot("toggle_edit_fail")
                return False

            await _human_delay(1.0, 2.0)

            # Find the textarea in the edit modal
            textarea = self._page.locator("textarea").first
            try:
                await textarea.wait_for(state="visible", timeout=ACTION_TIMEOUT)
            except PlaywrightTimeout:
                logger.error("Edit modal textarea not found after clicking edit.")
                await self._capture_screenshot("toggle_textarea_fail")
                return False

            # Get current text
            current_text = await textarea.input_value()
            if not current_text:
                current_text = await textarea.text_content() or ""

            # Toggle: append '.' if not ending with one, remove it if it does
            if current_text.endswith("."):
                new_text = current_text[:-1]
                toggle_action = "removed_dot"
            else:
                new_text = current_text + "."
                toggle_action = "added_dot"

            logger.info("Toggling summary: %s (length: %d → %d)",
                        toggle_action, len(current_text), len(new_text))

            # Clear and fill with new text
            await textarea.click()
            await textarea.fill("")
            await _human_delay(0.3, 0.7)
            await textarea.fill(new_text)
            await _human_delay(0.5, 1.0)

            # Click save
            save_clicked = await _safe_click(self._page, SELECTORS["summary_save_button"])
            if not save_clicked:
                logger.error("Could not click Save button after editing summary.")
                await self._capture_screenshot("toggle_save_fail")
                return False

            await _human_delay(2.0, 3.0)

            logger.info("Profile summary toggled successfully (%s).", toggle_action)
            self._actions.append(f"toggle_summary:{toggle_action}")
            await self._tracker.log(
                "naukri_summary_toggled", "success",
                f"Profile summary toggled ({toggle_action})",
                metadata={"action": toggle_action},
            )
            return True

        except PlaywrightTimeout as exc:
            logger.error("Timeout while toggling summary: %s", exc)
            await self._capture_screenshot("toggle_timeout")
            return False
        except Exception as exc:
            logger.error("Unexpected error toggling summary: %s", exc)
            await self._capture_screenshot("toggle_error")
            return False


    # ------------------------------------------------------------------
    # Resume Upload
    # ------------------------------------------------------------------

    async def upload_resume(self) -> bool:
        """Re-upload the resume file to Naukri profile.

        The resume path is read from NAUKRI_RESUME_PATH env var or config.
        Re-uploading refreshes the "resume updated" timestamp on Naukri.

        Returns:
            True if the resume was uploaded successfully.
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        if not self._resume_path:
            logger.warning("No resume path configured. Skipping upload.")
            self._actions.append("upload_resume:skipped_no_path")
            return False

        resume_file = Path(self._resume_path)
        if not resume_file.is_file():
            logger.error("Resume file not found: %s", self._resume_path)
            self._actions.append("upload_resume:file_not_found")
            return False

        logger.info("Uploading resume: %s", resume_file.name)
        try:
            # Ensure we're on the profile page
            current_url = self._page.url
            if "mnjuser/profile" not in current_url:
                await self._page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded",
                                      timeout=PAGE_LOAD_TIMEOUT)
                await _human_delay(2.0, 3.0)

            # Look for the file input element (may be hidden)
            # Naukri typically has a hidden input[type='file'] that we can set directly
            file_input = self._page.locator("input[type='file']").first

            try:
                # Set the file on the input element (works even if hidden)
                await file_input.set_input_files(str(resume_file), timeout=ACTION_TIMEOUT)
                logger.info("File set on input element.")
            except (PlaywrightTimeout, Exception) as exc:
                # Fallback: try clicking the upload button to trigger file dialog
                logger.debug("Direct file input failed (%s), trying button click...", exc)

                upload_buttons = [
                    "#attachCV",
                    ".uploadResume",
                    "input[name='attachCV']",
                    "[id*='attachCV']",
                    "button:has-text('Update Resume')",
                    "a:has-text('Update Resume')",
                ]

                upload_found = False
                for selector in upload_buttons:
                    try:
                        locator = self._page.locator(selector).first
                        if await locator.is_visible(timeout=3000):
                            # Use file chooser pattern
                            async with self._page.expect_file_chooser(timeout=ACTION_TIMEOUT) as fc:
                                await locator.click(timeout=ACTION_TIMEOUT)
                            file_chooser = await fc.value
                            await file_chooser.set_files(str(resume_file))
                            upload_found = True
                            logger.info("File uploaded via file chooser (selector: %s)", selector)
                            break
                    except (PlaywrightTimeout, Exception):
                        continue

                if not upload_found:
                    logger.error("Could not find any upload mechanism on profile page.")
                    await self._capture_screenshot("upload_no_input")
                    return False

            # Wait for success indicator
            await _human_delay(3.0, 5.0)

            # Check for success toast or confirmation
            success_found = False
            success_selectors = [s.strip() for s in SELECTORS["upload_success"].split(",")]
            for sel in success_selectors:
                try:
                    locator = self._page.locator(sel).first
                    if await locator.is_visible(timeout=5000):
                        success_found = True
                        break
                except (PlaywrightTimeout, Exception):
                    continue

            if success_found:
                logger.info("Resume upload confirmed with success indicator.")
            else:
                # No explicit success toast — check if page didn't error out
                logger.info("No explicit success toast found, but no error either. "
                            "Assuming upload succeeded.")

            self._actions.append(f"upload_resume:success:{resume_file.name}")
            await self._tracker.log(
                "naukri_resume_uploaded", "success",
                f"Resume uploaded: {resume_file.name}",
                metadata={"filename": resume_file.name},
            )
            return True

        except PlaywrightTimeout as exc:
            logger.error("Timeout while uploading resume: %s", exc)
            await self._capture_screenshot("upload_timeout")
            return False
        except Exception as exc:
            logger.error("Unexpected error uploading resume: %s", exc)
            await self._capture_screenshot("upload_error")
            return False


    # ------------------------------------------------------------------
    # Full Cycle
    # ------------------------------------------------------------------

    async def run(self) -> dict[str, Any]:
        """Execute the full Naukri profile freshening cycle.

        Steps:
            1. Launch browser (stealth mode)
            2. Login to Naukri.com
            3. Toggle profile summary ('.' append/remove)
            4. Re-upload resume
            5. Close browser

        Returns:
            Dict with keys:
                - success (bool): Whether the cycle completed without fatal errors
                - actions (list[str]): Log of actions taken
                - error (str | None): Error message if failed
        """
        self._actions = []
        self._last_error = None
        start_time = datetime.now(timezone.utc)

        logger.info("=" * 60)
        logger.info("Naukri Freshener — starting run at %s", start_time.isoformat())
        logger.info("=" * 60)

        await self._tracker.log(
            "naukri_cycle_start", "info", "Naukri freshener cycle started"
        )

        try:
            # Step 1: Launch browser
            await self.launch()

            # Step 2: Login
            login_ok = await self.login()
            if not login_ok:
                self._last_error = "Login failed"
                await self._tracker.log(
                    "naukri_cycle_end", "error", "Cycle failed: login unsuccessful"
                )
                return self._build_result(success=False, error="Login failed")

            # Step 3: Toggle summary
            toggle_ok = await self.toggle_summary()
            if not toggle_ok:
                logger.warning("Summary toggle failed, but continuing with resume upload...")

            # Step 4: Upload resume
            upload_ok = await self.upload_resume()
            if not upload_ok:
                logger.warning("Resume upload failed or skipped.")

            # Determine overall success
            success = toggle_ok or upload_ok  # At least one action succeeded
            if not success:
                self._last_error = "Both toggle and upload failed"

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info("Naukri Freshener cycle complete in %.1fs. Actions: %s",
                        duration, self._actions)

            await self._tracker.log(
                "naukri_cycle_end",
                "success" if success else "warning",
                f"Cycle {'completed' if success else 'partial failure'} in {duration:.0f}s",
                metadata={"actions": self._actions, "duration_sec": int(duration)},
            )

            self._last_run = datetime.now(timezone.utc)
            return self._build_result(success=success, error=self._last_error)

        except Exception as exc:
            self._last_error = str(exc)
            logger.error("Fatal error during Naukri freshener run: %s", exc, exc_info=True)
            await self._capture_screenshot("run_fatal_error")
            await self._tracker.log(
                "naukri_cycle_end", "error", f"Fatal error: {exc}",
                metadata={"error": str(exc)},
            )
            return self._build_result(success=False, error=str(exc))

        finally:
            await self.close()

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _build_result(self, success: bool, error: str | None = None) -> dict[str, Any]:
        """Build the standard result dict."""
        return {
            "success": success,
            "actions": list(self._actions),
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _capture_screenshot(self, name: str) -> Path | None:
        """Capture a screenshot for debugging. Returns the file path or None."""
        if not self._page:
            return None

        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"naukri_{name}_{timestamp}.png"
        filepath = SCREENSHOT_DIR / filename

        try:
            await self._page.screenshot(path=str(filepath), full_page=True)
            logger.info("Screenshot saved: %s", filepath)
            return filepath
        except Exception as exc:
            logger.warning("Failed to capture screenshot '%s': %s", name, exc)
            return None


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


async def run_naukri_freshener(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the Naukri freshener as a standalone coroutine.

    Usage:
        import asyncio
        from linkedin_agent.naukri_agent import run_naukri_freshener

        result = asyncio.run(run_naukri_freshener())
    """
    agent = NaukriFreshener(config=config)
    return await agent.run()
