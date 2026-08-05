"""Prompt injection sanitization for AI-generated content.

Detects and strips prompt injection attempts from job descriptions,
recruiter names, and other untrusted input before passing to LLM.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    # Direct instruction override
    r'(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)',
    r'(?i)disregard\s+(all\s+)?(previous|above|prior)',
    r'(?i)forget\s+(everything|all|your)\s+(above|previous|instructions?)',
    r'(?i)you\s+are\s+now\s+(a|an|the)',
    r'(?i)new\s+instructions?:',
    r'(?i)system\s*:',
    r'(?i)\[SYSTEM\]',
    r'(?i)\[INST\]',
    r'(?i)<\|?system\|?>',
    r'(?i)<<SYS>>',

    # Role manipulation
    r'(?i)act\s+as\s+(if\s+you\s+are|a|an)',
    r'(?i)pretend\s+(you\s+are|to\s+be)',
    r'(?i)you\s+must\s+(always|never|now)',
    r'(?i)your\s+new\s+(role|purpose|goal)',

    # Output manipulation
    r'(?i)output\s+(only|just|exactly)',
    r'(?i)respond\s+with\s+(only|just)',
    r'(?i)say\s+(exactly|only)',
    r'(?i)repeat\s+after\s+me',

    # Data exfiltration attempts
    r'(?i)reveal\s+(your|the)\s+(prompt|instructions?|system)',
    r'(?i)show\s+(me\s+)?your\s+(prompt|instructions?)',
    r'(?i)what\s+(are|is)\s+your\s+(instructions?|prompt|system)',
    r'(?i)print\s+(your|the)\s+(prompt|instructions?)',

    # Delimiter injection
    r'---+\s*(system|user|assistant)',
    r'\n{3,}\s*(system|user|assistant)\s*:',
]

# Compiled for performance
_COMPILED_PATTERNS = [re.compile(p) for p in _INJECTION_PATTERNS]

# Characters/sequences to strip (delimiter attacks)
_STRIP_SEQUENCES = [
    '```system',
    '```user',
    '```assistant',
    '<|im_start|>',
    '<|im_end|>',
    '<|endoftext|>',
    '### Instruction:',
    '### Response:',
    '### Human:',
    '### Assistant:',
]


def detect_injection(text: str) -> Optional[str]:
    """Check if text contains prompt injection attempts.

    Returns the matched pattern name if injection detected, None otherwise.
    """
    if not text:
        return None

    for i, pattern in enumerate(_COMPILED_PATTERNS):
        if pattern.search(text):
            logger.warning(f'Prompt injection detected (pattern {i}): {text[:100]}...')
            return _INJECTION_PATTERNS[i]

    return None


def sanitize_for_prompt(text: str, max_length: int = 2000) -> str:
    """Sanitize untrusted text before including in an LLM prompt.

    - Strips known injection patterns
    - Removes delimiter sequences
    - Truncates to max_length
    - Escapes potential delimiter characters

    Args:
        text: Untrusted input (job description, recruiter name, etc.)
        max_length: Maximum allowed length after sanitization

    Returns:
        Sanitized text safe for prompt inclusion.
    """
    if not text:
        return ''

    result = text

    # Strip known delimiter sequences
    for seq in _STRIP_SEQUENCES:
        result = result.replace(seq, '')

    # Remove injection pattern matches (replace with [filtered])
    for pattern in _COMPILED_PATTERNS:
        result = pattern.sub('[filtered]', result)

    # Normalize excessive whitespace (prevents delimiter injection via newlines)
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Truncate
    if len(result) > max_length:
        result = result[:max_length] + '...'

    return result.strip()


def sanitize_job_context(title: str, company: str, description: str = '') -> dict:
    """Sanitize all job-related fields before prompt construction.

    Returns a dict with sanitized values.
    """
    return {
        'title': sanitize_for_prompt(title, max_length=200),
        'company': sanitize_for_prompt(company, max_length=200),
        'description': sanitize_for_prompt(description, max_length=2000),
    }
