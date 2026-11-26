"""Offline tests (no API key or accounts needed): python -m pytest"""

from datetime import datetime, timezone
from pathlib import Path

from reply_radar.config import load_config
from reply_radar.dedupe import merge, normalize_subject
from reply_radar.models import Email
from reply_radar.pipeline import run
from reply_radar.sources.common import clean_body, thread_key

ROOT = Path(__file__).resolve().parents[1]


def _email(id, account, addr, mid, tk=None, to=None, date=None, replied=False):
    return Email(id=id, account=account, account_address=addr, message_id=mid, thread_key=tk or mid,
                 subject="Hi", sender_name="A", sender_email="a@x.com", to=to or [addr], cc=[],
                 date=date or datetime(2026, 11, 25, tzinfo=timezone.utc), body="?",
                 user_already_replied=replied)


def test_thread_key_uses_reference_root():
    assert thread_key("<c@x>", "<b@x>", "<a@x> <b@x>") == "<a@x>"
    assert thread_key("<c@x>", "<b@x>", None) == "<b@x>"
    assert thread_key("<C@X>", None, None) == "<c@x>"


def test_normalize_subject():
    assert normalize_subject("RE: Fwd:  Budget  plan") == "budget plan"


def test_clean_body_strips_quotes():
    body = "Sure, Tuesday works.\n\nOn Mon, Nov 24, Bob wrote:\n> old stuff"
    assert clean_body(body) == "Sure, Tuesday works."


def test_same_message_in_two_inboxes_is_merged_and_prefers_to_address():
    cfg = load_config(ROOT / "config.demo.yaml")
    accounts = {a.label: a for a in cfg.accounts}
    a = _email("school:1", "school", "s@x", "<m1>", to=["s@x"])
    b = _email("club:1", "club", "c@x", "<m1>", to=["s@x"])   # club only got a cc
    merged, removed = merge([a, b], accounts)
    assert removed == 1 and len(merged) == 1
    assert merged[0].account == "school" and merged[0].also_in == ["club"]


def test_newest_message_in_thread_is_kept():
    cfg = load_config(ROOT / "config.demo.yaml")
    accounts = {a.label: a for a in cfg.accounts}
    old = _email("school:1", "school", "s@x", "<root>", date=datetime(2026, 11, 20, tzinfo=timezone.utc))
    new = _email("personal:2", "personal", "p@x", "<reply>", tk="<root>",
                 date=datetime(2026, 11, 25, tzinfo=timezone.utc))
    merged, removed = merge([old, new], accounts)
    assert [m.id for m in merged] == ["personal:2"] and removed == 1


def test_demo_pipeline_runs_offline():
    cfg = load_config(ROOT / "config.demo.yaml")
    result = run(cfg, offline=True, log=lambda *_: None)
    assert result.stats["fetched"] == 39
    assert result.stats["duplicates"] >= 4
    assert result.items, "expected at least one email needing a reply"
    for it in result.items:
        assert it.send_from.endswith(".example.edu") or "example" in it.send_from
        if it.decision.sensitive:
            assert it.email.id not in {i.email.id for i in result.items if i.draft and i.decision.sensitive}
