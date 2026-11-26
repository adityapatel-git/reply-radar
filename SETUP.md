# Setup: the steps you do yourself

You need about 30 to 45 minutes. Do the steps in order. Steps 1 to 3 are enough for the demo. Steps 4 to 6
connect real test inboxes.

You need Python 3.10 or newer (`python --version`).

---

## 1. Put the project on GitHub

1. Unzip `reply-radar.zip` and open a terminal in the `reply-radar` folder.
2. On github.com, click **+ > New repository**. Name it `reply-radar`, choose Private or Public,
   and **don't** tick "Add a README" (the project already has one). Click **Create repository**.
3. In the terminal (the repo already has its first commit):

   ```bash
   git remote add origin https://github.com/<your-username>/reply-radar.git
   git push -u origin main
   ```

   If git asks for a password, use a GitHub **personal access token** (GitHub > Settings > Developer settings >
   Personal access tokens), or install GitHub Desktop / the `gh` CLI and run `gh auth login`.
4. Before every push, run `git status` and check that **no** `.env`, `config.yaml`, `secrets/` or
   `output/` files are listed. `.gitignore` already excludes them.

## 2. Get and store the Anthropic API key

1. Go to **console.anthropic.com**, sign in, and open **Settings > Billing**. Add a few dollars of credit
   (a demo run costs cents).
2. Open **Settings > API Keys > Create Key**. Name it `reply-radar` and copy the key (starts with `sk-ant-`).
   You only see it once.
3. In the project folder:

   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   ```

   Open `.env` and replace the placeholder:

   ```
   ANTHROPIC_API_KEY=sk-ant-...your key...
   ```

**Rules for the key**
- It lives only in `.env`, which is git-ignored. Never paste it into code, config.yaml, screenshots or the pitch.
- If it ever leaks (pushed to GitHub, shared in a chat), delete it in the Console right away and create a new one.
- Optional: set a monthly spend limit in **Settings > Limits**.

## 3. Install and run the demo

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m reply_radar --demo
python scripts/accuracy_test.py --demo
python -m pytest
```

The digest header should say `triage by claude-opus-5-5`. If it says "offline keyword rules", the key
wasn't picked up, so check that `.env` is in the project folder and has no quotes or spaces around the key.

---

## 4. Gmail: Google Cloud OAuth (read-only)

Use a **test Gmail account**, not your real one (the pitch promises this).

1. Go to **console.cloud.google.com**, then **Select a project > New project**, name it `reply-radar`, and click **Create**.
2. **APIs & Services > Library**: search **Gmail API** and click **Enable**.
3. **APIs & Services > OAuth consent screen** (or **Google Auth Platform > Branding**):
   - User type: **External**. App name: `Reply Radar`. Add your email as the support and developer contact.
   - **Data access / Scopes**: add `https://www.googleapis.com/auth/gmail.readonly` (read-only).
   - **Audience / Test users**: add every Gmail test address you'll connect. Leave the app in **Testing**.
4. **APIs & Services > Credentials > Create credentials > OAuth client ID**:
   - Application type: **Desktop app**. Name: `reply-radar-cli`. Click **Create**, then **Download JSON**.
5. Save the file as `secrets/gmail_credentials.json` in the project. One client file works for all your Gmail accounts.

On the first run a browser opens. Sign in to the test account and accept. Google shows "unverified app" for apps in
Testing: click **Continue**. The token is saved to `secrets/token_<label>.json`. Tokens for apps in Testing
expire after 7 days. If you see an `invalid_grant` error, delete that token file and run again.

## 5. Outlook: Azure app registration (Microsoft Graph, read-only)

1. Go to **portal.azure.com** (sign in with any Microsoft account; a free account is fine) and open
   **Microsoft Entra ID > App registrations > New registration**.
   - Name: `Reply Radar`.
   - Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**.
   - Redirect URI: leave empty. Click **Register**.
2. Copy the **Application (client) ID** from the Overview page. It goes in `config.yaml` as `client_id`.
3. **Authentication > Advanced settings > Allow public client flows: Yes**, then click **Save**. This is needed for
   the device-code sign-in.
4. **API permissions > Add a permission > Microsoft Graph > Delegated > `Mail.Read`**, then **Add**.
   (`User.Read` is already there. Don't add `Mail.Send` or `Mail.ReadWrite`.)
5. In `config.yaml`, set `tenant: common`. For a personal outlook.com/hotmail account you can use `tenant: consumers`.

On the first run the terminal prints a code and a link (microsoft.com/devicelogin). Open it, enter the code,
and sign in to the test account. The token cache goes to `secrets/token_<label>.json`.

**School account blocked?** Many schools don't let students consent to new apps ("Need admin approval").
If so, use a free outlook.com test account instead, or ask IT to approve `Mail.Read` for the app.

## 6. Create config.yaml and run on real inboxes

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`: your name, one entry per account (label, provider, address, tone), the Outlook `client_id`,
and any VIP senders. Then:

```bash
python -m reply_radar
```

For the work plan's Day 2 testing:

```bash
python scripts/accuracy_test.py --export labels.csv   # fill in my_judgment with y/n
python scripts/accuracy_test.py --score labels.csv --json results.json
```

Copy the accuracy, precision, recall and "missed" numbers into the pitch. Send a few emails from one account to two
of your test addresses at once to show the de-duplication.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Gmail OAuth client file not found` | Save the downloaded JSON as `secrets/gmail_credentials.json` (step 4.5) |
| `access_denied` / "app has not completed verification" | Add the Gmail address as a **Test user** (step 4.3) |
| `invalid_grant` | The token expired: delete `secrets/token_<label>.json` and run again |
| Outlook `AADSTS7000218` / public client error | Turn on **Allow public client flows** (step 5.3) |
| Outlook "Need admin approval" | Use a personal outlook.com test account (see step 5) |
| `authentication_error` from Anthropic | Check the key in `.env`, or create a new key |
| Digest says "offline keyword rules" | `ANTHROPIC_API_KEY` isn't set; check `.env` (step 2) |
