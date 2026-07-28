"""Browser automation via Playwright for LinkedIn interaction.

Uses async Playwright with persistent browser context to maintain login sessions.
Includes human-like delays and retry logic for robustness.

NOTE: LinkedIn frequently updates its DOM structure. Selectors in this module
may need updating if LinkedIn changes their markup.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    TimeoutError as PlaywrightTimeout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LINKEDIN_BASE = "https://www.linkedin.com"
LINKEDIN_LOGIN = f"{LINKEDIN_BASE}/login"
LINKEDIN_FEED = f"{LINKEDIN_BASE}/feed/"
LINKEDIN_JOBS = f"{LINKEDIN_BASE}/jobs/"

# Persistent browser data directory (platform-appropriate)
BROWSER_DATA_DIR = Path(user_data_dir("linkedin_agent", "linkedin_agent")) / "browser_data"

# Screenshot output directory
SCREENSHOT_DIR = Path(user_data_dir("linkedin_agent", "linkedin_agent")) / "screenshots"

# Delay range (seconds) between actions to appear human-like
DELAY_MIN = 1.0
DELAY_MAX = 3.0

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2.0

# ---------------------------------------------------------------------------
# Selectors — LinkedIn DOM selectors (may need updating as LinkedIn changes)
# ---------------------------------------------------------------------------

# NOTE: These selectors are based on LinkedIn's typical DOM structure as of 2024.
# They may break if LinkedIn updates their frontend.

SELECTORS = {
    # Login page
    "login_email": 'input[autocomplete="username"]',
    "login_password": 'input[type="password"]',
    "login_submit": 'button[type="submit"]',

    # Feed detection (logged-in indicator)
    "feed_indicator": "[data-test-id='feed-sort'], .feed-shared-update-v2, .scaffold-layout__main",

    # Jobs page
    "job_card": ".jobs-search-results__list-item, .scaffold-layout__list-item",
    "job_card_title": ".job-card-list__title, .artdeco-entity-lockup__title a",
    "job_card_company": ".artdeco-entity-lockup__subtitle span, .job-card-container__primary-description",
    "job_card_location": ".artdeco-entity-lockup__caption span, .job-card-container__metadata-wrapper span",
    "job_card_link": "a[href*='/jobs/view/']",

    # Job detail page
    "external_apply_indicator": "text=Responses managed off LinkedIn",
    "match_details_button": "button:has-text('Show match details'), button:has-text('See how you compare')",
    "match_score_text": ".job-details-skill-match-status-list, [class*='match']",
    "easy_apply_button": "button.jobs-apply-button, button:has-text('Easy Apply')",

    # Easy Apply modal
    "modal_container": ".jobs-easy-apply-modal, [role='dialog']",
    "modal_input_text": "input[type='text'], input[type='tel'], input[type='email'], input[type='number']",
    "modal_textarea": "textarea",
    "modal_select": "select",
    "modal_radio": "input[type='radio']",
    "modal_fieldset": "fieldset",
    "modal_label": "label",
    "next_button": "button[aria-label='Continue to next step'], button:has-text('Next')",
    "review_button": "button[aria-label='Review your application'], button:has-text('Review')",
    "submit_button": "button[aria-label='Submit application'], button:has-text('Submit application')",
    "success_message": "text=Your application was sent, text=Application submitted",
    "save_button": "button[aria-label='Save'], button:has-text('Save')",
    "dismiss_button": "button[aria-label='Dismiss'], button:has-text('Dismiss'), button:has-text('Not now')",
    "discard_button": "button:has-text('Discard')",
    "close_modal_button": "button[aria-label='Dismiss'], [data-test-modal-close-btn]",

    # Autocomplete dropdown
    "autocomplete_option": "[role='option'], .basic-typeahead__selectable, .typeahead-suggestion",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


async def _human_delay(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX) -> None:
    """Sleep for a randomized duration to mimic human behavior."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def _retry(coro_factory, retries: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """Retry an async operation with exponential backoff.

    Args:
        coro_factory: A callable that returns a new coroutine on each call.
        retries: Maximum number of attempts.
        delay: Base delay between retries (doubles each attempt).

    Returns:
        The result of the coroutine if successful.

    Raises:
        The last exception if all retries fail.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except (PlaywrightTimeout, Exception) as exc:
            last_exc = exc
            if attempt < retries - 1:
                wait = delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d failed: %s. Waiting %.1fs...",
                    attempt + 1, retries, str(exc)[:100], wait,
                )
                await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]



