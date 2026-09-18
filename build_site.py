#!/usr/bin/env python3
"""
build_site.py  -  positions.csv -> docs/index.html (public page, GitHub Pages)

Only columns listed in config.json "public_columns" can appear. Everything else is
structurally excluded, so a new private column in Notion can never leak by accident.
Rows whose Notes begin with the configured exclusion prefix (no EU route) are dropped.
"""
import csv
import html
import json
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())
SRC = ROOT / "positions.csv"
OUT = ROOT / "docs" / "index.html"

PUBLIC = CFG["public_columns"]
EXCL = CFG.get("public_exclude_notes_prefix", "")


def public_status(row):
    """Collapse the private pipeline status into what an outsider needs: is it open?"""
    status = (row.get("Status") or "").strip()
    deadline = (row.get("Deadline") or "").strip()
    today = dt.date.today().isoformat()
    if deadline and deadline < today:
        return "Closed"
    if status == "Not Yet Open" or not status:
        return "Not yet open"
    return "Open"


def load_rows():
    with open(SRC, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if EXCL and (r.get("Notes") or "").startswith(EXCL):
            continue
        item = {c: (r.get(c) or "").strip() for c in PUBLIC}
        item["Open?"] = public_status(r)
        out.append(item)
    out.sort(key=lambda x: (x["Open?"] != "Open", x["Firm"], x["Position"]))
    return out


def render(rows):
    cols = ["Open?"] + PUBLIC
    data_json = json.dumps(rows, ensure_ascii=False)
    cats = sorted({r["Category"] for r in rows if r["Category"]})
    locs = sorted({r["Location"] for r in rows if r["Location"]})
    n_open = sum(1 for r in rows if r["Open?"] == "Open")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(CFG["site_title"])}</title>
<style>
  :root {{ --bg:#fff; --fg:#1a1a1a; --muted:#666; --line:#e6e6e6; --open:#0a7a3b; --closed:#9a1f1f; --wait:#8a6d00; --pill:#f2f2f2; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#111; --fg:#eee; --muted:#aaa; --line:#2a2a2a; --pill:#222; }} }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg) }}
  header {{ padding:28px 20px 12px; max-width:1200px; margin:0 auto }}
  h1 {{ margin:0 0 4px; font-size:24px }}
  .sub {{ color:var(--muted); margin:0 0 14px }}
  .controls {{ display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 }}
  .controls input, .controls select {{ font:inherit; padding:7px 10px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg) }}
  .controls input {{ flex:1; min-width:200px }}
  .count {{ color:var(--muted); font-size:13px }}
  .wrap {{ max-width:1200px; margin:0 auto; padding:0 20px 40px; overflow-x:auto }}
  table {{ width:100%; border-collapse:collapse; font-size:14px }}
  th, td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top }}
  th {{ position:sticky; top:0; background:var(--bg); cursor:pointer; user-select:none; white-space:nowrap }}
  th.sorted::after {{ content:" \\2193"; color:var(--muted) }}
  th.sorted.asc::after {{ content:" \\2191" }}
  td.info, td.prep {{ max-width:320px; color:var(--muted); font-size:13px }}
  .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; background:var(--pill); font-size:12px; white-space:nowrap }}
  .open {{ color:var(--open); font-weight:600 }} .closed {{ color:var(--closed) }} .wait {{ color:var(--wait) }}
  a {{ color:inherit }}
  footer {{ max-width:1200px; margin:0 auto; padding:0 20px 40px; color:var(--muted); font-size:13px }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(CFG["site_title"])}</h1>
  <p class="sub">{html.escape(CFG["site_subtitle"])}</p>
  <div class="controls">
    <input id="q" type="search" placeholder="Search firm, position, location...">
    <select id="fOpen"><option value="">Any status</option><option>Open</option><option>Not yet open</option><option>Closed</option></select>
    <select id="fCat"><option value="">Any category</option>{''.join(f'<option>{html.escape(c)}</option>' for c in cats)}</select>
    <select id="fLoc"><option value="">Any location</option>{''.join(f'<option>{html.escape(l)}</option>' for l in locs)}</select>
    <select id="fVisa"><option value="">Any visa</option><option>Yes</option><option>Case by case</option><option>No</option><option>Unknown</option></select>
  </div>
  <div class="count"><span id="n"></span> positions shown &middot; {n_open} currently open &middot; updated {stamp}</div>
