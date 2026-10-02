"""Publish newly deployed figure summaries; no third-party dependencies.

State lives on the separate telegram-state branch, never in the evictable build
DB cache. Original post URLs survive database rebuilds and AI reclassification.
The first configured run establishes a baseline without sending the old archive.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

SITE = "https://nimania.github.io/jan-kalam"
STATE_BRANCH = "telegram-state"
STATE_PATH = "telegram/figures-state.json"
STATUSES = {"baseline", "pending", "sending", "sent"}


class TelegramRejected(RuntimeError):
    """Telegram explicitly rejected the request: a later retry is safe."""


class DeliveryUncertain(RuntimeError):
    """The request may have reached Telegram; never automatically replay it."""


def http_json(url, *, method="GET", data=None, headers=None):
    request = Request(url, method=method,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json",
                               "User-Agent": "JanKalamTelegram/1.0", **(headers or {})})
    try:
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.code
            raw = response.read()
    except (URLError, OSError, TimeoutError):
        # urllib's exception text contains the URL and therefore the bot token.
        raise RuntimeError("Network request failed; credentials withheld") from None
    try:
        return status, json.loads(raw)
    except (ValueError, UnicodeError):
        raise RuntimeError(f"Unreadable API response (HTTP {status})") from None


def post_key(url):
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    host = parts.netloc.lower()
    if parts.scheme != "https":
        raise ValueError("A figure post must use an HTTPS public source URL")
    if host == "t.me" and re.fullmatch(r"/[A-Za-z0-9_]+/[0-9]+", path):
        handle, number = path.strip("/").split("/")
        return f"https://t.me/{handle.lower()}/{int(number)}"
    if host == "ble.ir" and re.fullmatch(r"/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", path):
        handle, rid = path.strip("/").split("/")
        return f"https://ble.ir/{handle.lower()}/{rid}"
    raise ValueError("A figure post must link to its original Telegram or Bale message")


def shown_posts(export):
    if not isinstance(export, dict) or not isinstance(export.get("figures"), list):
        raise ValueError("Invalid figures export; refusing to initialize delivery state")
    posts = {}
    for figure in export["figures"]:
        if not isinstance(figure, dict) or not isinstance(figure.get("posts"), list):
            raise ValueError("Invalid figure in export")
        for row in figure["posts"]:
            if not isinstance(row, dict):
                raise ValueError("Invalid figure post in export")
            if row.get("kind") not in {"analysis", "party_claim"}:
                continue
            summary = str(row.get("summary_fa") or "").strip()
            if not summary:
                continue
            key = post_key(row.get("url") or "")
            handle = str(row.get("handle") or figure.get("handle") or key.split("/")[-2])
            posts[key] = {
                "url": key, "handle": handle,
                "name_fa": str(row.get("name_fa") or figure.get("name_fa") or handle),
                "topic_fa": str(row.get("topic_fa") or "دیدگاه تازه"),
                "summary_fa": summary,
                "published_at": row.get("published_at") or "",
            }
    return list(posts.values())


def clipped(text, limit):
    # Telegram entities use UTF-16 offsets; this also leaves ample room for emoji.
    encoded = text.encode("utf-16-le")
    if len(encoded) <= limit * 2:
        return text
    return encoded[:(limit - 1) * 2].decode("utf-16-le", errors="ignore").rstrip() + "…"


def message_payload(post, chat_id, site=SITE):
    name = clipped(post["name_fa"].strip(), 120)
    topic = clipped(post["topic_fa"].strip(), 200)
    figure_url = f"{site.rstrip('/')}/#/figure/{quote(post['handle'], safe='')}"
    text = (f"🗣 جان‌کلام {name}\n{topic}\n\n"
            f"{clipped(post['summary_fa'], 3200)}\n\n"
            f"{figure_url}\n\n@jane_kalaam")
    return {
        "chat_id": chat_id, "text": text,
        # Plain text avoids HTML/Markdown injection and broken Persian escaping.
        "link_preview_options": {"is_disabled": True},
        "reply_markup": {"inline_keyboard": [[
            {"text": "متن اصلی", "url": post["url"]},
            {"text": "صفحهٔ این شخص", "url": figure_url},
        ]]},
    }


class Telegram:
    def __init__(self, token, *, sleep=time.sleep):
        self.token = token
        self.sleep = sleep

    def call(self, method, data=None):
        for attempt in range(3):
            try:
                status, result = http_json(
                    f"https://api.telegram.org/bot{self.token}/{method}",
                    method="POST", data=data or {})
            except RuntimeError:
                if method == "sendMessage":
                    raise DeliveryUncertain("Telegram delivery could not be confirmed") from None
                raise RuntimeError("Telegram verification failed; credentials withheld") from None
            if status >= 500:
                if method == "sendMessage":
                    raise DeliveryUncertain("Telegram returned a server error during delivery")
                raise RuntimeError("Telegram is temporarily unavailable")
            if not isinstance(result, dict):
                if method == "sendMessage":
                    raise DeliveryUncertain("Telegram returned an unexpected delivery response")
                raise RuntimeError("Unexpected Telegram response")
            if result.get("ok") is True:
                return result["result"]
            code = result.get("error_code", status)
            delay = result.get("parameters", {}).get("retry_after", 0)
            if code == 429 and attempt < 2 and 0 < delay <= 60:
                self.sleep(min(delay + 1, 60))
                continue
            raise TelegramRejected(f"Telegram rejected {method} (code {code})")

    def verify(self, username, channel):
        bot = self.call("getMe")
        if str(bot.get("username", "")).lower() != username.lstrip("@").lower():
            raise RuntimeError("The token does not belong to @" + username.lstrip("@"))
        chat = self.call("getChat", {"chat_id": channel})
        if (chat.get("type") != "channel"
                or str(chat.get("username", "")).lower() != channel.lstrip("@").lower()):
            raise RuntimeError("The destination does not match the configured channel")
        member = self.call("getChatMember", {"chat_id": chat["id"], "user_id": bot["id"]})
        if (member.get("status") not in {"administrator", "creator"}
                or not (member.get("can_post_messages") or member.get("status") == "creator")):
            raise RuntimeError("Make the bot a channel administrator with Post Messages enabled")
        return chat["id"]

    def send(self, post, chat_id):
        result = self.call("sendMessage", message_payload(post, chat_id))
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise DeliveryUncertain("Telegram did not return the sent message ID")
        return result["message_id"]


class GitHubLedger:
    def __init__(self, repository, token, *, branch=STATE_BRANCH):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub repository")
        self.base = f"https://api.github.com/repos/{repository}"
        self.branch = branch
        self.headers = {"Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}
        self.sha = None

    def request(self, path, *, method="GET", data=None, raw=False):
        return http_json(self.base + path, method=method, data=data, headers={
            **self.headers, **({"Accept": "application/vnd.github.raw+json"} if raw else {})})

    @staticmethod
    def require(status):
        if not 200 <= status < 300:
            raise RuntimeError(f"GitHub delivery-state request failed (HTTP {status})")

    def load(self):
        path = f"/contents/{STATE_PATH}?ref={quote(self.branch, safe='')}"
        status, item = self.request(path)
        if status == 404:
            self.sha = None
            return None
        self.require(status)
        self.sha = item["sha"]
        # Contents API omits base64 content for files larger than 1 MB.
        if item.get("encoding") != "base64":
            status, state = self.request(path, raw=True)
            self.require(status)
            return state
        return json.loads(base64.b64decode(item["content"]))

    def save(self, state):
        if self.sha is None:
            status, _ = self.request(f"/git/ref/heads/{quote(self.branch, safe='')}")
            if status == 404:
                status, main = self.request("/git/ref/heads/main")
                self.require(status)
                status, _ = self.request("/git/refs", method="POST", data={
                    "ref": f"refs/heads/{self.branch}", "sha": main["object"]["sha"]})
            self.require(status)
        content = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        data = {"message": "Record Telegram figure delivery", "branch": self.branch,
                "content": base64.b64encode(content.encode()).decode()}
        if self.sha:
            data["sha"] = self.sha
        status, result = self.request(f"/contents/{STATE_PATH}", method="PUT", data=data)
        self.require(status)
        self.sha = result["content"]["sha"]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def publish(posts, ledger, telegram, chat_id, *, sleep=time.sleep,
            resolve_url="", resolution="mark_sent"):
    state = ledger.load()
    if state is None:
        if resolve_url:
            raise ValueError("There is no delivery state to recover")
        state = {"version": 1, "chat_id": str(chat_id), "initialized_at": utc_now(),
                 "posts": {post_key(p["url"]): {"status": "baseline"} for p in posts}}
        ledger.save(state)
        return {"baseline": len(posts), "sent": 0, "uncertain": 0}
    if (not isinstance(state, dict) or state.get("version") != 1
            or state.get("chat_id") != str(chat_id) or not isinstance(state.get("posts"), dict)):
        raise ValueError("Invalid delivery state or changed channel; refusing to reset it")
    entries = state["posts"]
    if any(not isinstance(e, dict) or e.get("status") not in STATUSES for e in entries.values()):
        raise ValueError("Invalid delivery status; refusing to reset state")
    if resolve_url:
        entry = entries.get(post_key(resolve_url))
        if not entry or entry["status"] != "sending":
            raise ValueError("Recovery URL must match an uncertain (sending) post")
        if resolution not in {"mark_sent", "retry"}:
            raise ValueError("Recovery must be mark_sent or retry")
        entry["status"] = "sent" if resolution == "mark_sent" else "pending"
        if resolution == "mark_sent":
            entry.pop("post", None)
        ledger.save(state)
    changed = False
    for post in posts:
        key = post_key(post["url"])
        if key not in entries:
            entries[key] = {"status": "pending", "post": post}
            changed = True
    if changed:
        ledger.save(state)  # persist the queue before any network delivery
    pending = sorted(((key, entry) for key, entry in entries.items() if entry["status"] == "pending"),
                     key=lambda item: (item[1]["post"].get("published_at") or "", item[0]))
    # Deliberately drain at most one queued figure post per workflow run.
    # build.yml runs every 15 minutes, so a large ingestion/backfill becomes a
    # paced stream instead of a Telegram burst. Nothing is dropped: remaining
    # pending entries stay on the persistent telegram-state branch.
    sent = 0
    for key, entry in pending[:1]:
        entry["status"] = "sending"
        ledger.save(state)  # a crash/timeout must not cause an automatic duplicate
        try:
            message_id = telegram.send(entry["post"], chat_id)
        except TelegramRejected:
            entry["status"] = "pending"
            ledger.save(state)
            raise
        except DeliveryUncertain:
            print(f"::warning::Check the channel before recovering delivery of {key}")
            raise
        entry.update(status="sent", message_id=message_id, sent_at=utc_now())
        entry.pop("post", None)
        ledger.save(state)  # checkpoint each successful message
        sent += 1
    uncertain = sum(e["status"] == "sending" for e in entries.values())
    for key, entry in entries.items():
        if entry["status"] == "sending":
            print(f"::warning::Uncertain delivery; check channel and resolve: {key}")
    return {"baseline": 0, "sent": sent, "uncertain": uncertain}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Preview only; no API calls or state writes")
    args = parser.parse_args(argv)
    posts = shown_posts(json.loads(args.figures.read_text(encoding="utf-8")))
    if args.dry_run:
        print(json.dumps([message_payload(p, "@jane_kalaam") for p in posts], ensure_ascii=False, indent=2))
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("::notice::Telegram is not enabled: add the TELEGRAM_BOT_TOKEN repository secret")
        return 0
    gh_token = os.environ.get("GH_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not gh_token or not repository:
        raise RuntimeError("GitHub repository and delivery-state credentials are required")
    telegram = Telegram(token)
    chat_id = telegram.verify(os.environ.get("TELEGRAM_BOT_USERNAME", "janekalaam_bot"),
                              os.environ.get("TELEGRAM_CHAT_ID", "@jane_kalaam"))
    result = publish(posts, GitHubLedger(repository, gh_token), telegram, chat_id,
                     resolve_url=os.environ.get("TELEGRAM_RESOLVE_URL", "").strip(),
                     resolution=os.environ.get("TELEGRAM_RESOLUTION", "") or "mark_sent")
    print("Telegram publishing: " + json.dumps(result))
    return 1 if result["uncertain"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        # These errors are raised locally with sanitized messages, never API bodies.
        print(f"::error::{exc}", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, KeyError, TypeError):
        # Never print arbitrary API bodies, URLs containing tokens, or traceback.
        print("::error::Telegram publishing failed. Check bot/channel permissions, state, and recovery warnings.",
              file=sys.stderr)
        sys.exit(1)
