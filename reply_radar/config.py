"""Loads config.yaml (accounts, tone, VIP senders)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_MODEL = "claude-opus-5-5"


@dataclass
class AccountConfig:
    label: str                 # short tag shown in the digest, e.g. "school"
    provider: str              # "gmail" | "outlook" | "mock"
    address: str
    tone: str = "friendly and clear"
    priority: int = 0          # tie-breaker when a thread reached several accounts
    max_emails: int = 50
    # Provider specific
    credentials_file: str = "secrets/gmail_credentials.json"   # gmail OAuth client
    token_file: str = ""                                        # cached user token
    client_id: str = ""                                         # outlook (Azure app)
    tenant: str = "common"


@dataclass
class Config:
    user_name: str
    accounts: list[AccountConfig]
    vip_senders: list[str] = field(default_factory=list)
    lookback_days: int = 3
    model: str = DEFAULT_MODEL
    output_dir: str = "output"


def load_config(path: str | os.PathLike) -> Config:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    accounts = []
    for a in raw.get("accounts", []):
        acc = AccountConfig(**a)
        if not acc.token_file:
            acc.token_file = f"secrets/token_{acc.label}.json"
        accounts.append(acc)
    if not accounts:
        raise ValueError(f"{path}: no accounts configured")
    return Config(
        user_name=raw.get("user_name", "Me"),
        accounts=accounts,
        vip_senders=[s.lower() for s in raw.get("vip_senders", [])],
        lookback_days=int(raw.get("lookback_days", 3)),
        model=raw.get("model", DEFAULT_MODEL),
        output_dir=raw.get("output_dir", "output"),
    )
