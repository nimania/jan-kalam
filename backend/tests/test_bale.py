import json
from datetime import timezone

from app.ingestion.bale import parse_bale_channel
from app.models.enums import FeedType
from app.models.source import Source


def test_parse_bale_rsc_messages():
    messages = [{
        "rid": 123456,
        "date": 1760000000000,
        "viewCount": 10,
        "message": {"textMessage": {"text": "این یک متن تحلیلی نمونه برای آزمون ورودی بله است."}},
    }]
    blob = '0:{"messages":' + json.dumps(messages, ensure_ascii=False) + '}'
    encoded = json.dumps(blob, ensure_ascii=False)[1:-1]
    raw = '<script>self.__next_f.push([1,"' + encoded + '"])</script>'
    source = Source(
        name="چهره: نمونه", homepage_url="https://t.me/example",
        feed_url="https://t.me/s/example", feed_type=FeedType.telegram,
        language="fa",
    )
    rows = parse_bale_channel(raw, source, "example_bale")
    assert len(rows) == 1
    assert rows[0].article_url == "https://ble.ir/example_bale/123456"
    assert "متن تحلیلی" in rows[0].description
    assert rows[0].published_at.tzinfo == timezone.utc
