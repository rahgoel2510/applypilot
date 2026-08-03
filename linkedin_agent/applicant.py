"""Application submission logic — orchestrates the Easy Apply flow step by step."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from linkedin_agent.answer_generator import AnswerGenerator, get_answer_generator

if TYPE_CHECKING:
    from playwright.async_api import Page

    from linkedin_agent.browser import BrowserManager
    from linkedin_agent.matcher import JobMatcher
    from linkedin_agent.telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)


@dataclass
class ApplicationResult:
    """Outcome of a single job application attempt."""

    status: Literal[
        "submitted",
        "paused",
        "skipped_threshold",
        "skipped_external",
        "duplicate",
        "error",
    ]
    job_id: str
    title: str
    company: str
    location: str
    match_score: float | None = None
    blocking_fields: list[str] = field(default_factory=list)
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class ApplicationExecutor:
    """Orchestrates the LinkedIn Easy Apply flow for a single job posting."""

    # CSS selectors for LinkedIn Easy Apply modal elements
    SELECTORS = {
        "easy_apply_btn": 'button.jobs-apply-button, button[aria-label*="Easy Apply"]',
        "modal": "div.jobs-easy-apply-modal",
        "next_btn": 'button[aria-label="Continue to next step"]',
        "review_btn": 'button[aria-label="Review your application"]',
        "submit_btn": 'button[aria-label="Submit application"]',
        "close_btn": 'button[aria-label="Dismiss"], button[data-test-modal-close-btn]',
        "discard_btn": 'button[data-test-dialog-primary-btn], button:has-text("Discard")',
        "done_btn": 'button[aria-label="Done"], button:has-text("Done")',
        "external_apply": 'a[data-tracking-control-name*="apply_external"]',
        "city_input": 'input[id*="city"], input[aria-label*="City"]',
        "autocomplete_option": 'div[role="option"], li[role="option"]',
        "resume_item": 'div[data-test-resume-card], label:has-text(".pdf")',
        "resume_selected": 'div[data-test-resume-card][aria-checked="true"]',
        "top_choice_checkbox": 'input[id*="topChoice"], label:has-text("top choice")',
        "form_fields": "div.jobs-easy-apply-form-section__grouping",
        "field_label": "label, legend, span.fb-dash-form-element__label",
        "text_input": 'input[type="text"], input[type="number"], input:not([type])',
        "select_input": "select",
        "textarea_input": "textarea",
        "radio_group": 'fieldset:has(input[type="radio"])',
        "save_draft_btn": 'button:has-text("Save"), button[aria-label*="save"]',
        "upsell_dismiss": 'button[aria-label="Not now"], button:has-text("Not now")',
    }

    # Fields we can auto-fill from candidate config
    AUTO_FILLABLE_PATTERNS = {
        "phone": ["phone", "mobile", "contact number"],
        "email": ["email"],
        "city": ["city", "location"],
        "notice_period": ["notice period", "start date", "joining"],
        "work_authorization": [
            "authorized",
            "work authorization",
            "legally authorized",
            "sponsorship",
        ],
        "willing_to_relocate": ["relocate", "relocation"],
    }

    # Fields that require human decision — trigger pause
    SENSITIVE_FIELD_PATTERNS = [
        "salary",
        "compensation",
        "expected ctc",
        "current ctc",
        "disability",
        "veteran",
        "gender",
        "ethnicity",
        "race",
    ]

    def __init__(
        self,
        browser: BrowserManager,
        matcher: JobMatcher,
        notifier: TelegramNotifier,
        config: dict,
    ) -> None:
        self.browser = browser
        self.matcher = matcher
        self.notifier = notifier
        self.config = config
        self.candidate = config.get("candidate", {})
        self.job_search = config.get("job_search", {})
        self._applied_jobs: set[str] = set()  # track duplicates within session
        self._current_job_title: str = ""  # set per-job for resume selection
        self._current_company: str = ""  # set per-job for AI answer context
        self._answer_gen = get_answer_generator({
            **self.candidate,
            'keywords': self.config.get('job_search', {}).get('keywords', []),
        })

    @property
    def page(self) -> Page:
        """Shortcut to active Playwright page."""
        return self.browser.page

    # ─── Main Entry Point ─────────────────────────────────────────────────

    async def apply_to_job(self, job: dict) -> ApplicationResult:
        """Run the full Easy Apply flow for one job posting.

        Args:
            job: Dict with keys: id, title, company, location, description, url

        Returns:
            ApplicationResult with status and metadata.
        """
        job_id = job.get("id", "unknown")
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        location = job.get("location", "Unknown")

        self._current_job_title = title
        self._current_company = company

        logger.info(f"Processing job: {title} at {company} ({job_id})")

        try:
            # Step a: Check external apply
            if await self._is_external_apply():
                logger.info(f"Skipping external apply: {title}")
                return ApplicationResult(
                    status="skipped_external",
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                )

            # Step b: Get match score (already computed by orchestrator)
            match_score = job.get("match_score")
            threshold = self.job_search.get("match_threshold", 0.80)

            if match_score is not None and match_score < threshold:
                logger.info(
                    f"Below threshold ({match_score:.2f} < {threshold}): {title}"
                )
                return ApplicationResult(
                    status="skipped_threshold",
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    match_score=match_score,
                )

            # Step c: Check duplicate
            if job_id in self._applied_jobs:
                logger.info(f"Duplicate job skipped: {title}")
                return ApplicationResult(
                    status="duplicate",
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    match_score=match_score,
                )

            # Step d: Click Easy Apply
            await self._click_easy_apply()
            await self._take_screenshot("after_easy_apply_click", job_id)

            # Step e: Contact info screen
            if not await self.handle_contact_screen():
                return await self._pause_and_return(
                    job_id, title, company, location, match_score, ["contact_info"]
                )
            await self._click_next()
            await self._take_screenshot("after_contact", job_id)

            # Step f: Resume screen
            if not await self.handle_resume_screen():
                return await self._pause_and_return(
                    job_id, title, company, location, match_score, ["resume_selection"]
                )
            await self._click_next()
            await self._take_screenshot("after_resume", job_id)

            # Step g: Handle 'Mark as top choice' (skip/uncheck)
            await self._handle_top_choice()

            # Step h: Additional questions
            can_proceed, blocking_fields = await self.handle_additional_questions()
            if not can_proceed:
                return await self._pause_and_return(
                    job_id, title, company, location, match_score, blocking_fields
                )
            await self._take_screenshot("after_questions", job_id)

            # Step i: Review screen
            if not await self.handle_review_screen():
                return await self._pause_and_return(
                    job_id,
                    title,
                    company,
                    location,
                    match_score,
                    ["review_verification"],
                )
            await self._take_screenshot("after_review", job_id)

            # Step j: Submit
            if not await self.submit():
                return ApplicationResult(
                    status="error",
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    match_score=match_score,
                    error_message="Submit button click failed",
                )

            # Step k: Confirm and dismiss upsells
            await self._dismiss_post_submit()
            await self._take_screenshot("after_submit", job_id)

            self._applied_jobs.add(job_id)

            logger.info(f"Successfully applied to: {title} at {company}")

            # Notify on successful submission
            if self.config.get("telegram", {}).get("notify_on_submit", True):
                score_pct = f"{match_score:.2f}" if match_score else "N/A"
                await self.notifier.send_notification(
                    f"✅ Applied: {title} at {company}\n"
                    f"📍 {location} | Score: {score_pct}"
                )

            return ApplicationResult(
                status="submitted",
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                match_score=match_score,
            )

        except Exception as e:
            logger.error(f"Error applying to {title} at {company}: {e}", exc_info=True)
            await self._take_screenshot("error", job_id)
            await self._close_modal_gracefully()

            return ApplicationResult(
                status="error",
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                match_score=None,
                error_message=str(e),
            )

    # ─── Screen Handlers ──────────────────────────────────────────────────

    def _select_resume_for_job(self, job_title: str) -> str:
        """Select the best resume file based on job title keyword matching.

        Checks resume_mapping entries in order. First match wins.
        Falls back to default resume_filename if no match.
        """
        title_lower = job_title.lower()
        for mapping in self.candidate.get('resume_mapping', []):
            keywords = mapping.get('keywords', [])
            for kw in keywords:
                if kw.lower() in title_lower or title_lower in kw.lower():
                    return mapping.get('resume', self.candidate.get('resume_filename', ''))
        return self.candidate.get('resume_filename', '')

    async def handle_contact_screen(self) -> bool:
        """Verify pre-filled contact info and fill city via autocomplete click.

        Returns:
            True if the screen is properly filled, False if manual intervention needed.
        """
        logger.debug("Handling contact info screen")

        await self._wait_for_form_load()

        # Verify email and phone are pre-filled (LinkedIn usually does this)
        # We don't overwrite them — just confirm they exist
        email_filled = await self._check_field_has_value("email")
        phone_filled = await self._check_field_has_value("phone")

        if not email_filled:
            logger.warning("Email field appears empty")
        if not phone_filled:
            logger.warning("Phone field appears empty")

        # Fill city using autocomplete dropdown (must CLICK suggestion, not just type)
        city_input = await self.page.query_selector(self.SELECTORS["city_input"])
        if city_input:
            preferred_city = self.candidate.get("preferred_cities", ["Bangalore"])[0]
            current_value = await city_input.input_value()

            if not current_value.strip():
                logger.info(f"Filling city field with: {preferred_city}")
                await city_input.click()
                await city_input.fill("")
                await city_input.type(preferred_city, delay=80)

                # Wait for autocomplete dropdown to appear
                await asyncio.sleep(1.0)

                # Click the first matching autocomplete suggestion
                autocomplete = await self.page.query_selector(
                    self.SELECTORS["autocomplete_option"]
                )
                if autocomplete:
                    await autocomplete.click()
                    logger.info(f"Selected city from autocomplete: {preferred_city}")
                    await asyncio.sleep(0.5)
                else:
                    logger.warning(
                        "No autocomplete suggestion appeared for city; "
                        "pressing Enter as fallback"
                    )
                    await city_input.press("Enter")

        return True

    async def handle_resume_screen(self) -> bool:
        """Ensure the correct resume is selected. Uploads if not found on LinkedIn.

        Strategy:
        1. Look for our resume in the existing resume cards
        2. If found → click to select it
        3. If NOT found → upload from local /resumes/ directory
        4. Verify selection

        Returns:
            True if resume is active, False if something went wrong.
        """
        logger.debug("Handling resume screen")

        await self._wait_for_form_load()

        expected_resume = self.candidate.get("resume_filename", "RAHUL_GOEL_Resume_Final.pdf")
        logger.info(f"Looking for resume: {expected_resume}")

        # Check if correct resume is already selected
        selected = await self.page.query_selector(self.SELECTORS["resume_selected"])
        if selected:
            text = await selected.inner_text()
            if expected_resume.lower() in text.lower():
                logger.info(f"Resume already selected: {expected_resume}")
                return True

        # Try to find and click the correct resume card
        resume_cards = await self.page.query_selector_all(self.SELECTORS["resume_item"])
        for card in resume_cards:
            card_text = await card.inner_text()
            if expected_resume.lower() in card_text.lower():
                await card.click()
                logger.info(f"Selected existing resume: {expected_resume}")
                await asyncio.sleep(0.5)
                return True

        # Resume NOT found on LinkedIn — try to upload it
        logger.info(f"Resume '{expected_resume}' not found on LinkedIn. Attempting upload...")

        # Look for the file locally
        from pathlib import Path as _Path
        search_paths = [
            _Path.cwd() / "resumes" / expected_resume,
            _Path.cwd() / expected_resume,
            _Path.home() / "Documents" / expected_resume,
            _Path.home() / "Downloads" / expected_resume,
        ]

        local_file = None
        for path in search_paths:
            if path.exists():
                local_file = path
                break

        if not local_file:
            logger.error(f"Resume file not found locally: {expected_resume}")
            logger.error(f"Searched: {[str(p) for p in search_paths]}")
            return False

        # Click the upload button/input on LinkedIn's resume screen
        try:
            # LinkedIn has a file input for resume upload
            file_input = await self.page.query_selector(
                'input[type="file"], input[name="file"], input[accept*=".pdf"]'
            )
            if file_input:
                await file_input.set_input_files(str(local_file))
                logger.info(f"Uploaded resume from: {local_file}")
                await asyncio.sleep(2.0)  # Wait for upload to process

                # Verify it appeared and select it
                await self._wait_for_form_load()
                resume_cards = await self.page.query_selector_all(self.SELECTORS["resume_item"])
                for card in resume_cards:
                    card_text = await card.inner_text()
                    if expected_resume.lower() in card_text.lower():
                        await card.click()
                        logger.info(f"Selected newly uploaded resume: {expected_resume}")
                        await asyncio.sleep(0.5)
                        return True

                # Upload succeeded but can't find it — try selecting the most recent
                if resume_cards:
                    await resume_cards[0].click()
                    logger.info("Selected first resume card (most recent upload)")
                    return True
            else:
                logger.warning("No file input found for resume upload")
                # Try clicking an "Upload resume" button/link
                upload_btn = await self.page.query_selector(
                    'button:has-text("Upload"), label:has-text("Upload"), a:has-text("Upload")'
                )
                if upload_btn:
                    await upload_btn.click()
                    await asyncio.sleep(1.0)
                    # Now look for file input again
                    file_input = await self.page.query_selector('input[type="file"]')
                    if file_input:
                        await file_input.set_input_files(str(local_file))
                        logger.info(f"Uploaded resume via button: {local_file}")
                        await asyncio.sleep(2.0)
                        return True

        except Exception as upload_exc:
            logger.error(f"Resume upload failed: {upload_exc}")

        # Last resort: select whatever is already selected/first available
        if resume_cards:
            logger.warning("Using first available resume as fallback")
            await resume_cards[0].click()
            return True

        return False

    async def handle_additional_questions(self) -> tuple[bool, list[str]]:
        """Process additional questions screens (may span multiple pages).

        Auto-fills fields where possible. Detects sensitive/complex fields
        that require human review.

        Returns:
            Tuple of (can_proceed, list_of_blocking_field_labels).
        """
        logger.debug("Handling additional questions")

        blocking_fields: list[str] = []
        max_pages = 10  # safety limit to prevent infinite loops

        for page_num in range(max_pages):
            await self._wait_for_form_load()

            # Process all form groups on current page
            groups = await self.page.query_selector_all(self.SELECTORS["form_fields"])

            for group in groups:
                label_el = await group.query_selector(self.SELECTORS["field_label"])
                label_text = (await label_el.inner_text()).strip() if label_el else ""

                if not label_text:
                    continue

                # Check if this is a sensitive field
                if self._is_sensitive_field(label_text):
                    blocking_fields.append(label_text)
                    logger.info(f"Sensitive field detected (pause): {label_text}")
                    continue

                # Try pre-configured answer for fields that match sensitive patterns
                # (fields where _is_sensitive_field returned False because a preconfigured answer exists)
                preconfigured = self._get_preconfigured_answer(label_text)
                if preconfigured is not None:
                    filled = await self._try_fill_value(group, label_text, preconfigured)
                    if filled:
                        logger.info(f"Auto-filled sensitive field '{label_text}' with pre-configured answer")
                        continue
                    else:
                        # Could not fill even with preconfigured answer
                        blocking_fields.append(label_text)
                        logger.warning(f"Had pre-configured answer for '{label_text}' but could not fill")
                        continue

                # Try AI-generated answer for common application questions
                if AnswerGenerator.is_ai_answerable(label_text):
                    ai_answer = await self._answer_gen.generate_answer(
                        label_text, self._current_job_title, self._current_company
                    )
                    if ai_answer:
                        filled = await self._try_fill_value(group, label_text, ai_answer)
                        if filled:
                            logger.info(f"AI-filled field '{label_text}'")
                            continue
                        else:
                            blocking_fields.append(label_text)
                            logger.warning(f"AI generated answer for '{label_text}' but could not fill")
                            continue
                    else:
                        # AI not configured or failed — treat as blocking
                        blocking_fields.append(label_text)
                        logger.info(f"AI answerable field '{label_text}' but no AI response; pausing")
                        continue

                # Try to auto-fill the field
                filled = await self._try_auto_fill(group, label_text)
                if not filled:
                    # Check if the field already has a value
                    has_value = await self._group_has_value(group)
                    if not has_value:
                        blocking_fields.append(label_text)
                        logger.info(f"Cannot auto-fill field: {label_text}")

            # If we found blocking fields, pause immediately
            if blocking_fields:
                logger.info(
                    f"Pausing: {len(blocking_fields)} field(s) need human review"
                )
                return False, blocking_fields

            # Try to advance to next page (could be Next or Review)
            review_btn = await self.page.query_selector(self.SELECTORS["review_btn"])
            if review_btn:
                await review_btn.click()
                await asyncio.sleep(1.0)
                break  # Reached review screen

            next_btn = await self.page.query_selector(self.SELECTORS["next_btn"])
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(1.0)
            else:
                # No next or review button — we're done with questions
                break

        return True, []

    async def handle_review_screen(self) -> bool:
        """Scroll through the review screen and verify content.

        Returns:
            True if review looks good, False if issues detected.
        """
        logger.debug("Handling review screen")

        await self._wait_for_form_load()

        # Scroll through the modal to load all content
        modal = await self.page.query_selector(self.SELECTORS["modal"])
        if modal:
            # Scroll in increments to trigger any lazy-loaded content
            for _ in range(5):
                await modal.evaluate("el => el.scrollTop += 300")
                await asyncio.sleep(0.3)

            # Scroll back to top
            await modal.evaluate("el => el.scrollTop = 0")
            await asyncio.sleep(0.3)

        # Verify submit button is visible
        submit_btn = await self.page.query_selector(self.SELECTORS["submit_btn"])
        if not submit_btn:
            logger.warning("Submit button not found on review screen")
            return False

        return True

    async def submit(self) -> bool:
        """Click the submit button and confirm the application was sent.

        Returns:
            True if submission succeeded, False otherwise.
        """
        logger.debug("Submitting application")

        submit_btn = await self.page.query_selector(self.SELECTORS["submit_btn"])
        if not submit_btn:
            logger.error("Submit button not found")
            return False

        await submit_btn.click()
        logger.info("Clicked submit button")

        # Wait for confirmation (success modal or page change)
        try:
            await self.page.wait_for_selector(
                'div:has-text("Application sent"), '
                'h2:has-text("applied"), '
                f'{self.SELECTORS["done_btn"]}',
                timeout=10000,
            )
            logger.info("Submission confirmed")
            return True
        except Exception:
            logger.warning("Could not confirm submission within timeout")
            # Check if modal closed (indicates success)
            modal = await self.page.query_selector(self.SELECTORS["modal"])
            return modal is None

    # ─── Private Helper Methods ───────────────────────────────────────────

    async def _is_external_apply(self) -> bool:
        """Check if the job has an external apply link instead of Easy Apply."""
        external_btn = await self.page.query_selector(self.SELECTORS["external_apply"])
        return external_btn is not None

    async def _click_easy_apply(self) -> None:
        """Click the Easy Apply button to open the application modal."""
        btn = await self.page.wait_for_selector(
            self.SELECTORS["easy_apply_btn"], timeout=5000
        )
        if not btn:
            raise RuntimeError("Easy Apply button not found")
        await btn.click()
        # Wait for modal to appear
        await self.page.wait_for_selector(self.SELECTORS["modal"], timeout=5000)
        await asyncio.sleep(1.0)
        logger.debug("Easy Apply modal opened")

    async def _click_next(self) -> None:
        """Click the 'Next' button in the Easy Apply modal."""
        next_btn = await self.page.query_selector(self.SELECTORS["next_btn"])
        if next_btn:
            await next_btn.click()
            await asyncio.sleep(1.0)
        else:
            logger.warning("Next button not found, trying review button")
            review_btn = await self.page.query_selector(self.SELECTORS["review_btn"])
            if review_btn:
                await review_btn.click()
                await asyncio.sleep(1.0)

    async def _handle_top_choice(self) -> None:
        """Handle the 'Mark as top choice' checkbox — uncheck if present."""
        checkbox = await self.page.query_selector(
            self.SELECTORS["top_choice_checkbox"]
        )
        if checkbox:
            is_checked = await checkbox.is_checked()
            if is_checked:
                await checkbox.click()
                logger.debug("Unchecked 'Mark as top choice'")
            else:
                logger.debug("'Mark as top choice' already unchecked")

            # Advance past this screen
            await self._click_next()

    async def _wait_for_form_load(self) -> None:
        """Wait briefly for form elements to stabilize."""
        await asyncio.sleep(0.8)

    async def _check_field_has_value(self, field_type: str) -> bool:
        """Check if a common field type has a non-empty value."""
        selectors_map = {
            "email": 'input[type="email"], input[name*="email"], input[id*="email"]',
            "phone": 'input[type="tel"], input[name*="phone"], input[id*="phone"]',
        }
        selector = selectors_map.get(field_type)
        if not selector:
            return False

        el = await self.page.query_selector(selector)
        if not el:
            return False

        value = await el.input_value()
        return bool(value.strip())

    def _is_sensitive_field(self, label: str) -> bool:
        """Determine if a field label matches known sensitive patterns.

        Returns False if a pre-configured answer exists for the field,
        allowing it to be auto-filled instead of blocking.
        """
        label_lower = label.lower()
        is_sensitive = any(
            pattern in label_lower for pattern in self.SENSITIVE_FIELD_PATTERNS
        )
        if is_sensitive:
            # If there's a pre-configured answer, don't treat as blocking
            if self._get_preconfigured_answer(label) is not None:
                return False
        return is_sensitive

    def _get_preconfigured_answer(self, label: str) -> str | None:
        """Fuzzy-match a field label against sensitive_field_answers keys.

        Matching logic:
        - Normalize both the label and the keys (lowercase, strip)
        - Replace underscores in keys with spaces for comparison
        - Check if any key token appears as a substring of the label, or vice versa
        - E.g., key 'salary_expectation' matches labels containing 'salary' or 'expectation'
        - Key 'current_ctc' matches labels containing 'current ctc' or 'current CTC'

        Returns:
            The pre-configured answer string if matched, None otherwise.
        """
        answers = self.candidate.get("sensitive_field_answers", {})
        if not answers:
            return None

        label_normalized = label.lower().strip()

        for key, value in answers.items():
            key_normalized = key.lower().strip().replace("_", " ")
            # Check if key (with spaces) is a substring of the label
            if key_normalized in label_normalized:
                return str(value)
            # Check if label is a substring of the key
            if label_normalized in key_normalized:
                return str(value)
            # Check individual words from the key against the label
            key_parts = key_normalized.split()
            if any(part in label_normalized for part in key_parts if len(part) > 2):
                return str(value)

        return None

    def _get_auto_fill_value(self, label: str) -> str | None:
        """Get auto-fill value from candidate config based on label text."""
        label_lower = label.lower()

        for config_key, patterns in self.AUTO_FILLABLE_PATTERNS.items():
            if any(pattern in label_lower for pattern in patterns):
                # Map config key to candidate value
                if config_key == "phone":
                    return self.candidate.get("phone", "")
                elif config_key == "email":
                    return self.candidate.get("email", "")
                elif config_key == "city":
                    cities = self.candidate.get("preferred_cities", [])
                    return cities[0] if cities else ""
                elif config_key == "notice_period":
                    return self.candidate.get("notice_period", "")
                elif config_key == "work_authorization":
                    return self.candidate.get("work_authorization", "")
                elif config_key == "willing_to_relocate":
                    return "Yes" if self.candidate.get("willing_to_relocate") else "No"

        return None

    async def _try_auto_fill(self, group, label_text: str) -> bool:
        """Attempt to auto-fill a form group based on its label.

        Returns:
            True if filled successfully, False if not auto-fillable.
        """
        value = self._get_auto_fill_value(label_text)
        if not value:
            return False

        # Try text input
        text_input = await group.query_selector(self.SELECTORS["text_input"])
        if text_input:
            current = await text_input.input_value()
            if not current.strip():
                await text_input.fill(value)
                logger.debug(f"Auto-filled '{label_text}' with '{value}'")
                return True
            return True  # already has a value

        # Try select dropdown
        select_input = await group.query_selector(self.SELECTORS["select_input"])
        if select_input:
            # Try to select option matching our value
            try:
                await select_input.select_option(label=value)
                logger.debug(f"Selected '{value}' for '{label_text}'")
                return True
            except Exception:
                # Try partial match
                options = await select_input.query_selector_all("option")
                for option in options:
                    option_text = await option.inner_text()
                    if value.lower() in option_text.lower():
                        option_value = await option.get_attribute("value")
                        if option_value:
                            await select_input.select_option(value=option_value)
                            return True
                return False

        # Try textarea
        textarea = await group.query_selector(self.SELECTORS["textarea_input"])
        if textarea:
            current = await textarea.input_value()
            if not current.strip():
                await textarea.fill(value)
                logger.debug(f"Auto-filled textarea '{label_text}'")
                return True
            return True

        # Try radio buttons (Yes/No)
        radio_group = await group.query_selector(self.SELECTORS["radio_group"])
        if radio_group:
            target_label = value.lower()
            labels = await radio_group.query_selector_all("label")
            for lbl in labels:
                lbl_text = (await lbl.inner_text()).strip().lower()
                if lbl_text == target_label or target_label in lbl_text:
                    await lbl.click()
                    logger.debug(f"Selected radio '{lbl_text}' for '{label_text}'")
                    return True

        return False

    async def _try_fill_value(self, group, label_text: str, value: str) -> bool:
        """Fill a form group with a specific value.

        Similar to _try_auto_fill but takes an explicit value parameter.

        Returns:
            True if filled successfully, False otherwise.
        """
        # Try text input
        text_input = await group.query_selector(self.SELECTORS["text_input"])
        if text_input:
            current = await text_input.input_value()
            if not current.strip():
                await text_input.fill(value)
                logger.debug(f"Filled '{label_text}' with pre-configured: '{value}'")
                return True
            return True  # already has a value

        # Try select dropdown
        select_input = await group.query_selector(self.SELECTORS["select_input"])
        if select_input:
            try:
                await select_input.select_option(label=value)
                logger.debug(f"Selected '{value}' for '{label_text}'")
                return True
            except Exception:
                # Try partial match
                options = await select_input.query_selector_all("option")
                for option in options:
                    option_text = await option.inner_text()
                    if value.lower() in option_text.lower():
                        option_value = await option.get_attribute("value")
                        if option_value:
                            await select_input.select_option(value=option_value)
                            return True
                return False

        # Try textarea
        textarea = await group.query_selector(self.SELECTORS["textarea_input"])
        if textarea:
            current = await textarea.input_value()
            if not current.strip():
                await textarea.fill(value)
                logger.debug(f"Filled textarea '{label_text}' with pre-configured answer")
                return True
            return True

        # Try radio buttons
        radio_group = await group.query_selector(self.SELECTORS["radio_group"])
        if radio_group:
            target_label = value.lower()
            labels = await radio_group.query_selector_all("label")
            for lbl in labels:
                lbl_text = (await lbl.inner_text()).strip().lower()
                if lbl_text == target_label or target_label in lbl_text:
                    await lbl.click()
                    logger.debug(f"Selected radio '{lbl_text}' for '{label_text}'")
                    return True

        return False

    async def _group_has_value(self, group) -> bool:
        """Check if any input within a form group already has a value."""
        # Check text inputs
        text_input = await group.query_selector(self.SELECTORS["text_input"])
        if text_input:
            val = await text_input.input_value()
            if val.strip():
                return True

        # Check select
        select_input = await group.query_selector(self.SELECTORS["select_input"])
        if select_input:
            val = await select_input.input_value()
            if val and val != "":
                return True

        # Check textarea
        textarea = await group.query_selector(self.SELECTORS["textarea_input"])
        if textarea:
            val = await textarea.input_value()
            if val.strip():
                return True

        # Check radio buttons
        checked_radio = await group.query_selector('input[type="radio"]:checked')
        if checked_radio:
            return True

        return False

    async def _pause_and_return(
        self,
        job_id: str,
        title: str,
        company: str,
        location: str,
        match_score: float | None,
        blocking_fields: list[str],
    ) -> ApplicationResult:
        """Ask human for input on sensitive fields. If they respond, fill and continue."""
        await self._take_screenshot("needs_human_input", job_id)

        # Ask human via Telegram and wait for response
        human_response = await self.notifier.ask_human_input(
            job_title=title,
            company=company,
            fields=blocking_fields,
            timeout=self.candidate.get("human_input_timeout", 300),
        )

        if not human_response:
            # Human didn't respond — save draft and skip
            await self._save_draft()
            return ApplicationResult(
                status="paused",
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                match_score=match_score,
                blocking_fields=blocking_fields,
            )

        # Human responded! Parse their answers and fill the fields
        answers = [a.strip() for a in human_response.strip().split('\n') if a.strip()]

        # Fill each blocking field with the corresponding answer
        await self._fill_human_answers(blocking_fields, answers)

        # Continue the application flow
        try:
            await self._click_next()
            await asyncio.sleep(1.0)

            # Check if we're now at review screen or more questions
            review_btn = await self.page.query_selector(self.SELECTORS["review_btn"])
            if review_btn:
                await review_btn.click()
                await asyncio.sleep(1.0)

            # Handle review screen
            if not await self.handle_review_screen():
                await self._save_draft()
                return ApplicationResult(
                    status="paused",
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    match_score=match_score,
                    blocking_fields=["review_after_human_input"],
                )

            # Submit!
            if not await self.submit():
                return ApplicationResult(
                    status="error",
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    match_score=match_score,
                    error_message="Submit failed after human input",
                )

            await self._dismiss_post_submit()
            self._applied_jobs.add(job_id)

            logger.info(f"Successfully applied with human input: {title} at {company}")

            if self.config.get("telegram", {}).get("notify_on_submit", True):
                score_pct = f"{match_score:.2f}" if match_score else "N/A"
                await self.notifier.send_notification(
                    f"✅ Applied (with your input!): {title} at {company}\n"
                    f"📍 {location} | Score: {score_pct}"
                )

            return ApplicationResult(
                status="submitted",
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                match_score=match_score,
            )

        except Exception as exc:
            logger.error(f"Error continuing after human input: {exc}")
            await self._save_draft()
            return ApplicationResult(
                status="error",
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                match_score=match_score,
                error_message=f"Post-human-input error: {str(exc)[:100]}",
            )

    async def _fill_human_answers(self, fields: list[str], answers: list[str]) -> None:
        """Fill form fields with human-provided answers."""
        groups = await self.page.query_selector_all(self.SELECTORS["form_fields"])

        answer_idx = 0
        for group in groups:
            if answer_idx >= len(answers):
                break

            label_el = await group.query_selector(self.SELECTORS["field_label"])
            label_text = (await label_el.inner_text()).strip() if label_el else ""

            # Check if this is one of the blocking fields
            if label_text and label_text in fields:
                answer = answers[answer_idx] if answer_idx < len(answers) else ""
                answer_idx += 1

                # Fill the field
                text_input = await group.query_selector(self.SELECTORS["text_input"])
                if text_input:
                    await text_input.fill(answer)
                    continue

                textarea = await group.query_selector(self.SELECTORS["textarea_input"])
                if textarea:
                    await textarea.fill(answer)
                    continue

                select_input = await group.query_selector(self.SELECTORS["select_input"])
                if select_input:
                    try:
                        await select_input.select_option(label=answer)
                    except Exception:
                        # Try by value or partial match
                        options = await select_input.query_selector_all("option")
                        for option in options:
                            option_text = await option.inner_text()
                            if answer.lower() in option_text.lower():
                                option_value = await option.get_attribute("value")
                                if option_value:
                                    await select_input.select_option(value=option_value)
                                    break
                    continue

                # Radio buttons
                radio_group = await group.query_selector(self.SELECTORS["radio_group"])
                if radio_group:
                    labels = await radio_group.query_selector_all("label")
                    for lbl in labels:
                        lbl_text = (await lbl.inner_text()).strip().lower()
                        if answer.lower() in lbl_text or lbl_text in answer.lower():
                            await lbl.click()
                            break

        logger.info(f"Filled {answer_idx} field(s) with human answers")

    async def _save_draft(self) -> None:
        """Attempt to save the current application as a draft."""
        try:
            save_btn = await self.page.query_selector(self.SELECTORS["save_draft_btn"])
            if save_btn:
                await save_btn.click()
                await asyncio.sleep(1.0)
                logger.info("Draft saved")
            else:
                logger.debug("No save draft button found")
        except Exception as e:
            logger.warning(f"Could not save draft: {e}")

    async def _dismiss_post_submit(self) -> None:
        """Dismiss the post-submission upsell/confirmation dialogs."""
        await asyncio.sleep(1.5)

        # Click 'Done' if present
        done_btn = await self.page.query_selector(self.SELECTORS["done_btn"])
        if done_btn:
            await done_btn.click()
            await asyncio.sleep(0.5)

        # Dismiss any upsell (premium, follow company, etc.)
        upsell_btn = await self.page.query_selector(self.SELECTORS["upsell_dismiss"])
        if upsell_btn:
            await upsell_btn.click()
            await asyncio.sleep(0.5)
            logger.debug("Dismissed post-submit upsell")

    async def _close_modal_gracefully(self) -> None:
        """Close the Easy Apply modal safely on error, discarding if needed."""
        try:
            # Try the X button
            close_btn = await self.page.query_selector(self.SELECTORS["close_btn"])
            if close_btn:
                await close_btn.click()
                await asyncio.sleep(0.5)

            # Handle the "Discard application?" confirmation dialog
            discard_btn = await self.page.query_selector(
                self.SELECTORS["discard_btn"]
            )
            if discard_btn:
                await discard_btn.click()
                await asyncio.sleep(0.5)
                logger.debug("Modal closed and draft discarded")
            else:
                logger.debug("Modal closed")

        except Exception as e:
            logger.warning(f"Failed to close modal gracefully: {e}")

    async def _take_screenshot(self, step_name: str, job_id: str) -> None:
        """Take a screenshot for debugging purposes."""
        try:
            filename = f"{job_id}_{step_name}_{datetime.now():%Y%m%d_%H%M%S}.png"
            filepath = SCREENSHOTS_DIR / filename
            await self.page.screenshot(path=str(filepath))
            logger.debug(f"Screenshot saved: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
