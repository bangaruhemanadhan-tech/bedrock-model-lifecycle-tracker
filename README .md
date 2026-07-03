# AWS Bedrock Model Lifecycle Tracker

Scrapes the public AWS Bedrock model lifecycle page daily, detects what changed since the last run (new models, deprecations, EOL updates), and stores the results — with an alert hook for failures.

## Problem it solves

AWS regularly adds, deprecates, and retires Bedrock models. Tracking this manually means repeatedly re-checking documentation and missing changes until a customer or ticket flags it. This automates the check and surfaces exactly what changed, every run.

## How it works

1. Fetches the AWS Bedrock model lifecycle documentation page
2. Parses the model table (name, provider, status, EOL date)
3. Compares against the previous run's snapshot to detect additions/removals
4. Saves the full snapshot as JSON, a running history log, and a flat CSV
5. If scraping or parsing fails for any reason, triggers an alert instead of failing silently

This mirrors a real production automation pattern: **scheduled scrape → diff → store → alert on failure** — the same shape used for daily monitoring jobs in an AWS support environment.

## Tech stack

Python 3, `requests`, `beautifulsoup4`. No external services required to run — the alert hook is a stub you can wire to email/Slack/a ticketing API.

## How to run it

```bash
pip install -r requirements.txt

# Run against the live AWS docs page
python lifecycle_tracker.py

# Run in demo mode against local sample data (no network needed)
python lifecycle_tracker.py --demo
```

Outputs land in `output/`:
- `lifecycle_latest.json` — most recent snapshot + detected changes
- `lifecycle_history.json` — full run history
- `model_lifecycle.csv` — flat table for spreadsheet use

## Example output

```
New models detected: ['Claude 3.5 Sonnet v2', 'Titan Text G1 - Express']
Models no longer listed: ['Claude Instant']
Lifecycle tracker run completed successfully
```

## What I'd build next

- Deploy on a Lambda + EventBridge daily schedule with S3 as the storage backend
- Wire the alert hook to Slack or email
- Add a small dashboard to visualize lifecycle trends over time

---
*Note: this project is an original, from-scratch implementation built to demonstrate the automation pattern — it targets only publicly documented AWS pages and contains no proprietary code or internal systems.*
