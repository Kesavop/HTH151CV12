---
title: Gladiators Road Damage API
emoji: 🚧
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Gladiators AI backend

FastAPI server for the Gladiators road-repair project.

- `POST /api/report` — send a road photo (+ optional `lat`, `lon`). YOLOv8 finds the damage (D00, D10, D20, D40), and the report is saved in the SQLite database `data/reports.db`.
- `GET /api/reports` — every saved report. `GET /api/reports.csv` — the same as CSV.
- `POST /api/reports/{id}/status` — `{"status": "repaired"}` marks a report as fixed.
- `/docs` — try every API in the browser.

Run on a laptop: `python -m uvicorn main:app --port 8000`, then open http://127.0.0.1:8000

The top of this file is the settings block Hugging Face Spaces reads (Docker, port 7860).
