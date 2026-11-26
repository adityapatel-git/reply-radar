"""Data types shared across Reply Radar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


@dataclass
class Email:
    """One message pulled from one account. Read-only snapshot; never written back."""

    id: str                      # unique within this run, e.g. "school:AAMk..."
    account: str                 # account label from config, e.g. "school"
    account_address: str         # the inbox address it was pulled from
    message_id: str              # RFC 822 Message-ID header (same across inboxes)
    thread_key: str              # root of the thread (References[0] / In-Reply-To / Message-ID)
    subject: str
    sender_name: str
    sender_email: str
    to: list[str]
    cc: list[str]
    date: datetime
    body: str
    user_already_replied: bool = False
    # Filled in by dedupe: every account this message/thread reached.
    also_in: list[str] = field(default_factory=list)

    @property
    def addressed_directly(self) -> bool:
        return self.account_address.lower() in (a.lower() for a in self.to)


# ---------- Claude structured outputs ----------

class TriageDecision(BaseModel):
    id: str = Field(description="The email id exactly as given in the input.")
    needs_reply: bool = Field(description="True if the sender asks something or clearly expects a personal reply.")
    confidence: float = Field(description="0.0 to 1.0")
    reason: str = Field(description="One short sentence explaining the decision.")
    ask_summary: str = Field(description="One line: what the sender wants from me. Empty if no reply needed.")
    deadline: Optional[str] = Field(default=None, description="ISO date (YYYY-MM-DD) if the email states or implies a deadline, else null.")
    priority: int = Field(description="1 (low) to 5 (urgent).")
    sensitive: bool = Field(description="True if it touches health, money, or relationships. No draft will be written.")
    needs_real_work: bool = Field(description="True if answering needs real work (a document, research, a task) beyond a quick reply.")
    reminder_task: Optional[str] = Field(default=None, description="If needs_real_work, a short to-do line for a dated reminder.")


class TriageBatch(BaseModel):
    decisions: list[TriageDecision]


class DraftReply(BaseModel):
    id: str
    draft: str = Field(description="The reply body only, no subject line, signed with the user's first name.")


class DraftBatch(BaseModel):
    drafts: list[DraftReply]


@dataclass
class DigestItem:
    email: Email
    decision: TriageDecision
    send_from: str               # address the reply should be sent from
    draft: Optional[str]
    score: float
    waited_hours: float
