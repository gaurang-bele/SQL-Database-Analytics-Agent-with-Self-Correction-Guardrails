import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Pattern definitions for malicious input detection
TAUTOLOGY_PATTERN = re.compile(
    r"(\bOR\b\s+['\"]?1['\"]?\s*=\s*['\"]?1['\"]?|\bOR\b\s+['\"]?[a-zA-Z]['\"]?\s*=\s*['\"]?[a-zA-Z]['\"]?|\bOR\b\s+true\b|\bHAVING\s+1\s*=\s*1\b|\bWHERE\s+1\s*=\s*1\b)",
    re.IGNORECASE
)

COMMENT_EXPANSION_PATTERN = re.compile(
    r"(--|/\*|\*/|#\s*$|;\s*--)",
    re.IGNORECASE
)

SCRIPT_TAG_PATTERN = re.compile(
    r"(<\s*script\b[^>]*>.*?<\s*/\s*script\s*>|<\s*script\b[^>]*>|javascript\s*:|onerror\s*=|onload\s*=)",
    re.IGNORECASE | re.DOTALL
)

DESTRUCTIVE_SQL_PATTERN = re.compile(
    r"\b(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE\s+TABLE|ALTER\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+\s+SET)\b",
    re.IGNORECASE
)


@dataclass
class GuardrailScanResult:
    is_safe: bool
    blocked_reason: Optional[str] = None
    violation_type: Optional[str] = None


class InputGuardrails:
    """
    Guardrail engine providing input validation layers:
    1. Fast deterministic regex and semantic scanner (tautologies, comment expansions, script tags, destructive commands).
    2. NeMo Guardrails configuration integration (lazy-loaded).
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (Path(__file__).parent / "configs")
        self._nemo_rails = None
        self._nemo_attempted = False

    def get_nemo_rails(self):
        """Lazy load NeMo RailsApp when needed."""
        if self._nemo_attempted:
            return self._nemo_rails

        self._nemo_attempted = True
        if not settings.ENABLE_NEMO_GUARDRAILS:
            return None

        try:
            from nemoguardrails import RailsConfig, LLMRails
            if self.config_path.exists():
                rails_config = RailsConfig.from_path(str(self.config_path))
                self._nemo_rails = LLMRails(rails_config)
                logger.info("NeMo Guardrails successfully initialized.")
        except Exception as e:
            logger.warning(f"NeMo Guardrails initialization deferred/skipped: {e}")

        return self._nemo_rails

    def scan_input(self, user_text: str) -> GuardrailScanResult:
        """
        Scans raw user input before reaching the LLM.
        Checks for:
        - Script tags (<script>, onerror, etc.)
        - SQL comment expansions (-- , /* ... */)
        - Tautologies (' OR '1'='1)
        - Destructive raw SQL keywords (DROP TABLE, DELETE FROM, etc.)
        """
        if not user_text or not user_text.strip():
            return GuardrailScanResult(
                is_safe=False,
                blocked_reason="Input prompt is empty.",
                violation_type="empty_input"
            )

        # 1. Check Script Tags
        if SCRIPT_TAG_PATTERN.search(user_text):
            return GuardrailScanResult(
                is_safe=False,
                blocked_reason="Security Alert: Cross-site scripting / script tag injection pattern detected.",
                violation_type="script_tag_injection"
            )

        # 2. Check Tautology injections
        if TAUTOLOGY_PATTERN.search(user_text):
            return GuardrailScanResult(
                is_safe=False,
                blocked_reason="Security Alert: SQL tautology injection pattern detected (e.g., OR 1=1).",
                violation_type="tautology_injection"
            )

        # 3. Check Comment expansions
        if COMMENT_EXPANSION_PATTERN.search(user_text):
            return GuardrailScanResult(
                is_safe=False,
                blocked_reason="Security Alert: SQL comment expansion pattern detected (e.g., '--' or '/*').",
                violation_type="comment_expansion_injection"
            )

        # 4. Check explicit destructive command statements directly submitted as input
        if DESTRUCTIVE_SQL_PATTERN.search(user_text):
            return GuardrailScanResult(
                is_safe=False,
                blocked_reason="Security Alert: Destructive write command detected in user prompt (e.g., DROP/DELETE/ALTER).",
                violation_type="destructive_command"
            )

        return GuardrailScanResult(is_safe=True)


# Global guardrails singleton
input_guardrails = InputGuardrails()
