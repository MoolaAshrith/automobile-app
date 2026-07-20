# Floor Control — Automobile Manufacturing Tracker

A Flask web app for tracking **production line status** (an andon-style board) and
**parts inventory** on a factory floor. Uses SQLite, so there's no external database to set up.

## Features

- **Andon board dashboard** — see every production line's status (running / idle /
  maintenance / stopped), output vs. target, and change status with one click.
- **Parts inventory** — add/edit/delete parts, quick +1/−1 stock adjustments, search,
  and automatic reorder alerts for anything at or below its reorder level.
- **JSON API** at `/api/status` for hooking into other dashboards or scripts.
- Seeded with sample lines and parts on first run so you can see it working immediately.

## Run it locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Visit **http://localhost:5000**. The SQLite database is created automatically at
`instance/factory.db` the first time you run it, pre-loaded with sample lines and parts.
Delete that file if you want to start from empty.

## Project structure

```
factory-track/
├── app.py                 # Flask app: models, routes, API
├── requirements.txt
├── instance/
│   └── factory.db         # SQLite database (auto-created)
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── dashboard.html      # Andon board + reorder alerts
    ├── parts.html          # Parts inventory table
    ├── part_form.html      # Add/edit part
    ├── lines.html          # Production lines table
    └── line_form.html      # Add/edit line
```

## Deploying

### Option A — any VM / server with Python
```bash
pip install -r requirements.txt
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```
Put it behind Nginx/Caddy for TLS, or a process manager (systemd, supervisor) to keep
it running.

### Option B — Docker
Create a `Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```
Then:
```bash
docker build -t floor-control .
docker run -p 8000:8000 -v $(pwd)/instance:/app/instance floor-control
```
The volume mount keeps your SQLite data across container restarts.

### Option C — PaaS (Render, Railway, Fly.io, Heroku-style platforms)
Push this repo, set the start command to:
```
gunicorn -w 4 -b 0.0.0.0:$PORT app:app
```
Set a real `SECRET_KEY` environment variable in production (the app falls back to a
dev key otherwise). If your platform doesn't persist local disk, swap SQLite for a
managed Postgres by changing `SQLALCHEMY_DATABASE_URI` and adding `psycopg2-binary`
to `requirements.txt` — the model code doesn't need to change.

## Notes on scaling this up

- **Multiple users editing at once**: SQLite is fine for a single-plant, low-concurrency
  setup. For multiple simultaneous editors or multi-plant deployments, switch to Postgres.
- **Authentication**: there's no login system yet — add Flask-Login if this needs to be
  restricted to specific staff.
- **Audit trail**: `updated_at` timestamps exist on both models; if you need a full
  history of status changes or stock movements, add a separate `Event` log table that
  records old → new values.
