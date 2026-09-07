# Inventory & Procurement Assistant

Chat assistant for an inventory and procurement system. Pick a role (Business Owner, Procurement Owner or Inventory Owner), ask a question in plain English, and get an answer with a chart where it helps.

Stack: Next.js (frontend), FastAPI (backend), LangGraph + OpenAI (agent), PostgreSQL on Railway (data).

## Setup

Backend (Python 3.11+):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend (Node 18+), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Credentials are already in `backend/.env` and `frontend/.env.local`.

## Tests

```bash
cd backend
pytest tests/test_safety.py     # permissions and SQL guard rails, offline
pytest tests/test_questions.py  # 18 real questions across the 3 roles, calls OpenAI + DB
```

## Notes

- Roles are chosen from a dropdown, there is no login. Access is controlled per table.
- Data changes (e.g. setting a minimum stock level) ask for a confirm click before saving.
- The data covers April to August 2026.
