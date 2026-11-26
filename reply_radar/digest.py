"""Rank the items and render the daily digest (terminal Markdown + HTML file)."""

from __future__ import annotations

import html
from datetime import date, datetime, timezone

from .config import AccountConfig, Config
from .models import DigestItem, Email, TriageDecision


def score(e: Email, d: TriageDecision, vip: list[str], now: datetime) -> tuple[float, float]:
    waited = max(0.0, (now - e.date).total_seconds() / 3600)
    s = d.priority * 10
    s += min(waited, 72) / 72 * 10                       # up to +10 for waiting 3 days
    if e.sender_email in vip or e.sender_email.split("@")[-1] in vip:
        s += 8
    if d.deadline:
        try:
            days = (date.fromisoformat(d.deadline) - now.date()).days
            s += 15 if days <= 0 else 10 if days == 1 else 5 if days <= 3 else 0
        except ValueError:
            pass
    return s, waited


def build_items(emails, decisions, drafts, cfg: Config, now: datetime | None = None) -> list[DigestItem]:
    now = now or datetime.now(timezone.utc)
    accounts = {a.label: a for a in cfg.accounts}
    items = []
    for e in emails:
        d = decisions.get(e.id)
        if not d or not d.needs_reply:
            continue
        s, waited = score(e, d, cfg.vip_senders, now)
        items.append(DigestItem(e, d, accounts[e.account].address, drafts.get(e.id), s, waited))
    items.sort(key=lambda i: i.score, reverse=True)
    return items


def _waited(h: float) -> str:
    return f"{int(h)}h" if h < 48 else f"{int(h // 24)}d"


def render_markdown(items: list[DigestItem], stats: dict) -> str:
    n = len(items)
    lines = [f"# Reply Radar: {n} {'person is' if n == 1 else 'people are'} waiting on you", ""]
    lines.append(
        f"_Scanned {stats['fetched']} emails from {stats['accounts']} accounts, removed "
        f"{stats['duplicates']} duplicate copies, triage by {stats['engine']}._"
    )
    lines.append("")
    for i, it in enumerate(items, 1):
        e, d = it.email, it.decision
        tags = [f"`{e.account}`"] + [f"`also in {a}`" for a in e.also_in]
        if d.deadline:
            tags.append(f"**due {d.deadline}**")
        if d.sensitive:
            tags.append("**sensitive: handle yourself**")
        lines.append(f"## {i}. {e.sender_name}: {e.subject}  ")
        lines.append(f"{' '.join(tags)} · waiting {_waited(it.waited_hours)} · priority {d.priority}/5")
        lines.append("")
        lines.append(f"**Ask:** {d.ask_summary}")
        lines.append(f"**Reply from:** {it.send_from}")
        if d.needs_real_work and d.reminder_task:
            lines.append(f"**Reminder:** {d.reminder_task}" + (f" (by {d.deadline})" if d.deadline else ""))
        if it.draft and not d.sensitive:
            lines.append("")
            lines.append("> " + it.draft.replace("\n", "\n> "))
        lines.append("")
    return "\n".join(lines)


def render_html(items: list[DigestItem], stats: dict) -> str:
    esc = html.escape
    cards = []
    for it in items:
        e, d = it.email, it.decision
        chips = f'<span class="chip">{esc(e.account)}</span>' + "".join(
            f'<span class="chip ghost">also in {esc(a)}</span>' for a in e.also_in)
        if d.deadline:
            chips += f'<span class="chip due">due {esc(d.deadline)}</span>'
        if d.sensitive:
            chips += '<span class="chip warn">sensitive: handle yourself</span>'
        draft = ""
        if it.draft and not d.sensitive:
            draft = f"<details><summary>Suggested reply</summary><pre>{esc(it.draft)}</pre></details>"
        reminder = ""
        if d.needs_real_work and d.reminder_task:
            reminder = f'<p class="meta">Reminder: {esc(d.reminder_task)}</p>'
        cards.append(f"""
<article>
  <div class="chips">{chips}</div>
  <h2>{esc(e.sender_name)}: {esc(e.subject)}</h2>
  <p class="ask">{esc(d.ask_summary)}</p>
  <p class="meta">Reply from <b>{esc(it.send_from)}</b> · waiting {_waited(it.waited_hours)} · priority {d.priority}/5</p>
  {reminder}{draft}
</article>""")
    n = len(items)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reply Radar digest</title>
<style>
:root{{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--accent:#3355ff;--line:#e4e4e0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--card:#1f1f22;--ink:#f0f0f2;--muted:#a0a0a8;--line:#333338}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:720px;margin:0 auto;padding:24px 16px}}
h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--muted);margin:0 0 20px}}
article{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}}
h2{{font-size:17px;margin:8px 0 4px}} .ask{{margin:4px 0}} .meta{{color:var(--muted);font-size:14px;margin:4px 0}}
.chip{{display:inline-block;font-size:12px;padding:2px 8px;border-radius:99px;background:var(--accent);color:#fff;margin-right:6px}}
.chip.ghost{{background:transparent;color:var(--muted);border:1px solid var(--line)}}
.chip.due{{background:#d9480f}} .chip.warn{{background:#8a6d00}}
pre{{white-space:pre-wrap;font:14px/1.5 ui-monospace,monospace;background:var(--bg);padding:12px;border-radius:8px}}
summary{{cursor:pointer;color:var(--accent);font-size:14px;margin-top:6px}}
</style></head><body><main>
<h1>{n} {'person is' if n == 1 else 'people are'} waiting on you</h1>
<p class="sub">Scanned {stats['fetched']} emails from {stats['accounts']} accounts · removed {stats['duplicates']} duplicate copies · triage by {esc(stats['engine'])} · {esc(stats['generated'])}</p>
{''.join(cards) or '<p>Inbox zero on replies. Nice.</p>'}
</main></body></html>"""
