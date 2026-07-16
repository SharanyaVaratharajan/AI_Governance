import re

def detect_pii(text: str) -> bool:
    t = text.lower()

    # --- Keyword-based PII ---
    keywords = [
        "email", "phone", "ssn", "address", "credit card",
        "dob", "date of birth", "passport", "driver's license",
        "dl number", "insurance id", "medical record", "mrn",
        "bank account", "routing number", "tax id", "itin",
        "social security", "contact info", "personal info"
    ]

    if any(k in t for k in keywords):
        return True

    # --- Regex-based PII ---
    patterns = [
        # Email
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",

        # US Phone numbers
        r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",

        # SSN
        r"\b\d{3}-\d{2}-\d{4}\b",

        # Credit card (Visa, MC, Amex, Discover)
        r"\b(?:\d[ -]*?){13,16}\b",

        # IP address
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",

        # Passport (generic)
        r"\b[A-Z]{1}\d{7,8}\b",

        # Driver’s license (generic)
        r"\b[A-Z0-9]{6,12}\b",

        # Date formats (DOB)
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b"
    ]

    for p in patterns:
        if re.search(p, text):
            return True

    return False
