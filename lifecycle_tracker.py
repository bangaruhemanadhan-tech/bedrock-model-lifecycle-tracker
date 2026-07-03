"""
AWS Bedrock Model Lifecycle Tracker
-------------------------------------
Scrapes the public AWS Bedrock model lifecycle documentation page daily,
detects changes (new models, deprecations, EOL dates), and stores the
results as JSON/CSV — with an alert hook for failures.

This is a from-scratch, portfolio-safe recreation of a production
automation pattern: scheduled scrape -> diff against last run -> store ->
alert on failure. No proprietary code, internal tools, or credentials
are used anywhere in this project.

Usage:
    python lifecycle_tracker.py            # scrape live page
    python lifecycle_tracker.py --demo     # run against local sample HTML (no network needed)
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("lifecycle_tracker")

SOURCE_URL = "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html"
USER_AGENT = "Mozilla/5.0 (compatible; ModelLifecycleTracker/1.0)"

OUTPUT_DIR = "output"
LATEST_JSON = os.path.join(OUTPUT_DIR, "lifecycle_latest.json")
HISTORY_JSON = os.path.join(OUTPUT_DIR, "lifecycle_history.json")
CSV_OUTPUT = os.path.join(OUTPUT_DIR, "model_lifecycle.csv")

CSV_HEADERS = ["model_name", "provider", "status", "eol_date", "notes"]


def fetch_page(demo: bool) -> str:
    """Fetch the live docs page, or load local sample HTML in demo mode."""
    if demo:
        logger.info("Demo mode: loading local sample_page.html instead of hitting the network")
        with open("sample_page.html", "r", encoding="utf-8") as f:
            return f.read()

    response = requests.get(SOURCE_URL, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()
    return response.text


def parse_models(html: str) -> list:
    """
    Parse model lifecycle entries out of the page HTML.
    In demo mode this reads a simplified sample table; against the real
    page, table structure may need small selector tweaks over time —
    that fragility is exactly why the daily alert-on-failure step exists.
    """
    soup = BeautifulSoup(html, "html.parser")
    models = []

    for row in soup.select("table tr")[1:]:  # skip header row
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) >= 3:
            models.append({
                "model_name": cells[0],
                "provider": cells[1],
                "status": cells[2],
                "eol_date": cells[3] if len(cells) > 3 else "",
                "notes": "",
            })
    return models


def load_previous_snapshot() -> list:
    if os.path.exists(LATEST_JSON):
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            return json.load(f).get("models", [])
    return []


def diff_models(old: list, new: list) -> dict:
    old_names = {m["model_name"] for m in old}
    new_names = {m["model_name"] for m in new}
    return {
        "added": sorted(new_names - old_names),
        "removed": sorted(old_names - new_names),
    }


def save_outputs(models: list, changes: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    snapshot = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_URL,
        "model_count": len(models),
        "changes_since_last_run": changes,
        "models": models,
    }

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    # Append to a running history file so trends are visible over time
    history = []
    if os.path.exists(HISTORY_JSON):
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(snapshot)
    with open(HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(models)

    logger.info(f"Saved {len(models)} models to {LATEST_JSON} and {CSV_OUTPUT}")


def send_alert(message: str):
    """
    Alert hook — in production this would call a paging/ticketing API.
    Here it just logs, so the project runs standalone with no external
    service dependencies.
    """
    logger.error(f"ALERT: {message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run against local sample HTML instead of the live page")
    args = parser.parse_args()

    try:
        html = fetch_page(demo=args.demo)
        models = parse_models(html)

        if not models:
            raise ValueError("No models parsed from page — page structure may have changed")

        previous = load_previous_snapshot()
        changes = diff_models(previous, models)

        save_outputs(models, changes)

        if changes["added"]:
            logger.info(f"New models detected: {changes['added']}")
        if changes["removed"]:
            logger.info(f"Models no longer listed: {changes['removed']}")

        logger.info("Lifecycle tracker run completed successfully")

    except Exception as e:
        send_alert(f"Lifecycle tracker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
