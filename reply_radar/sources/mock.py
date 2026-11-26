"""Demo source: reads data/sample_emails.json so the project runs without real accounts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import AccountConfig
from ..models import Email
from .common import clean_body, normalize_message_id, thread_key

SAMPLE_FILE = Path(__file__).resolve().parents[2] / "data" / "sample_emails.json"


def load_all(path: Path = SAMPLE_FILE, now: datetime | None = None) -> list[dict]:
    raw = json.loads(Path(path).read_text())
    return raw["emails"]


def fetch(acc: AccountConfig, lookback_days: int, path: Path = SAMPLE_FILE,
          now: datetime | None = None) -> list[Email]:
    """Sample dates are stored as 'hours_ago' so the demo always looks fresh."""
    now = now or datetime.now(timezone.utc)
    out = []
    for e in load_all(path):
        if e["account"] != acc.label:
            continue
        date = now - timedelta(hours=e["hours_ago"])
        if date < now - timedelta(days=lookback_days):
            continue
        mid = normalize_message_id(e["message_id"])
        out.append(
            Email(
                id=e["id"],
                account=acc.label,
                account_address=acc.address.lower(),
                message_id=mid,
                thread_key=thread_key(mid, e.get("in_reply_to"), e.get("references")),
                subject=e["subject"],
                sender_name=e["from_name"],
                sender_email=e["from_email"].lower(),
                to=[a.lower() for a in e["to"]],
                cc=[a.lower() for a in e.get("cc", [])],
                date=date,
                body=clean_body(e["body"]),
                user_already_replied=e.get("user_already_replied", False),
            )
        )
    return out[: acc.max_emails]
