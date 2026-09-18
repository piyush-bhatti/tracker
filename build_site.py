#!/usr/bin/env python3
"""
build_site.py  -  positions.csv -> docs/index.html (public page, GitHub Pages)

trackr-style table: logo, firm and role, countdown, requirement badges, expandable info. Only columns listed in config.json "public_columns"
can appear; anything else is structurally excluded. Rows whose Notes begin with the
configured exclusion prefix (no EU route) are dropped.

Plain template with __TOKENS__ replaced at the end (no f-string), so braces in
CSS/JS never need escaping.
"""
import csv
import html
import json
import re
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())
SRC = ROOT / "positions.csv"
OUT = ROOT / "docs" / "index.html"

PUBLIC = CFG["public_columns"]
EXCL = CFG.get("public_exclude_notes_prefix", "")
TODAY = dt.date.today()

# Tabs: order and label. Categories not listed fall into "Other".
TABS = [
    ("Bulge Bracket Markets", "Banks"),
    ("Prop / Market Making", "Prop & market making"),
    ("Systematic / Quant Fund", "Quant funds"),
    ("Structured Products", "Structured products"),
    ("Commodities", "Commodities"),
    ("Trading Tech / Quant Dev", "Trading tech"),
    ("Advisory / IBD", "Advisory"),
]


def public_status(row):
    status = (row.get("Status") or "").strip()
    deadline = (row.get("Deadline") or "").strip()
    if deadline and deadline < TODAY.isoformat():
        return "closed"
    if status == "Not Yet Open" or not status:
        return "upcoming"
    return "open"


def days_left(deadline):
    try:
        return (dt.date.fromisoformat(deadline[:10]) - TODAY).days
    except Exception:
        return None


def domain_of(url):
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    host = re.sub(r"^www\.", "", host)
    # Collapse ATS / job-board hosts to the firm's own domain where obvious.
    for ats in ("myworkdayjobs.com", "greenhouse.io", "lever.co", "smartrecruiters.com",
                "oraclecloud.com", "successfactors.com", "icims.com", "taleo.net", "workable.com",
                "ashbyhq.com", "teamtailor.com", "avature.net", "eightfold.ai"):
        if host.endswith(ats):
            return ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[0] in ("careers", "jobs", "career", "campus", "apply", "recruiting", "join", "search"):
        host = ".".join(parts[1:])
    return host


