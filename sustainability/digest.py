#!/usr/bin/env python3
"""Daily sustainability / energy news digest.

Pulls RSS feeds (trade press + Google News topic searches), keeps the articles
that match the watched topics, drops ones already sent, and delivers the top
headlines to your phone. Also writes feed.json, which the hub page
(sustainability/index.html) shows as the live "Latest" list.

Standard library only, so it runs on a bare GitHub Actions runner.

Delivery channels (set whichever you want as env vars / repo secrets):
  ntfy push   NTFY_TOPIC                         (free, no account; easiest)
  SMS         TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, SMS_TO
  Email       SMTP_USER, SMTP_PASSWORD, EMAIL_TO  (+ SMTP_HOST, SMTP_PORT)
Optional:     DIGEST_URL  link to the hub page, appended to every message
              MAX_ITEMS   headlines per message (default 5)

Run locally:  python3 sustainability/digest.py --dry-run
"""

import argparse
import base64
import email.utils
import hashlib
import html
import json
import os
import re
import smtplib
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

HERE = Path(__file__).resolve().parent
FEED_FILE = HERE / "feed.json"
RESOURCES_FILE = HERE / "resources.json"
KEEP_ARTICLES = 400  # how many past articles feed.json remembers (dedupe + page)
MAX_AGE = timedelta(days=3)


