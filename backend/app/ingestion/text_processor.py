"""Conservative section tags; never interprets text as executable policy."""

import re
import unicodedata


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).replace("\u00ad", "").split())


def section_kind(value: str) -> str:
    lowered = value.casefold()
    for kind, pattern in (
        ("exclusion", r"not eligible|exclusion|ineligible|discontinued"),
        ("eligibility", r"eligib|family income|disability|candidate should"),
        ("required_documents", r"certificate|documents required|documentary proof"),
        ("deadline", r"deadline|last date|closing date|apply before"),
        ("benefit", r"amount of|benefit|scholarship amount|financial assistance"),
    ):
        if re.search(pattern, lowered):
            return kind
    return "general"
