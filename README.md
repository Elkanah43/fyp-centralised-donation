# LifeBridge — Centralised Blood & Organ Donation Platform

A Django-backed operations console for coordinating blood and organ donation:
donor registry, blood bank inventory, recipient waitlists, compatibility
matching, network alerts, and appointment scheduling.

## Stack

- **Backend**: Django 6, SQLite (swappable), JSON API under `/api/`
- **Frontend**: Vanilla JS single-page console served by Django templates,
  static assets via WhiteNoise
- **Deployment**: Gunicorn + WhiteNoise (see `Procfile`), 12-factor env config

## Quick start (development)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Create a user account, then open http://127.0.0.1:8000/ and sign in:

```bash
python manage.py createsuperuser
```

Demo data is seeded automatically on first load (demo mode is on by default
in development).

## Authentication

The console and every API endpoint require a signed-in user. Anonymous
visitors are redirected to `/login/`; anonymous API calls receive `401`.
Accounts are created by an administrator (`createsuperuser`, or via the
Django admin at `/admin/`). There is no self-service signup by design —
this is an internal operations tool.

## Running tests

```bash
python manage.py test
```

## API

All mutating endpoints require the CSRF token (sent automatically by the
frontend via the `X-CSRFToken` header).

| Endpoint             | Method | Purpose                                   |
| -------------------- | ------ | ----------------------------------------- |
| `/api/state/`        | GET    | Full application state                    |
| `/api/donors/`       | POST   | Register a donor                          |
| `/api/cases/`        | POST   | Create a recipient case (+ alert)         |
| `/api/appointments/` | POST   | Schedule an appointment                   |
| `/api/inventory/`    | POST   | Adjust blood stock (`blood_type`, `delta`)|
| `/api/alerts/`       | POST   | Create a network alert                    |
| `/api/reset/`        | POST   | Reset to demo data (demo mode only)       |

Validation errors return `400` with `{"errors": {field: message}}`.

## Production deployment

1. Copy `.env.example` and set real values — at minimum:
   - `DJANGO_SECRET_KEY` (required; the app refuses to boot without it when
     `DJANGO_DEBUG=0`)
   - `DJANGO_DEBUG=0`
   - `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`
   - `DEMO_MODE=0` (disables sample data seeding and the public reset endpoint)
2. Install and collect static files:
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
3. Serve with Gunicorn (Linux):
   ```bash
   gunicorn donation_backend.wsgi
   ```
   On Windows, use `waitress` instead: `pip install waitress` then
   `waitress-serve donation_backend.wsgi:application`.

With `DJANGO_DEBUG=0` the app enables HTTPS redirect, HSTS, secure cookies,
clickjacking protection, and hashed/compressed static files. Verify with:

```bash
python manage.py check --deploy
```

### Database

SQLite is the default and is adequate for a single-instance MVP. For
multi-instance or higher-write deployments, point `DATABASES` at
PostgreSQL and add `psycopg[binary]` to requirements.

## Project layout

```
donation_backend/   Django project (settings, urls, wsgi/asgi)
donation/           App: models, API views, tests
templates/          index.html (SPA shell), robots.txt, sitemap.xml
static/             css/, js/, site.webmanifest
```
