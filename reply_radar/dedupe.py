"""Merge inboxes: one entry per thread, even if it reached several of my addresses."""

from __future__ import annotations

import re

from .config import AccountConfig
from .models import Email

_PREFIX = re.compile(r"^\s*((re|fw|fwd|aw)\s*:\s*)+", re.I)


def normalize_subject(subject: str) -> str:
    return re.sub(r"\s+", " ", _PREFIX.sub("", subject)).strip().lower()


def cluster_key(e: Email) -> str:
    # The thread root Message-ID is the same in every inbox the thread reached.
    # Fallback for mail with no usable headers: same sender + same normalized subject.
    return e.thread_key or f"{e.sender_email}|{normalize_subject(e.subject)}"


def choose_send_from(copies: list[Email], accounts: dict[str, AccountConfig]) -> Email:
    """Pick which copy (and so which address) to reply from.

    1. An address in To beats one in Cc (the sender was writing to that address).
    2. Then the account's configured priority.
    """
    def rank(e: Email):
        acc = accounts.get(e.account)
        return (1 if e.addressed_directly else 0, acc.priority if acc else 0)

    return max(copies, key=rank)


def merge(emails: list[Email], accounts: dict[str, AccountConfig]) -> tuple[list[Email], int]:
    """Returns (one email per thread, number of duplicate copies removed).

    For each thread we keep the newest message, and mark it replied if I answered
    anywhere in that thread from any account.
    """
    groups: dict[str, list[Email]] = {}
    for e in emails:
        groups.setdefault(cluster_key(e), []).append(e)

    merged: list[Email] = []
    removed = 0
    for copies in groups.values():
        newest_date = max(c.date for c in copies)
        newest = [c for c in copies if c.date == newest_date]
        # Copies of the same newest message delivered to different addresses.
        same_msg = [c for c in copies if c.message_id == newest[0].message_id] or newest
        keep = choose_send_from(same_msg, accounts)
        keep.also_in = sorted({c.account for c in copies} - {keep.account})
        replied_after_newest = any(c.user_already_replied for c in copies if c.date >= newest_date)
        keep.user_already_replied = keep.user_already_replied or replied_after_newest
        merged.append(keep)
        removed += len(copies) - 1
    merged.sort(key=lambda e: e.date, reverse=True)
    return merged, removed
