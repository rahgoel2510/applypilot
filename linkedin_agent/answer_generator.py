"""AI-powered answer generator for common application questions.

Uses OpenRouter/OpenAI to generate contextual answers for text fields
like cover letters, 'why this company', experience descriptions, etc.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Questions that can be answered by AI (removed from sensitive patterns)
AI_ANSWERABLE_PATTERNS = [
    "cover letter",
    "why do you want",
    "why are you interested",
    "describe your experience",
    "tell us about yourself",
    "what makes you a good fit",
    "additional information",
    "anything else",
]

SYSTEM_PROMPT = """You are a professional job applicant writing brief, compelling answers for job application forms.

Candidate profile:
- Name: {name}
- Role focus: {keywords}
- Key skills: {skills}
- Experience: {notice_period} notice period (currently employed)

Rules:
- Keep answers concise (2-4 sentences max for short fields, 5-8 for cover letters)
- Be specific but not fabricated — reference the actual job title and company
- Sound natural, not generic
- Never mention being an AI or automation
- Match professional tone
"""


class AnswerGenerator:
    """Generates contextual answers for application text fields."""

    def __init__(self, candidate_config: dict):
        self._config = candidate_config
        self._api_key = os.environ.get('OPENAI_API_KEY', '')
        self._model = os.environ.get('AI_MODEL', 'openrouter/free')
    
    @staticmethod
    def is_ai_answerable(field_label: str) -> bool:
        """Check if a field can be answered by AI."""
        label_lower = field_label.lower()
        return any(pattern in label_lower for pattern in AI_ANSWERABLE_PATTERNS)
    
    async def generate_answer(
        self,
        field_label: str,
        job_title: str,
        company: str,
        max_length: int = 500,
    ) -> Optional[str]:
        """Generate an AI answer for a form field.
        
        Returns None if AI is not configured or fails.
        """
        if not self._api_key or self._api_key.startswith('placeholder'):
            return None
        
        system = SYSTEM_PROMPT.format(
            name=self._config.get('name', 'the candidate'),
            keywords=', '.join(self._config.get('keywords', [])),
            skills=', '.join(self._config.get('skills', []))[:200],
            notice_period=self._config.get('notice_period', 'N/A'),
        )
        
        user_prompt = (
            f"Write a response for this application field:\n"
            f"Field: \"{field_label}\"\n"
            f"Job: {job_title} at {company}\n\n"
            f"Keep it under {max_length} characters. Be specific to the role."
        )
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={
                        'Authorization': f'Bearer {self._api_key}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': self._model,
                        'messages': [
                            {'role': 'system', 'content': system},
                            {'role': 'user', 'content': user_prompt},
                        ],
                        'temperature': 0.7,
                        'max_tokens': 300,
                    },
                )
            
            if resp.status_code != 200:
                logger.warning(f'AI answer generation failed: HTTP {resp.status_code}')
                return None
            
            data = resp.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if content:
                # Trim to max_length
                answer = content.strip()[:max_length]
                logger.info(f'AI generated answer for "{field_label}" ({len(answer)} chars)')
                return answer
            return None
            
        except Exception as exc:
            logger.warning(f'AI answer generation error: {exc}')
            return None


def get_answer_generator(candidate_config: dict) -> AnswerGenerator:
    return AnswerGenerator(candidate_config)
