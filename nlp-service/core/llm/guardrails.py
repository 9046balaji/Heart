"""
Safety Guardrails - enforces safety policies on all AI outputs.

All LLM responses MUST pass through this module before reaching users.
This ensures:
1. PII (Personally Identifiable Information) is redacted
2. Medical and nutrition disclaimers are appended
3. Content is logged for compliance auditing

Usage:
    from core.guardrails import SafetyGuardrail

    guardrail = SafetyGuardrail()
    safe_response = guardrail.process_output(raw_response, {"type": "medical"})
"""

import re
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class SafetyGuardrail:
    """
    Enforces safety policies on AI outputs.

    Responsibilities:
    1. PII Redaction - SSN, phone, email, credit card
    2. Medical Disclaimers - Required for health-related content
    3. Nutrition Disclaimers - Required for diet/nutrition content
    4. Audit Logging - Log all outputs for compliance review
    """

    # PII detection patterns
    PII_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }

    MEDICAL_DISCLAIMER = """

---
⚕️ **IMPORTANT HEALTH DISCLAIMER**

I am an AI assistant, not a licensed healthcare provider. The information provided is for educational purposes only and should not be considered medical advice. Always consult with a qualified healthcare professional before making any changes to your diet, exercise routine, or medications.

If you are experiencing a medical emergency, please call emergency services (911) immediately.
"""

    NUTRITION_DISCLAIMER = """

---
🥗 **NUTRITION NOTICE**

Nutritional information is estimated and may vary. This guidance is for informational purposes only. Consult a registered dietitian for personalized nutrition advice.
"""

    def __init__(self, strict_mode: bool = True):
        """
        Initialize SafetyGuardrail.

        Args:
            strict_mode: If True, log all outputs for compliance review
        """
        self.strict_mode = strict_mode
        self._compile_patterns()
        logger.info(f"SafetyGuardrail initialized (strict_mode={strict_mode})")

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for better performance."""
        self.compiled_patterns: Dict[str, re.Pattern] = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PII_PATTERNS.items()
        }

    def process_output(self, text: str, context: Dict) -> str:
        """
        Main entry point - process AI output through all safety checks.

        Args:
            text: Raw AI output
            context: Dict with 'type' (medical/nutrition/general)

        Returns:
            Sanitized output with appropriate disclaimers
        """
        # Step 1: Redact PII
        text = self.redact_pii(text)

        # Step 2: Add appropriate disclaimer
        content_type = context.get("type", "general")
        text = self.add_disclaimer(text, content_type)

        # Step 3: Safety classification (log for review in strict mode)
        if self.strict_mode:
            self.log_for_review(text, context)

        return text

    def redact_pii(self, text: str) -> str:
        """
        Redact personally identifiable information.

        Args:
            text: Input text to scan for PII

        Returns:
            Text with PII redacted as [REDACTED-TYPE]
        """
        redacted = text
        redactions_made: List[str] = []

        for pii_type, pattern in self.compiled_patterns.items():
            matches = pattern.findall(redacted)
            if matches:
                redactions_made.append(f"{pii_type}:{len(matches)}")
                redacted = pattern.sub(f"[REDACTED-{pii_type.upper()}]", redacted)

        if redactions_made:
            logger.warning(f"PII redacted: {', '.join(redactions_made)}")

        return redacted

    def add_disclaimer(self, text: str, content_type: str) -> str:
        """
        Add appropriate disclaimer based on content type.

        Args:
            text: Processed text
            content_type: One of 'medical', 'nutrition', 'general'

        Returns:
            Text with disclaimer appended
        """
        if content_type == "medical":
            return text + self.MEDICAL_DISCLAIMER
        elif content_type == "nutrition":
            return text + self.NUTRITION_DISCLAIMER
        return text

    def get_disclaimer(self, content_type: str = "medical") -> str:
        """
        Get disclaimer text for external use.

        Args:
            content_type: Type of disclaimer needed

        Returns:
            Disclaimer text
        """
        if content_type == "medical":
            return self.MEDICAL_DISCLAIMER.strip()
        elif content_type == "nutrition":
            return self.NUTRITION_DISCLAIMER.strip()
        return ""

    def log_for_review(self, text: str, context: Dict) -> None:
        """
        Log output for compliance review.

        This creates an audit trail for HIPAA compliance.
        """
        content_type = context.get("type", "unknown")
        user_id = context.get("user_id", "anonymous")

        logger.info(
            f"GUARDRAIL_AUDIT: type={content_type} "
            f"user={user_id} "
            f"len={len(text)} "
            f"has_disclaimer={content_type in ('medical', 'nutrition')}"
        )

    def check_safety(self, text: str) -> Dict[str, any]:
        """
        Check text for safety issues without modifying it.

        Useful for pre-flight validation before allowing content.

        Returns:
            Dict with 'safe' (bool) and 'issues' (list) keys
        """
        issues: List[str] = []

        # Check for PII
        for pii_type, pattern in self.compiled_patterns.items():
            if pattern.search(text):
                issues.append(f"Contains {pii_type}")

        return {"safe": len(issues) == 0, "issues": issues, "text_length": len(text)}
