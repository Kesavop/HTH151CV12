# WinterRoad: Multi-Page Web Architecture & Browser Verification Report

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Branch**: `winterroad-v2`  
**Execution Environment**: macOS (Chromium Headless via Playwright 1.63.0 / Python 3.13)  
**Date**: 2026-10-08  
**Backend Address**: `http://127.0.0.1:8000`  
**Artifact Results**: `results/browser_verification_results.json`  

---

## 1. Executive Summary

WinterRoad's web application was restructured from a monolithic single-page interface into a dedicated, modular **multi-page civic architecture** separating public citizen services from municipal engineering administration:
1. **Public Citizen Surfaces**:
   - `/`: Landing page introducing the municipal knapsack prioritization system with clear entry pathways.
   - `/report`: Single-shot defect photo upload with automated OpenCV YuNet privacy protection, location consent, and ticket receipt issuance.
   - `/track`: 4-stage progression stepper (`received` $\to$ `verified` $\to$ `scheduled` $\to$ `fixed`) exposing strictly sanitized data.
   - `/map`: Leaflet map displaying municipality-verified potholes and surface restorations with live civic counters.
2. **Municipal Admin Surfaces (Server-Side Authentication Enforced)**:
   - `/admin/login`: Salted PBKDF2 authentication with 60-second brute-force rate limiting.
   - `/admin`: Executive overview with KPIs and live road damage network map.
   - `/admin/reports`: Verification queue table, side-by-side photo inspection, GPS tamper detection, and triage actions (`Verify`, `Schedule`, `Fixed`, `Reject`).
   - `/admin/planner`: Budget knapsack slider, 4-strategy comparison, repair justifications, and printable work orders.
   - `/admin/research`: Computer vision benchmarks with explicit `REAL MEASUREMENT` and `SIMULATED DATA` badges.
   - `/admin/equity`: Ward funding allocations, spatial Gini index, price of fairness, and rolling repair horizons.
   - `/admin/about`: Team WinterBorn attribution, 2D severity proxy assumptions, limitations, and OSS licenses.

---

## 2. Server-Side Route Architecture & Security Controls

### 2.1 Route Mapping
| Route | Access Role | HTTP Response / Mechanism | Cache-Control Header |
|---|---|---|---|
| `/` | Public | Serves `backend/static/index.html` | Default |
| `/report` | Public | Serves `backend/static/report.html` | Default |
| `/track` | Public | Serves `backend/static/track.html` | Default |
| `/map` | Public | Serves `backend/static/map.html` | Default |
| `/admin/login` | Public / Guest | Serves `backend/static/admin/login.html` (Redirects to `/admin` if already logged in) | `no-cache, no-store, must-revalidate` |
| `/admin` | Admin | Serves `backend/static/admin/index.html` (HTTP 303 Redirect to `/admin/login` if unauthenticated) | `no-cache, no-store, must-revalidate` |
| `/admin/reports` | Admin | Serves `backend/static/admin/reports.html` (HTTP 303 Redirect if unauthenticated) | `no-cache, no-store, must-revalidate` |
| `/admin/planner` | Admin | Serves `backend/static/admin/planner.html` (HTTP 303 Redirect if unauthenticated) | `no-cache, no-store, must-revalidate` |
| `/admin/research` | Admin | Serves `backend/static/admin/research.html` (HTTP 303 Redirect if unauthenticated) | `no-cache, no-store, must-revalidate` |
| `/admin/equity` | Admin | Serves `backend/static/admin/equity.html` (HTTP 303 Redirect if unauthenticated) | `no-cache, no-store, must-revalidate` |
| `/admin/about` | Admin | Serves `backend/static/admin/about.html` (HTTP 303 Redirect if unauthenticated) | `no-cache, no-store, must-revalidate` |

### 2.2 Security Rules Enforced
1. **Server-Side Interception (Rule 1)**: Any direct navigation or link to `/admin/*` without a valid `winterroad_token` cookie triggers an immediate **HTTP 303 See Other** redirect to `/admin/login` on the server before any HTML or data is transmitted.
2. **Back-Button & Bfcache Invalidation**: All admin pages set `Cache-Control: no-cache, no-store, must-revalidate`. When an administrator clicks Logout, the session cookie is purged. Pressing the browser's "Back" button cannot load cached admin DOMs; the browser sends a new request to the server, receives HTTP 303, and lands safely at `/admin/login`.
3. **API Authorization**: All admin endpoints (`/api/reports`, `/api/plan`, `/api/admin/metrics`, `/api/reports.csv`) enforce `check_admin_auth()`, returning **HTTP 401 Unauthorized** when credentials are absent.
4. **Data Sanitization**: The citizen tracking endpoint (`/api/citizen/track/{ticket_code}`) never returns citizen names, notes, phone numbers, reviewer identities, or raw file paths.

---

## 3. End-to-End Playwright Headless Browser Test Results

The full test suite was executed against the live backend server using Playwright Chromium (`tests/test_frontend_e2e_playwright.py`).

```text
================ FINAL MULTI-PAGE VERIFICATION SUMMARY ================
Total Tests: 24 | Passed: 24 | Failed: 0
Execution Status: 100% SUCCESS
```

### Detailed Execution Matrix