def gnews(query):
    q = urllib.parse.quote_plus(f"{query} when:1d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


# Viewpoints, so the brief carries more than one side of every issue.
VIEWS = {
    "climate": "🌱 Climate press",
    "markets": "📈 Business & markets",
    "industry": "🛢️ Energy industry",
    "freemarket": "🗽 Free-market & skeptic",
    "research": "🔬 Research & data",
    "mixed": "⚖️ All sides",
    "general": "📰 General news",
}

# (source label, feed url, viewpoint) - viewpoint None means "decide by outlet" (Google News searches)
FEEDS = [
    # Climate & clean-energy press
    ("Canary Media", "https://www.canarymedia.com/rss.rss", "climate"),
    ("Inside Climate News", "https://insideclimatenews.org/feed/", "climate"),
    ("Grist", "https://grist.org/feed/", "climate"),
    ("Electrek", "https://electrek.co/feed/", "climate"),
    ("edie", "https://www.edie.net/feed/", "climate"),
    ("Trellis", "https://trellis.net/feed/", "climate"),
    # These sites block plain RSS fetches, so read them through Google News.
    ("Carbon Brief", gnews("site:carbonbrief.org"), "climate"),
    ("CleanTechnica", gnews("site:cleantechnica.com"), "climate"),
    # Business, markets & trade press
    ("Utility Dive", "https://www.utilitydive.com/feeds/news/", "markets"),
    ("Renewable Energy World", "https://www.renewableenergyworld.com/feed/", "markets"),
    ("pv magazine", gnews("site:pv-magazine.com"), "markets"),
    ("Reuters", gnews("site:reuters.com energy OR electricity OR climate"), "markets"),
    ("Wall Street Journal", gnews("site:wsj.com energy OR electricity OR climate"), "markets"),
    # Energy industry (oil, gas, power)
    ("Oilprice.com", "https://oilprice.com/rss/main", "industry"),
    ("Rigzone", "https://www.rigzone.com/news/rss/rigzone_latest.aspx", "industry"),
    ("NGI", "https://www.naturalgasintel.com/feed/", "industry"),
    ("POWER", "https://www.powermag.com/feed/", "industry"),
    # Free-market and skeptical-of-climate-policy voices
    ("Robert Bryce", "https://robertbryce.substack.com/feed", "freemarket"),
    ("Alex Epstein", "https://alexepstein.substack.com/feed", "freemarket"),
    ("AEI", "https://www.aei.org/feed/", "freemarket"),
    ("Washington Examiner", gnews("site:washingtonexaminer.com energy OR climate"), "freemarket"),
    ("Fox Business", gnews("site:foxbusiness.com energy OR electricity"), "freemarket"),
    # Research & data
    ("EIA Today in Energy", "https://www.eia.gov/rss/todayinenergy.xml", "research"),
    ("Energy Institute at Haas", "https://energyathaas.wordpress.com/feed/", "research"),
    # Aggregator that deliberately collects pieces from across the spectrum
    ("RealClearEnergy", "https://www.realclearenergy.org/index.xml", "mixed"),
    # Topic searches across all outlets (viewpoint decided by outlet below)
    ("News: solar", gnews('"solar panels" OR "solar power" OR "solar farm"'), None),
    ("News: energy prices", gnews('"electricity prices" OR "energy prices" OR "power prices" OR "natural gas prices"'), None),
    ("News: net zero", gnews('"net zero" OR "carbon emissions" OR "greenhouse gas emissions"'), None),
    ("News: storage & grid", gnews('"battery storage" OR "power grid" OR "transmission line"'), None),
    ("News: efficiency", gnews('"energy efficiency" OR "heat pump" OR "building decarbonization"'), None),
    ("News: sustainable dev", gnews('"sustainable development" OR ESG OR "sustainability report"'), None),
]

# Outlets that show up in Google News searches, grouped the same way
OUTLET_VIEWS = {
    "climate": ["canary media", "inside climate news", "grist", "electrek", "cleantechnica", "carbon brief", "the guardian",
                "heatmap", "edie", "trellis", "the cool down", "yale climate connections", "e&e news", "eenews"],
    "markets": ["reuters", "bloomberg", "wall street journal", "wsj", "financial times", "cnbc", "forbes", "axios",
                "utility dive", "pv magazine", "renewable energy world", "s&p global", "barron", "marketwatch", "business insider"],
    "industry": ["oilprice", "rigzone", "naturalgasintel", "ngi", "power magazine", "power engineering", "world oil",
                 "offshore energy", "hart energy", "american oil & gas reporter", "energy voice"],
    "freemarket": ["fox business", "fox news", "washington examiner", "daily caller", "national review", "the federalist",
                   "washington free beacon", "aei", "manhattan institute", "heritage", "cato", "realclear", "townhall", "daily signal"],
    "research": ["eia", "iea", "energy institute at haas", "rmi", "brookings", "resources for the future", "nrel", "lazard"],
}


def view_for(outlet):
    o = outlet.lower()
    for view, names in OUTLET_VIEWS.items():
        if any(n in o for n in names):
            return view
    return "general"

# topic -> keywords (lowercase, matched on word boundaries)
TOPICS = {
    "Solar": ["solar", "photovoltaic", "photovoltaics", "pv module", "rooftop", "perovskite", "agrivoltaic"],
    "Wind": ["wind farm", "wind power", "offshore wind", "onshore wind", "wind turbine"],
    "Storage & Grid": ["battery", "batteries", "storage", "grid", "transmission", "interconnection",
                       "virtual power plant", "utility", "utilities", "data center", "data centers"],
    "Energy Prices": ["price", "prices", "rates", "tariff", "bill", "bills", "ppa", "lcoe",
                      "natural gas", "lng", "oil", "capacity auction", "wholesale", "ferc", "pjm", "ercot"],
    "Carbon & Net Zero": ["net zero", "net-zero", "carbon", "emissions", "greenhouse", "ghg", "co2",
                          "methane", "decarbonization", "decarbonize", "decarbonizing", "scope 3", "offset", "carbon capture", "carbon removal", "sbti"],
    "Efficiency": ["efficiency", "efficient", "heat pump", "insulation", "retrofit", "led lighting",
                   "building performance", "energy star", "demand response"],
    "Sustainable Development": ["sustainable development", "sustainability", "esg", "sdg", "circular",
                                "climate finance", "green bond", "disclosure", "csrd"],
    "Policy": ["tax credit", "ira", "epa", "regulation", "legislation", "doe", "cop30", "cop31", "policy", "tariffs"],
    "Clean Tech": ["renewable", "renewables", "clean energy", "geothermal", "nuclear", "hydrogen",
                   "electric vehicle", "ev", "evs", "fusion", "electrification"],
}

TOPIC_PATTERNS = {
    t: re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")(s|es)?\b", re.I)
    for t, kws in TOPICS.items()
}

