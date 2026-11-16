# 🏋️ FitCoach: Workout Management System

A Persian (RTL) web platform for gym coaches and trainees: build workout programs, track weight/BMI, manage an exercise library, download programs as PDF, and administer everything from an admin panel.
Built with **Django**, with three separate panels: **Admin | Coach | Trainee**.

## ✨ Features

**Coach panel**
- Trainee management with automatic BMI calculation
- Personal + public exercise library (images/videos)
- Workout program builder (superset, tri-set, drop-set) with automatic archiving of previous programs
- Notifications and program requests

**Trainee panel**
- View the active program, request a new program, weight/BMI trend chart
- Download the program as PDF (via reportlab)

**Admin panel**
- Manage coaches and trainees, public exercises, activity log

**Technical**
- Dark/light theme, Add to Home Screen; online connection required (old offline caches are retired)
- Vazirmatn font, Font Awesome and Chart.js served locally (no CDN)
- Optional SMS sending via Melipayamak

## 🚀 Running Locally

Requirements: Python 3.10+

```bash
git clone <repo-url>
cd fitcoach

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then fill in the values
# For local development, set in .env: DJANGO_DEBUG=True

python manage.py migrate
python manage.py setup_fitcoach   # creates sample users (passwords are printed once)
python manage.py runserver
```

Then open http://127.0.0.1:8000

> If `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` must be set, otherwise the project will not start.

## ⚙️ Environment Variables

All are documented in `.env.example`: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, Melipayamak SMS settings, and `NUTRITION_ENABLED`.

Generate a SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 🧪 Tests

```bash
python manage.py collectstatic --noinput
python manage.py test
```

## 📦 Deployment

See [DEPLOY.md](DEPLOY.md) for the deployment guide.

### Online-only operation

Application pages require an internet connection and use `Cache-Control: no-store`.
After deploying, run `collectstatic` as usual. Keep `/sw.js` available: it replaces
previous offline workers, clears `fitcoach-*` caches, and unregisters itself.
Public pages and panels also load the cleanup script. Existing users need an
online visit to receive this update; already-open pages remain visible until
navigation or reload. Installing a home-screen shortcut does not enable offline use.

## 📁 Project Structure

```
fitcoach/       Django settings
accounts/       Users, trainee profile, activity log
coach/          Coach panel, workout and program models
trainee/        Trainee panel and PDF generation
admin_panel/    Admin panel
templates/      HTML templates
static/         CSS/JS/fonts/icons
media/          Uploaded files (not tracked in git)
```

## ⚠️ Security Notes

- Never commit the `.env` file or `db.sqlite3` (both are in `.gitignore`).
- Provide real passwords and the SECRET_KEY only through environment variables.
