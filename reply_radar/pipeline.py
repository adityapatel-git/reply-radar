"""fetch -> merge/dedupe -> triage -> draft -> rank. No message content is stored."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .config import Config
from .dedupe import merge
from .digest import build_items
from .models import DigestItem, Email, TriageDecision
from .sources import fetch_account
from .triage import make_triager


@dataclass
class RunResult:
    items: list[DigestItem]
    emails: list[Email]
    decisions: dict[str, TriageDecision]
    stats: dict


def run(cfg: Config, offline: bool = False, skip_drafts: bool = False, log=print) -> RunResult:
    all_emails: list[Email] = []
    for acc in cfg.accounts:
        got = fetch_account(acc, cfg.lookback_days)
        log(f"  {acc.label:<10} {acc.address:<32} {len(got)} emails")
        all_emails.extend(got)

    accounts = {a.label: a for a in cfg.accounts}
    merged, dupes = merge(all_emails, accounts)
    log(f"  merged into {len(merged)} threads ({dupes} duplicate copies removed)")

    triager, using_claude = make_triager(cfg.model, cfg.user_name, offline)
    engine = cfg.model if using_claude else "offline keyword rules (set ANTHROPIC_API_KEY to use Claude)"
    log(f"  triage engine: {engine}")
    decisions = triager.triage(merged)

    to_draft = [
        (e, decisions[e.id], accounts[e.account])
        for e in merged
        if e.id in decisions and decisions[e.id].needs_reply and not decisions[e.id].sensitive
    ]
    drafts = {} if skip_drafts else triager.draft(to_draft)

    items = build_items(merged, decisions, drafts, cfg)
    stats = {
        "fetched": len(all_emails),
        "accounts": len(cfg.accounts),
        "duplicates": dupes,
        "engine": engine,
        "generated": datetime.now().strftime("%a %b %d, %H:%M"),
    }
    return RunResult(items, merged, decisions, stats)
