---
title: WinterRoad Road Damage API
emoji: ❄️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# WinterRoad AI Backend

FastAPI server for the WinterRoad budget-constrained road maintenance optimization system.
Team: WinterBorn | Authors: B K Kesavkrishnan, S Arun Kumar

- `GET /api/config` — Central configuration parameters (single source of truth).
- `POST /api/report` — Citizen report submission with single-shot location permission and privacy blurring.
- `GET /api/reports` — All saved reports (newest first). `GET /api/reports.csv` — CSV export.
- `POST /api/plan` — 0/1 knapsack municipal repair plan generator.
- `POST /api/reports/{id}/status` — Mark a report as repaired.
- `/docs` — Interactive OpenAPI documentation.

Run locally: `python -m uvicorn main:app --port 8000`, open http://127.0.0.1:8000
