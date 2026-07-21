import re
from typing import Any


PII_PATTERNS = [
    ("EMAIL", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("PASSPORT", re.compile(r"\b[A-Z]\d{7,8}\b")),
    ("DATE", re.compile(r"\b(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b")),
]


def detect_pii(text: str) -> bool:
    t = text.lower()
    keywords = [
        "email", "phone", "ssn", "address", "credit card", "dob", "date of birth",
        "passport", "driver's license", "dl number", "insurance id", "medical record",
        "mrn", "bank account", "routing number", "tax id", "itin", "social security",
        "contact info", "personal info",
    ]
    return any(keyword in t for keyword in keywords) or any(pattern.search(text) for _, pattern in PII_PATTERNS)


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace recognisable sensitive values with typed placeholders."""
    redacted_types: list[str] = []
    redacted = text
    for pii_type, pattern in PII_PATTERNS:
        redacted, replacements = pattern.subn(f"[REDACTED_{pii_type}]", redacted)
        if replacements:
            redacted_types.append(pii_type)
    return redacted, redacted_types


def redact_pii_payload(value: Any) -> tuple[Any, list[str]]:
    """Recursively redact strings while preserving the original JSON structure."""
    detected: list[str] = []

    def redact_value(item: Any) -> Any:
        if isinstance(item, str):
            redacted, pii_types = redact_pii(item)
            detected.extend(pii_types)
            return redacted
        if isinstance(item, dict):
            return {key: redact_value(nested) for key, nested in item.items()}
        if isinstance(item, list):
            return [redact_value(nested) for nested in item]
        return item

    return redact_value(value), list(dict.fromkeys(detected))

def assess_phishing_risk(value: Any) -> str:
    """Return ALLOW, REVIEW, or BLOCK using conservative local phishing signals."""
    def collect_text(item: Any) -> str:
        if isinstance(item, str): return item
        if isinstance(item, dict): return " ".join(collect_text(nested) for nested in item.values())
        if isinstance(item, list): return " ".join(collect_text(nested) for nested in item)
        return ""
    text = collect_text(value).lower()
    has_link = bool(re.search(r"https?://|www\.", text))
    credential_terms = any(term in text for term in ("password", "login", "sign in", "verify your account", "credential"))
    urgency_terms = any(term in text for term in ("urgent", "immediately", "suspended", "expire", "action required"))
    shortener = any(domain in text for domain in ("bit.ly", "tinyurl", "t.co"))
    if has_link and credential_terms and urgency_terms:
        return "BLOCK"
    if has_link and (credential_terms or urgency_terms or shortener):
        return "REVIEW"
    return "ALLOW"
