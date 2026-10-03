"""Build only the weather + air-quality JSON used by the static site."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.weather.service import fetch_weather


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="public/data/weather.json")
    args = p.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = fetch_weather()
    out.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    official = sum(1 for x in rows if x.get("aqi") is not None and not x.get("air_estimated"))
    estimated = sum(1 for x in rows if x.get("aqi") is not None and x.get("air_estimated"))
    print(f"weather: {len(rows)} cities; air official={official}, estimated={estimated}")


if __name__ == "__main__":
    main()