# ---------------------------------------------------------------------------
# LinkedInBrowser class
# ---------------------------------------------------------------------------


class LinkedInBrowser:
    """Async Playwright-based browser automation for LinkedIn.

    Usage:
        browser = LinkedInBrowser()
        await browser.launch(headless=True)
        await browser.login(email, password)
        ...
        await browser.close()
    """

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        """Get the active page, raising if browser not launched."""
        if self._page is None:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def launch(self, headless: bool = True) -> None:
        """Launch browser with persistent context for session reuse.

        Args:
            headless: Run in headless mode (default True). Set False for debugging.
        """
        # Ensure data directories exist
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        # Use persistent context to retain cookies/session across runs
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        # Use the first page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        logger.info("Browser launched (headless=%s, data_dir=%s)", headless, BROWSER_DATA_DIR)

    async def close(self) -> None:
        """Close browser and clean up Playwright resources."""
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed.")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> None:
        """Login to LinkedIn if not already logged in.

        Checks if the current session is still valid by navigating to the feed.
        If already logged in, returns immediately.

        Args:
            email: LinkedIn account email.
            password: LinkedIn account password.
        """
        page = self.page

        # Check if already logged in by visiting feed
        import time as _time
        t0 = _time.time()
        await page.goto(LINKEDIN_FEED, wait_until="domcontentloaded", timeout=15000)

        # Wait up to 5s for possible redirect to feed (session cookies should work fast)
        try:
            await page.wait_for_url("**/feed/**", timeout=5000)
            logger.info("Already logged in (session persisted). (%.1fs)", _time.time()-t0)
            return
        except PlaywrightTimeout:
            pass

        # Double-check current URL after wait
        current = page.url
        if "/feed" in current and "/login" not in current:
            logger.info("Already logged in (session persisted). (%.1fs)", _time.time()-t0)
            return

        logger.info("Session check took %.1fs — not logged in.", _time.time()-t0)

        # Not logged in — but if credentials are empty, skip login attempt
        if not email or not password:
            logger.warning("No credentials provided and session expired. Agent cannot proceed.")
            raise RuntimeError(
                "LinkedIn session expired and no credentials configured. "
                "Copy a valid session into Docker: ./copy-session-to-docker.sh"
            )

        # Navigate to login page
        logger.info("Session expired. Logging in with credentials...")
        await page.goto(LINKEDIN_LOGIN, wait_until="domcontentloaded")
        await _human_delay(2, 4)

        # LinkedIn's login page sometimes hides the email field initially
        # or uses a multi-step flow. Try multiple approaches:
        try:
            # Approach 1: Wait for visible email input
            email_locator = page.locator(SELECTORS["login_email"]).first
            visible = await email_locator.is_visible()

            if not visible:
                # The input exists but is hidden — LinkedIn may show it after interaction
                # Try clicking the page to trigger the form
                await page.click("body")
                await _human_delay(1, 2)
                visible = await email_locator.is_visible()

            if visible:
                await email_locator.fill(email)
                await _human_delay(0.5, 1.0)

                pass_locator = page.locator(SELECTORS["login_password"]).first
                await pass_locator.wait_for(state="visible", timeout=5000)
                await pass_locator.fill(password)
                await _human_delay(0.5, 1.5)

                # Submit
                await page.click(SELECTORS["login_submit"])
            else:
                # Approach 2: Try JavaScript fill as fallback
                logger.info("Email input hidden. Attempting JS-based login...")
                await page.evaluate(f'''() => {{
                    const emailEl = document.querySelector('input[autocomplete="username"]');
                    const passEl = document.querySelector('input[type="password"]');
                    if (emailEl) {{ emailEl.value = "{email}"; emailEl.dispatchEvent(new Event("input", {{bubbles: true}})); }}
                    if (passEl) {{ passEl.value = "{password}"; passEl.dispatchEvent(new Event("input", {{bubbles: true}})); }}
                }}''')
                await _human_delay(1, 2)
                submit = page.locator(SELECTORS["login_submit"]).first
                if await submit.is_visible():
                    await submit.click()
                else:
                    await page.keyboard.press("Enter")

        except PlaywrightTimeout:
            # Check if we ended up on feed anyway
            if "/feed" in page.url:
                logger.info("Login successful (redirected through challenge).")
                return
            raise RuntimeError(
                f"LinkedIn login form not accessible. The page may require manual interaction. "
                f"Current URL: {page.url[:80]}"
            )

        # Wait for navigation to feed (or security challenge)
        try:
            await page.wait_for_url("**/feed/**", timeout=60000)
            logger.info("Login successful.")
        except PlaywrightTimeout:
            # Check if we landed on feed despite timeout
            if "/feed" in page.url:
                logger.info("Login successful (late redirect).")
                return
            # May have hit a security challenge (CAPTCHA, verification)
            current_url = page.url
            logger.warning(
                "Login did not redirect to feed. Current URL: %s. "
                "Manual intervention may be required.",
                current_url,
            )
            await self.take_screenshot("login_challenge")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def navigate_to_jobs(self, collection: str = "Recommended") -> None:
        """Navigate to a specific job collection page.

        Args:
            collection: The job collection to navigate to (e.g. 'Recommended').
        """
        page = self.page

        # Navigate to jobs landing page
        # NOTE: LinkedIn's job collection URLs may vary. This targets the
        # collections/recommended path.
        collection_slug = collection.lower().replace(" ", "-")
        url = f"{LINKEDIN_JOBS}collections/{collection_slug}/"

        await page.goto(url, wait_until="domcontentloaded")
        await _human_delay()

        logger.info("Navigated to jobs collection: %s", collection)

    async def search_jobs(
        self,
        keyword: str,
        location: str = "",
        posted_within: str = "week",
    ) -> None:
        """Search LinkedIn jobs by keyword and location.

        Args:
            keyword: Job title/keyword to search (e.g. "Engineering Manager").
            location: Location filter (e.g. "India", "Bangalore").
            posted_within: Time filter — "day", "week", "month", or "" for any.
        """
        page = self.page

        # Build LinkedIn job search URL with parameters
        # LinkedIn search URL format: /jobs/search/?keywords=X&location=Y&f_TPR=rN
        import urllib.parse
        params = {"keywords": keyword}
        if location:
            params["location"] = location

        # Time posted filter
        # LinkedIn uses f_TPR for time and supports these values:
        #   r86400 = past 24 hours
        #   r604800 = past week
        #   r2592000 = past month
        time_map = {
            "24h": "r86400", "day": "r86400",
            "week": "r604800", "7d": "r604800",
            "month": "r2592000", "30d": "r2592000",
        }
        if posted_within in time_map:
            params["f_TPR"] = time_map[posted_within]

        # Easy Apply filter
        params["f_AL"] = "true"  # Only show Easy Apply jobs

        search_url = f"{LINKEDIN_JOBS}search/?{urllib.parse.urlencode(params)}"
        await page.goto(search_url, wait_until="domcontentloaded")
        await _human_delay(2, 4)

        logger.info(
            "Searched jobs: keyword='%s', location='%s', posted='%s'",
            keyword, location, posted_within,
        )

    # ------------------------------------------------------------------
    # Job Listings
    # ------------------------------------------------------------------

    async def get_job_listings(self, max_count: int = 50) -> list[dict[str, Any]]:
        """Scrape job cards from the current job collection page.

        Scrolls to load more cards if needed.

        Args:
            max_count: Maximum number of job listings to retrieve.

        Returns:
            List of dicts with keys: job_id, title, company, location, url.
        """
        page = self.page
        listings: list[dict[str, Any]] = []

        # Scroll to load job cards (LinkedIn lazy-loads them)
        for _ in range(max_count // 10 + 1):
            await page.evaluate("window.scrollBy(0, 800)")
            await _human_delay(0.5, 1.5)

        # Find all job card links
        # NOTE: Selector targets anchor elements linking to /jobs/view/<id>/
        job_links = await page.query_selector_all("a[href*='/jobs/view/']")

        seen_ids: set[str] = set()

        for link in job_links:
            if len(listings) >= max_count:
                break

            href = await link.get_attribute("href") or ""
            # Extract job ID from URL like /jobs/view/1234567890/
            match = re.search(r"/jobs/view/(\d+)", href)
            if not match:
                continue

            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            # Get the card container (parent elements)
            card = await link.evaluate_handle(
                "el => el.closest('.job-card-container, .jobs-search-results__list-item, li')"
            )

            title = ""
            company = ""
            location = ""

            if card:
                # Try to extract title from the link text itself
                title = (await link.inner_text()).strip()

                # Extract company name
                # NOTE: Selector may need updating
                company_el = await card.as_element().query_selector(
                    ".artdeco-entity-lockup__subtitle span, "
                    ".job-card-container__primary-description, "
                    ".job-card-container__company-name"
                )
                if company_el:
                    company = (await company_el.inner_text()).strip()

                # Extract location
                # NOTE: Selector may need updating
                location_el = await card.as_element().query_selector(
                    ".artdeco-entity-lockup__caption span, "
                    ".job-card-container__metadata-wrapper span, "
                    ".job-card-container__metadata-item"
                )
                if location_el:
                    location = (await location_el.inner_text()).strip()

            listings.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": f"{LINKEDIN_BASE}/jobs/view/{job_id}/",
            })

        logger.info("Found %d job listings (max requested: %d).", len(listings), max_count)
        return listings

    async def open_job(self, job_id: str) -> None:
        """Navigate to a specific job detail page.

        Args:
            job_id: The LinkedIn job ID.
        """
        page = self.page
        url = f"{LINKEDIN_BASE}/jobs/view/{job_id}/"
        await page.goto(url, wait_until="domcontentloaded")
        await _human_delay()
        logger.info("Opened job %s", job_id)

    # ------------------------------------------------------------------
    # Job Detail Analysis
    # ------------------------------------------------------------------

    async def is_external_apply(self) -> bool:
        """Check if the current job routes applications externally.

        Returns:
            True if the job explicitly shows 'Responses managed off LinkedIn'.
            False if Easy Apply button is found OR no clear external indicator.
        """
        page = self.page
        try:
            # Wait a moment for the page to fully render
            await asyncio.sleep(1)

            # Check for explicit external indicator text
            external_indicator = await page.query_selector(
                "text=Responses managed off LinkedIn"
            )
            if external_indicator:
                logger.info("Job is external apply (explicit indicator).")
                return True

            # Look for Easy Apply button (wait up to 5 seconds)
            try:
                easy_apply = await page.wait_for_selector(
                    SELECTORS["easy_apply_button"], timeout=5000
                )
                if easy_apply:
                    return False  # Easy Apply found — not external
            except PlaywrightTimeout:
                pass

            # If we searched with Easy Apply filter but button isn't visible,
            # it might just be loading slow. Don't skip aggressively.
            # Only skip if there's a clear "Apply" link pointing externally.
            external_link = await page.query_selector(
                'a[data-tracking-control-name*="apply_external"], '
                'a[href*="applyWithLinkedIn=false"]'
            )
            if external_link:
                logger.info("Job has external apply link.")
                return True

            # Default: not external (give it the benefit of doubt)
            logger.info("No Easy Apply button found, but no external indicator either. Treating as Easy Apply.")
            return False

        except Exception:
            return False

    async def get_match_score(self) -> tuple[int, int]:
        """Get the qualification match score from LinkedIn's AI coach.

        Clicks 'Show match details' which triggers LinkedIn's AI assessment
        in the coach overlay (bottom-right drawer). Waits for the AI to
        finish evaluating, then parses the result.

        Returns:
            Tuple of (matched, total) qualifications. e.g. (6, 8).
            Returns (0, 0) if match info is unavailable.
        """
        page = self.page

        try:
            # Click 'Show match details' (it's a <p> tag, not a button)
            match_el = page.locator("text=Show match details").first
            if not await match_el.is_visible():
                logger.warning("'Show match details' not found on this page.")
                return (0, 0)

            await match_el.click()
            logger.info("Clicked 'Show match details' — waiting for AI evaluation...")

            # Poll the coach overlay for the result (AI takes 5-15 seconds)
            for attempt in range(20):  # Check every 1.5s for 30s total
                await asyncio.sleep(1.5)

                # Find the overlay/coach panel
                overlay = await page.query_selector(
                    "[class*='overlay'], [class*='coach'], [class*='drawer'], [role='dialog']"
                )
                if not overlay:
                    continue

                text = await overlay.inner_text()

                # Still loading?
                if "loading" in text.lower() or "evaluating" in text.lower():
                    continue

                # Look for the score pattern
                # LinkedIn says: "Matches X of the Y required qualifications"
                # or: "Matches X of Y required qualifications"
                patterns = [
                    r"[Mm]atches?\s+(\d+)\s+of\s+(?:the\s+)?(\d+)\s+required\s+qualifications?",
                    r"[Mm]atches?\s+(\d+)\s+of\s+(?:the\s+)?(\d+)\s+qualifications?",
                    r"(\d+)\s+of\s+(?:the\s+)?(\d+)\s+required\s+qualifications?",
                    r"(\d+)\s+of\s+(?:the\s+)?(\d+)\s+qualifications?\s+match",
                ]

                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        matched = int(match.group(1))
                        total = int(match.group(2))
                        logger.info("Match score: %d/%d (%.0f%%)", matched, total, matched / total * 100)
                        return (matched, total)

                # If we have content but no pattern match, check if evaluation completed
                if len(text) > 100 and "evaluating" not in text.lower():
                    # Try a broader search
                    broad = re.search(r"(\d+)\s+of\s+(?:the\s+)?(\d+)", text)
                    if broad:
                        matched = int(broad.group(1))
                        total = int(broad.group(2))
                        if 0 < matched <= total <= 20:  # Sanity check
                            logger.info("Match score (broad): %d/%d (%.0f%%)", matched, total, matched / total * 100)
                            return (matched, total)
                    break  # Content loaded but no score found

            logger.warning("LinkedIn AI did not return a parseable match score within 30s.")
            return (0, 0)

        except Exception as exc:
            logger.warning("Failed to get match score: %s", exc)
            return (0, 0)

    # ------------------------------------------------------------------
    # Easy Apply Flow
    # ------------------------------------------------------------------

    async def click_easy_apply(self) -> None:
        """Click the Easy Apply button on the current job page."""
        page = self.page

        async def _click():
            btn = await page.wait_for_selector(
                SELECTORS["easy_apply_button"], timeout=10000
            )
            await btn.click()

        await _retry(_click)
        await _human_delay()
        logger.info("Clicked Easy Apply button.")

    async def get_current_modal_fields(self) -> list[dict[str, Any]]:
        """Parse the current Easy Apply modal screen for form fields.

        Returns:
            List of field dicts with keys: name, type, selector, required, options.
            'type' is one of: 'text', 'textarea', 'select', 'radio', 'checkbox'.
        """
        page = self.page
        fields: list[dict[str, Any]] = []

        await _human_delay(0.5, 1.0)

        # Wait for modal to be visible
        try:
            await page.wait_for_selector(SELECTORS["modal_container"], timeout=5000)
        except PlaywrightTimeout:
            logger.warning("Modal container not found.")
            return fields

        # --- Text inputs ---
        text_inputs = await page.query_selector_all(
            f"{SELECTORS['modal_container']} input[type='text'], "
            f"{SELECTORS['modal_container']} input[type='tel'], "
            f"{SELECTORS['modal_container']} input[type='email'], "
            f"{SELECTORS['modal_container']} input[type='number']"
        )
        for inp in text_inputs:
            label_text = await self._get_field_label(inp)
            required = await inp.get_attribute("required") is not None
            field_id = await inp.get_attribute("id") or ""
            fields.append({
                "name": label_text,
                "type": "text",
                "selector": f"#{field_id}" if field_id else None,
                "required": required,
                "options": None,
            })

        # --- Textareas ---
        textareas = await page.query_selector_all(
            f"{SELECTORS['modal_container']} textarea"
        )
        for ta in textareas:
            label_text = await self._get_field_label(ta)
            required = await ta.get_attribute("required") is not None
            field_id = await ta.get_attribute("id") or ""
            fields.append({
                "name": label_text,
                "type": "textarea",
                "selector": f"#{field_id}" if field_id else None,
                "required": required,
                "options": None,
            })

        # --- Select dropdowns ---
        selects = await page.query_selector_all(
            f"{SELECTORS['modal_container']} select"
        )
        for sel in selects:
            label_text = await self._get_field_label(sel)
            required = await sel.get_attribute("required") is not None
            field_id = await sel.get_attribute("id") or ""
            # Get options
            options = await sel.evaluate(
                "el => Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}))"
            )
            fields.append({
                "name": label_text,
                "type": "select",
                "selector": f"#{field_id}" if field_id else None,
                "required": required,
                "options": options,
            })

        # --- Radio buttons (grouped by fieldset/name) ---
        fieldsets = await page.query_selector_all(
            f"{SELECTORS['modal_container']} fieldset"
        )
        for fs in fieldsets:
            legend = await fs.query_selector("legend, span[aria-hidden='true']")
            label_text = (await legend.inner_text()).strip() if legend else "Unknown"
            radios = await fs.query_selector_all("input[type='radio']")
            options = []
            for radio in radios:
                radio_label = await radio.evaluate_handle(
                    "el => el.closest('label') || el.parentElement.querySelector('label') || el.nextElementSibling"
                )
                radio_text = ""
                if radio_label:
                    radio_text = (await radio_label.as_element().inner_text()).strip()
                value = await radio.get_attribute("value") or radio_text
                options.append({"value": value, "text": radio_text})
            fields.append({
                "name": label_text,
                "type": "radio",
                "selector": None,
                "required": True,
                "options": options,
            })

        logger.info("Found %d fields in current modal screen.", len(fields))
        return fields

    async def _get_field_label(self, element) -> str:
        """Extract the label text for a form field element.

        Tries aria-label, associated <label>, then placeholder.
        """
        # Try aria-label
        aria_label = await element.get_attribute("aria-label")
        if aria_label:
            return aria_label.strip()

        # Try associated label via id
        field_id = await element.get_attribute("id")
        if field_id:
            page = self.page
            label = await page.query_selector(f"label[for='{field_id}']")
            if label:
                return (await label.inner_text()).strip()

        # Try parent label
        parent_label = await element.evaluate_handle(
            "el => el.closest('label')"
        )
        if parent_label:
            el = parent_label.as_element()
            if el:
                return (await el.inner_text()).strip()

        # Fallback to placeholder
        placeholder = await element.get_attribute("placeholder")
        if placeholder:
            return placeholder.strip()

        return "Unknown field"

    # ------------------------------------------------------------------
    # Form Interaction
    # ------------------------------------------------------------------

    async def fill_field(self, field_name: str, value: str) -> None:
        """Fill a form field by its label/name.

        Handles text inputs, textareas, selects, and radio buttons.

        Args:
            field_name: The label or name of the field to fill.
            value: The value to set.
        """
        page = self.page
        await _human_delay(0.3, 0.8)

        # Strategy: find the field by label text, then interact with its input
        # Try label[for] -> input#id approach first
        label = await page.query_selector(f"label:has-text('{field_name}')")

        if label:
            field_id = await label.get_attribute("for")
            if field_id:
                element = await page.query_selector(f"#{field_id}")
                if element:
                    tag = await element.evaluate("el => el.tagName.toLowerCase()")
                    input_type = await element.get_attribute("type") or ""

                    if tag == "select":
                        await element.select_option(label=value)
                        logger.info("Selected '%s' for field '%s'", value, field_name)
                        return

                    if input_type == "radio":
                        # Find the radio with matching value/text
                        await self._select_radio(field_name, value)
                        return

                    # Text input or textarea — clear and type
                    await element.click()
                    await element.fill("")  # Clear existing value
                    await element.type(value, delay=random.randint(30, 80))
                    logger.info("Filled field '%s' with '%s'", field_name, value[:30])
                    return

        # Fallback: try aria-label matching
        input_el = await page.query_selector(
            f"input[aria-label*='{field_name}'], "
            f"textarea[aria-label*='{field_name}'], "
            f"select[aria-label*='{field_name}']"
        )
        if input_el:
            tag = await input_el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                await input_el.select_option(label=value)
            else:
                await input_el.click()
                await input_el.fill("")
                await input_el.type(value, delay=random.randint(30, 80))
            logger.info("Filled field '%s' (aria-label match) with '%s'", field_name, value[:30])
            return

        logger.warning("Could not find field '%s' to fill.", field_name)

    async def _select_radio(self, group_name: str, value: str) -> None:
        """Select a radio button by group name and value text."""
        page = self.page

        # Find fieldset or group containing the label
        fieldset = await page.query_selector(
            f"fieldset:has(legend:has-text('{group_name}')), "
            f"fieldset:has(span:has-text('{group_name}'))"
        )
        if not fieldset:
            logger.warning("Could not find radio group '%s'", group_name)
            return

        # Find the label matching the value and click it
        radio_label = await fieldset.query_selector(f"label:has-text('{value}')")
        if radio_label:
            await radio_label.click()
            logger.info("Selected radio '%s' in group '%s'", value, group_name)
        else:
            # Try clicking the radio input directly by value attribute
            radio_input = await fieldset.query_selector(f"input[value='{value}']")
            if radio_input:
                await radio_input.click()
                logger.info("Selected radio value '%s' in group '%s'", value, group_name)
            else:
                logger.warning("Could not find radio option '%s' in group '%s'", value, group_name)

    async def click_autocomplete_option(self, field_selector: str, value: str) -> None:
        """Type a value into an autocomplete field and click the matching dropdown option.

        IMPORTANT: Never press Enter — always click the option from the dropdown.

        Args:
            field_selector: CSS selector for the input field.
            value: The text to type and select from suggestions.
        """
        page = self.page

        # Focus and clear the input
        input_el = await page.wait_for_selector(field_selector, timeout=5000)
        await input_el.click()
        await input_el.fill("")
        await _human_delay(0.3, 0.5)

        # Type the value character by character to trigger autocomplete
        await input_el.type(value, delay=random.randint(50, 120))
        await _human_delay(1.0, 2.0)  # Wait for dropdown to appear

        # Wait for and click the autocomplete option
        # NOTE: LinkedIn's autocomplete uses role='option' or specific class names
        try:
            option = await page.wait_for_selector(
                f"{SELECTORS['autocomplete_option']}:has-text('{value}')",
                timeout=5000,
            )
            await option.click()
            logger.info("Clicked autocomplete option: '%s'", value)
        except PlaywrightTimeout:
            # Try a more lenient match (first visible option)
            logger.warning(
                "Exact autocomplete match not found for '%s'. Trying first option.", value
            )
            first_option = await page.query_selector(SELECTORS["autocomplete_option"])
            if first_option:
                await first_option.click()
                logger.info("Clicked first autocomplete option as fallback.")
            else:
                logger.error("No autocomplete options appeared for '%s'", value)

        await _human_delay(0.3, 0.8)

    # ------------------------------------------------------------------
    # Modal Navigation & Submission
    # ------------------------------------------------------------------

    async def click_next(self) -> None:
        """Click the Next button in the Easy Apply modal."""
        page = self.page

        async def _click():
            # Try Next button first, then Review button
            btn = await page.query_selector(SELECTORS["next_button"])
            if not btn:
                btn = await page.query_selector(SELECTORS["review_button"])
            if not btn:
                raise PlaywrightTimeout("Next/Review button not found")
            await btn.click()

        await _retry(_click)
        await _human_delay()
        logger.info("Clicked Next button.")

    async def click_submit(self) -> None:
        """Click the Submit button in the Easy Apply modal."""
        page = self.page

        async def _click():
            btn = await page.wait_for_selector(
                SELECTORS["submit_button"], timeout=10000
            )
            await btn.click()

        await _retry(_click)
        await _human_delay()
        logger.info("Clicked Submit button.")

    async def confirm_submission(self) -> bool:
        """Check if the application was successfully submitted.

        Returns:
            True if a success message is detected.
        """
        page = self.page

        try:
            # Wait for success indicators
            success = await page.wait_for_selector(
                SELECTORS["success_message"], timeout=10000
            )
            if success:
                logger.info("Application submission confirmed.")
                return True
        except PlaywrightTimeout:
            pass

        # Fallback: check page content for success text
        content = await page.content()
        if "application was sent" in content.lower() or "application submitted" in content.lower():
            logger.info("Application submission confirmed (text match).")
            return True

        logger.warning("Could not confirm submission.")
        return False

    async def save_and_close(self) -> None:
        """Close the Easy Apply modal by clicking Save (preserves progress).

        Does NOT click Discard — preserves the draft application.
        """
        page = self.page

        # Click the close/dismiss button on the modal
        close_btn = await page.query_selector(SELECTORS["close_modal_button"])
        if close_btn:
            await close_btn.click()
            await _human_delay(0.5, 1.0)

        # A confirmation dialog may appear — click Save (not Discard)
        try:
            save_btn = await page.wait_for_selector(
                SELECTORS["save_button"], timeout=3000
            )
            if save_btn:
                await save_btn.click()
                logger.info("Saved and closed modal.")
        except PlaywrightTimeout:
            # No confirmation dialog appeared — modal already closed
            logger.info("Modal closed (no save confirmation needed).")

    async def dismiss_upsell(self) -> None:
        """Dismiss any post-submission upsell or prompt dialogs.

        LinkedIn often shows 'Get Premium' or 'Follow company' prompts after applying.
        """
        page = self.page
        await _human_delay(0.5, 1.0)

        # Try various dismiss buttons
        dismiss_selectors = [
            SELECTORS["dismiss_button"],
            "button:has-text('Not now')",
            "button:has-text('No thanks')",
            "button[aria-label='Dismiss']",
            "button:has-text('Done')",
        ]

        for selector in dismiss_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info("Dismissed upsell/prompt: %s", selector)
                    await _human_delay(0.3, 0.8)
                    return
            except Exception:
                continue

        logger.debug("No upsell dialog to dismiss.")

    # ------------------------------------------------------------------
    # Debugging & Utilities
    # ------------------------------------------------------------------

    async def take_screenshot(self, name: str) -> None:
        """Save a screenshot for debugging purposes.

        Args:
            name: Descriptive name for the screenshot file.
        """
        page = self.page
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        filepath = SCREENSHOT_DIR / f"{name}.png"
        await page.screenshot(path=str(filepath), full_page=False)
        logger.info("Screenshot saved: %s", filepath)