</header>
<div class="wrap">
<table id="t">
  <thead><tr>{''.join(f'<th data-k="{html.escape(c)}">{html.escape(c)}</th>' for c in cols)}</tr></thead>
  <tbody></tbody>
</table>
</div>
<footer>
  Compiled from public careers pages; verify eligibility and dates on the firm's own posting before applying. Nothing here is affiliated with any listed firm.
</footer>
<script>
const COLS = {json.dumps(cols)};
const DATA = {data_json};
let sortKey = "Open?", asc = true;
const $ = id => document.getElementById(id);
function cell(k, v) {{
  if (k === "Open?") return `<span class="${{v==="Open"?"open":v==="Closed"?"closed":"wait"}}">${{v}}</span>`;
  if (k === "Portal Link") return v ? `<a href="${{v}}" target="_blank" rel="noopener">Apply &rarr;</a>` : "";
  if (k === "Application Requirements") return v.split(";").filter(Boolean).map(x=>`<span class="pill">${{x.trim()}}</span>`).join(" ");
  if (k === "Category" || k === "Type" || k === "Visa Sponsorship" || k === "Eligibility") return v ? `<span class="pill">${{v}}</span>` : "";
  return v.replace(/&/g,"&amp;").replace(/</g,"&lt;");
}}
function render() {{
  const q = $("q").value.toLowerCase(), fo=$("fOpen").value, fc=$("fCat").value, fl=$("fLoc").value, fv=$("fVisa").value;
  let rows = DATA.filter(r =>
    (!fo || r["Open?"]===fo) && (!fc || r["Category"]===fc) && (!fl || r["Location"]===fl) && (!fv || r["Visa Sponsorship"]===fv) &&
    (!q || Object.values(r).join(" ").toLowerCase().includes(q)));
    const RANK = {"Open":0, "Not yet open":1, "Closed":2};
    const RANK = {{"Open":0, "Not yet open":1, "Closed":2}};
  rows.sort((a,b)=>{{
    let x=a[sortKey]||"", y=b[sortKey]||"";
    if (sortKey==="Open?") {{ x=RANK[x]??9; y=RANK[y]??9; if (x===y) {{ x=a["Deadline"]||"9999"; y=b["Deadline"]||"9999"; }} }}
    return (x<y?-1:x>y?1:0)*(asc?1:-1);
  }}); return (x<y?-1:x>y?1:0)*(asc?1:-1); }});
  $("t").querySelector("tbody").innerHTML = rows.map(r =>
    "<tr>"+COLS.map(k=>`<td class="${{k==="Info"?"info":k==="Test Prep"?"prep":""}}">${{cell(k, r[k]||"")}}</td>`).join("")+"</tr>").join("");
  $("n").textContent = rows.length;
  document.querySelectorAll("th").forEach(th=>{{ th.classList.toggle("sorted", th.dataset.k===sortKey); th.classList.toggle("asc", th.dataset.k===sortKey && asc); }});
}}
document.querySelectorAll("th").forEach(th=>th.onclick=()=>{{ if(sortKey===th.dataset.k) asc=!asc; else {{sortKey=th.dataset.k; asc=true;}} render(); }});
["q","fOpen","fCat","fLoc","fVisa"].forEach(id=>$(id).oninput=render);
render();
</script>
</body>
</html>"""


if __name__ == "__main__":
    rows = load_rows()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(rows), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(rows)} public rows")
