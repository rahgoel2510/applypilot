"""External job application handler.

Attempts to auto-fill application forms on known ATS platforms:
- Greenhouse (boards.greenhouse.io)
- Lever (jobs.lever.co)
- Workday (*.myworkdayjobs.com)
- Ashby (jobs.ashbyhq.com)
- SmartRecruiters

For unknown platforms: takes screenshot and notifies user.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Known ATS platform detection
ATS_PATTERNS = {
    'greenhouse': [r'boards\.greenhouse\.io', r'greenhouse\.io/'],
    'lever': [r'jobs\.lever\.co', r'lever\.co/'],
    'workday': [r'myworkdayjobs\.com', r'myworkday\.com'],
    'ashby': [r'jobs\.ashbyhq\.com', r'ashbyhq\.com/'],
    'smartrecruiters': [r'jobs\.smartrecruiters\.com', r'smartrecruiters\.com/'],
}


def detect_ats(url: str) -> str | None:
    """Detect which ATS platform a URL belongs to. Returns platform name or None."""
    url_lower = url.lower()
    for platform, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return platform
    return None


class ExternalApplicant:
    """Handles auto-filling external job application forms."""

    def __init__(self, page: Page, candidate: dict):
        self.page = page
        self.candidate = candidate
        self.resume_path = self._find_resume()

    def _find_resume(self) -> Path | None:
        """Find resume file on disk."""
        filename = self.candidate.get('resume_filename', '')
        if not filename:
            return None
        search_paths = [
            Path.cwd() / 'resumes' / filename,
            Path.cwd() / filename,
            Path.home() / 'Documents' / filename,
            Path.home() / 'Downloads' / filename,
        ]
        for p in search_paths:
            if p.exists():
                return p
        return None

    async def apply(self, url: str) -> dict:
        """Navigate to external URL and attempt to fill the application form.
        
        Returns:
            dict with keys: status ('applied'|'partial'|'screenshot'|'failed'),
            platform, message
        """
        platform = detect_ats(url)
        logger.info(f'External apply: {url} (platform: {platform or "unknown"})')

        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)

            if platform == 'greenhouse':
                return await self._fill_greenhouse()
            elif platform == 'lever':
                return await self._fill_lever()
            elif platform == 'workday':
                return await self._fill_workday()
            elif platform == 'ashby':
                return await self._fill_ashby()
            else:
                # Unknown ATS — try generic fill, then screenshot
                result = await self._fill_generic()
                if result['status'] == 'failed':
                    await self._take_screenshot(url)
                    result['status'] = 'screenshot'
                return result

        except Exception as exc:
            logger.error(f'External apply failed: {exc}')
            return {'status': 'failed', 'platform': platform, 'message': str(exc)[:100]}

    async def _fill_generic(self) -> dict:
        """Try to fill common form fields regardless of ATS."""
        filled_count = 0
        name = self.candidate.get('name', '')
        email = self.candidate.get('email', '')
        phone = self.candidate.get('phone', '')

        # Try common field selectors
        field_map = [
            (['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="name" i]', 'input[autocomplete="name"]'], name),
            (['input[name*="first"]', 'input[id*="first"]', 'input[placeholder*="first" i]'], name.split()[0] if name else ''),
            (['input[name*="last"]', 'input[id*="last"]', 'input[placeholder*="last" i]'], name.split()[-1] if name and ' ' in name else ''),
            (['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'], email),
            (['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'], phone),
        ]

        for selectors, value in field_map:
            if not value:
                continue
            for selector in selectors:
                try:
                    el = await self.page.query_selector(selector)
                    if el and await el.is_visible():
                        current = await el.input_value()
                        if not current.strip():
                            await el.fill(value)
                            filled_count += 1
                            break
                except Exception:
                    continue

        # Try resume upload
        if self.resume_path:
            try:
                file_input = await self.page.query_selector('input[type="file"]')
                if file_input:
                    await file_input.set_input_files(str(self.resume_path))
                    filled_count += 1
                    logger.info(f'Uploaded resume to external form')
            except Exception:
                pass

        if filled_count > 0:
            logger.info(f'Generic fill: {filled_count} fields filled')
            return {'status': 'partial', 'platform': 'unknown', 'message': f'{filled_count} fields auto-filled'}
        return {'status': 'failed', 'platform': 'unknown', 'message': 'No fillable fields found'}

    async def _fill_greenhouse(self) -> dict:
        """Fill Greenhouse application form."""
        filled = 0
        name = self.candidate.get('name', '')
        email = self.candidate.get('email', '')
        phone = self.candidate.get('phone', '')

        # Greenhouse uses specific IDs
        fields = [
            ('#first_name', name.split()[0] if name else ''),
            ('#last_name', name.split()[-1] if name and ' ' in name else ''),
            ('#email', email),
            ('#phone', phone),
        ]
        for selector, value in fields:
            if not value:
                continue
            try:
                el = await self.page.query_selector(selector)
                if el:
                    await el.fill(value)
                    filled += 1
            except Exception:
                pass

        # Resume upload
        if self.resume_path:
            try:
                file_input = await self.page.query_selector('input[type="file"][name*="resume"], input[type="file"]')
                if file_input:
                    await file_input.set_input_files(str(self.resume_path))
                    filled += 1
            except Exception:
                pass

        return {'status': 'partial' if filled > 0 else 'failed', 'platform': 'greenhouse', 'message': f'{filled} fields filled'}

    async def _fill_lever(self) -> dict:
        """Fill Lever application form."""
        filled = 0
        name = self.candidate.get('name', '')
        email = self.candidate.get('email', '')
        phone = self.candidate.get('phone', '')

        # Lever uses application-* names
        fields = [
            ('input[name="name"]', name),
            ('input[name="email"]', email),
            ('input[name="phone"]', phone),
        ]
        for selector, value in fields:
            if not value:
                continue
            try:
                el = await self.page.query_selector(selector)
                if el:
                    await el.fill(value)
                    filled += 1
            except Exception:
                pass

        if self.resume_path:
            try:
                file_input = await self.page.query_selector('input[type="file"]')
                if file_input:
                    await file_input.set_input_files(str(self.resume_path))
                    filled += 1
            except Exception:
                pass

        return {'status': 'partial' if filled > 0 else 'failed', 'platform': 'lever', 'message': f'{filled} fields filled'}

    async def _fill_workday(self) -> dict:
        """Workday forms are complex SPAs — just screenshot for now."""
        await self._take_screenshot('workday')
        return {'status': 'screenshot', 'platform': 'workday', 'message': 'Workday forms require manual apply (screenshot sent)'}

    async def _fill_ashby(self) -> dict:
        """Fill Ashby application form."""
        return await self._fill_generic()

    async def _take_screenshot(self, context: str = '') -> None:
        """Take a screenshot for manual review."""
        try:
            screenshots_dir = Path('screenshots')
            screenshots_dir.mkdir(exist_ok=True)
            filename = f'external_{context}_{self.page.url[:30].replace("/", "_")}.png'
            await self.page.screenshot(path=str(screenshots_dir / filename))
            logger.info(f'Screenshot saved: {filename}')
        except Exception:
            pass
