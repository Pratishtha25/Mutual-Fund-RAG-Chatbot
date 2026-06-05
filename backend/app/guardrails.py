import re

# Word to digit mapping for word-based number representation
WORD_TO_DIGIT = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9"
}

# ----------------------------------------------------
# Original Text Regular Expressions (With Boundaries)
# ----------------------------------------------------
# Email pattern
EMAIL_ORIG_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Phone number: India standard (starts with 6-9, 10 digits, optional country code +91/91/0)
# Handles spaces/hyphens between digits
PHONE_ORIG_PATTERN = re.compile(
    r"\b(?:(?:\+91|91|0)\s?[\-\.]?\s?)?[6-9](?:\s?[\-\.]?\s?[0-9]){9}\b"
)

# Aadhaar card: 12 digits starting with 2-9, optional spaces/hyphens between digits
AADHAAR_ORIG_PATTERN = re.compile(
    r"\b[2-9](?:\s?[\-\.]?\s?[0-9]){11}\b"
)

# PAN card: 5 letters, 4 digits, 1 letter, optional spaces/hyphens
PAN_ORIG_PATTERN = re.compile(
    r"\b[A-Za-z](?:\s?[\-\.]?\s?[A-Za-z]){4}\s?[\-\.]?\s?[0-9](?:\s?[\-\.]?\s?[0-9]){3}\s?[\-\.]?\s?[A-Za-z]\b"
)

# Partial PAN card (Confidence check): 5 letters, 4 digits
PAN_PARTIAL_ORIG_PATTERN = re.compile(
    r"\b[A-Za-z](?:\s?[\-\.]?\s?[A-Za-z]){4}\s?[\-\.]?\s?[0-9](?:\s?[\-\.]?\s?[0-9]){3}\b"
)


# ----------------------------------------------------
# Normalized Text Regular Expressions (No Spaces/Punctuation)
# ----------------------------------------------------
# Normalized Phone number
PHONE_NORM_PATTERN = re.compile(
    r"\b(?:91|\+91)?[6-9][0-9]{9}\b"
)

# Normalized Aadhaar card
AADHAAR_NORM_PATTERN = re.compile(
    r"\b[2-9][0-9]{11}\b"
)

# Normalized PAN card (strictly 5 letters, 4 digits, 1 letter)
PAN_NORM_PATTERN = re.compile(
    r"(?<![A-Za-z])[A-Za-z]{5}[0-9]{4}[A-Za-z](?![A-Za-z])"
)

# Normalized Partial PAN card (strictly 5 letters, 4 digits)
PAN_PARTIAL_NORM_PATTERN = re.compile(
    r"(?<![A-Za-z])[A-Za-z]{5}[0-9]{4}(?!\d)"
)


# ----------------------------------------------------
# Advisory & Speculation Keywords list
# ----------------------------------------------------
ADVISORY_KEYWORDS = [
    "should i buy",
    "should i invest",
    "should i sell",
    "i should buy",
    "i should invest",
    "i should sell",
    "should we buy",
    "should we invest",
    "should we sell",
    "should one buy",
    "should one invest",
    "should buy",
    "should invest",
    "should sell",
    "buy fund",
    "buy stock",
    "invest in",
    "recommend a fund",
    "recommend small cap",
    "recommend stock",
    "recommend funds",
    "recommend me",
    "suggest me",
    "do you recommend",
    "do you suggest",
    "would you recommend",
    "would you suggest",
    "give me advice",
    "advisable to",
    "returns comparison",
    "price prediction",
    "price forecast",
    "market direction",
    "better investment",
    "higher return potential",
    "which is better",
    "which is best",
    "which to choose",
    "which one to buy",
    "which one is better",
    "which is a better",
    "comparison of returns",
    "to the moon",
    "multibagger",
    "dump",
    "pump",
    "bullish",
    "bearish",
    "crash",
    "going to rise",
    "going to fall",
    "is federal better than",
    "is au small finance bank better than",
    "is axis better than",
    "axis vs",
    "federal bank vs",
    "glenmark vs",
    "max financial vs",
    "indian bank vs",
    "better than"
]


def replace_word_digits(text: str) -> str:
    """
    Translates word-based numbers (zero-nine) to digits case-insensitively.
    """
    text_lower = text.lower()
    for word, digit in WORD_TO_DIGIT.items():
        text_lower = re.sub(rf"\b{word}\b", digit, text_lower)
    return text_lower


def normalize_query(query: str) -> str:
    """
    Strips all spaces, hyphens, and periods, and translates word-based numbers.
    """
    normalized = replace_word_digits(query)
    # Strip spaces, hyphens, periods, and standard quotes/punctuation
    normalized = re.sub(r"[\s\-\.\,\'\"]+", "", normalized)
    return normalized


def is_pii(text: str) -> bool:
    """
    Scans the original text and normalized text for PAN, Aadhaar, phone numbers, and emails.
    Returns True if any PII is detected, otherwise False.
    """
    # 1. Scan original text
    if EMAIL_ORIG_PATTERN.search(text):
        return True
    if PHONE_ORIG_PATTERN.search(text):
        return True
    if AADHAAR_ORIG_PATTERN.search(text):
        return True
    if PAN_ORIG_PATTERN.search(text):
        return True
    if PAN_PARTIAL_ORIG_PATTERN.search(text):
        return True

    # 2. Scan normalized shadow text
    norm_text = normalize_query(text)
    
    # Run tests on normalized copy
    if AADHAAR_NORM_PATTERN.search(norm_text):
        return True
    if PAN_NORM_PATTERN.search(norm_text):
        return True
    if PAN_PARTIAL_NORM_PATTERN.search(norm_text):
        return True
        
    # We also check for simple sequences of 10 digits starting with 6-9 in normalized text
    # even without word boundary constraints in case they are obfuscated.
    # To prevent matching longer digit chains (e.g. 12 digits), we match exactly 10 digits.
    phone_simple_match = re.search(r"(?<!\d)[6-9]\d{9}(?!\d)", norm_text)
    if phone_simple_match:
        return True

    return False


def is_advisory(text: str) -> bool:
    """
    Scans the query for investment advisory and speculative keywords.
    Returns True if advisory intent is detected, otherwise False.
    """
    text_lower = text.lower()
    for keyword in ADVISORY_KEYWORDS:
        if keyword in text_lower:
            return True
    return False


def get_pii_response() -> str:
    """
    Returns the standard PII rejection response.
    """
    return (
        "For your security, please do not share personal information such as PAN, "
        "Aadhaar, phone numbers, or account details. I do not collect, store, or "
        "process personal data, and I cannot access your personal Groww account "
        "details. For account-specific assistance, please visit the Help & Support "
        "section on the Groww App."
    )


def get_advisory_response() -> str:
    """
    Returns the standard investment advisory deflection response.
    """
    return (
        "I am a facts-only assistant designed to provide official stock and fund "
        "details and cannot offer investment advice, comparisons, or buy/sell "
        "recommendations. For investment decisions, please refer to official "
        "scheme materials or consult a SEBI-registered financial advisor. "
        "You can read more about investing basics on the [AMFI Educational Portal]"
        "(https://www.amfiindia.com) or [Groww Academy](https://groww.in/academy)."
    )
