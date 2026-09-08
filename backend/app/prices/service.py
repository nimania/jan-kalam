"""Live market prices for «بورس اخبار» — dollar, euro, gold, coins, crypto.

Source: tgju's public, keyless JSON (call.tgju.org/ajax.json), widely used and
free. Values come in Rial (with thousands separators); we convert the Rial ones
to Toman (÷10, how Iranians read them) and leave global quotes (ounce, BTC) in
USD. Everything is best-effort: on any failure we return [] and the price board
simply hides — never blocks the build.
"""
from __future__ import annotations

import httpx

from app.core.logging import get_logger

logger = get_logger("prices")

URL = "https://call.tgju.org/ajax.json"

# label, candidate keys (first present wins), unit, rial→toman?
_ITEMS = [
    ("دلار آمریکا", ["price_dollar_rl"], "تومان", True),
    ("یورو", ["price_eur"], "تومان", True),
    ("پوند", ["price_gbp"], "تومان", True),
    ("لیر ترکیه", ["price_try"], "تومان", True),
    ("درهم امارات", ["price_aed"], "تومان", True),
    ("سکه امامی", ["sekee", "sekee_new"], "تومان", True),
    ("نیم‌سکه", ["nim"], "تومان", True),
    ("ربع‌سکه", ["rob"], "تومان", True),
    ("مثقال طلا", ["mesghal"], "تومان", True),
    ("اونس جهانی طلا", ["ons"], "دلار", False),
]


def _num(s) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_prices(timeout: float = 20.0) -> list[dict]:
    """Return [{label_fa, value, unit_fa, dp, dir}] or [] on any failure."""
    try:
        resp = httpx.get(URL, timeout=timeout,
                         headers={"user-agent": "JanKalam/1.0"})
        resp.raise_for_status()
        cur = resp.json().get("current", {})
    except Exception as exc:
        logger.warning("could not fetch prices: %s", exc)
        return []

    out: list[dict] = []
    for label, keys, unit, to_toman in _ITEMS:
        node = None
        for k in keys:
            if k in cur:
                node = cur[k]
                break
        if not node:
            continue
        val = _num(node.get("p"))
        if val is None:
            continue
        if to_toman:
            val = round(val / 10)
        dt = node.get("dt", "")
        direction = "up" if dt == "high" else "down" if dt == "low" else "flat"
        out.append({
            "label_fa": label,
            "value": val,
            "unit_fa": unit,
            "dp": node.get("dp", 0),
            "dir": direction,
        })
    logger.info("fetched %d price rows", len(out))
    return out
