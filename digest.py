#!/usr/bin/env python3
"""Weekly literature digest.

Finds new papers on PubMed, bioRxiv and medRxiv for your keywords and the
researchers you follow, plus Bluesky posts, and sends them to you by email once
a week (or whenever you run it).

Uses only the Python standard library (Python 3.11 or newer).

    python3 digest.py              run now; email it if email notifications are on
    python3 digest.py --dry-run    preview only: writes preview.html, sends nothing, saves nothing
    python3 digest.py --scheduled  run only if the day and time in settings.toml have come round

Secrets come from environment variables (or a .env file next to this script):
    EMAIL_ADDRESS, EMAIL_APP_PASSWORD   the account that sends the digest
    EMAIL_TO                            optional; where to send it (default: EMAIL_ADDRESS)
    SMTP_HOST, SMTP_PORT                optional; default smtp.gmail.com and 465
    ANTHROPIC_API_KEY                   optional; only for AI summaries
    NCBI_API_KEY                        optional; faster PubMed access
    BLUESKY_HANDLE, BLUESKY_APP_PASSWORD optional; only for Bluesky keyword search
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import smtplib
import ssl
import sys
import time
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

ROOT = Path(__file__).resolve().parent
USER_AGENT = "weekly-literature-digest/1.0 (+https://github.com/RajatJoshi15/weekly-literature-digest)"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PREPRINT_API = "https://api.biorxiv.org/details"
BSKY_PUBLIC = "https://public.api.bsky.app/xrpc"
BSKY_AUTH = "https://bsky.social/xrpc"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
GENERIC_TYPES = {"journal article", "research support, non-u.s. gov't", "research support, n.i.h., extramural",
                 "research support, u.s. gov't, non-p.h.s.", "research support, n.i.h., intramural",
                 "research support, u.s. gov't, p.h.s.", "english abstract", "comment", "news"}
SUMMARY_LABELS = ["Aim", "Methods", "Results", "Discussion", "Caveats"]

DEFAULTS: dict = {
    "digest": {"title": "Weekly literature digest", "lookback_days": 7, "max_papers_per_topic": 10,
               "max_papers_per_combination": 25, "max_papers_per_researcher": 10,
               "include_abstracts": True, "sources": ["pubmed", "biorxiv", "medrxiv", "bluesky"]},
    "email": {"notifications": True, "day": "Monday", "time": "09:00", "timezone": "UTC"},
    "ai": {"summaries": False, "model": "claude-haiku-5-5", "max_papers": 40},
    "preprints": {"biorxiv_categories": [], "medrxiv_categories": [], "max_pages": 60},
    "bluesky": {"researcher_posts": True, "keyword_search": False, "max_posts_per_topic": 5,
                "only_posts_with_links": True, "max_keywords_per_topic": 5},
    "topics": [], "combinations": [], "researchers": [],
}

# --------------------------------------------------------------------------- helpers


def log(msg: str) -> None:
    print(msg, flush=True)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch(url: str, *, form: dict | None = None, data: dict | None = None,
          headers: dict | None = None, timeout: int = 60, retries: int = 3) -> bytes:
    """GET (or POST when form/data is given) with retries on transient errors."""
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def deep_merge(base: dict, extra: dict) -> dict:
    out = json.loads(json.dumps(base))
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_settings(path: Path) -> dict:
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    settings = deep_merge(DEFAULTS, raw)
    for topic in settings["topics"]:
        topic.setdefault("exclude", [])
        if not topic.get("name") or not topic.get("keywords"):
            raise SystemExit("Each [[topics]] entry needs a name and at least one keyword.")
    names = {t["name"] for t in settings["topics"]}
    for combo in settings["combinations"]:
        missing = [t for t in combo.get("topics", []) if t not in names]
        if missing or len(combo.get("topics", [])) < 2:
            raise SystemExit(f"Combination '{combo.get('name')}' must list two or more topic names from [[topics]]."
                             + (f" Unknown: {missing}" if missing else ""))
    settings["digest"]["sources"] = [s.lower() for s in settings["digest"]["sources"]]
    return settings


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def keyword_plain(kw: str) -> list[str]:
    """Plain phrases from a keyword, for matching titles and abstracts outside PubMed."""
    if re.search(r"\b(AND|NOT)\b", kw):
        return []
    parts = re.split(r"\s+OR\s+", kw)
    out = []
    for part in parts:
        part = re.sub(r"\[[^\]]*\]", "", part).replace('"', "").replace("(", "").replace(")", "").strip()
        if part:
            out.append(part)
    return out


def keyword_regex(phrase: str) -> re.Pattern:
    # spaces and hyphens are interchangeable: "set shifting" also matches "set-shifting"
    body = r"[\s\-]*".join(re.escape(part) for part in re.split(r"[\s\-]+", phrase.strip()) if part)
    pattern = r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])"
    is_acronym = phrase.isupper() and len(phrase) <= 8
    return re.compile(pattern, 0 if is_acronym else re.IGNORECASE)


class Matcher:
    """Finds which keywords of a topic appear in a piece of text."""

    def __init__(self, keywords: list[str], exclude: list[str] | None = None):
        self.rules = [(p, keyword_regex(p)) for kw in keywords for p in keyword_plain(kw)]
        self.exclude = [keyword_regex(p) for kw in (exclude or []) for p in keyword_plain(kw)]

    def matches(self, text: str) -> list[str]:
        if any(rx.search(text) for rx in self.exclude):
            return []
        seen, out = set(), []
        for phrase, rx in self.rules:
            if rx.search(text) and phrase.lower() not in seen:
                seen.add(phrase.lower())
                out.append(phrase)
        return out


# --------------------------------------------------------------------------- PubMed


def pubmed_term(kw: str) -> str:
    kw = kw.strip()
    if "[" in kw or re.search(r"\b(AND|OR|NOT)\b", kw):
        return f"({kw})"
    return f'"{kw}"[tiab]'


def topic_query(topic: dict) -> str:
    q = "(" + " OR ".join(pubmed_term(k) for k in topic["keywords"]) + ")"
    if topic.get("exclude"):
        q += " NOT (" + " OR ".join(pubmed_term(k) for k in topic["exclude"]) + ")"
    return q


def researcher_query(person: dict) -> str | None:
    parts = []
    if person.get("orcid"):
        parts.append(f'"{person["orcid"].strip()}"[auid]')
    if person.get("name"):
        name_q = f'"{person["name"].strip()}"[au]'
        if person.get("affiliation"):
            name_q = f'({name_q} AND "{person["affiliation"].strip()}"[ad])'
        parts.append(name_q)
    return "(" + " OR ".join(parts) + ")" if parts else None


def date_filter(start: dt.date, end: dt.date) -> str:
    return f'("{start:%Y/%m/%d}"[edat] : "{end:%Y/%m/%d}"[edat])'


def pubmed_link(query: str, start: dt.date, end: dt.date) -> str:
    return "https://pubmed.ncbi.nlm.nih.gov/?" + urllib.parse.urlencode(
        {"term": f"{query} AND {date_filter(start, end)}", "sort": "date"})


def ncbi_params() -> dict:
    params = {"tool": "weekly-literature-digest"}
    if os.environ.get("NCBI_EMAIL") or os.environ.get("EMAIL_ADDRESS"):
        params["email"] = os.environ.get("NCBI_EMAIL") or os.environ.get("EMAIL_ADDRESS", "")
    if os.environ.get("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    return params


def ncbi_pause() -> None:
    time.sleep(0.12 if os.environ.get("NCBI_API_KEY") else 0.4)


def esearch(query: str, start: dt.date, end: dt.date, retmax: int = 9999) -> tuple[int, list[str]]:
    form = {"db": "pubmed", "term": f"{query} AND {date_filter(start, end)}", "retmode": "json",
            "retmax": str(retmax), "sort": "relevance", **ncbi_params()}
    raw = json.loads(fetch(f"{EUTILS}/esearch.fcgi", form=form))
    ncbi_pause()
    result = raw.get("esearchresult", {})
    if "ERROR" in result:
        raise RuntimeError(f"PubMed rejected the query: {result['ERROR']}")
    return int(result.get("count", 0)), list(result.get("idlist", []))


def _text(el: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _pub_date(article: ET.Element) -> str:
    months = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                          "sep", "oct", "nov", "dec"], start=1)}
    ad = article.find(".//Article/ArticleDate")
    if ad is not None and ad.findtext("Year"):
        return f"{ad.findtext('Year')}-{int(ad.findtext('Month') or 1):02d}-{int(ad.findtext('Day') or 1):02d}"
    pd = article.find(".//Article/Journal/JournalIssue/PubDate")
    if pd is None:
        return ""
    year = pd.findtext("Year")
    if not year:
        medline = pd.findtext("MedlineDate") or ""
        return medline[:4]
    month = (pd.findtext("Month") or "").strip()
    mnum = int(month) if month.isdigit() else months.get(month[:3].lower(), 0)
    day = pd.findtext("Day")
    if mnum and day:
        return f"{year}-{mnum:02d}-{int(day):02d}"
    if mnum:
        return f"{year}-{mnum:02d}"
    return year


def parse_pubmed_article(art: ET.Element) -> dict:
    cit = art.find("MedlineCitation")
    article = cit.find("Article") if cit is not None else None
    pmid = cit.findtext("PMID") if cit is not None else ""
    authors = []
    for au in (article.findall("AuthorList/Author") if article is not None else []):
        if au.findtext("CollectiveName"):
            authors.append(au.findtext("CollectiveName"))
        elif au.findtext("LastName"):
            authors.append(f"{au.findtext('LastName')} {au.findtext('Initials') or ''}".strip())
    abstract = []
    for ab in (article.findall("Abstract/AbstractText") if article is not None else []):
        abstract.append((ab.get("Label", "").title(), _text(ab)))
    types = [_text(t) for t in (article.findall("PublicationTypeList/PublicationType") if article is not None else [])]
    informative = [t for t in types if t.lower() not in GENERIC_TYPES]
    doi = ""
    pmc = ""
    for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi" and not doi:
            doi = (aid.text or "").strip()
        if aid.get("IdType") == "pmc":
            pmc = (aid.text or "").strip()
    if not doi and article is not None:
        for eid in article.findall("ELocationID"):
            if eid.get("EIdType") == "doi":
                doi = (eid.text or "").strip()
    journal = ""
    if article is not None:
        journal = article.findtext("Journal/ISOAbbreviation") or article.findtext("Journal/Title") or ""
    return {
        "key": f"pmid:{pmid}", "source": "PubMed", "pmid": pmid, "doi": doi, "pmc": pmc,
        "title": _text(article.find("ArticleTitle")) if article is not None else "",
        "authors": authors, "journal": journal, "date": _pub_date(art) if article is not None else "",
        "type": ", ".join(informative) if informative else ("Journal Article" if types else ""),
        "abstract": abstract, "matched": [], "summary": None,
        "url": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def efetch(pmids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(pmids), 150):
        batch = pmids[i:i + 150]
        form = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml", **ncbi_params()}
        root = ET.fromstring(fetch(f"{EUTILS}/efetch.fcgi", form=form))
        ncbi_pause()
        for art in root.findall("PubmedArticle"):
            paper = parse_pubmed_article(art)
            out[paper["pmid"]] = paper
    return out


# --------------------------------------------------------------------------- bioRxiv / medRxiv


def preprints(server: str, start: dt.date, end: dt.date, categories: list[str], max_pages: int) -> tuple[list[dict], bool]:
    """All preprints posted in the window (first versions only). Returns (papers, complete)."""
    papers: list[dict] = []
    complete = True
    wanted = [c.strip().lower() for c in categories if c.strip()]
    for category in (wanted or [None]):
        cursor, pages = 0, 0
        while True:
            url = f"{PREPRINT_API}/{server}/{start:%Y-%m-%d}/{end:%Y-%m-%d}/{cursor}/json"
            if category:
                url += "?" + urllib.parse.urlencode({"category": category.replace(" ", "_")})
            payload = json.loads(fetch(url))
            batch = payload.get("collection", []) or []
            msg = (payload.get("messages") or [{}])[0]
            for p in batch:
                if str(p.get("version", "1")) != "1":
                    continue
                if category and p.get("category", "").strip().lower() not in (category, category.replace("_", " ")):
                    continue
                papers.append(p)
            pages += 1
            count = int(msg.get("count", len(batch)) or len(batch) or 0)
            total = int(msg.get("total", 0) or 0)
            cursor += count
            if not batch or count == 0 or cursor >= total:
                break
            if pages >= max_pages:
                complete = False
                break
            time.sleep(0.3)
    return papers, complete


def preprint_to_paper(p: dict, server_label: str) -> dict:
    doi = p.get("doi", "")
    abstract = p.get("abstract", "") or ""
    return {
        "key": f"doi:{doi.lower()}", "source": server_label, "pmid": "", "doi": doi, "pmc": "",
        "title": re.sub(r"\s+", " ", p.get("title", "")).strip(),
        "authors": [a.strip() for a in (p.get("authors", "") or "").split(";") if a.strip()],
        "journal": server_label, "date": p.get("date", ""),
        "type": f"Preprint ({p.get('category', '').strip()}), not peer reviewed",
        "abstract": [("", abstract.strip())] if abstract.strip() else [],
        "matched": [], "summary": None, "url": f"https://doi.org/{doi}" if doi else "",
        "published_doi": p.get("published", "") if p.get("published", "NA") != "NA" else "",
    }


def name_key(name: str) -> tuple[str, str]:
    """('neumann', 'w') from 'Neumann WJ' or 'Neumann, W.-J.'."""
    name = strip_accents(name).strip()
    if "," in name:
        last, first = name.split(",", 1)
    else:
        bits = name.split()
        last, first = (" ".join(bits[:-1]), bits[-1]) if len(bits) > 1 else (name, "")
    initial = re.sub(r"[^A-Za-z]", "", first)[:1].lower()
    return last.strip().lower(), initial


def person_in_authors(person: dict, authors: list[str]) -> bool:
    if not person.get("name"):
        return False
    want_last, want_initial = name_key(person["name"])
    for author in authors:
        last, initial = name_key(author)
        if last == want_last and (not want_initial or not initial or initial == want_initial):
            return True
    return False


# --------------------------------------------------------------------------- Bluesky


def bsky_post_url(post: dict) -> str:
    rkey = post.get("uri", "").rsplit("/", 1)[-1]
    handle = post.get("author", {}).get("handle", "")
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def bsky_simplify(post: dict) -> dict:
    record = post.get("record", {}) or {}
    links = []
    embed = post.get("embed", {}) or {}
    ext = (embed.get("external") or {}).get("uri")
    if ext:
        links.append(ext)
    for facet in record.get("facets", []) or []:
        for feature in facet.get("features", []) or []:
            if feature.get("uri"):
                links.append(feature["uri"])
    author = post.get("author", {}) or {}
    return {"key": "bsky:" + post.get("uri", ""), "author": author.get("displayName") or author.get("handle", ""),
            "handle": author.get("handle", ""), "text": record.get("text", ""),
            "date": (record.get("createdAt") or "")[:10], "likes": post.get("likeCount", 0) or 0,
            "reposts": post.get("repostCount", 0) or 0, "url": bsky_post_url(post), "links": links}


PAPER_LINK = re.compile(r"doi\.org|biorxiv\.org|medrxiv\.org|pubmed|ncbi\.nlm\.nih\.gov|arxiv\.org|"
                        r"nature\.com|science\.org|cell\.com|sciencedirect|springer|wiley|plos|frontiersin|"
                        r"elifesciences|jneurosci|oup\.com|tandfonline|sagepub|mdpi", re.I)


def bsky_author_posts(handle: str, since: dt.datetime) -> list[dict]:
    url = f"{BSKY_PUBLIC}/app.bsky.feed.getAuthorFeed?" + urllib.parse.urlencode(
        {"actor": handle, "limit": 50, "filter": "posts_no_replies"})
    feed = json.loads(fetch(url)).get("feed", [])
    out = []
    for item in feed:
        if item.get("reason"):  # a repost by this person; keep only their own posts
            continue
        post = bsky_simplify(item.get("post", {}))
        created = (item.get("post", {}).get("record", {}) or {}).get("createdAt", "")
        if created and created[:19] >= since.strftime("%Y-%m-%dT%H:%M:%S"):
            out.append(post)
    return out


def bsky_session() -> str | None:
    handle, password = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        return None
    resp = json.loads(fetch(f"{BSKY_AUTH}/com.atproto.server.createSession",
                            data={"identifier": handle, "password": password}))
    return resp.get("accessJwt")


def bsky_search(token: str, query: str, since: dt.datetime, limit: int = 25) -> list[dict]:
    url = f"{BSKY_AUTH}/app.bsky.feed.searchPosts?" + urllib.parse.urlencode(
        {"q": query, "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "sort": "top", "limit": limit})
    posts = json.loads(fetch(url, headers={"Authorization": f"Bearer {token}"})).get("posts", [])
    return [bsky_simplify(p) for p in posts]


# --------------------------------------------------------------------------- AI summaries (optional)


def ai_summary(paper: dict, model: str, api_key: str) -> dict | None:
    abstract = " ".join(f"{label}: {text}" if label else text for label, text in paper["abstract"])
    if not abstract:
        return None
    prompt = (
        "Summarise this research paper for a researcher's weekly literature digest. "
        "Write exactly five fields, one plain sentence each, in your own words (do not copy sentences "
        "from the abstract): Aim, Methods (include design and sample size if given), Results, Discussion, "
        "Caveats. If the abstract does not say, write \"Not stated\". Reply with JSON only, for example "
        '{"Aim": "...", "Methods": "...", "Results": "...", "Discussion": "...", "Caveats": "..."}\n\n'
        f"Title: {paper['title']}\nAbstract: {abstract[:6000]}"
    )
    body = {"model": model, "max_tokens": 500, "messages": [{"role": "user", "content": prompt}]}
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    resp = json.loads(fetch(ANTHROPIC_URL, data=body, headers=headers, timeout=90))
    text = "".join(block.get("text", "") for block in resp.get("content", []) if block.get("type") == "text")
    found = re.search(r"\{.*\}", text, re.S)
    if not found:
        return None
    try:
        parsed = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None
    return {label: str(parsed.get(label, "")).strip() for label in SUMMARY_LABELS if parsed.get(label)}


# --------------------------------------------------------------------------- state and schedule


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("state file was unreadable; starting fresh")
    return {"sent": {}, "last_run": None, "last_scheduled_run": None}


def save_state(path: Path, state: dict, today: dt.date) -> None:
    cutoff = (today - dt.timedelta(days=365)).isoformat()
    state["sent"] = {k: v for k, v in state.get("sent", {}).items() if v >= cutoff}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def tzinfo(name: str):
    if ZoneInfo is None:
        return dt.timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        log(f"Unknown timezone '{name}', using UTC. Use a name like 'Asia/Kolkata' or 'Europe/London'.")
        return dt.timezone.utc


def latest_slot(settings: dict, now_utc: dt.datetime) -> dt.datetime:
    sched = settings["email"]
    tz = tzinfo(sched["timezone"])
    now = now_utc.astimezone(tz)
    day = DAYS.index(sched["day"].strip().lower())
    hour, minute = (int(x) for x in sched["time"].strip().split(":"))
    slot = (now - dt.timedelta(days=(now.weekday() - day) % 7)).replace(hour=hour, minute=minute,
                                                                         second=0, microsecond=0)
    if slot > now:
        slot -= dt.timedelta(days=7)
    return slot


def is_due(settings: dict, state: dict, now_utc: dt.datetime) -> tuple[bool, str]:
    if not settings["email"]["notifications"]:
        return False, "email notifications are off (run it manually instead)"
    if not os.environ.get("EMAIL_ADDRESS") or not os.environ.get("EMAIL_APP_PASSWORD"):
        return False, "email notifications are on, but EMAIL_ADDRESS / EMAIL_APP_PASSWORD are not set"
    slot = latest_slot(settings, now_utc)
    last = state.get("last_scheduled_run")
    if last and dt.datetime.fromisoformat(last) >= slot:
        return False, f"already sent for {slot:%a %d %b %H:%M %Z}"
    if now_utc - slot > dt.timedelta(hours=24):
        return False, f"not yet; next digest {slot + dt.timedelta(days=7):%a %d %b %H:%M %Z}"
    return True, f"due: {slot:%a %d %b %H:%M %Z}"


# --------------------------------------------------------------------------- building the digest


def collect(settings: dict, state: dict, today: dt.date) -> dict:
    d = settings["digest"]
    sources = set(d["sources"])
    last_run = state.get("last_run")
    start = today - dt.timedelta(days=int(d["lookback_days"]))
    if last_run:
        last_day = dt.date.fromisoformat(last_run[:10]) - dt.timedelta(days=1)
        start = max(min(start, last_day), today - dt.timedelta(days=30))
    end = today
    since = dt.datetime.combine(start, dt.time(0, 0), tzinfo=dt.timezone.utc)
    sent = state.get("sent", {})
    shown: set[str] = set()
    problems: list[str] = []
    matchers = {t["name"]: Matcher(t["keywords"], t.get("exclude")) for t in settings["topics"]}

    def fresh(key: str) -> bool:
        return key not in sent and key not in shown

    sections: list[dict] = []
    topic_ids: dict[str, list[str]] = {}
    topic_counts: dict[str, int] = {}
    researcher_ids: dict[str, list[str]] = {}

    # PubMed searches
    if "pubmed" in sources:
        try:
            for topic in settings["topics"]:
                count, ids = esearch(topic_query(topic), start, end)
                topic_counts[topic["name"]], topic_ids[topic["name"]] = count, ids
            for person in settings["researchers"]:
                q = researcher_query(person)
                if q:
                    _, ids = esearch(q, start, end, retmax=200)
                    researcher_ids[person.get("name") or person.get("orcid")] = ids
        except Exception as err:  # keep going with the other sources
            problems.append(f"PubMed: {err}")
            log(f"PubMed failed: {err}")

    # Preprints
    preprint_pool: list[dict] = []
    for server, label in (("biorxiv", "bioRxiv"), ("medrxiv", "medRxiv")):
        if server not in sources:
            continue
        try:
            raw, complete = preprints(server, start, end, settings["preprints"].get(f"{server}_categories", []),
                                      int(settings["preprints"]["max_pages"]))
            preprint_pool += [preprint_to_paper(p, label) for p in raw]
            if not complete:
                problems.append(f"{label}: stopped after {settings['preprints']['max_pages']} pages; "
                                "add categories in settings to narrow it")
        except Exception as err:
            problems.append(f"{label}: {err}")
            log(f"{label} failed: {err}")
    for p in preprint_pool:
        text = f"{p['title']} {' '.join(t for _, t in p['abstract'])}"
        p["_topics"] = {name: m.matches(text) for name, m in matchers.items()}

    # Fetch PubMed records we may show
    wanted: list[str] = []
    for ids in researcher_ids.values():
        wanted += ids[: int(d["max_papers_per_researcher"]) * 2]
    combo_ids: dict[str, list[str]] = {}
    for combo in settings["combinations"]:
        sets = [set(topic_ids.get(t, [])) for t in combo["topics"]]
        first = topic_ids.get(combo["topics"][0], [])
        combo_ids[combo["name"]] = [i for i in first if all(i in s for s in sets)]
        wanted += combo_ids[combo["name"]][: int(d["max_papers_per_combination"]) * 2]
    for topic in settings["topics"]:
        wanted += topic_ids.get(topic["name"], [])[: int(d["max_papers_per_topic"]) * 3]
    wanted = [i for i in dict.fromkeys(wanted) if f"pmid:{i}" not in sent]
    records: dict[str, dict] = {}
    if wanted:
        try:
            records = efetch(wanted)
        except Exception as err:
            problems.append(f"PubMed details: {err}")
    for rec in records.values():
        text = f"{rec['title']} {' '.join(t for _, t in rec['abstract'])}"
        rec["_topics"] = {name: m.matches(text) for name, m in matchers.items()}

    def take(paper: dict, matched: list[str] | None = None) -> dict:
        shown.add(paper["key"])
        paper["matched"] = matched or sorted({kw for kws in paper.get("_topics", {}).values() for kw in kws})
        return paper

    # 1. Researchers you follow
    for person in settings["researchers"]:
        label = person.get("name") or person.get("orcid")
        items = []
        for pmid in researcher_ids.get(label, []):
            rec = records.get(pmid)
            if rec and fresh(rec["key"]):
                items.append(take(rec, [label]))
        for p in preprint_pool:
            if fresh(p["key"]) and person_in_authors(person, p["authors"]):
                items.append(take(p, [label]))
        items = items[: int(d["max_papers_per_researcher"])]
        posts = []
        if "bluesky" in sources and settings["bluesky"]["researcher_posts"] and person.get("bluesky"):
            try:
                posts = bsky_author_posts(person["bluesky"].lstrip("@"), since)
            except Exception as err:
                problems.append(f"Bluesky ({person['bluesky']}): {err}")
        if items or posts:
            sections.append({"kind": "researcher", "name": label, "items": items, "posts": posts})

    # 2. Combinations (papers matching several topics)
    for combo in settings["combinations"]:
        items = []
        for pmid in combo_ids.get(combo["name"], []):
            rec = records.get(pmid)
            if rec and fresh(rec["key"]):
                items.append(take(rec))
        for p in preprint_pool:
            if fresh(p["key"]) and all(p["_topics"].get(t) for t in combo["topics"]):
                items.append(take(p))
        items = items[: int(d["max_papers_per_combination"])]
        sections.append({"kind": "combination", "name": combo["name"], "items": items,
                         "pubmed_total": len(combo_ids.get(combo["name"], [])),
                         "pubmed_link": pubmed_link(" AND ".join(topic_query(t) for t in settings["topics"]
                                                                 if t["name"] in combo["topics"]), start, end)
                         if topic_ids else ""})

    # 3. Each topic on its own
    bsky_token = None
    if "bluesky" in sources and settings["bluesky"]["keyword_search"]:
        try:
            bsky_token = bsky_session()
            if not bsky_token:
                problems.append("Bluesky keyword search is on, but BLUESKY_HANDLE / BLUESKY_APP_PASSWORD are not set")
        except Exception as err:
            problems.append(f"Bluesky sign-in: {err}")
    for topic in settings["topics"]:
        name = topic["name"]
        items = []
        for pmid in topic_ids.get(name, []):
            rec = records.get(pmid)
            if rec and fresh(rec["key"]) and len(items) < int(d["max_papers_per_topic"]):
                items.append(take(rec))
        pre = [p for p in preprint_pool if fresh(p["key"]) and p["_topics"].get(name)]
        pre.sort(key=lambda p: p["date"], reverse=True)
        pre.sort(key=lambda p: len(p["_topics"][name]), reverse=True)
        items += [take(p) for p in pre[: max(3, int(d["max_papers_per_topic"]) // 2)]]
        posts = []
        if bsky_token:
            found: dict[str, dict] = {}
            phrases = [p for kw in topic["keywords"] for p in keyword_plain(kw)]
            for phrase in phrases[: int(settings["bluesky"]["max_keywords_per_topic"])]:
                try:
                    for post in bsky_search(bsky_token, f'"{phrase}"' if " " in phrase else phrase, since):
                        if settings["bluesky"]["only_posts_with_links"] and not any(
                                PAPER_LINK.search(u) for u in post["links"]):
                            continue
                        found.setdefault(post["key"], post)
                except Exception as err:
                    problems.append(f"Bluesky search '{phrase}': {err}")
                    break
            posts = sorted(found.values(), key=lambda p: -(p["likes"] + 2 * p["reposts"]))
            posts = [p for p in posts if p["key"] not in sent][: int(settings["bluesky"]["max_posts_per_topic"])]
        sections.append({"kind": "topic", "name": name, "items": items, "posts": posts,
                         "pubmed_total": topic_counts.get(name, 0),
                         "pubmed_link": pubmed_link(topic_query(topic), start, end) if name in topic_counts else ""})

    return {"title": d["title"], "start": start.isoformat(), "end": end.isoformat(),
            "sections": sections, "problems": problems}


def add_ai_summaries(digest: dict, settings: dict) -> None:
    if not settings["ai"]["summaries"]:
        return
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        digest["problems"].append("AI summaries are on, but ANTHROPIC_API_KEY is not set")
        return
    budget = int(settings["ai"]["max_papers"])
    for section in digest["sections"]:
        for paper in section["items"]:
            if budget <= 0:
                return
            try:
                paper["summary"] = ai_summary(paper, settings["ai"]["model"], key)
                budget -= 1
            except Exception as err:
                digest["problems"].append(f"AI summary failed: {err}")
                return


# --------------------------------------------------------------------------- rendering


def fmt_date(value: str) -> str:
    try:
        parsed = dt.date.fromisoformat(value[:10])
        return f"{parsed.day} {parsed:%b %Y}"
    except ValueError:
        return value


def short_authors(authors: list[str]) -> str:
    if len(authors) <= 3:
        return ", ".join(authors)
    return ", ".join(authors[:3]) + " et al."


SECTION_TITLES = {"researcher": "New from {name}", "combination": "{name}", "topic": "{name}"}


def abstract_excerpt(abstract: list[tuple[str, str]], max_words: int = 90) -> list[tuple[str, str]]:
    """Results and conclusions when the abstract is labelled; otherwise its opening words."""
    keep = [(label, text) for label, text in abstract
            if label.lower().startswith(("result", "finding", "conclusion", "interpretation"))]
    chosen = keep or abstract
    out, used = [], 0
    for label, text in chosen:
        words = text.split()
        if used + len(words) > max_words:
            words = words[: max(0, max_words - used)]
            if words:
                out.append((label, " ".join(words) + " …"))
            break
        out.append((label, text))
        used += len(words)
    return out


def render_html(digest: dict, include_abstracts: bool) -> str:
    e = html.escape
    out = [f"<div style=\"font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:720px;color:#1d1d1b;\">",
           f"<h1 style=\"font-size:22px;margin:0 0 4px;\">{e(digest['title'])}</h1>",
           f"<p style=\"color:#6b6a64;margin:0 0 18px;\">New papers added {e(fmt_date(digest['start']))} to "
           f"{e(fmt_date(digest['end']))}</p>"]
    total = sum(len(s["items"]) for s in digest["sections"])
    if total == 0 and not any(s.get("posts") for s in digest["sections"]):
        out.append("<p>No new papers matched your keywords this time.</p>")
    for s in digest["sections"]:
        if not s["items"] and not s.get("posts") and s["kind"] != "topic":
            continue
        out.append(f"<h2 style=\"font-size:18px;border-bottom:1px solid #e5e2da;padding-bottom:4px;margin:26px 0 8px;\">"
                   f"{e(SECTION_TITLES[s['kind']].format(name=s['name']))}</h2>")
        if s.get("pubmed_link"):
            out.append(f"<p style=\"color:#6b6a64;font-size:13px;margin:0 0 10px;\">{s.get('pubmed_total', 0)} new on PubMed "
                       f"&middot; <a href=\"{e(s['pubmed_link'])}\">see the full list</a></p>")
        if not s["items"] and not s.get("posts"):
            out.append("<p style=\"color:#6b6a64;\">Nothing new.</p>")
        for p in s["items"]:
            links = [f"<a href=\"{e(p['url'])}\">{'DOI' if p['doi'] else 'Link'}</a>"]
            if p.get("pmid"):
                links.append(f"<a href=\"https://pubmed.ncbi.nlm.nih.gov/{e(p['pmid'])}/\">PubMed</a>")
            if p.get("pmc"):
                links.append(f"<a href=\"https://pmc.ncbi.nlm.nih.gov/articles/{e(p['pmc'])}/\">Free full text</a>")
            if p.get("published_doi"):
                links.append(f"<a href=\"https://doi.org/{e(p['published_doi'])}\">Published version</a>")
            out.append("<div style=\"margin:0 0 16px;\">")
            out.append(f"<div style=\"font-weight:600;\"><a style=\"color:#1d1d1b;text-decoration:none;\" "
                       f"href=\"{e(p['url'])}\">{e(p['title'])}</a></div>")
            meta = " &middot; ".join(e(x) for x in [short_authors(p["authors"]), p["journal"], fmt_date(p["date"]), p["type"]] if x)
            out.append(f"<div style=\"color:#6b6a64;font-size:13px;\">{meta}</div>")
            if p.get("matched"):
                out.append(f"<div style=\"font-size:12px;color:#2f5d50;\">Matched: {e(', '.join(p['matched']))}</div>")
            if p.get("summary"):
                out.append("<ul style=\"margin:6px 0;padding-left:18px;font-size:14px;\">" + "".join(
                    f"<li><b>{e(k)}:</b> {e(v)}</li>" for k, v in p["summary"].items()) + "</ul>")
            elif include_abstracts and p["abstract"]:
                parts = []
                for label, text in abstract_excerpt(p["abstract"]):
                    parts.append((f"<b>{e(label)}:</b> " if label else "") + e(text))
                out.append(f"<div style=\"font-size:13px;margin:4px 0;color:#3f3e3a;\">{'<br>'.join(parts)}</div>")
            out.append(f"<div style=\"font-size:13px;\">{' &middot; '.join(links)}</div></div>")
        if s.get("posts"):
            out.append("<p style=\"font-weight:600;margin:12px 0 6px;\">On Bluesky</p>")
            for post in s["posts"]:
                out.append(f"<div style=\"margin:0 0 10px;font-size:14px;\"><b>{e(post['author'])}</b> "
                           f"<span style=\"color:#6b6a64;\">@{e(post['handle'])} &middot; {e(fmt_date(post['date']))}</span>"
                           f"<div>{e(post['text'])}</div><a href=\"{e(post['url'])}\">Open post</a></div>")
    if digest["problems"]:
        out.append("<p style=\"color:#9a3412;font-size:13px;margin-top:24px;\">Notes: " +
                   e("; ".join(digest["problems"])) + "</p>")
    out.append("<p style=\"color:#6b6a64;font-size:12px;margin-top:24px;\">Data from PubMed (NCBI), bioRxiv, medRxiv "
               "and Bluesky. Preprints are not peer reviewed. Made with "
               "<a href=\"https://github.com/RajatJoshi15/weekly-literature-digest\">weekly-literature-digest</a>.</p></div>")
    return "\n".join(out)


def render_text(digest: dict) -> str:
    lines = [digest["title"], f"New papers added {fmt_date(digest['start'])} to {fmt_date(digest['end'])}", ""]
    for s in digest["sections"]:
        if not s["items"] and not s.get("posts"):
            continue
        lines += [SECTION_TITLES[s["kind"]].format(name=s["name"]).upper(), ""]
        for p in s["items"]:
            lines.append(f"- {p['title']}")
            lines.append(f"  {short_authors(p['authors'])} | {p['journal']} | {fmt_date(p['date'])} | {p['type']}")
            if p.get("summary"):
                for k, v in p["summary"].items():
                    lines.append(f"  {k}: {v}")
            lines.append(f"  {p['url']}")
        for post in s.get("posts", []):
            lines.append(f"- Bluesky @{post['handle']}: {post['text'][:200]} {post['url']}")
        lines.append("")
    if digest["problems"]:
        lines.append("Notes: " + "; ".join(digest["problems"]))
    return "\n".join(lines)


def render_markdown(digest: dict) -> str:
    """Archive copy for the repository: no abstracts, so it is safe in a public repo."""
    md = [f"# {digest['title']}", "", f"New papers added {fmt_date(digest['start'])} to {fmt_date(digest['end'])}.", ""]
    for s in digest["sections"]:
        if not s["items"] and not s.get("posts"):
            continue
        md += [f"## {SECTION_TITLES[s['kind']].format(name=s['name'])}", ""]
        if s.get("pubmed_link"):
            md += [f"{s.get('pubmed_total', 0)} new on PubMed, [see the full list]({s['pubmed_link']}).", ""]
        for p in s["items"]:
            md.append(f"- **[{p['title']}]({p['url']})**  ")
            md.append(f"  {short_authors(p['authors'])} · {p['journal']} · {fmt_date(p['date'])} · {p['type']}"
                      + (f"  \n  Matched: {', '.join(p['matched'])}" if p.get("matched") else ""))
            if p.get("summary"):
                for k, v in p["summary"].items():
                    md.append(f"  - **{k}:** {v}")
        for post in s.get("posts", []):
            md.append(f"- Bluesky, [{post['author']} (@{post['handle']})]({post['url']}), {fmt_date(post['date'])}")
        md.append("")
    md.append("_Data from PubMed (NCBI), bioRxiv, medRxiv and Bluesky. Preprints are not peer reviewed._")
    return "\n".join(md) + "\n"


# --------------------------------------------------------------------------- email


def send_email(subject: str, html_body: str, text_body: str) -> None:
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_APP_PASSWORD"]
    to = os.environ.get("EMAIL_TO") or sender
    host = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT") or 465)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Weekly literature digest", sender))
    msg["To"] = to
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    recipients = [a.strip() for a in to.split(",") if a.strip()]
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=60) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=60) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly literature digest")
    parser.add_argument("--settings", default=str(ROOT / "settings.toml"))
    parser.add_argument("--state", default=str(ROOT / "state" / "sent.json"))
    parser.add_argument("--dry-run", action="store_true", help="preview only: no email, nothing saved")
    parser.add_argument("--scheduled", action="store_true", help="run only when the scheduled time has come")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    settings = load_settings(Path(args.settings))
    state_path = Path(args.state)
    state = load_state(state_path)
    now_utc = dt.datetime.now(dt.timezone.utc)

    if args.scheduled:
        due, why = is_due(settings, state, now_utc)
        log(f"Scheduled check: {why}")
        if not due:
            return 0

    today = now_utc.astimezone(tzinfo(settings["email"]["timezone"])).date()
    log(f"Collecting papers up to {today}...")
    digest = collect(settings, state, today)
    add_ai_summaries(digest, settings)
    count = sum(len(s["items"]) for s in digest["sections"])
    posts = sum(len(s.get("posts", [])) for s in digest["sections"])
    log(f"Found {count} papers and {posts} Bluesky posts. Notes: {digest['problems'] or 'none'}")

    include_abstracts = bool(settings["digest"]["include_abstracts"])
    html_body = render_html(digest, include_abstracts)
    (ROOT / "preview.html").write_text("<!DOCTYPE html><meta charset=\"utf-8\"><title>Digest preview</title>"
                                       + html_body, encoding="utf-8")
    if args.dry_run:
        log("Dry run: wrote preview.html; no email sent and nothing saved.")
        return 0

    archive = ROOT / "digests"
    archive.mkdir(exist_ok=True)
    markdown = render_markdown(digest)
    (archive / f"{today.isoformat()}.md").write_text(markdown, encoding="utf-8")
    (archive / "latest.md").write_text(markdown, encoding="utf-8")

    emailed = False
    if settings["email"]["notifications"]:
        if os.environ.get("EMAIL_ADDRESS") and os.environ.get("EMAIL_APP_PASSWORD"):
            subject = f"{settings['digest']['title']}: {count} new papers ({fmt_date(today.isoformat())})"
            send_email(subject, html_body, render_text(digest))
            emailed = True
            log(f"Emailed the digest to {os.environ.get('EMAIL_TO') or os.environ['EMAIL_ADDRESS']}.")
        else:
            log("Email notifications are on, but EMAIL_ADDRESS / EMAIL_APP_PASSWORD are not set; saved the digest only.")

    for s in digest["sections"]:
        for p in s["items"]:
            state.setdefault("sent", {})[p["key"]] = today.isoformat()
        for post in s.get("posts", []):
            state.setdefault("sent", {})[post["key"]] = today.isoformat()
    state["last_run"] = now_utc.isoformat()
    if args.scheduled and emailed:
        state["last_scheduled_run"] = now_utc.isoformat()
    save_state(state_path, state, today)
    log(f"Saved digests/{today.isoformat()}.md and digests/latest.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
