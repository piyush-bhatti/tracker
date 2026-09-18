#!/usr/bin/env python3
"""
sync_notion.py  -  canonical CSV  <->  Notion

    python sync_notion.py pull     Notion -> positions.csv + contacts.csv (+ dated snapshot)
                                   Assigns a position_id to any Notion row that lacks one.
    python sync_notion.py push     positions.csv -> Notion, FILE-OWNED columns only.
                                   Creates Notion rows for CSV rows with no notion_page_id.
    python sync_notion.py verify   Read-only sanity check: token, database access, schema.

Ownership rule (enforced here, configured in config.json):
  * file_owned_columns are the ONLY columns push ever writes.
  * Everything else (Status, Deadline, Notes, Eligibility, ...) is Notion-owned:
    it flows Notion -> CSV on pull and is never written back.
  So a Notion edit or a daily-scan update can never be overwritten by a push.

Requires env var NOTION_TOKEN (an internal-integration token shared with the databases).
"""
import csv
import json
import os
import sys
import time
import uuid
import datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())
POSITIONS_CSV = ROOT / "positions.csv"
CONTACTS_CSV = ROOT / "contacts.csv"
SNAP_DIR = ROOT / "snapshots"

API = "https://api.notion.com/v1"
TOKEN = os.environ.get("NOTION_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": CFG["notion_version"],
    "Content-Type": "application/json",
}

META_COLS = ["notion_page_id", "notion_url", "last_edited_time"]


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _req(method, path, **kw):
    for attempt in range(5):
        r = requests.request(method, f"{API}{path}", headers=HEADERS, timeout=60, **kw)
        if r.status_code == 429:
            wait = float(r.headers.get("Retry-After", 2))
            time.sleep(wait)
            continue
        if r.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        if not r.ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        return r.json()
    raise RuntimeError(f"{method} {path}: gave up after retries")


def db_schema(db_id):
    return _req("GET", f"/databases/{db_id}")["properties"]


def db_query_all(db_id):
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _req("POST", f"/databases/{db_id}/query", json=body)
        pages.extend(data["results"])
        if not data.get("has_more"):
            return pages
        cursor = data["next_cursor"]
        time.sleep(0.34)  # stay under 3 req/s


# --------------------------------------------------------------------------- #
# Property <-> plain value
# --------------------------------------------------------------------------- #
def _plain(rt):
    return "".join(t.get("plain_text", "") for t in (rt or []))


def prop_to_value(p):
    t = p["type"]
    if t == "title":
        return _plain(p["title"])
    if t == "rich_text":
        return _plain(p["rich_text"])
    if t == "select":
        return (p["select"] or {}).get("name", "")
    if t == "status":
        return (p["status"] or {}).get("name", "")
    if t == "multi_select":
        return "; ".join(o["name"] for o in p["multi_select"])
    if t == "date":
        return (p["date"] or {}).get("start", "") or ""
    if t == "url":
        return p["url"] or ""
    if t == "checkbox":
        return "yes" if p["checkbox"] else "no"
    if t == "number":
        return "" if p["number"] is None else str(p["number"])
    if t == "email":
        return p["email"] or ""
    if t == "phone_number":
        return p["phone_number"] or ""
    if t in ("created_time", "last_edited_time"):
        return p[t]
    if t == "formula":
        f = p["formula"]
        return str(f.get(f["type"], ""))
    return ""


def value_to_prop(schema_prop, value):
    """Build a Notion property payload from a CSV string, based on the live schema type."""
    t = schema_prop["type"]
    value = "" if value is None else str(value).strip()
    if t == "title":
        return {"title": [{"text": {"content": value}}]}
    if t == "rich_text":
        return {"rich_text": [{"text": {"content": value}}] if value else []}
    if t == "select":
        return {"select": {"name": value} if value else None}
    if t == "status":
        return {"status": {"name": value} if value else None}
    if t == "multi_select":
        names = [v.strip() for v in value.split(";") if v.strip()]
        return {"multi_select": [{"name": n} for n in names]}
    if t == "date":
        return {"date": {"start": value} if value else None}
    if t == "url":
        return {"url": value or None}
    if t == "checkbox":
        return {"checkbox": value.lower() in ("yes", "true", "1", "__yes__")}
    if t == "number":
        return {"number": float(value) if value else None}
    raise ValueError(f"Unsupported property type for push: {t}")


def page_to_row(page, columns):
    row = {c: "" for c in columns}
    for name, p in page["properties"].items():
        if name in row:
            row[name] = prop_to_value(p)
    row["notion_page_id"] = page["id"]
    row["notion_url"] = page["url"]
    row["last_edited_time"] = page["last_edited_time"]
    return row


# --------------------------------------------------------------------------- #
# CSV helpers
# --------------------------------------------------------------------------- #
def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path):
    if not path.exists():
        return [], []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), list(r.fieldnames or [])


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_verify():
    if not TOKEN:
        sys.exit("NOTION_TOKEN is not set.")
    for label, key in (("positions", "positions_database_id"), ("contacts", "contacts_database_id")):
        db_id = CFG[key]
        schema = db_schema(db_id)
        print(f"[ok] {label}: {len(schema)} properties -> {', '.join(sorted(schema))}")
    missing = [c for c in CFG["file_owned_columns"] if c not in db_schema(CFG["positions_database_id"])]
    if missing:
        print(f"[warn] file-owned columns missing from Notion: {missing}")
    print("verify complete")


