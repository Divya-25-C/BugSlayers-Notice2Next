from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DATE_PATTERNS = [
    re.compile(rf"\b(?P<raw>\d{{1,2}}\s*[-–]\s*\d{{1,2}}\s+{MONTH}(?:,?\s+\d{{4}})?)\b", re.I),
    re.compile(rf"\b(?P<raw>\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH}(?:,?\s+\d{{4}})?)\b", re.I),
    re.compile(rf"\b(?P<raw>{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)\b", re.I),
    re.compile(r"\b(?P<raw>\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4}))\b"),
]
ACTION_WORDS = (
    "deadline", "due", "submit", "submission", "register", "registration",
    "apply", "application", "last date", "closes", "exam", "orientation",
    "workshop", "session", "event", "interview", "meeting", "report",
)
DEADLINE_WORDS = ("deadline", "due", "submit", "submission", "register", "registration", "apply", "application", "last date", "closes")
EVENT_WORDS = ("exam", "orientation", "workshop", "session", "event", "interview", "meeting")


def _sentences(text: str) -> list[str]:
    cleaned = text.replace("\x00", " ")
    chunks: list[str] = []
    for line in cleaned.splitlines():
        line = re.sub(r"\s+", " ", line).strip(" \t•-–")
        if not line:
            continue
        chunks.extend(part.strip() for part in re.split(r"(?<=[.!?;])\s+", line) if part.strip())
    return chunks


def _iso_date(raw: str) -> str | None:
    raw_clean = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", raw, flags=re.I).replace("–", "-")
    formats = (
        "%d %B %Y", "%d %b %Y", "%d %B, %Y", "%d %b, %Y",
        "%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y",
        "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw_clean, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _title(sentence: str, raw_date: str) -> str:
    lower = sentence.casefold()
    if any(word in lower for word in ("submit", "submission", "report")):
        return "Submission deadline"
    if any(word in lower for word in ("register", "registration")):
        return "Registration deadline"
    if any(word in lower for word in ("apply", "application")):
        return "Application deadline"
    if any(word in lower for word in DEADLINE_WORDS):
        return "Deadline to review"
    for word, title in (("exam", "Exam"), ("orientation", "Orientation"), ("workshop", "Workshop"), ("interview", "Interview"), ("meeting", "Meeting"), ("session", "Session"), ("event", "Event")):
        if word in lower:
            return title
    return f"Review notice for {raw_date}"


def analyze_pages(pages: list[str]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for page_number, page_text in enumerate(pages, start=1):
        for sentence in _sentences(page_text):
            matches: list[str] = []
            for pattern in DATE_PATTERNS:
                for match in pattern.finditer(sentence):
                    raw = re.sub(r"\s+", " ", match.group("raw")).strip(" ,.")
                    if raw and raw.casefold() not in {m.casefold() for m in matches}:
                        matches.append(raw)
            for raw_date in matches:
                key = (page_number, raw_date.casefold(), sentence.casefold())
                if key in seen:
                    continue
                seen.add(key)
                lowered = sentence.casefold()
                if any(word in lowered for word in DEADLINE_WORDS):
                    kind = "deadline"
                elif any(word in lowered for word in EVENT_WORDS):
                    kind = "event"
                elif any(word in lowered for word in ACTION_WORDS):
                    kind = "action"
                else:
                    kind = "date mention"
                evidence = sentence if len(sentence) <= 260 else sentence[:257].rstrip() + "..."
                digest = hashlib.sha1(f"{page_number}|{raw_date}|{sentence}".encode("utf-8")).hexdigest()[:12]
                candidates.append({
                    "id": digest,
                    "title": _title(sentence, raw_date),
                    "kind": kind,
                    "page": page_number,
                    "raw_date": raw_date,
                    "date_iso": _iso_date(raw_date),
                    "evidence": evidence,
                })
    return {
        "candidates": candidates,
        "candidate_count": len(candidates),
        "message": "Review each suggestion against its source before approving a reminder." if candidates else "No clear dates found. Try a text-based PDF or paste the relevant notice text.",
    }


def analyze_text(text: str) -> dict[str, Any]:
    return analyze_pages([text])


def validate_reminder(title: str, date_value: str, page: int, evidence: str) -> dict[str, Any]:
    title = title.strip()[:120]
    evidence = evidence.strip()[:260]
    try:
        normalized_date = date.fromisoformat(date_value).isoformat()
    except ValueError:
        raise ValueError("Use a valid date in YYYY-MM-DD format.")
    if not title:
        raise ValueError("Add a reminder title before approving.")
    if page < 1:
        raise ValueError("Source page must be 1 or greater.")
    if not evidence:
        raise ValueError("A source excerpt is required before a reminder can be drafted.")
    return {
        "title": title,
        "date": normalized_date,
        "source_page": page,
        "evidence": evidence,
        "status": "awaiting_student_approval",
        "side_effect": "none",
    }
