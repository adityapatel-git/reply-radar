"""Gmail source (Gmail API, read-only scope)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from ..config import AccountConfig
from ..models import Email
from .common import clean_body, html_to_text, normalize_message_id, parse_addresses, parse_sender, thread_key

# Read-only. Reply Radar can never send, delete, archive or label mail.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _service(acc: AccountConfig):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = Path(acc.token_file)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(acc.credentials_file).exists():
                raise FileNotFoundError(
                    f"Gmail OAuth client file not found: {acc.credentials_file}. See README > Gmail setup."
                )
            flow = InstalledAppFlow.from_client_secrets_file(acc.credentials_file, SCOPES)
            print(f"[{acc.label}] Opening a browser to sign in to {acc.address} (read-only)...")
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _body_from_payload(payload: dict) -> str:
    plain, html = [], []

    def walk(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            (plain if mime == "text/plain" else html if mime == "text/html" else plain).append(text)
        for p in part.get("parts", []) or []:
            walk(p)

    walk(payload)
    if plain:
        return "\n".join(plain)
    return html_to_text("\n".join(html))


def fetch(acc: AccountConfig, lookback_days: int) -> list[Email]:
    svc = _service(acc)
    me = acc.address.lower()
    query = f"in:inbox newer_than:{lookback_days}d -from:me -category:promotions -category:social"
    resp = svc.users().messages().list(userId="me", q=query, maxResults=acc.max_emails).execute()
    emails: list[Email] = []
    thread_last_sender: dict[str, str] = {}

    for ref in resp.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        sender_name, sender_email = parse_sender(headers.get("from"))
        mid = normalize_message_id(headers.get("message-id")) or f"<gmail-{msg['id']}>"
        try:
            date = parsedate_to_datetime(headers["date"])
        except Exception:
            date = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        # Has the user already replied in this Gmail thread? (last message is from me)
        tid = msg["threadId"]
        if tid not in thread_last_sender:
            thread = svc.users().threads().get(
                userId="me", id=tid, format="metadata", metadataHeaders=["From"]
            ).execute()
            last = thread["messages"][-1]
            last_from = next(
                (h["value"] for h in last["payload"].get("headers", []) if h["name"].lower() == "from"), ""
            )
            thread_last_sender[tid] = parse_sender(last_from)[1]

        emails.append(
            Email(
                id=f"{acc.label}:{msg['id']}",
                account=acc.label,
                account_address=me,
                message_id=mid,
                thread_key=thread_key(mid, headers.get("in-reply-to"), headers.get("references")),
                subject=headers.get("subject", "(no subject)"),
                sender_name=sender_name,
                sender_email=sender_email,
                to=parse_addresses(headers.get("to")),
                cc=parse_addresses(headers.get("cc")),
                date=date,
                body=clean_body(_body_from_payload(msg["payload"])),
                user_already_replied=thread_last_sender[tid] == me,
            )
        )
    return emails