UA = "Mozilla/5.0 (compatible; sustainability-digest/1.0)"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_feed(raw, source):
    """Parse RSS 2.0 or Atom into a list of article dicts."""
    root = ET.fromstring(raw)
    items = [el for el in root.iter() if local(el.tag) in ("item", "entry")]
    out = []
    for it in items:
        fields = {}
        link = None
        for child in it:
            name = local(child.tag)
            if name == "link":
                link = link or child.get("href") or (child.text or "").strip()
            elif name in ("title", "description", "summary", "pubDate", "published", "updated", "source"):
                fields.setdefault(name, child.text or "")
        title = strip_tags(fields.get("title"))
        if not title or not link:
            continue
        outlet = strip_tags(fields.get("source")) or source
        # Google News appends " - Outlet" to every title
        if source.startswith("News:") or "news.google.com" in link:
            m = re.match(r"(.*)\s+-\s+([^-]+)$", title)
            if m:
                title, outlet = m.group(1).strip(), m.group(2).strip()
        published = parse_date(fields.get("pubDate") or fields.get("published") or fields.get("updated"))
        out.append({
            "title": title,
            "link": link,
            "source": outlet,
            "summary": strip_tags(fields.get("description") or fields.get("summary"))[:280],
            "published": published.isoformat() if published else None,
        })
    return out


def classify(article):
    text = f"{article['title']} {article['summary']}"
    title_hits, topics = 0, []
    for topic, pat in TOPIC_PATTERNS.items():
        if pat.search(text):
            topics.append(topic)
            if pat.search(article["title"]):
                title_hits += 1
    return topics, len(topics) + title_hits


def article_id(link):
    """Short stable id used in text-message links (go.html?a=<id>)."""
    return hashlib.sha1(link.encode()).hexdigest()[:7]


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()[:80]


def load_feed():
    try:
        return json.loads(FEED_FILE.read_text())
    except (OSError, ValueError):
        return {"articles": []}


def gather(seen_links, seen_titles):
    now = datetime.now(timezone.utc)
    fresh, errors = [], []
    for source, url, view in FEEDS:
        try:
            items = parse_feed(fetch(url), source)
        except Exception as e:  # one dead feed shouldn't kill the digest
            errors.append(f"{source}: {e}")
            continue
        for a in items:
            if a["link"] in seen_links or norm_title(a["title"]) in seen_titles:
                continue
            if a["published"] and now - datetime.fromisoformat(a["published"]) > MAX_AGE:
                continue
            topics, score = classify(a)
            if not topics:
                continue
            a["topics"], a["score"] = topics, score
            a["view"] = view or view_for(a["source"])
            a["id"] = article_id(a["link"])
            a["added"] = now.isoformat()
            seen_links.add(a["link"])
            seen_titles.add(norm_title(a["title"]))
            fresh.append(a)
    fresh.sort(key=lambda a: (a["score"], a["published"] or ""), reverse=True)
    return fresh, errors


def balanced(articles, n):
    """Top stories, taking turns across viewpoints so no single side fills the brief."""
    buckets = {}
    for a in articles:  # already sorted best-first
        buckets.setdefault(a.get("view", "general"), []).append(a)
    order = sorted(buckets, key=lambda v: (v == "general", -buckets[v][0]["score"]))
    picked = []
    while len(picked) < n and any(buckets.values()):
        for v in order:
            if buckets[v] and len(picked) < n:
                picked.append(buckets[v].pop(0))
    return picked


def pick_of_the_day():
    """Rotate through resources.json so each digest suggests one thing to read/watch/listen to."""
    try:
        res = json.loads(RESOURCES_FILE.read_text())
    except (OSError, ValueError):
        return None
    pool = []
    for section in ("books", "podcasts", "documentaries"):
        for r in res.get(section, []):
            pool.append((section, r))
    if not pool:
        return None
    section, r = pool[datetime.now(timezone.utc).timetuple().tm_yday % len(pool)]
    label = {"books": "Read", "podcasts": "Listen", "documentaries": "Watch"}[section]
    by = f" ({r['by']})" if r.get("by") else ""
    text = f"{label}: {r['title']}{by}"
    url = os.environ.get("DIGEST_URL")
    if url:  # deep link into the study app so you can track it and unlock its flashcards
        item = re.sub(r"[^a-z0-9]+", "-", r["title"].lower()).strip("-")
        text += f"\n   Track & study: {url.rstrip('/')}/learn.html?item={item}"
    return text


