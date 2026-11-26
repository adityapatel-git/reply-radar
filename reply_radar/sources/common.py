"""Helpers shared by the mail sources."""

from __future__ import annotations

import re
from email.utils import getaddresses, parseaddr

_ID_RE = re.compile(r"<[^>]+>")
MAX_BODY_CHARS = 4000


def normalize_message_id(value: str | None) -> str:
    if not value:
        return ""
    m = _ID_RE.search(value)
    return (m.group(0) if m else value.strip()).lower()


def thread_key(message_id: str, in_reply_to: str | None, references: str | None) -> str:
    """The root message of a thread. Identical in every inbox the thread reached."""
    if references:
        ids = _ID_RE.findall(references)
        if ids:
            return ids[0].lower()
    if in_reply_to:
        return normalize_message_id(in_reply_to)
    return normalize_message_id(message_id)


def parse_addresses(header: str | None) -> list[str]:
    if not header:
        return []
    return [addr.lower() for _, addr in getaddresses([header]) if addr]


def parse_sender(header: str | None) -> tuple[str, str]:
    name, addr = parseaddr(header or "")
    return name or addr, addr.lower()


_QUOTE_MARKERS = re.compile(r"^(On .+wrote:|-----Original Message-----|From: .+)$", re.M)


def clean_body(text: str) -> str:
    """Drop quoted history so Claude reads only the newest message."""
    text = text.replace("\r\n", "\n")
    m = _QUOTE_MARKERS.search(text)
    if m and m.start() > 0:
        text = text[: m.start()]
    lines = [ln for ln in text.split("\n") if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()[:MAX_BODY_CHARS]


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return re.sub(r"\n{3,}", "\n\n", text)
