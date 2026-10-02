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
CRYPTO_URL = "https://api.coingecko.com/api/v3/coins/markets"
_CRYPTO = [
    ("bitcoin", "بیت‌کوین", "BTC"),
    ("ethereum", "اتریوم", "ETH"),
    ("tether", "تتر", "USDT"),
    ("binancecoin", "BNB", "BNB"),
    ("solana", "سولانا", "SOL"),
    ("ripple", "XRP", "XRP"),
    ("dogecoin", "دوج‌کوین", "DOGE"),
]

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
        dp = _num(node.get("dp")) or 0
        # TGJU exposes the percentage move; derive an approximate absolute
        # 24h move in the displayed unit so the compact strip can show both.
        prev = (val / (1 + dp / 100)) if dp and (1 + dp / 100) else val
        delta24 = round(val - prev)
        out.append({
            "label_fa": label, "value": val, "unit_fa": unit,
            "dp": dp, "dir": direction, "delta24": delta24,
        })
    logger.info("fetched %d price rows", len(out))
    return out


def fetch_crypto_prices(timeout: float = 20.0) -> list[dict]:
    """Top crypto reference prices in USD, with 24h change. Best-effort."""
    wanted = {coin_id: (label, symbol) for coin_id, label, symbol in _CRYPTO}
    try:
        resp = httpx.get(
            CRYPTO_URL,
            params={
                "vs_currency": "usd",
                "ids": ",".join(wanted),
                "price_change_percentage": "24h",
                "sparkline": "false",
            },
            timeout=timeout,
            headers={"user-agent": "JanKalam/1.0"},
        )
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:
        logger.warning("could not fetch crypto prices: %s", exc)
        return []

    found = {}
    for row in rows if isinstance(rows, list) else []:
        coin_id = row.get("id")
        if coin_id not in wanted:
            continue
        label, symbol = wanted[coin_id]
        price = _num(row.get("current_price"))
        change = _num(row.get("price_change_percentage_24h"))
        if price is None:
            continue
        found[coin_id] = {
            "id": coin_id, "label_fa": label, "symbol": symbol,
            "value": price, "unit_fa": "دلار",
            "dp": round(change or 0, 2),
            "dir": "up" if (change or 0) > 0 else "down" if (change or 0) < 0 else "flat",
            "market_cap": row.get("market_cap"),
            "volume_24h": row.get("total_volume"),
        }
    return [found[x[0]] for x in _CRYPTO if x[0] in found]