def build_message(articles, max_items):
    """Headline + a short link per story. Raw Google News links are ~200 chars, so with
    DIGEST_URL set each story links through go.html, which forwards to the article."""
    day = datetime.now(timezone.utc).strftime("%b %d")
    base = (os.environ.get("DIGEST_URL") or "").rstrip("/")
    lines = [f"Energy & Sustainability Brief - {day}", ""]
    for i, a in enumerate(balanced(articles, max_items), 1):
        icon = VIEWS.get(a.get("view", "general"), "").split(" ")[0]
        lines.append(f"{i}. {icon} {a['title']} ({a['source']})")
        if base:
            lines.append(f"   {base}/go.html?a={a['id']}")
    extra = len(articles) - max_items
    if extra > 0:
        lines.append(f"+{extra} more")
    pick = pick_of_the_day()
    if pick:
        lines += ["", f"Today's pick - {pick}"]
    url = os.environ.get("DIGEST_URL")
    if url:
        lines += ["", f"All stories + resources: {url}"]
    return "\n".join(lines)


def post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def send_ntfy(msg, articles):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return None
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    headers = {"Title": "Energy & Sustainability Brief", "Tags": "seedling,zap"}
    if os.environ.get("DIGEST_URL"):
        headers["Click"] = os.environ["DIGEST_URL"]
    post(f"{server}/{topic}", msg.encode(), headers)
    return "ntfy"


def send_sms(msg, articles):
    sid, token = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    sender, to = os.environ.get("TWILIO_FROM"), os.environ.get("SMS_TO")
    if not all([sid, token, sender, to]):
        return None
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    # Twilio splits long bodies itself; cap at 1500 chars to stay within its limit.
    for number in [n.strip() for n in to.split(",") if n.strip()]:
        data = urllib.parse.urlencode({"From": sender, "To": number, "Body": msg[:1500]}).encode()
        post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data,
             {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"})
    return "sms"


def send_email(msg, articles):
    user, pw, to = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD"), os.environ.get("EMAIL_TO")
    if not all([user, pw, to]):
        return None
    rows = []
    for a in balanced(articles, 25):
        rows.append(
            f'<p style="margin:0 0 14px"><a href="{html.escape(a["link"])}" style="font-weight:600">'
            f'{html.escape(a["title"])}</a><br><span style="color:#666;font-size:13px">'
            f'{html.escape(a["source"])} &middot; {html.escape(VIEWS.get(a.get("view", "general"), ""))} &middot; {html.escape(", ".join(a["topics"]))}</span></p>')
    body = (f'<div style="font-family:sans-serif;max-width:620px">'
            f'<pre style="white-space:pre-wrap;font-family:inherit">{html.escape(msg.split(chr(10))[0])}</pre>'
            + "".join(rows))
    pick = pick_of_the_day()
    if pick:
        body += f"<p><b>Today's pick</b> &mdash; {html.escape(pick.splitlines()[0])}</p>"
    if os.environ.get("DIGEST_URL"):
        body += f'<p><a href="{html.escape(os.environ["DIGEST_URL"])}">Open the full hub</a></p>'
    body += "</div>"
    m = MIMEText(body, "html")
    m["Subject"] = msg.split("\n")[0]
    m["From"], m["To"] = user, to
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(user, [t.strip() for t in to.split(",")], m.as_string())
    return "email"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the message, send nothing, don't save")
    args = ap.parse_args()

    data = load_feed()
    old = data.get("articles", [])
    seen_links = {a["link"] for a in old}
    seen_titles = {norm_title(a["title"]) for a in old}
    fresh, errors = gather(seen_links, seen_titles)
    for e in errors:
        print(f"warn: {e}", file=sys.stderr)
    print(f"{len(fresh)} new articles")

    if not fresh:
        return
    max_items = int(os.environ.get("MAX_ITEMS", "5"))
    msg = build_message(fresh, max_items)
    print("\n" + msg + "\n")
    if args.dry_run:
        return

    sent, failures = [], []
    for sender in (send_ntfy, send_sms, send_email):
        try:
            channel = sender(msg, fresh)
            if channel:
                sent.append(channel)
        except Exception as e:
            failures.append(f"{sender.__name__}: {e}")
    print("sent via:", ", ".join(sent) or "nothing (no delivery secrets set)")
    for f in failures:
        print(f"error: {f}", file=sys.stderr)

    for a in old:  # backfill ids on articles saved before ids existed
        a.setdefault("id", article_id(a["link"]))
    data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "articles": (fresh + old)[:KEEP_ARTICLES],
    }
    FEED_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    if failures and not sent:
        sys.exit(1)


if __name__ == "__main__":
    main()
