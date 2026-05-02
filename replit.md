# Аксай Гриль — Restaurant Web Application

## Overview
Flask-веб-приложение для ресторана «Аксай Гриль» (г. Аксай, Ростовская область).
Публичный сайт + полнофункциональная админ-панель для управления заявками и контентом.

## Tech Stack
- **Framework:** Flask (Python 3.11)
- **Database:** SQLite (via SQLAlchemy ORM, `SessionLocal` pattern), файл `data.db`
- **Auth:** Flask-Login (username/password, bcrypt), только для администраторов
- **Forms:** Flask-WTF / WTForms + CSRFProtect (все формы защищены)
- **Email:** smtplib (фоновые треды), настраивается через env vars или БД
- **Server:** Gunicorn (2 workers × 2 threads, порт 5000)
- **CSS:** Tailwind CSS (build → `assets/css/main.css`)
- **Compression:** flask-compress (gzip)

## Architecture Map (top-down)

```
main.py                  → точка входа (from app import app)
app.py                   → Flask app factory + bootstrap
  ├── db.py              → SQLAlchemy engine / SessionLocal / Base (SQLite)
  ├── models.py          → все ORM-модели + константы + seed-данные (~925 строк)
  ├── forms.py           → WTForms-формы (Login, Setup, BusinessLunch, Catering, Hall)
  ├── routes_public.py   → публичные маршруты (~360 строк)
  ├── routes_admin.py    → маршруты админки (~1611 строк)
  ├── mailer.py          → SMTP-уведомления + форматировщики писем (~560 строк)
  └── login_archive.py   → CSV-архив входов + email при входе (~236 строк)
```

## Project Structure
- `main.py` — точка входа, импортирует `app` из `app.py`
- `app.py` — Flask-приложение, расширения (CSRF, LoginManager, Compress), `init_db()`, хелперы `_client_ip`, `_safe_referrer`, `_is_safe_next`; импортирует маршруты в конце
- `routes_public.py` — публичные маршруты: `/`, `/business-lunch`, `/catering`, `/events`, `/about`, `/privacy.html`, `/offer`, `/cookies`, `/uploads/<file>`, `/healthz`, `/order/delivery` (JSON), `/quick-request`, `/spasibo/*`
- `routes_admin.py` — все `/admin/*` маршруты
- `models.py` — модели: `Admin`, `LoginLog`, `SiteText`, `MenuCategory`, `MenuItem`, `DeliveryOrder`, `QuickRequest`, `BusinessLunchOrder`, `CateringRequest`, `HallReservation`; константы `BUSINESS_LUNCH_MENU`, `CATERING_FORMATS`, `EVENT_TYPES`, `SITE_TEXT_CATALOG`
- `db.py` — `engine`, `SessionLocal`, `Base`, `BASE_DIR`, `DB_PATH`
- `forms.py` — WTForms: `LoginForm`, `SetupForm`, `BusinessLunchOrderForm`, `CateringRequestForm`, `HallReservationForm`
- `mailer.py` — SMTP; приватные `_format_*_email()` + публичные `send_*_notification[_async]()` + `_guarded_send()` хелпер; `send_test_email`, `send_contact_question`, `smtp_status`
- `login_archive.py` — `archive_login[_async]()`, `send_login_notify_async()`, `is_setup_done()`, `save_settings()`

## Running the App
```
node_modules/.bin/tailwindcss -i assets/css/input.css -o assets/css/main.css --minify
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload --workers 2 --threads 2 --timeout 60 main:app
```

## Environment Variables / Secrets
- `SESSION_SECRET` — секретный ключ Flask-сессии (обязателен в продакшене; без него — предупреждение в логах)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — SMTP для e-mail уведомлений (опционально; пароль также может храниться в `site_texts.smtp_password`)

