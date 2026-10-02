"""Download recent periodical PDFs from Jan-e Jaraid Telegram sources.

Requires a Telegram user session because public preview pages expose metadata but
not reliable downloadable document bytes. Secrets:
 TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION
The session is a Telethon StringSession. Nothing is downloaded when credentials
are absent; the normal news build continues.

Sources are collectors only. Published attribution is inferred from the document
caption/name (Economist, Guardian Weekly, Independent, etc.), never the channel.
"""
from __future__ import annotations
import os,re
from pathlib import Path

CHANNELS=("dailynewspaper88magzine","dailynewspaper88")
WANTED=re.compile(r"(economist|guardian\s*weekly|independent|new\s*yorker|time\b|newsweek|the\s*week|financial\s*times|wall\s*street\s*journal)",re.I)
OUT=Path(__file__).resolve().parents[1]/"periodicals_pdf"
OUT.mkdir(exist_ok=True)

def run(limit:int=80)->dict:
    api_id=os.getenv("TELEGRAM_API_ID","").strip()
    api_hash=os.getenv("TELEGRAM_API_HASH","").strip()
    session=os.getenv("TELEGRAM_SESSION","").strip()
    if not (api_id and api_hash and session):
        print("Jan-e Jaraid Telegram ingest skipped: TELEGRAM_API_ID/HASH/SESSION not configured")
        return {"downloaded":0,"skipped":"credentials"}
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    client=TelegramClient(StringSession(session),int(api_id),api_hash)
    downloaded=0
    async def _go():
        nonlocal downloaded
        await client.start()
        for channel in CHANNELS:
            async for msg in client.iter_messages(channel,limit=limit):
                doc=getattr(msg,"document",None)
                if not doc: continue
                name=""
                for a in getattr(doc,"attributes",[]) or []:
                    name=getattr(a,"file_name",name) or name
                text=(getattr(msg,"message","") or "")+" "+name
                if not name.lower().endswith(".pdf") or not WANTED.search(text): continue
                target=OUT/f"{channel}-{msg.id}-{Path(name).name}"
                if target.exists(): continue
                await msg.download_media(file=str(target))
                downloaded+=1
        await client.disconnect()
    with client:
        client.loop.run_until_complete(_go())
    print(f"Jan-e Jaraid Telegram ingest: downloaded {downloaded} PDF(s)")
    return {"downloaded":downloaded}

if __name__=="__main__": run()
