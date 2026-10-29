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
LIVE_SNAPSHOT = 'https://nimania.github.io/jan-kalam/data/snapshot.json.gz'
REQUIRED = {'stories.json', 'figures.json', 'meta.json'}
LOCAL_KEYS = {'feed.json', 'news-archive.json', 'pendar-reports.json', 'snapshot-health.json'}

def fetch_url(url):
    request = Request(url, headers={'User-Agent': 'JanKalamSnapshot/2.0'})
    with urlopen(request, timeout=25) as response:
        payload = response.read()
        if payload[:2] == b'\x1f\x8b':
            payload = gzip.decompress(payload)
        return json.loads(payload)

def fetch(key):
    return fetch_url(BASE + quote(key, safe='/'))

def is_editorial(row):
    return bool(row.get('editorial_report') or row.get('has_editorial_report'))

def news_card(row):
    fields = ('id', 'headline_fa', 'summary_fa', 'category', 'status', 'iran_relevance',
              'importance_score', 'source_count', 'published_at', 'source_names',
              'credibility', 'topics', 'entities', 'countries', 'figure_count', 'geo',
              'image_url', 'image_credit', 'factcheck', 'trend')
    card = {key: row[key] for key in fields if key in row}
    if not card.get('source_names'):
        card['source_names'] = list(dict.fromkeys(s.get('source_name') for s in row.get('sources', []) if s.get('source_name')))
    return card

def partition_news(updated, editorial):
    for key, row in list(updated.items()):
        if key.startswith('story/') and isinstance(row, dict) and row.get('id'):
            sid = str(row['id'])
            if is_editorial(row):
                editorial.setdefault(sid, 'https://pendar.io/story/' + sid + '/')
            if sid in editorial:
                del updated[key]
    updated['pendar-reports.json'] = editorial
    updated['stories.json'] = [row for row in updated['stories.json']
                               if str(row.get('id')) not in editorial and not is_editorial(row)]
    updated['feed.json'] = updated['stories.json']
    archive = {str(row['id']): news_card(row) for key, row in updated.items()
               if key.startswith('story/') and isinstance(row, dict) and row.get('id')}
    archive.update({str(row['id']): row for row in updated['stories.json']})
    updated['news-archive.json'] = sorted(archive.values(), key=lambda x: x.get('published_at') or '', reverse=True)
    # Keep links to authored reports out of the news reader and its search.
    groups = updated.get('press-source-stories.json', {})
    updated['press-source-stories.json'] = {
        name: [row for row in rows if str(row.get('id')) not in editorial]
        for name, rows in groups.items() if isinstance(rows, list)}

def refresh():
    with gzip.open(SNAPSHOT, 'rt', encoding='utf-8') as source:
        previous = json.load(source)
    # Each Actions checkout starts from the same seed. Carry the deployed
    # archive forward so yesterday's links do not disappear on the next run.
    try:
        deployed = fetch_url(LIVE_SNAPSHOT)
        previous.update({key: value for key, value in deployed.items()
                         if key.startswith('story/') or key in LOCAL_KEYS})
    except Exception as exc:
        print('Could not restore deployed archive; retaining checked-in seed:', str(exc))
    keys = [key for key in previous if '/' not in key and key not in LOCAL_KEYS]
    keys += ['story-permalinks.json', 'editorial-archive.json', 'news-destinations.json']
    keys = list(dict.fromkeys(keys))
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
    editorial = dict(previous.get('pendar-reports.json', {}))
    editorial.update(updated.get('news-destinations.json', {}).get('editorial', {}))
    for row in updated.get('editorial-archive.json', {}).get('reports', []):
        if row.get('id'):
            editorial.setdefault(str(row['id']), 'https://pendar.io/story/' + str(row['id']) + '/')
    try:
        exported = fetch('news-export.json.gz')
        assert exported.get('version') == 1 and isinstance(exported.get('stories'), dict), 'Invalid news export'
        for sid, row in exported['stories'].items():
            assert isinstance(row, dict) and row.get('id') == sid, 'Invalid archived story'
            updated['story/' + sid + '.json'] = row
        editorial.update(exported.get('editorial', {}))
    except Exception as exc:
        # Bootstrap before Pendar's export is first published. Import every
        # discoverable legacy detail, not only the latest sixty headlines.
        errors['news-export.json.gz'] = str(exc)
        ids = {str(row['id']) for rows in updated.get('press-source-stories.json', {}).values()
               if isinstance(rows, list) for row in rows if row.get('id')}
        missing = ['story/' + sid + '.json' for sid in ids
                   if sid not in editorial and 'story/' + sid + '.json' not in updated]
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(fetch, key): key for key in missing}
            for future in concurrent.futures.as_completed(futures):
                key = futures[future]
                try:
                    row = future.result()
                    assert isinstance(row, dict) and key == 'story/' + str(row.get('id')) + '.json'
                    updated[key] = row
                except Exception as archive_error:
                    errors[key] = str(archive_error)
    details = ['story/' + str(row['id']) + '.json' for row in stories]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for key, value in zip(details, pool.map(fetch, details)):
            assert isinstance(value, dict) and value.get('id'), 'Invalid story detail: ' + key
            updated[key] = value
    partition_news(updated, editorial)
    updated['meta.json'] = dict(updated['meta.json'], count=len(updated['stories.json']))
    updated['snapshot-health.json'] = {'generated_at': datetime.now(timezone.utc).isoformat(), 'upstream_built_iso': updated['meta.json']['built_iso'], 'story_count': len(updated['stories.json']), 'archive_count': len(updated['news-archive.json']), 'pendar_reports': len(editorial), 'optional_source_errors': errors}
    payload = json.dumps(updated, ensure_ascii=False, separators=(',', ':')).encode()
    temporary = SNAPSHOT.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(payload, mtime=0))
    temporary.replace(SNAPSHOT)
    print(json.dumps(updated['snapshot-health.json'], ensure_ascii=False))

if __name__ == '__main__':
    refresh()