## Admin Panel Routes
| Маршрут | Описание |
|---|---|
| `/admin/setup` | Первичное создание администратора (только пока нет ни одного) |
| `/admin/login` | Вход в админку |
| `/admin` | Дашборд: счётчики новых заявок, лог входов |
| `/admin/business-lunches` | Управление заявками на бизнес-ланчи |
| `/admin/catering` | Управление заявками на кейтеринг |
| `/admin/events` | Управление бронированием зала |
| `/admin/delivery-orders` | Управление заказами доставки |
| `/admin/stats` | Статистика обработки по администраторам + CSV-экспорт |
| `/admin/journal` | Журнал действий (кто/когда/что обработал) + CSV-экспорт |
| `/admin/texts` | Редактор текстов сайта |
| `/admin/email-settings` | Настройки SMTP + тест отправки |
| `/admin/menu` | Управление меню (категории + блюда) |
| `/admin/admins` | Управление администраторами |
| `/admin/archive-setup` | Настройка CSV-архива входов |

## Public Pages
- `/` — главная страница: меню, корзина, быстрый заказ, отзывы, карта
- `/about` — о ресторане
- `/business-lunch` — форма заявки на бизнес-ланчи
- `/catering` — форма заявки на кейтеринг
- `/events` — форма бронирования зала
- `/privacy.html`, `/offer`, `/cookies` — юридические страницы

## API Endpoints
- `POST /order/delivery` — заказ из корзины (JSON body, CSRF-exempt)
- `POST /quick-request` — быстрая заявка на доставку (form POST)
- `POST /contact` — вопрос с контактной формы (возвращает JSON)
- `GET /healthz` — health-check (возвращает `{"status": "ok"}`)

## Key Patterns
- **Session pattern:** `session = SessionLocal(); try: ... finally: session.close()` — везде, нет Flask-SQLAlchemy `db.session`
- **Email pattern:** `_format_*_email(obj)` → `_guarded_send(format_fn, obj, base_url)` → `_send_smtp()` → фоновый тред через `_send_notification_async()`
- **Snapshot pattern:** перед запуском фонового треда из ORM-объекта создаётся dict-снимок, чтобы не передавать detached-объект в тред
- **Safe redirect:** `_safe_referrer(fallback)` — извлекает path?query из Referer, проверяет через `_is_safe_next()`
- **Admin filter:** все 4 детальных страницы поддерживают `?admin=username` фильтр по обработчику

## Homepage Features
- **Cart / Drawer** — кнопки «В корзину» на блюдах; корзина открывается по CTA
- **Checkout modal** — имя/телефон/email/адрес; POST JSON → `/order/delivery`
- **Quick Request modal** — «Оставить заявку»; POST form → `/quick-request`
- **Reviews carousel** — 10 отзывов, 3-up desktop / 1-up mobile, стрелки + точки

## Layout Notes
- Главная: левый сайдбар `fixed w-1/4`, контент `md:ml-[25%]`
- Публичные под-страницы: `base_public.html` (шапка + подвал)
- Иконки: `material-symbols-outlined` (НЕ `material-icons`)
- Шрифты: локальные (не Google Fonts)
- `TEMPLATES_AUTO_RELOAD = True` — Jinja2 перечитывает шаблоны при каждом запросе

## Security Notes
- CSRF: Flask-WTF на всех формах; только `/order/delivery` exempt (JSON API)
- Open redirect: `_safe_referrer()` + `_is_safe_next()` на всех редиректах
- Auth: bcrypt-хэши паролей; `@login_required` на всех `/admin/*` маршрутах
- IP: `_client_ip()` читает X-Forwarded-For (ProxyFix настроен)
- Latent risk: `load_user()` возвращает detached ORM-объект; безопасно пока у `Admin` нет lazy relationships

## Known Technical Debt
- Inline ALTER TABLE миграции в `app.py:init_db()` — SQLite-specific, не масштабируется; при росте схемы нужен Alembic
- `inject_site_texts()` context_processor открывает сессию БД на КАЖДЫЙ запрос
- `send_contact_question()` использует захардкоженный адрес `aksaygryl@mail.ru` вместо настраиваемого через БД
