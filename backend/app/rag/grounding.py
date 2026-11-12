"""Extractive answer boundaries: no unsupported prose or invented citations."""

import re

from app.rag.citations import SourceCitation

STOPWORDS = {
    "what",
    "are",
    "the",
    "for",
    "this",
    "scheme",
    "scholarship",
    "which",
    "does",
    "document",
    "where",
    "guideline",
    "mention",
    "condition",
    "requirements",
    "requirement",
    "please",
    "tell",
    "about",
    "is",
    "of",
    "a",
    "an",
    "and",
    "or",
    "to",
    "in",
    "my",
    "me",
    "how",
    "can",
    "i",
    "it",
    "on",
    "do",
    "eligibility",
    "eligible",
}
INTENTS = {
    "income": {"income", "financial", "earnings"},
    "documents": {"certificate", "certificates", "documents", "proof", "document"},
    "disability": {"disability", "disabled", "specially", "percentage"},
    "requirements": {"requirements", "eligibility", "eligible", "conditions", "condition", "scholarship"},
    "application": {"apply", "application", "deadline", "date", "dates"},
    "benefits": {"benefit", "benefits", "amount", "award"},
}


def query_terms(query: str) -> set[str]:
    return {word for word in re.findall(r"\w+", query.casefold()) if len(word) > 2 and word not in STOPWORDS}


def question_intent(question: str) -> str | None:
    words = set(re.findall(r"\w+", question.casefold()))
    return next((name for name, terms in INTENTS.items() if words & terms), None)


def relevant(question: str, excerpt: str) -> bool:
    intent = question_intent(question)
    text = excerpt.casefold()
    if intent is None:
        return False
    if intent == "requirements":
        return bool(re.search(r"eligib|require|must|should|candidate|applicant|student", text))
    if intent == "documents":
        return bool(re.search(r"certificate|document|proof|enclos|attach", text))
    if intent == "application":
        return bool(re.search(r"appl|deadline|date|portal", text))
    if intent == "benefits":
        return bool(re.search(r"benefit|amount|award|payment|rs\.|inr|₹", text))
    return bool(query_terms(question) & set(re.findall(r"\w+", text)))


def grounded_quotes(question: str, citations: list[SourceCitation]) -> list[SourceCitation]:
    return [item for item in citations if relevant(question, item.excerpt)][:3]
