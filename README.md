# Reply Radar

**One agent that finds who's waiting on you across all your inboxes.**

Reply Radar connects to several email accounts (Gmail and Outlook) with **read-only** access, merges them
into one daily digest of emails that need a reply, tags each item with the account it came from, removes
duplicates when the same thread reached more than one of your addresses, and writes a suggested reply for
each one, marked with the address it should be sent from.

Built for the Side Quest beta (Persona-driven AI agent, *Persona 4: You*).

```
# Reply Radar: 16 people are waiting on you
_Scanned 39 emails from 3 accounts, removed 5 duplicate copies, triage by claude-opus-5-5._

## 1. Dr. Lena Moreau: Robotics club faculty sponsor form
`school` `also in club` · waiting 8h · priority 4/5
**Ask:** Send her the sponsor form to sign before the end of the week.
**Reply from:** aditya@school.example.edu
> Hi Dr. Moreau, thank you so much for agreeing to sponsor the club! ...
```

## What it does

1. **Pulls** recent inbox mail from each account (default: last 3 days, up to 50 per account).
2. **Merges and de-duplicates.** A thread that reached two of your addresses shows up once, tagged
   `also in <account>`. It matches on the thread's root `Message-ID`, which is identical in every inbox,
   with a sender + subject fallback.
3. **Triages with Claude.** It flags emails where a real person asks you something or expects an answer, and
   skips newsletters, receipts, FYIs, and threads you already answered.
4. **Ranks** by priority, how long they have waited, deadlines in the text, and your VIP senders.
5. **Drafts** a reply for each item, in the tone you set for that account, and says which address to send from.
6. **Flags** sensitive topics (health, money, relationships) for you to handle yourself, with no draft.
7. **Adds reminders.** Anything that needs real work (a document, a review) gets a dated to-do line.

## What it will not do

- Send, delete, archive, label or move mail. The scopes are `gmail.readonly` and `Mail.Read`, so it
  *can't*, even by mistake.
- Store message content. Emails are read into memory for one run. The only file written is
  `output/digest.html` (summaries and drafts), and `--no-save` skips even that.
- Follow instructions inside emails. Bodies are passed to Claude as untrusted data. The sample data includes a
  prompt-injection email to test this.

## Quick start (demo mode, about 2 minutes)

Demo mode uses three synthetic inboxes in `data/sample_emails.json` (school, personal, club: 39 emails,
including threads sent to two addresses). No email accounts are needed.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m reply_radar --demo     # works with no API key (keyword rules)
```

To use Claude, add your API key (see [SETUP.md](SETUP.md), step 2) and run it again:

```bash
cp .env.example .env             # then paste your key into .env
python -m reply_radar --demo
open output/digest.html          # Windows: start output\digest.html
```

Without `ANTHROPIC_API_KEY` the app falls back to simple keyword rules, so you can always demo the
pipeline. The digest header says which engine was used.

## Using your real (test) accounts

Follow **[SETUP.md](SETUP.md)**. It covers Google Cloud OAuth for Gmail, an Azure app registration for
Outlook, the API key, and `config.yaml`. Then:

```bash
python -m reply_radar            # reads config.yaml
```

The first run opens a browser (Gmail) or prints a device code (Outlook) to sign in. Tokens are cached in
`secrets/`, which is git-ignored.

| Flag | What it does |
|---|---|
| `--demo` | Use the sample inboxes (`config.demo.yaml`) |
| `--config FILE` | Use a different config file |
| `--offline` | Don't call Claude; use keyword rules |
| `--no-drafts` | Skip drafting replies |
| `--no-save` | Print only; don't write `output/digest.html` |

## Measuring accuracy

```bash
python scripts/accuracy_test.py --demo                 # against labelled sample data
python scripts/accuracy_test.py --demo --json results.json
```

For real inboxes (Day 2 of the work plan):

```bash
python scripts/accuracy_test.py --export labels.csv    # triage + labelling sheet
# open labels.csv and put y/n in the my_judgment column
python scripts/accuracy_test.py --score labels.csv
```

It reports **accuracy**, **precision** (how many flags were right), **recall** (how many real asks were
caught), the **missed** emails, the false alarms, and a per-account breakdown. These are the numbers for the pitch.

> Note: the offline keyword rules score near 100% on the sample data only because the samples are small and
> the rules were written alongside them. Use Claude's score on real inboxes for the pitch.

## Tests

```bash
python -m pytest
```

These are offline tests for thread keys, de-duplication, choosing the send-from address, and a full demo run.

## Project layout

```
reply_radar/
  __main__.py        CLI: python -m reply_radar
  pipeline.py        fetch -> merge -> triage -> draft -> rank
  sources/gmail.py   Gmail API (gmail.readonly)
  sources/outlook.py Microsoft Graph (Mail.Read, device-code sign-in)
  sources/mock.py    demo inboxes from data/sample_emails.json
  dedupe.py          cross-inbox thread merge + "reply from" choice
  triage.py          Claude triage + drafts (structured JSON output); offline fallback
  digest.py          ranking, Markdown + HTML digest
scripts/accuracy_test.py
tests/test_pipeline.py
data/sample_emails.json
config.demo.yaml  config.example.yaml  .env.example
```

## How the Claude calls work

- Model: `claude-opus-5-5` (change `model:` in the config).
- Emails go in batches of 15. Claude returns JSON that matches a Pydantic schema (`TriageBatch`, `DraftBatch`)
  through the SDK's structured outputs (`client.beta.messages.parse`), so there's no fragile text parsing.
- Server-side refusal fallback is on (`fallbacks="default"`). If a safety classifier declines a batch, the
  API retries it on a fallback model.
- Rough cost: one run over about 100 emails is two or three requests, a few cents.

## Privacy checklist (for the pitch)

- Read-only OAuth scopes on test accounts only
- No mail stored; the digest holds only one-line summaries and drafts
- `.env`, `config.yaml`, `secrets/` and `output/` are git-ignored
- Sensitive topics are flagged and never drafted
- Nothing is ever sent; you send every reply yourself