| # | Test Name | Simulated Action / Verification | Real Measured Output | Result |
|:---:|:---|:---|:---|:---:|
| **1** | **Landing Page Load** | Opened Chromium at `http://127.0.0.1:8000/`. Checked title and uncaught errors. | Title: `'WinterRoad · Budget-Constrained Road Maintenance Prioritization'` | **PASS** |
| **2** | **Nav Link -> /report** | Clicked `.site-nav a[href='/report']` on landing page. Waited for URL update. | Navigated to: `http://127.0.0.1:8000/report` | **PASS** |
| **3** | **Nav Link -> /track** | Clicked `.site-nav a[href='/track']`. Waited for URL update. | Navigated to: `http://127.0.0.1:8000/track` | **PASS** |
| **4** | **Nav Link -> /map** | Clicked `.site-nav a[href='/map']`. Waited for URL update. | Navigated to: `http://127.0.0.1:8000/map` | **PASS** |
| **5** | **Nav Link -> /admin/login** | Clicked `.site-nav a[href='/admin/login']`. Waited for URL update. | Navigated to: `http://127.0.0.1:8000/admin/login` | **PASS** |
| **6** | **Hero Button -> /report** | Clicked hero CTA `Report Defect` on landing page. | Navigated to: `http://127.0.0.1:8000/report` | **PASS** |
| **7** | **Hero Button -> /admin/login** | Clicked hero CTA `Admin Login` on landing page. | Navigated to: `http://127.0.0.1:8000/admin/login` | **PASS** |
| **8** | **Citizen Defect Submission at /report** | Attached photo `20260924-225749-5b0a6b.jpg`, added citizen note, clicked submit. | `Generated Ticket Code: WR-DVCEB7` | **PASS** |
| **9** | **Citizen Ticket Stepper at /track** | Navigated to `/track?ticket=WR-DVCEB7`. Verified stepper and sanitized fields. | `Looked up: WR-DVCEB7, Status: RECEIVED, Type: Pothole` (Zero leaks) | **PASS** |
| **10** | **Public Verified Map at /map** | Navigated to `/map`. Intercepted call to `/api/citizen/verified-potholes`. | `Counters: Total=11, Verified=7, Fixed=6`, SVG defect markers rendered | **PASS** |
| **11** | **Public Pathway Security** | Audited all network calls made during public browsing for `/api/reports`. | `Admin route calls on public pages: 0` | **PASS** |
| **12** | **Server-Side Redirect: /admin** | Visited `http://127.0.0.1:8000/admin` in fresh unauthenticated session. | `Target: /admin -> Redirected to: http://127.0.0.1:8000/admin/login` | **PASS** |
| **13** | **Server-Side Redirect: /admin/reports** | Visited `http://127.0.0.1:8000/admin/reports` while logged out. | `Target: /admin/reports -> Redirected to: http://127.0.0.1:8000/admin/login` | **PASS** |
| **14** | **Unauthenticated API Returns 401** | Executed direct GET request to `/api/reports` without authentication. | `Status Code: 401, Detail: Authentication required` | **PASS** |
| **15** | **Admin Login & Redirect** | Submitted configured admin credentials (`admin` / `[ADMIN_PASSWORD from .env]`) at `/admin/login`. | `Redirected to: http://127.0.0.1:8000/admin` | **PASS** |
| **16** | **Admin Page 1: Overview** | Verified Executive Overview KPIs and live network geometry map. | Heading: `'EXECUTIVE OVERVIEW & DAMAGE MAP'` | **PASS** |
| **17** | **Admin Page 2: Verification Queue** | Visited `/admin/reports`. Inspected triage table with row data. | Heading: `'VERIFICATION QUEUE (11 OF 11 RECORDS)'` | **PASS** |
| **18** | **Admin Triage Action: Verify** | Clicked `Verify` button on report ticket row. Verified POST `/api/reports/{id}/status`. | `Row status updated to: VERIFIED` | **PASS** |
| **19** | **Admin Page 3: Planner** | Visited `/admin/planner`. Verified 4-strategy comparison and knapsack metrics. | `Optimal Risk Removed: 64.4%`, Repair justification schedule loaded | **PASS** |
| **20** | **Admin Page 4: Research** | Visited `/admin/research`. Checked detection mAP table and methodology. | Badges verified: `Real=True (REAL MEASUREMENT)`, `Simulated=True` | **PASS** |
| **21** | **Admin Page 5: Equity** | Visited `/admin/equity`. Checked spatial Gini index and multi-month rolling horizon. | Heading: `'WARD ALLOCATION & THE PRICE OF FAIRNESS'` | **PASS** |
| **22** | **Admin Page 6: About** | Visited `/admin/about`. Checked team attributions and open-source licenses. | Verified authors: `B K Kesavkrishnan, S Arun Kumar` | **PASS** |
| **23** | **Admin Logout & Cookie Purge** | Clicked `Logout` button in admin header. Verified cookie deletion. | `Target: /admin/login (Current: http://127.0.0.1:8000/admin/login)` | **PASS** |
| **24** | **Back-Button Protection** | Invoked browser `page.go_back()` following admin logout. | `URL after Back button: http://127.0.0.1:8000/admin/login` | **PASS** |

---

## 4. How to Reproduce

To rerun the full 24-test browser verification suite locally:
```bash
# Ensure virtual environment is active
.venv/bin/python tests/test_frontend_e2e_playwright.py
```
Test results will be validated and automatically saved to `results/browser_verification_results.json`.
