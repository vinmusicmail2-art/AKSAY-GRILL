# Аксай Гриль — Restaurant Web Application

## Overview
A Flask-based web application for the Aksay Grill restaurant in Aksay, Russia. It provides a public-facing website for viewing menus and submitting service requests, plus a comprehensive admin panel for managing orders and site content.

## Tech Stack
- **Framework:** Flask (Python 3.11)
- **Database:** SQLite (via SQLAlchemy ORM), stored in `data.db`
- **Auth:** Flask-Login (custom username/password for admin)
- **Forms:** Flask-WTF / WTForms with CSRF protection
- **Email:** smtplib via environment variables (optional, gracefully skipped if unconfigured)
- **Server:** Gunicorn (production/dev)

## Project Structure
- `main.py` — Entry point, imports app from app.py
- `app.py` — All Flask routes (public + admin), app factory, DB init
- `models.py` — SQLAlchemy models: Admin, LoginLog, BusinessLunchOrder, CateringRequest, HallReservation, SiteText, DeliveryOrder
- `db.py` — SQLAlchemy engine/session setup (SQLite)
- `forms.py` — WTForms form definitions
- `mailer.py` — Background email notifications via SMTP
- `templates/` — Jinja2 templates (public pages + admin panel)
- `assets/` — Static files (images, CSS, JS)

## Running the App
The app runs via gunicorn on port 5000:
```
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## Environment Variables / Secrets
- `SESSION_SECRET` — Flask session secret key (required)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — Optional SMTP config for email notifications

## Admin Panel
- `/admin/setup` — One-time first admin creation (only available when no admins exist)
- `/admin/login` — Admin login
- `/admin` — Dashboard with pending order counts and login log
- `/admin/business-lunches` — Manage business lunch orders
- `/admin/catering` — Manage catering requests
- `/admin/events` — Manage hall reservation requests
- `/admin/delivery-orders` — Manage delivery orders from homepage cart
- `/admin/texts` — Edit site content/texts
- `/admin/email-settings` — Configure SMTP email notifications

## Public Pages
- `/` — Main restaurant homepage with cart, checkout, reviews carousel
- `/business-lunch` — Business lunch menu and order form
- `/catering` — Catering service request form
- `/events` — Hall reservation form
- `/privacy.html` — Privacy policy

## API Endpoints
- `POST /order/delivery` — Submit delivery order (JSON, CSRF-exempt); saves to DeliveryOrder table

## Homepage Features
- **Cart / Drawer** — All menu sections (incl. mangal) have "Add to order" buttons; cart drawer opens from hero CTA or floating button
- **Checkout modal** — Collects name, phone, email, address, comment; POSTs JSON to `/order/delivery`
- **Reviews section** (`#reviews`) — 10 hardcoded reviews in a carousel (3-up desktop / 1-up mobile), arrow nav + dot indicators + scroll-to-top button
- **Hero CTA** — "Заказать доставку" opens cart, "Посмотреть отзывы" scrolls to `#reviews`

## Layout Notes
- Left sidebar: `fixed`, `w-1/4` — all content areas use `md:ml-[25%]` to offset
- `TEMPLATES_AUTO_RELOAD = True` in app.py — Jinja2 always reads templates fresh (no caching with gunicorn)
- `html { overflow-x: hidden; overflow-y: scroll }` — prevents horizontal shift from carousel and always reserves vertical scrollbar space
- Scroll lock for modals uses `lockScroll()`/`unlockScroll()` with `padding-right` compensation to prevent layout shift when scrollbar appears/disappears
