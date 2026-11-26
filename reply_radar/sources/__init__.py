"""Mail sources. Each exposes fetch(account_config, lookback_days) -> list[Email]."""

from __future__ import annotations

from ..config import AccountConfig
from ..models import Email


def fetch_account(acc: AccountConfig, lookback_days: int) -> list[Email]:
    if acc.provider == "gmail":
        from . import gmail
        return gmail.fetch(acc, lookback_days)
    if acc.provider == "outlook":
        from . import outlook
        return outlook.fetch(acc, lookback_days)
    if acc.provider == "mock":
        from . import mock
        return mock.fetch(acc, lookback_days)
    raise ValueError(f"Unknown provider '{acc.provider}' for account '{acc.label}'")
