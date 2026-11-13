#!/usr/bin/env python3
"""Recover current Jan Kalam news from Pendar's independently validated Actions artifact.

The public Pendar Pages deployment can be stale even when the independent
news collector succeeds. Never label old news fresh or discard archived stories.
"""
import gzip
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from refresh_snapshot import (ROOT, SNAPSHOT, LIVE_SNAPSHOT, fetch_url,
                              include_curated_news, partition_news)

PENDAR = "nimania/pendar"


def gh_json(path):
    command = ["gh", "api", f"repos/{PENDAR}/{path}"]
    result = subprocess.run(command, check=True, capture_output=True, text=True,
                            timeout=35)
    return json.loads(result.stdout)


def download_validated_artifact(workflow, artifact_name, destination):
    # Look up the latest successful run, never a cancelled or failed build.
    runs = gh_json(f"actions/workflows/{workflow}/runs?status=success&per_page=5")
    for run in runs.get("workflow_runs", []):
        artifacts = gh_json(f"actions/runs/{run['id']}/artifacts").get("artifacts", [])
        if not any(a.get("name") == artifact_name and not a.get("expired") for a in artifacts):
            continue
        command = ["gh", "run", "download", str(run["id"]), "--repo", PENDAR,
                   "--name", artifact_name, "--dir", str(destination)]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
        return run["id"]
    raise RuntimeError(f"No available successful {artifact_name} artifact")


def load_json(root, name):
    path = root / "data" / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_news(root):
    metadata = load_json(root, "meta.json")
    stories = load_json(root, "stories.json")
    assert isinstance(stories, list) and 1 <= len(stories) <= 60, "Invalid news count"
    built = datetime.fromisoformat(str(metadata["built_iso"]).replace("Z", "+00:00"))
    assert built.tzinfo is not None, "News timestamp lacks timezone"
    age = (datetime.now(timezone.utc) - built).total_seconds()
    assert -900 < age < 43200, f"Independent news is stale: {age / 3600:.1f} hours"
    for row in stories:
        assert isinstance(row, dict) and row.get("id") and row.get("headline_fa"), "Invalid news card"
        detail = load_json(root, "story/" + str(row["id"]) + ".json")
        assert isinstance(detail, dict) and str(detail.get("id")) == str(row["id"]), "Missing story details"
    return metadata, stories


def recover():
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as source:
        previous = json.load(source)
    try:
        deployed = fetch_url(LIVE_SNAPSHOT)
        if isinstance(deployed, dict):
            # Carry forward the entire last published snapshot, not just the
            # most recent sixty headlines and not just the seed in git.
            previous.update(deployed)
    except Exception as error:
        print("Could not read live archive; preserving versioned seed:", error)

    with tempfile.TemporaryDirectory(prefix="jankalam-recovery-") as tmp:
        root = Path(tmp) / "news"
        root.mkdir()
        run_id = download_validated_artifact("news-refresh.yml", "pendar-news-data", root)
        metadata, stories = validate_news(root)
        updated = dict(previous)
        # Merge current independently verified news into existing historical
        # stories. Do not replace unrelated periodical/book/figure datasets.
        for name in ("stories.json", "meta.json", "topics.json", "entities.json",
                     "trends.json", "stats.json", "press-stats.json",
                     "press-source-stories.json", "press-source-health.json",
                     "press-source-repair-queue.json", "factchecks.json",
                     "geo.json", "news-health.json", "editorial-archive.json"):
            path = root / "data" / name
            if path.is_file():
                updated[name] = json.loads(path.read_text(encoding="utf-8"))
        for row in stories:
            sid = str(row["id"])
            updated["story/" + sid + ".json"] = load_json(root, "story/" + sid + ".json")

        figures_run = None
        try:
            figures_root = Path(tmp) / "figures"
            figures_root.mkdir()
            figures_run = download_validated_artifact("figures-refresh.yml",
                                                       "pendar-figures-data", figures_root)
            figures = load_json(figures_root, "figures.json")
            existing = updated.get("figures.json", {})
            assert isinstance(figures, dict) and len(figures.get("figures", [])) >= 100
            assert len(figures["figures"]) >= len(existing.get("figures", [])) * 0.8
            updated["figures.json"] = figures
            if (figures_root / "data/figures-health.json").is_file():
                updated["figures-health.json"] = load_json(figures_root, "figures-health.json")
        except Exception as error:
            print("Figure artifact not available; preserving existing figure index:", error)

        # Respect Pendar's editorial-report ownership and keep confirmed
        # independent curated stories on Jan Kalam.
        editorial = dict(previous.get("pendar-reports.json", {}))
        editorial.update(updated.get("news-destinations.json", {}).get("editorial", {}))
        for row in updated.get("editorial-archive.json", {}).get("reports", []):
            if isinstance(row, dict) and row.get("id"):
                sid = str(row["id"])
                editorial.setdefault(sid, "https://pendar.io/story/" + sid + "/")
        include_curated_news(updated)
        partition_news(updated, editorial)
        updated["meta.json"] = dict(metadata, count=len(updated["stories.json"]))
        updated["snapshot-health.json"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "upstream_built_iso": metadata["built_iso"],
            "story_count": len(updated["stories.json"]),
            "archive_count": len(updated["news-archive.json"]),
            "pendar_reports": len(editorial),
            "source": "pendar-independent-actions-artifact",
            "news_run_id": run_id,
            "figures_run_id": figures_run,
            "notice": "Unrelated modules retain the last published archive until their source pipelines recover.",
        }
        payload = json.dumps(updated, ensure_ascii=False, separators=(",", ":")).encode()
        temporary = SNAPSHOT.with_suffix(".tmp")
        temporary.write_bytes(gzip.compress(payload, mtime=0))
        temporary.replace(SNAPSHOT)
        print(json.dumps(updated["snapshot-health.json"], ensure_ascii=False))


if __name__ == "__main__":
    recover()
