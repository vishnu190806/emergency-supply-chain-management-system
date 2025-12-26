# 🚚 ESCM Priority Delivery Console

Smart, priority‑based dispatch system for disaster relief supplies.  
FastAPI backend + cinematic dark dashboard frontend.

---

## 💡 What it does

In a disaster, not all requests are equal.

This app runs a **priority queue** for supply requests instead of simple FIFO:

- ⚕️ **Medical kits** and expiring items are boosted
- 💧 **Water / food** get higher base scores than blankets/tarpaulins
- ⏱️ **Waiting time** increases priority over time
- 📍 **Closer camps** get a small bump so trucks can clear them quickly

The console always **dispatches the highest‑priority request next**.

---

## 🧱 Tech stack

- **Backend:** Python, FastAPI, Uvicorn, `heapq` priority queue
- **Frontend:** HTML, CSS, vanilla JS (no framework)
- **Extras:** CSV import + small simulation script to compare FIFO vs priority

---

## 🔌 API endpoints

All under `/api`:

- `POST /requests` – enqueue a new request
- `GET /queue` – current queue with computed priorities
- `POST /dispatch` – pop the next request to send
- `POST /import_csv` – load sample requests from a CSV (for demos)

---

## 🖥️ Dashboard features

- **Compose request**  
  Request ID, supply type dropdown, quantity, optional expiry (with date picker), distance, destination.

- **Live queue**

  - Table ordered by **score**, not arrival time
  - Priority chips: 🔴 High / 🔵 Medium / 🟢 Low
  - Auto‑updates on enqueue and dispatch

- **Footer goodies**
  - Total dispatched counter
  - “Queue mode: Priority‑based”
  - Two cards explaining:
    - Base scores per supply type
    - Dynamic boosts (expiry, wait, distance)

Fully responsive: 2‑column layout on desktop, stacked on mobile.

---

## ▶️ How to run

**Backend**

from project root
python -m venv venv
source venv/bin/activate # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py

API at http://127.0.0.1:8000

Make sure the URL shown in the top‑right of the UI matches your API (`http://127.0.0.1:8000`).

---

## 🎯 Why this project is cool

- Shows **real priority scheduling** (not just CRUD)
- Has a **polished, production‑style console UI**
- Great for talking about **trade‑offs** in logistics: fairness vs urgency, distance vs expiry, etc.

Feel free to fork it, tweak the scoring, or hook it to a real data source.

## Testing & Coverage

pytest --cov=backend/ --cov-report=html

- 13 automated tests for:
  - Delivery queue priority logic.
  - FastAPI API endpoints (`/api/requests`, `/api/queue`, `/api/dispatch`).
  - CSV import helper and CLI usage.
  - Priority vs FIFO simulation and metrics.
- **90% backend code coverage**, verified via `coverage.py` HTML report. [file:3][file:5][file:8][file:9][file:165]
