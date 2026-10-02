"""Best-effort Telegram periodical PDF collector.

The Telegram channels are transport only. Publisher identity is inferred from
the document filename and stored separately, so @dailynewspaper88 never becomes
the visible news source.

Requires TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_SESSION. With any
credential missing, exits successfully and leaves the normal news build alone.
"""
from __future__ import annotations
import asyncio, hashlib, json, os, re
from pathlib import Path
from pypdf import PdfReader
from telethon import TelegramClient

CHANNELS = ("dailynewspaper88", "the_wall_street_journal_epaper", "dailynewspaper88magzine")
OUT = Path("periodicals")
STATE = OUT / "state.json"

PUBLISHERS = [
    (re.compile(r"\b(?:the\s+)?wall\s*street\s+journal|\bwsj\b", re.I), "وال‌استریت ژورنال"),
    (re.compile(r"\bguardian\s+weekly\b", re.I), "هفته‌نامه گاردین"),
    (re.compile(r"\b(?:the\s+)?guardian\b", re.I), "گاردین"),
    (re.compile(r"\b(?:the\s+)?economist\b", re.I), "اکونومیست"),
    (re.compile(r"\bfinancial\s+times\b|\bft\b", re.I), "فایننشال تایمز"),
    (re.compile(r"\bnew\s*york\s+times\b|\bnyt\b", re.I), "نیویورک تایمز"),
    (re.compile(r"\bwashington\s+post\b", re.I), "واشنگتن پست"),
    (re.compile(r"\btime\b", re.I), "تایم"),
]

def publisher_for(filename: str) -> str | None:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    for pattern, name in PUBLISHERS:
        if pattern.search(stem):
            return name
    return None

def page_articles(pdf: Path, publisher: str, origin: str, message_id: int) -> list[dict]:
    """Conservative extraction: one page = one candidate, later clustering
    collapses continuations/duplicates. We never publish/store the PDF itself."""
    rows = []
    reader = PdfReader(str(pdf))
    for page_no, page in enumerate(reader.pages, 1):
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        if len(text) < 350:
            continue
        title = text[:180].rsplit(" ", 1)[0]
        rows.append({
            "id": hashlib.sha1(f"{origin}:{message_id}:{page_no}".encode()).hexdigest(),
            "publisher": publisher,
            "transport": f"telegram:@{origin}",
            "telegram_message_id": message_id,
            "page": page_no,
            "title_original": title,
            "text": text[:12000],
        })
    return rows

async def main() -> None:
    api_id=os.getenv("TELEGRAM_API_ID"); api_hash=os.getenv("TELEGRAM_API_HASH"); session=os.getenv("TELEGRAM_SESSION")
    if not (api_id and api_hash and session):
        print("periodicals: Telegram credentials absent; safe skip")
        return
    OUT.mkdir(exist_ok=True)
    state=json.loads(STATE.read_text() if STATE.exists() else "{}")
    client=TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("TELEGRAM_SESSION is not authorized")
    output=[]
    try:
        for channel in CHANNELS:
            after=int(state.get(channel, 0))
            newest=after
            async for msg in client.iter_messages(channel, limit=30):
                newest=max(newest, msg.id)
                if msg.id <= after or not msg.document:
                    continue
                filename=getattr(msg.file, "name", "") or ""
                if not filename.lower().endswith(".pdf"):
                    continue
                publisher=publisher_for(filename)
                if not publisher:
                    print(f"periodicals: unknown publisher, quarantined: {filename}")
                    continue
                path=await client.download_media(msg, file=str(OUT / f"{channel}-{msg.id}.pdf"))
                pdf=Path(path)
                try: output.extend(page_articles(pdf,publisher,channel,msg.id))
                finally: pdf.unlink(missing_ok=True)
            state[channel]=newest
    finally:
        await client.disconnect()
    (OUT/"articles.json").write_text(json.dumps(output,ensure_ascii=False),encoding="utf-8")
    STATE.write_text(json.dumps(state),encoding="utf-8")
    print(f"periodicals: extracted {len(output)} page candidates")

if __name__ == "__main__":
    from telethon.sessions import StringSession
    asyncio.run(main())