def cmd_pull():
    if not TOKEN:
        sys.exit("NOTION_TOKEN is not set.")

    # ---- positions ----
    db_id = CFG["positions_database_id"]
    schema = db_schema(db_id)
    pages = db_query_all(db_id)
    print(f"pulled {len(pages)} position rows")

    # Column order: file-owned first (stable identity), then everything else alphabetically, then meta.
    file_owned = [c for c in CFG["file_owned_columns"] if c in schema]
    others = sorted(c for c in schema if c not in file_owned)
    columns = file_owned + others + META_COLS

    rows = [page_to_row(p, columns) for p in pages]

    # Assign position_id to any row lacking one, and write it back to Notion.
    assigned = 0
    if "position_id" in schema:
        for row in rows:
            if not row["position_id"]:
                pid = "pos_" + uuid.uuid4().hex[:10]
                _req("PATCH", f"/pages/{row['notion_page_id']}",
                     json={"properties": {"position_id": value_to_prop(schema["position_id"], pid)}})
                row["position_id"] = pid
                assigned += 1
                time.sleep(0.34)
        if assigned:
            print(f"assigned position_id to {assigned} rows")

    rows.sort(key=lambda r: (r.get("Firm", ""), r.get("Position", "")))
    write_csv(POSITIONS_CSV, rows, columns)
    print(f"wrote {POSITIONS_CSV.name} ({len(rows)} rows, {len(columns)} columns)")

    # ---- contacts ----
    cdb = CFG["contacts_database_id"]
    cschema = db_schema(cdb)
    cpages = db_query_all(cdb)
    ccols = sorted(cschema) + META_COLS
    crows = [page_to_row(p, ccols) for p in cpages]
    write_csv(CONTACTS_CSV, crows, ccols)
    print(f"wrote {CONTACTS_CSV.name} ({len(crows)} rows)")

    # ---- dated snapshot (Git history has every day; this is a convenience copy) ----
    SNAP_DIR.mkdir(exist_ok=True)
    stamp = dt.date.today().isoformat()
    write_csv(SNAP_DIR / f"positions_{stamp}.csv", rows, columns)
    print(f"snapshot -> snapshots/positions_{stamp}.csv")


def cmd_push():
    if not TOKEN:
        sys.exit("NOTION_TOKEN is not set.")
    rows, _ = read_csv(POSITIONS_CSV)
    if not rows:
        sys.exit("positions.csv is empty or missing; run pull first.")

    db_id = CFG["positions_database_id"]
    schema = db_schema(db_id)
    file_owned = [c for c in CFG["file_owned_columns"] if c in schema]

    # Map existing Notion rows by position_id so we match on the stable key, never by name.
    live = db_query_all(db_id)
    by_pid = {}
    for p in live:
        pid = prop_to_value(p["properties"].get("position_id", {"type": "rich_text", "rich_text": []}))
        if pid:
            by_pid[pid] = p

    updated = created = skipped = 0
    for row in rows:
        pid = row.get("position_id", "").strip()
        props = {c: value_to_prop(schema[c], row.get(c, "")) for c in file_owned if c != "position_id"}

        if pid and pid in by_pid:
            page = by_pid[pid]
            current = {c: prop_to_value(page["properties"][c]) for c in props}
            wanted = {c: (row.get(c, "") or "").strip() for c in props}
            if all(current[c] == wanted[c] for c in props):
                skipped += 1
                continue
            _req("PATCH", f"/pages/{page['id']}", json={"properties": props})
            updated += 1
        else:
            # New row: create with identity columns + safe defaults for Notion-owned fields.
            if not pid:
                pid = "pos_" + uuid.uuid4().hex[:10]
                row["position_id"] = pid
            props["position_id"] = value_to_prop(schema["position_id"], pid)
            if "Status" in schema and "Status" not in props:
                props["Status"] = value_to_prop(schema["Status"], "Not Yet Open")
            if "Eligibility" in schema:
                props["Eligibility"] = value_to_prop(schema["Eligibility"], "Unverified")
            if "Visa Sponsorship" in schema:
                props["Visa Sponsorship"] = value_to_prop(schema["Visa Sponsorship"], "Unknown")
            _req("POST", "/pages", json={"parent": {"database_id": db_id}, "properties": props})
            created += 1
        time.sleep(0.34)

    print(f"push complete: {updated} updated, {created} created, {skipped} unchanged")
    if created:
        # Persist any position_ids we generated for new rows.
        _, cols = read_csv(POSITIONS_CSV)
        write_csv(POSITIONS_CSV, rows, cols)
        print("positions.csv updated with new position_ids (commit this)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"pull": cmd_pull, "push": cmd_push, "verify": cmd_verify}.get(
        cmd, lambda: sys.exit(__doc__)
    )()
