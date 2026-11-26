"""Outlook / Microsoft 365 source (Microsoft Graph, Mail.Read delegated scope)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from ..config import AccountConfig
from ..models import Email
from .common import clean_body, html_to_text, normalize_message_id, thread_key

# Read-only. Mail.Read cannot send, delete or move mail.
SCOPES = ["Mail.Read"]
GRAPH = "https://graph.microsoft.com/v1.0"


def _token(acc: AccountConfig) -> str:
    import msal

    if not acc.client_id:
        raise ValueError(f"[{acc.label}] Outlook needs client_id in config.yaml. See README > Outlook setup.")
    cache = msal.SerializableTokenCache()
    cache_path = Path(acc.token_file)
    if cache_path.exists():
        cache.deserialize(cache_path.read_text())
    app = msal.PublicClientApplication(
        acc.client_id, authority=f"https://login.microsoftonline.com/{acc.tenant}", token_cache=cache
    )
    result = None
    accounts = app.get_accounts(username=acc.address) or app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Could not start device sign-in: {json.dumps(flow, indent=2)}")
        print(f"[{acc.label}] {flow['message']}")
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"[{acc.label}] Sign-in failed: {result.get('error_description')}")
    if cache.has_state_changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(cache.serialize())
    return result["access_token"]


def _get(url: str, token: str, params: dict | None = None) -> dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "Prefer": 'outlook.body-content-type="text"'},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _addr(entry: dict) -> str:
    return entry.get("emailAddress", {}).get("address", "").lower()


def fetch(acc: AccountConfig, lookback_days: int) -> list[Email]:
    token = _token(acc)
    me = acc.address.lower()
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _get(
        f"{GRAPH}/me/mailFolders/inbox/messages",
        token,
        {
            "$top": str(acc.max_emails),
            "$filter": f"receivedDateTime ge {since}",
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,"
                       "internetMessageId,conversationId,internetMessageHeaders,inferenceClassification",
        },
    )

    # Conversations the user has already answered: anything in Sent Items in the window.
    sent = _get(
        f"{GRAPH}/me/mailFolders/sentitems/messages",
        token,
        {"$top": "100", "$filter": f"sentDateTime ge {since}", "$select": "conversationId,sentDateTime"},
    )
    last_sent: dict[str, datetime] = {}
    for s in sent.get("value", []):
        t = datetime.fromisoformat(s["sentDateTime"].replace("Z", "+00:00"))
        cid = s["conversationId"]
        last_sent[cid] = max(t, last_sent.get(cid, t))

    emails: list[Email] = []
    for m in data.get("value", []):
        if m.get("inferenceClassification") == "other":   # Focused Inbox "Other" tab = bulk mail
            continue
        sender = _addr(m.get("from", {}))
        if sender == me:
            continue
        headers = {h["name"].lower(): h["value"] for h in m.get("internetMessageHeaders") or []}
        mid = normalize_message_id(m.get("internetMessageId")) or f"<outlook-{m['id']}>"
        date = datetime.fromisoformat(m["receivedDateTime"].replace("Z", "+00:00"))
        body = m.get("body", {})
        text = body.get("content", "")
        if body.get("contentType") == "html":
            text = html_to_text(text)
        replied_at = last_sent.get(m.get("conversationId"))
        emails.append(
            Email(
                id=f"{acc.label}:{m['id'][-24:]}",
                account=acc.label,
                account_address=me,
                message_id=mid,
                thread_key=thread_key(mid, headers.get("in-reply-to"), headers.get("references")),
                subject=m.get("subject") or "(no subject)",
                sender_name=m.get("from", {}).get("emailAddress", {}).get("name", sender),
                sender_email=sender,
                to=[_addr(r) for r in m.get("toRecipients", [])],
                cc=[_addr(r) for r in m.get("ccRecipients", [])],
                date=date,
                body=clean_body(text),
                user_already_replied=bool(replied_at and replied_at > date),
            )
        )
    return emails
