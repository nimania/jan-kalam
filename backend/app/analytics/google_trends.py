"""Best-effort Google Trends overlay (EXPERIMENTAL).

Google Trends has no free official API. We use the unofficial `pytrends` library
at build time (the GitHub Action runs outside Iran, so it can reach Google). This
is fragile: Google rate-limits and occasionally blocks it. EVERY failure here is
swallowed and returns {} — the site then simply shows our own trend without the
Google comparison line. It must never break the build.

Returns, per topic slug, Google's relative-interest series (0–100) for Iran over
the last 7 days, aligned to daily points so it can overlay our own daily curve.
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("google_trends")


def fetch(topic_terms: list[tuple[str, str]], *, geo: str = "IR") -> dict:
    """topic_terms: list of (slug, persian_search_term). At most 5 are queried
    (pytrends' per-request limit). Returns {slug: {"term", "points":[{d,v}]}}."""
    terms = topic_terms[:5]
    if not terms:
        return {}
    try:
        from pytrends.request import TrendReq
    except Exception as e:  # library not installed
        logger.info("pytrends unavailable: %s", e)
        return {}
    try:
        pt = TrendReq(hl="fa-IR", tz=-210, timeout=(6, 14))  # tz -210 min = UTC+3:30
        kw = [t for _, t in terms]
        pt.build_payload(kw, timeframe="now 7-d", geo=geo)
        df = pt.interest_over_time()
        if df is None or df.empty:
            return {}
        out: dict = {}
        for slug, term in terms:
            if term not in df.columns:
                continue
            pts = []
            for ts, val in df[term].items():
                try:
                    pts.append({"d": ts.isoformat(), "v": int(val)})
                except Exception:
                    continue
            if pts:
                out[slug] = {"term": term, "points": pts}
        logger.info("google trends fetched for %d topics", len(out))
        return out
    except Exception as e:
        logger.warning("google trends fetch failed (ignored): %s", e)
        return {}
