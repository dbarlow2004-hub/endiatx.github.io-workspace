#!/usr/bin/env python3
"""Podcast transcripts for the Energy Brief study app.

The app asks for a transcript by posting a small JSON message to the private ntfy
topic  <NTFY_TOPIC>-transcribe  ({"podcast": <Apple show id>, "track": <Apple episode
id>, "item": <app item id>}). This script, run every few minutes by GitHub Actions:

  1. reads pending requests from that topic (ntfy keeps messages for 12 hours),
  2. looks the episode up in the public Apple Podcasts directory (never trusting a
     URL from the request),
  3. uses the publisher's own transcript if the RSS feed has a <podcast:transcript>,
     otherwise transcribes the audio with faster-whisper,
  4. encrypts the text with a key derived from NTFY_TOPIC (the repo is public; only
     someone who knows the topic can read it) and saves it under transcripts/,
  5. sends a "transcript ready" notification that opens the episode in the app.

File names are hashes of topic + episode id, so the public repo doesn't reveal what
you listen to.

  python3 sustainability/transcribe.py --check   # just report whether there's work
  python3 sustainability/transcribe.py           # do the work (needs faster-whisper, cryptography)
"""

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "transcripts"
INDEX = OUT / "index.json"
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
APP_URL = (os.environ.get("DIGEST_URL") or "").rstrip("/") + "/learn.html"
MODEL = os.environ.get("WHISPER_MODEL", "base.en")
MAX_PER_RUN = 3
MAX_AUDIO_BYTES = 400 * 1024 * 1024
MAX_SECONDS = 3 * 3600
UA = "Mozilla/5.0 (compatible; energy-brief-transcripts/1.0)"


def fetch(url, limit=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit) if limit else r.read()


def file_key(track):
    return hashlib.sha256(f"{TOPIC}:{track}".encode()).hexdigest()[:24]


def load_index():
    try:
        return json.loads(INDEX.read_text())
    except (OSError, ValueError):
        return {}


def pending_requests(index):
    """Requests from the last 12 hours that aren't done yet (failed ones retry if re-requested later)."""
    if not TOPIC:
        return []
    raw = fetch(f"{SERVER}/{urllib.parse.quote(TOPIC)}-transcribe/json?poll=1&since=12h").decode()
    seen, out = set(), []
    for line in raw.splitlines():
        try:
            msg = json.loads(line)
            req = json.loads(msg.get("message", ""))
            podcast, track = int(req["podcast"]), int(req["track"])
        except (ValueError, KeyError, TypeError):
            continue
        key = file_key(track)
        entry = index.get(key, {})
        if key in seen or entry.get("status") == "done":
            continue
        if entry.get("status") == "failed" and entry.get("at", 0) >= msg.get("time", 0):
            continue
        item = re.sub(r"[^A-Za-z0-9-]", "", str(req.get("item", "")))[:60]
        seen.add(key)
        out.append({"podcast": podcast, "track": track, "item": item, "key": key})
    return out


def find_episode(podcast, track):
    data = json.loads(fetch(f"https://itunes.apple.com/lookup?id={podcast}&entity=podcastEpisode&limit=200"))
    show = next((r for r in data.get("results", []) if r.get("wrapperType") == "track"), {})
    ep = next((r for r in data.get("results", []) if r.get("trackId") == track), None)
    if not ep:
        raise RuntimeError("episode not found in Apple Podcasts (it may be too old)")
    return show, ep


# ---------- publisher transcripts (<podcast:transcript>) ----------

def to_text(body, mime, url):
    text = body.decode("utf-8", "replace")
    kind = (mime or "").lower() + " " + url.lower()
    if "json" in kind:
        try:
            segs = json.loads(text).get("segments", [])
            return "\n".join(s.get("body", "").strip() for s in segs if s.get("body"))
        except (ValueError, AttributeError):
            pass
    if "vtt" in kind or "srt" in kind or "subrip" in kind or "-->" in text[:2000]:
        lines = []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln or "-->" in ln or ln.isdigit() or ln.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
                continue
            ln = re.sub(r"<[^>]+>", "", ln)
            if not lines or lines[-1] != ln:
                lines.append(ln)
        return " ".join(lines)
    if "html" in kind or "<p" in text[:2000].lower():
        text = re.sub(r"(?i)</p>|<br\s*/?>", "\n", text)
        return html.unescape(re.sub(r"<[^>]+>", " ", text))
    return text


