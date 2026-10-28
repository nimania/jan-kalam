#!/usr/bin/env python3
"""Refresh the standalone local snapshot at build time; preserve archived stories."""
import concurrent.futures
import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data/snapshot.json.gz'
BASE = os.environ.get('JANKALAM_DATA_BASE', 'https://pendar.io/data/').rstrip('/') + '/'
REQUIRED = {'stories.json', 'figures.json', 'meta.json'}

def fetch(key):
    request = Request(BASE + quote(key, safe='/'), headers={'User-Agent': 'JanKalamSnapshot/1.0'})
    with urlopen(request, timeout=25) as response:
        return json.load(response)

def refresh():
    with gzip.open(SNAPSHOT, 'rt', encoding='utf-8') as source:
        previous = json.load(source)
    keys = [key for key in previous if '/' not in key and key != 'feed.json']
    updated = dict(previous)
    errors = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch, key): key for key in keys}
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                updated[key] = future.result()
            except Exception as exc:
                errors[key] = str(exc)
    if REQUIRED.intersection(errors):
        raise RuntimeError('Required datasets unavailable: ' + ', '.join(sorted(REQUIRED.intersection(errors))))
    stories = updated['stories.json']
    assert isinstance(stories, list) and stories, 'Empty or invalid news feed'
    assert isinstance(updated['figures.json'], dict) and updated['figures.json'].get('figures'), 'Empty figure index'
    built = datetime.fromisoformat(updated['meta.json']['built_iso'].replace('Z', '+00:00'))
    if built.tzinfo is None:
        built = built.replace(tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - built).total_seconds() < 43200, 'Upstream news snapshot is over 12 hours old'
    details = ['story/' + str(row['id']) + '.json' for row in stories]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for key, value in zip(details, pool.map(fetch, details)):
            assert isinstance(value, dict) and value.get('id'), 'Invalid story detail: ' + key
            updated[key] = value
    updated['feed.json'] = stories
    updated['snapshot-health.json'] = {'generated_at': datetime.now(timezone.utc).isoformat(), 'upstream_built_iso': updated['meta.json']['built_iso'], 'story_count': len(stories), 'optional_source_errors': errors}
    payload = json.dumps(updated, ensure_ascii=False, separators=(',', ':')).encode()
    temporary = SNAPSHOT.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(payload, mtime=0))
    temporary.replace(SNAPSHOT)
    print(json.dumps(updated['snapshot-health.json'], ensure_ascii=False))

if __name__ == '__main__':
    refresh()
