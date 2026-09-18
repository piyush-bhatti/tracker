# Applications 2027 — canonical tracker

Notion is the daily workspace. This repo is the durable base: a versioned CSV,
refreshed from Notion every night, plus a public page built from a whitelist.

```
positions.csv          canonical position list (one row per position, stable position_id)
contacts.csv           contacts backup
snapshots/             dated copies (Git history has every day anyway)
docs/index.html        public page, built nightly, served by GitHub Pages
sync_notion.py         pull / push / verify
build_site.py          positions.csv -> docs/index.html
config.json            database IDs, column ownership, public whitelist
```

## How data flows

```
 daily scan (Cowork) ──┐
 phone / desktop edits ─┼──>  Notion  ──nightly pull──>  positions.csv  ──>  docs/index.html
                        │       ^                              │
                        │       └──── push on commit ──────────┘  (identity columns only)
```

**Column ownership** (config.json → `file_owned_columns`) is the single rule:

| Owner  | Columns | Who edits |
|--------|---------|-----------|
| File   | position_id, Firm, Position, Category, Location, Type, Priority | you or Claude, in the CSV, then commit |
| Notion | everything else: Status, Deadline, Eligibility, Visa, Requirements, Info, Test Prep, Notes, Next Step, Applied On, CV Version, ... | you, the daily scan, in Notion |

`push` only ever writes file-owned columns, so nothing you or the scan set in Notion
can be overwritten. `pull` copies everything down as a backup.

## One-time setup (about 10 minutes)

1. **Create the repo.** New private GitHub repo, upload these files, default branch `main`.

2. **Notion integration token.**
   notion.so/profile/integrations → New integration → name it `tracker-bot`,
   type Internal, capabilities: read + update + insert content. Copy the secret.
   Then open the *Summer 2027 Applications HQ* page in Notion → `...` menu →
   Connections → add `tracker-bot`. (Child databases inherit access.)

3. **Add the secret.** Repo → Settings → Secrets and variables → Actions →
   New repository secret → name `NOTION_TOKEN`, value = the secret from step 2.

4. **Enable Pages.** Repo → Settings → Pages → Source: *Deploy from a branch*,
   branch `main`, folder `/docs`. Your public link will be
   `https://<your-username>.github.io/<repo-name>/`.

5. **First run.** Actions tab → *Nightly pull from Notion* → Run workflow.
   Wait ~1 minute. `positions.csv` appears, every Notion row gets a `position_id`,
   and the public page is live.

After that it runs itself at 02:00 UTC daily.

## Doing structural work (adding firms, retiering)

Edit `positions.csv` (Excel, pandas, or ask Claude), commit to `main`.
The *Push CSV identity columns to Notion* workflow creates/updates the Notion rows.
New rows need only the file-owned columns; leave `position_id` and `notion_page_id`
blank and the push assigns them.

## Running locally

```
export NOTION_TOKEN=secret_xxx
python sync_notion.py verify   # checks token + schema
python sync_notion.py pull
python build_site.py
```

## Notes

* The `Firm` property in Notion should be a **Text** field, not Select.
  Select caps at 100 options, which is what created the old Overflow database.
  Convert it once in the Notion UI (property → Edit property → Type → Text).
* The public page shows only `public_columns` from config.json and collapses
  the private pipeline Status to Open / Not yet open / Closed. Rows whose Notes
  start with "NO EU EARLY-CAREERS ROUTE FOUND" are dropped from the page.