def publisher_transcript(feed_url, ep):
    if not feed_url:
        return None
    try:
        root = ET.fromstring(fetch(feed_url, limit=30 * 1024 * 1024))
    except Exception:
        return None
    want_audio = urllib.parse.urlsplit(ep.get("episodeUrl") or "").path
    want_title = (ep.get("trackName") or "").strip().lower()
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip().lower()
        enc = item.find("enclosure")
        audio = urllib.parse.urlsplit(enc.get("url", "")).path if enc is not None else ""
        if not ((want_audio and audio == want_audio) or (want_title and title == want_title)):
            continue
        tags = [el for el in item if el.tag.endswith("}transcript")]
        order = ["text/vtt", "application/x-subrip", "application/srt", "application/json", "text/html", "text/plain"]
        tags.sort(key=lambda el: order.index(el.get("type")) if el.get("type") in order else 99)
        for el in tags:
            try:
                text = to_text(fetch(el.get("url")), el.get("type"), el.get("url")).strip()
                if len(text) > 500:
                    return text
            except Exception:
                continue
        return None
    return None


# ---------- speech to text ----------

_model = None


def whisper_transcript(audio_url):
    global _model
    from faster_whisper import WhisperModel  # installed only in the Action when there's work
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        req = urllib.request.Request(audio_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            size = 0
            while chunk := r.read(1 << 20):
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise RuntimeError("audio file too large")
                f.write(chunk)
        f.flush()
        _model = _model or WhisperModel(MODEL, device="cpu", compute_type="int8")
        segments, info = _model.transcribe(f.name, beam_size=1, vad_filter=True, condition_on_previous_text=False)
        if info.duration > MAX_SECONDS:
            raise RuntimeError("episode longer than 3 hours")
        # paragraphs with a timestamp roughly every minute, so it's easy to find your place
        paras, cur, start = [], [], 0.0
        for s in segments:
            if not cur:
                start = s.start
            cur.append(s.text.strip())
            if s.end - start > 60 and s.text.strip().endswith((".", "?", "!")):
                paras.append(f"[{int(start // 60)}:{int(start % 60):02d}] " + " ".join(cur))
                cur = []
        if cur:
            paras.append(f"[{int(start // 60)}:{int(start % 60):02d}] " + " ".join(cur))
        return "\n\n".join(paras)


# ---------- encryption (matches learn.html's WebCrypto code) ----------

def encrypt(text):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000).derive(TOPIC.encode())
    ct = AESGCM(key).encrypt(iv, text.encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def notify(title, body, click=None):
    q = {"title": title, "tags": "memo"}
    if click:
        q["click"] = click
    try:
        req = urllib.request.Request(f"{SERVER}/{urllib.parse.quote(TOPIC)}?{urllib.parse.urlencode(q)}",
                                     data=body.encode(), method="POST", headers={"User-Agent": UA})
        urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        print(f"warn: notify failed: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not TOPIC:
        print("NTFY_TOPIC not set; nothing to do")
        return
    index = load_index()
    todo = pending_requests(index)
    print(f"{len(todo)} transcript request(s) pending")
    if args.check:
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"work={'true' if todo else 'false'}\n")
        return
    OUT.mkdir(exist_ok=True)
    for req in todo[:MAX_PER_RUN]:
        key, now = req["key"], int(time.time())
        try:
            show, ep = find_episode(req["podcast"], req["track"])
            title = ep.get("trackName", "episode")
            text, source = publisher_transcript(show.get("feedUrl"), ep), "publisher"
            if not text:
                if not ep.get("episodeUrl"):
                    raise RuntimeError("no audio file listed for this episode")
                print(f"transcribing {title!r}...")
                text, source = whisper_transcript(ep["episodeUrl"]), "speech-to-text"
            if len(text) < 200:
                raise RuntimeError("transcript came out empty")
            (OUT / f"{key}.json").write_text(json.dumps(encrypt(text)) + "\n")
            index[key] = {"status": "done", "source": source, "at": now, "words": len(text.split())}
            print(f"done: {title!r} ({source}, {len(text.split())} words)")
            click = f"{APP_URL}?item={req['item']}&ep={req['track']}" if req["item"] and APP_URL.startswith("http") else None
            notify(f"📝 Transcript ready: {title}"[:120], f"{show.get('collectionName', '')}. Tap to make notes and flashcards from it.", click)
        except Exception as e:
            print(f"failed {req}: {e}", file=sys.stderr)
            index[key] = {"status": "failed", "reason": str(e)[:200], "at": now}
            notify("📝 Couldn't get a transcript", f"{e}"[:300])
        INDEX.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
