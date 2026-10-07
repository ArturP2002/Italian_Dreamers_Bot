# Italian Dreamers Mini App

Monorepo scaffold (Phase 0): FastAPI + aiogram bot + React Mini App.

## Structure

- `backend/` — FastAPI, SQLAlchemy models, Alembic, Telegram `initData` auth
- `bot/` — aiogram 3: `/start` opens WebApp (no FSM questionnaire)
- `web/` — React + Vite Mini App (user + admin routes, role gate)

## Quick start

```bash
cp .env.example .env
# set BOT_TOKEN, ADMIN_TELEGRAM_IDS, WEBAPP_URL

docker compose up --build
```

- API: http://localhost:8000/health
- Mini App: http://localhost:5173
- Postgres: localhost:5432

Local web without Docker:

```bash
cd web && npm install && npm run dev
```

Local API:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# DATABASE_URL + BOT_TOKEN in ../.env or environment
alembic upgrade head
uvicorn app.main:app --reload
```

## Design

Tokens from `italian dreamers miniapp.pdf`: graphite `#1A1511`, cream `#EFE4D2`, champagne `#C8A774`, Bebas Neue / Playfair Display / Poppins. Loading screen uses `Loading_Photo.jpg` with **Войти** / **Entra**.