def load_rows():
    with open(SRC, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if EXCL and (r.get("Notes") or "").startswith(EXCL):
            continue
        item = {c: (r.get(c) or "").strip() for c in PUBLIC}
        item["status"] = public_status(r)
        item["days"] = days_left(item.get("Deadline", ""))
        item["domain"] = domain_of(item.get("Portal Link", ""))
        item["opens"] = (r.get("Opens (est.)") or "").strip()[:40]
        out.append(item)
    return out


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#FFFFFF; --ink:#000000; --ink-2:#333333; --grey:#6E6E6E; --rule:#D9D9D9; --rule-2:#000000;
    --accent:#1A1AFF; --accent-ink:#FFFFFF; --alert:#E0261C; --alert-bg:#FFF1F0; --band:#F5F5F5; --focus:#1A1AFF;
  }
  @media (prefers-color-scheme: dark){
    :root{ --paper:#000000; --ink:#FFFFFF; --ink-2:#D0D0D0; --grey:#9A9A9A; --rule:#2A2A2A; --rule-2:#FFFFFF;
           --accent:#5C5CFF; --alert:#FF5A4F; --alert-bg:#2A0F0D; --band:#111111; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 Archivo,"Helvetica Neue",Helvetica,Arial,sans-serif;font-variant-numeric:tabular-nums}
  a{color:inherit} button{font:inherit;color:inherit}
  :focus-visible{outline:2px solid var(--focus);outline-offset:2px}

  .top{background:var(--accent);color:var(--accent-ink)}
  .top .in{max-width:1400px;margin:0 auto;padding:28px 24px 0}
  .head{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end;justify-content:space-between}
  h1{margin:0;font-size:34px;font-weight:700;letter-spacing:-0.03em;line-height:1;max-width:22ch}
  .sub{margin:10px 0 0;max-width:64ch;font-size:14px;opacity:.85}
  .counts{display:flex;gap:26px;font-size:13px;opacity:.9}
  .counts b{display:block;font-size:26px;font-weight:600;letter-spacing:-0.02em;line-height:1;margin-bottom:3px}
  .counts .soon b{color:#FFD54A}
  .tabs{display:flex;gap:0;overflow-x:auto;margin-top:22px;scrollbar-width:none;border-top:1px solid rgba(255,255,255,.35)}
  .tabs::-webkit-scrollbar{display:none}
  .tab{border:none;background:none;color:inherit;padding:11px 14px 11px 0;margin-right:14px;border-top:2px solid transparent;margin-top:-1px;font-weight:500;white-space:nowrap;cursor:pointer;opacity:.8}
  .tab[aria-selected="true"]{opacity:1;border-top-color:#fff;font-weight:600}
  .tab small{opacity:.7;margin-left:5px}

  .tools{position:sticky;top:0;z-index:6;background:var(--paper);border-bottom:2px solid var(--rule-2)}
  .tools .in{max-width:1400px;margin:0 auto;padding:10px 24px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .tools input,.tools select{font:inherit;font-size:13.5px;padding:7px 10px;border:1px solid var(--ink);border-radius:0;background:var(--paper);color:var(--ink);min-height:36px}
  .tools input{flex:1 1 220px}
  .tools .tog{display:inline-flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;user-select:none;padding:0 4px;color:var(--ink-2)}
  .tools .n{margin-left:auto;color:var(--grey);font-size:13px;white-space:nowrap}

  .wrap{max-width:1400px;margin:0 auto;padding:0 24px 64px;overflow-x:auto}
  table{width:100%;min-width:1080px;border-collapse:collapse}
  thead th{position:sticky;top:57px;z-index:4;text-align:left;font-weight:500;font-size:12.5px;color:var(--grey);padding:12px 10px 8px;background:var(--paper);border-bottom:1px solid var(--rule-2);cursor:pointer;user-select:none;white-space:nowrap}
  thead th.on{color:var(--ink);font-weight:600}
  thead th.on::after{content:" \2193";font-size:11px}
  thead th.on.asc::after{content:" \2191"}
  tbody td{padding:10px 10px;border-bottom:1px solid var(--rule);vertical-align:middle}
  tr.sect td{background:var(--paper);color:var(--ink);font-size:13px;font-weight:600;padding:22px 10px 6px;border-bottom:1px solid var(--rule-2)}
  tr.r.closed td{color:var(--grey)}
  tr.r.soon td{background:var(--alert-bg)}

  .logo{width:30px;height:30px;border:1px solid var(--rule);background:#fff;display:grid;place-items:center;overflow:hidden}
  .logo img{width:100%;height:100%;object-fit:contain;padding:3px}
  .logo .ltr{font-weight:700;font-size:13px;color:var(--ink);background:var(--band);width:100%;height:100%;display:grid;place-items:center}
  @media (prefers-color-scheme: dark){ .logo .ltr{color:#fff} }
  td.firm b{display:block;font-weight:600;line-height:1.25}
  td.firm span{display:block;color:var(--grey);font-size:13px;line-height:1.3;max-width:40ch}
  td.loc,td.dl{white-space:nowrap}
  td.dl small{display:block;color:var(--grey);font-size:12px}
  tr.soon td.dl small{color:var(--alert);font-weight:600}

  .pill{display:inline-flex;align-items:center;gap:7px;font-weight:500;font-size:13px;white-space:nowrap}
  .pill::before{content:"";width:8px;height:8px;background:currentColor;display:inline-block}
  .pill.open{color:var(--ink)}
  .pill.soon{color:var(--alert);font-weight:600}
  .pill.upcoming{color:var(--grey)}
  .pill.closed{color:var(--grey)} .pill.closed::before{background:none;border:1px solid currentColor;width:6px;height:6px}

  .chip{display:inline-block;font-size:11.5px;padding:2px 6px;border:1px solid var(--ink-2);color:var(--ink-2);white-space:nowrap;margin:1px 4px 1px 0}
  .chip.need{border-color:var(--ink);color:var(--ink);font-weight:500}
  tr.closed .chip{border-color:var(--rule);color:var(--grey)}

  .apply{display:inline-block;padding:6px 12px;background:var(--ink);color:var(--paper);text-decoration:none;font-weight:600;font-size:12.5px;white-space:nowrap}
  .apply:hover{background:var(--accent);color:#fff}
  tr.closed .apply,tr.upcoming .apply{background:none;color:var(--ink);border:1px solid var(--ink);padding:5px 11px}
  tr.closed .apply{color:var(--grey);border-color:var(--rule)}
  .btn{background:none;border:none;border-bottom:1px solid var(--rule-2);padding:4px 0;margin-left:14px;font-size:12.5px;cursor:pointer;white-space:nowrap}
  .btn[aria-expanded="true"]{color:var(--accent);border-bottom-color:var(--accent)}
  .btn:disabled{opacity:.3;cursor:default;border-bottom-color:transparent}
  tr.detail td{background:var(--band);padding:12px 14px 14px 56px;border-bottom:1px solid var(--rule)}
  tr.detail .box{display:grid;grid-template-columns:1fr 1fr;gap:28px;font-size:13.5px;max-width:1000px}
  tr.detail h4{margin:0 0 3px;font-size:12px;color:var(--grey);font-weight:500}
  tr.detail p{margin:0;max-width:70ch}
  .empty{padding:60px 24px;text-align:center;color:var(--grey)}
  footer{max-width:1400px;margin:0 auto;padding:0 24px 40px;color:var(--grey);font-size:12.5px;border-top:1px solid var(--rule-2);padding-top:14px}
  @media (max-width:700px){ thead th{top:0} .tools{position:static} h1{font-size:26px} }
</style>
</head>
<body>
<header class="top"><div class="in">
  <div class="head">
    <div><h1>__TITLE__</h1><p class="sub">__SUBTITLE__</p></div>
    <div class="counts"><span><b>__N_OPEN__</b> open</span><span class="soon"><b>__N_SOON__</b> close this week</span><span><b>__N_FIRMS__</b> firms</span></div>
  </div>
  <div class="tabs" role="tablist" id="tabs"></div>
</div></header>

<div class="tools"><div class="in">
  <input id="q" type="search" placeholder="Search firm, role, city" aria-label="Search">
  <select id="fLoc" aria-label="Location"><option value="">All locations</option>__LOCS__</select>
  <select id="fType" aria-label="Type"><option value="">Summer and graduate</option><option>Summer</option><option>Graduate</option><option>Off-cycle</option></select>
  <select id="fCoh" aria-label="Who can apply"><option value="">Anyone</option>__COHS__</select>
  <select id="fVisa" aria-label="Visa"><option value="">Any visa policy</option><option>Yes</option><option>Case by case</option><option>Unknown</option><option>No</option></select>
  <label class="tog"><input id="showUp" type="checkbox" checked> Not yet open</label>
  <label class="tog"><input id="showClosed" type="checkbox"> Closed</label>
  <span class="n"><span id="n"></span> programmes</span>
</div></div>

<main class="wrap">
  <table id="t">
    <thead><tr>
      <th style="width:44px"></th>
      <th data-k="Firm">Firm and role</th>
      <th data-k="Location">Location</th>
      <th data-k="Type">Type</th>
      <th data-k="status">Status</th>
      <th data-k="Deadline">Deadline</th>
      <th data-k="Application Requirements">Needs</th>
      <th data-k="Cohort Requirement">Who can apply</th>
      <th data-k="Visa Sponsorship">Visa</th>
      <th></th>
    </tr></thead>
    <tbody></tbody>
  </table>
  <div id="empty" class="empty" hidden>Nothing matches. Clear a filter, or tick "Closed" to include past deadlines.</div>
</main>
<footer>Compiled from firms' public careers pages, refreshed nightly (last build __STAMP__). Check the posting before applying; requirements and dates change. Logos belong to their owners. Not affiliated with any listed firm.</footer>

<script>
const DATA = __DATA__;
const TABS = __TABS__;
const RANK = {soon:0, open:1, upcoming:2, closed:3};
const SECT = {soon:"Closing within 7 days", open:"Open", upcoming:"Not yet open", closed:"Closed"};
let tab = "", sortKey = "status", asc = true;
const $ = id => document.getElementById(id);
const esc = s => String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const bucket = r => r.status==="open" && r.days!==null && r.days<=7 ? "soon" : r.status;

function logo(r){
  const ltr = '<span class="ltr">'+esc((r.Firm||"?").trim()[0].toUpperCase())+'</span>';
  if (!r.domain) return '<div class="logo">'+ltr+'</div>';
  return '<div class="logo"><img src="https://www.google.com/s2/favicons?domain='+esc(r.domain)+'&sz=64" alt="" loading="lazy" onerror="this.parentNode.innerHTML=\''+ltr.replace(/'/g,"&#39;")+'\'"></div>';
}
function pill(r){
  const b = bucket(r);
  if (b==="closed") return '<span class="pill closed">Closed</span>';
  if (b==="upcoming") return '<span class="pill upcoming">Not yet open</span>';
  if (b==="soon") return '<span class="pill soon">Closing soon</span>';
  return '<span class="pill open">'+(r.Deadline?"Open":"Open, rolling")+'</span>';
}
function dl(r){
  if (r.status==="upcoming") return '<td class="dl">'+(r.opens?'<small>expected '+esc(r.opens)+'</small>':'')+'</td>';
  if (!r.Deadline) return '<td class="dl"><span style="color:var(--muted)">Rolling</span></td>';
  const d=new Date(r.Deadline+"T00:00:00"), txt=d.toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"});
  const sub = r.days===null?"": r.days<0?"closed": r.days===0?"today": r.days===1?"tomorrow":"in "+r.days+" days";
  return '<td class="dl">'+txt+(sub?'<small>'+sub+'</small>':'')+'</td>';
}
function needs(v){
  const S={"Cover Letter (optional)":"Cover optional","Video Interview":"Video","Online Test":"Test","Cover Letter":"Cover"};
  return String(v||"").split(";").map(s=>s.trim()).filter(Boolean).map(s=>'<span class="chip need">'+esc(S[s]||s)+'</span>').join("");
}
function row(r,i){
  const b = bucket(r), hasInfo=!!r.Info, hasPrep=!!r["Test Prep"];
  return '<tr class="r '+r.status+(b==="soon"?" soon":"")+'">'+
    '<td>'+logo(r)+'</td>'+
    '<td class="firm"><b>'+esc(r.Firm)+'</b><span>'+esc(r.Position)+'</span></td>'+
    '<td class="loc">'+esc(r.Location)+'</td>'+
    '<td>'+esc(r.Type)+'</td>'+
    '<td>'+pill(r)+'</td>'+
    dl(r)+
    '<td>'+needs(r["Application Requirements"])+'</td>'+
    '<td>'+(r["Cohort Requirement"]?'<span class="chip">'+esc(r["Cohort Requirement"].replace(" / recent graduates OK","").replace(" (see Info)",""))+'</span>':'')+'</td>'+
    '<td>'+(r["Visa Sponsorship"]?'<span class="chip">'+esc(r["Visa Sponsorship"])+'</span>':'')+'</td>'+
    '<td style="white-space:nowrap;text-align:right">'+
      (r["Portal Link"]?'<a class="apply" href="'+esc(r["Portal Link"])+'" target="_blank" rel="noopener">'+(r.status==="upcoming"?"Careers":"Apply")+'</a>':'')+
      '<button class="btn" data-p="info-'+i+'" aria-expanded="false"'+(hasInfo?'':' disabled')+'>Info</button>'+
      '<button class="btn" data-p="prep-'+i+'" aria-expanded="false"'+(hasPrep?'':' disabled')+'>Test prep</button>'+
    '</td></tr>'+
    (hasInfo||hasPrep ? '<tr class="detail" id="d-'+i+'" hidden><td colspan="10"><div class="box">'+
      (hasInfo?'<div id="info-'+i+'"><h4>About the programme</h4><p>'+esc(r.Info)+'</p></div>':'')+
      (hasPrep?'<div id="prep-'+i+'"><h4>Assessments and prep</h4><p>'+esc(r["Test Prep"])+'</p></div>':'')+
    '</div></td></tr>' : '');
}
function counts(){ const c={}; DATA.forEach(r=>{const k=r.Category||"Other"; c[k]=(c[k]||0)+(r.status!=="closed"?1:0);}); return c; }
function renderTabs(){
  const c=counts(), total=Object.values(c).reduce((a,b)=>a+b,0);
  const all=[["","All",total]].concat(TABS.filter(t=>c[t[0]]).map(t=>[t[0],t[1],c[t[0]]]));
  if (c["Other"]) all.push(["Other","Other",c["Other"]]);
  $("tabs").innerHTML=all.map(t=>'<button class="tab" role="tab" data-t="'+esc(t[0])+'" aria-selected="'+(tab===t[0])+'">'+esc(t[1])+'<small>'+t[2]+'</small></button>').join("");
  $("tabs").querySelectorAll(".tab").forEach(b=>b.onclick=()=>{tab=b.dataset.t; renderTabs(); render();});
}
function sortVal(r,k){
  if (k==="status") return [RANK[bucket(r)], r.Deadline||"9999-12-31", r.Firm];
  if (k==="Deadline") return [r.Deadline||"9999-12-31", r.Firm];
  return [String(r[k]||"").toLowerCase(), r.Firm];
}
function cmp(a,b){ for(let i=0;i<a.length;i++){ if(a[i]<b[i]) return -1; if(a[i]>b[i]) return 1;} return 0; }
function render(){
  const q=$("q").value.toLowerCase(), fl=$("fLoc").value, ft=$("fType").value, fh=$("fCoh").value, fv=$("fVisa").value, up=$("showUp").checked, cl=$("showClosed").checked;
  let rows=DATA.filter(r=>
    (!tab||(r.Category||"Other")===tab) && (up||r.status!=="upcoming") && (cl||r.status!=="closed") &&
    (!fl||r.Location===fl) && (!ft||r.Type===ft) && (!fh||r["Cohort Requirement"]===fh) && (!fv||r["Visa Sponsorship"]===fv) &&
    (!q||(r.Firm+" "+r.Position+" "+r.Location+" "+r.Info).toLowerCase().includes(q)));
  rows.sort((a,b)=>cmp(sortVal(a,sortKey),sortVal(b,sortKey))*(asc?1:-1));
  let html="", last=null;
  rows.forEach((r,i)=>{
    if (sortKey==="status"){ const b=bucket(r); if (b!==last){ html+='<tr class="sect"><td colspan="10">'+SECT[b]+'</td></tr>'; last=b; } }
    html+=row(r,i);
  });
  $("t").querySelector("tbody").innerHTML=html;
  $("n").textContent=rows.length; $("empty").hidden=rows.length>0; $("t").hidden=rows.length===0;
  document.querySelectorAll("thead th[data-k]").forEach(th=>{th.classList.toggle("on",th.dataset.k===sortKey); th.classList.toggle("asc",th.dataset.k===sortKey&&asc);});
  document.querySelectorAll(".btn[data-p]").forEach(b=>b.onclick=()=>{
    const i=b.dataset.p.split("-")[1], d=$("d-"+i), open=b.getAttribute("aria-expanded")==="true";
    const tr=b.closest("tr"); tr.querySelectorAll(".btn[data-p]").forEach(o=>o.setAttribute("aria-expanded","false"));
    if(open){ d.hidden=true; return; }
    b.setAttribute("aria-expanded","true"); d.hidden=false;
    const target=$(b.dataset.p); if(target) target.scrollIntoView({block:"nearest"});
  });
}
document.querySelectorAll("thead th[data-k]").forEach(th=>th.onclick=()=>{ if(sortKey===th.dataset.k) asc=!asc; else {sortKey=th.dataset.k; asc=true;} render(); });
["q","fLoc","fType","fCoh","fVisa","showUp","showClosed"].forEach(id=>$(id).oninput=render);
renderTabs(); render();
</script>
</body>
</html>"""


def render(rows):
    locs = sorted({r["Location"] for r in rows if r.get("Location")})
    cohs = [c for c in ["Final year / recent graduates OK", "Not stated - ask the firm", "Penultimate year only",
                        "PhD only", "Right-to-work restriction (see Info)", "Language requirement (see Info)", "Unverified"]
            if any(r.get("Cohort Requirement") == c for r in rows)]
    opts = lambda xs: "".join(f"<option>{html.escape(x)}</option>" for x in xs)
    n_open = sum(1 for r in rows if r["status"] == "open")
    n_soon = sum(1 for r in rows if r["status"] == "open" and r["days"] is not None and 0 <= r["days"] <= 7)
    n_firms = len({r["Firm"] for r in rows if r.get("Firm")})
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%-d %b %Y, %H:%M UTC")
    return (TEMPLATE
            .replace("__TITLE__", html.escape(CFG["site_title"]))
            .replace("__SUBTITLE__", html.escape(CFG["site_subtitle"]))
            .replace("__N_OPEN__", str(n_open)).replace("__N_SOON__", str(n_soon)).replace("__N_FIRMS__", str(n_firms))
            .replace("__LOCS__", opts(locs)).replace("__COHS__", opts(cohs))
            .replace("__STAMP__", stamp)
            .replace("__TABS__", json.dumps(TABS))
            .replace("__DATA__", json.dumps(rows, ensure_ascii=False)))


if __name__ == "__main__":
    rows = load_rows()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(rows), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(rows)} public rows")
