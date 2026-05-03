"""
Аксай Гриль — Flask backend.
Маршруты вынесены в routes_public.py и routes_admin.py.
"""
import logging
import os
from urllib.parse import urlparse

from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_compress import Compress
from flask_limiter import Limiter
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from db import Base, SessionLocal, engine

logging.basicConfig(level=logging.DEBUG)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="assets",
    static_url_path="/assets",
)
_secret_key = os.environ.get("SESSION_SECRET") or os.environ.get("SECRET_KEY")
if not _secret_key:
    logging.getLogger(__name__).warning(
        "SESSION_SECRET не задан — используется небезопасный ключ. "
        "Установите переменную окружения SESSION_SECRET в продакшене."
    )
app.secret_key = _secret_key or "dev-secret-change-me"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["COMPRESS_ALGORITHM"] = "gzip"
app.config["COMPRESS_LEVEL"] = 6
app.config["COMPRESS_MIN_SIZE"] = 500
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

Compress(app)

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Сначала войдите в админку."
login_manager.login_message_category = "warning"


def init_db() -> None:
    """Создать таблицы, применить inline-миграции ALTER TABLE и засеять начальные данные.

    Вызывается один раз при старте приложения внутри ``app.app_context()``.
    SQLite-specific PRAGMA-миграции выполняются вручную, т.к. Alembic не используется.
    """
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine, checkfirst=True)

    with engine.begin() as conn:
        try:
            cols = {row[1] for row in conn.exec_driver_sql(
                "PRAGMA table_info(business_lunch_orders)").fetchall()}
            for col, definition in (
                ("is_processed", "BOOLEAN NOT NULL DEFAULT 0"),
                ("processed_at",  "DATETIME"),
                ("processed_by",  "VARCHAR(64)"),
            ):
                if col not in cols:
                    conn.exec_driver_sql(
                        f"ALTER TABLE business_lunch_orders ADD COLUMN {col} {definition}")
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "business_lunch_orders migration skipped: %s", exc)

        try:
            cols = {row[1] for row in conn.exec_driver_sql(
                "PRAGMA table_info(menu_categories)").fetchall()}
            if cols:
                for col, definition in (
                    ("show_in_nav", "BOOLEAN NOT NULL DEFAULT 1"),
                    ("description", "TEXT NOT NULL DEFAULT ''"),
                ):
                    if col not in cols:
                        conn.exec_driver_sql(
                            f"ALTER TABLE menu_categories ADD COLUMN {col} {definition}")
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "menu_categories migration skipped: %s", exc)

    with engine.begin() as conn:
        try:
            cols = {row[1] for row in conn.exec_driver_sql(
                "PRAGMA table_info(quick_requests)").fetchall()}
            if cols:
                for col, definition in (
                    ("is_processed", "BOOLEAN NOT NULL DEFAULT 0"),
                    ("processed_at",  "DATETIME"),
                    ("processed_by",  "VARCHAR(64)"),
                ):
                    if col not in cols:
                        conn.exec_driver_sql(
                            f"ALTER TABLE quick_requests ADD COLUMN {col} {definition}")
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "quick_requests migration skipped: %s", exc)

    session = SessionLocal()
    try:
        models.seed_site_texts(session)
        models.seed_menu(session)
    finally:
        session.close()


_site_texts_cache = None
_site_texts_cache_time = None
_CACHE_TTL = 300


def get_cached_site_texts():
    """Получить site_texts с кэшированием (TTL 5 минут)."""
    from datetime import datetime
    from models import load_site_texts

    global _site_texts_cache, _site_texts_cache_time
    now = datetime.utcnow()

    if _site_texts_cache is None or _site_texts_cache_time is None or \
       (now - _site_texts_cache_time).total_seconds() > _CACHE_TTL:
        session = SessionLocal()
        try:
            _site_texts_cache = load_site_texts(session)
            _site_texts_cache_time = now
        finally:
            session.close()

    return _site_texts_cache


@app.context_processor
def inject_site_texts():
    """Внедрить словарь ``texts`` в контекст всех Jinja2-шаблонов.

    Позволяет любому шаблону обращаться к редактируемым текстам сайта
    через ``{{ texts.hero_title }}``, ``{{ texts.contact_phone }}`` и т.д.
    """
    return {"texts": get_cached_site_texts()}


@login_manager.user_loader
def load_user(user_id: str):
    """Загрузить администратора по ID для Flask-Login (вызывается на каждый запрос).

    Примечание: объект возвращается после закрытия сессии. Поскольку у ``Admin``
    нет ленивых relationship, DetachedInstanceError не возникает. При добавлении
    связей — переключить на ``expire_on_commit=False`` или ``make_transient``.
    """
    from models import Admin

    session = SessionLocal()
    try:
        return session.get(Admin, int(user_id))
    finally:
        session.close()


def _client_ip() -> str:
    """Вернуть IP клиента с учётом заголовка X-Forwarded-For от reverse-proxy."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

limiter = Limiter(
    key_func=_client_ip,
    app=app,
    storage_uri="memory://",
    default_limits=[],
)

# Лимиты, применяемые к публичным POST-роутам:
#   5 запросов в минуту И 30 запросов в час с одного IP.
FORM_RATE_LIMIT = "5 per minute; 30 per hour"


@app.errorhandler(429)
def _too_many_requests(e):
    """Обработчик превышения лимита запросов (HTTP 429).

    JSON-клиентам (fetch/AJAX) возвращает JSON-ошибку.
    Обычным браузерным запросам — flash-сообщение + редирект назад.
    """
    if request.is_json or request.path.startswith("/order/") or request.path == "/contact":
        return jsonify({"ok": False, "error": "Слишком много запросов. Попробуйте через минуту."}), 429
    flash("Слишком много попыток. Пожалуйста, подождите минуту и попробуйте снова.", "error")
    ref = request.referrer
    if ref:
        from urllib.parse import urlparse as _up
        p = _up(ref)
        safe = p.path + (("?" + p.query) if p.query else "")
        if safe.startswith("/"):
            return redirect(safe), 429
    return redirect(url_for("home")), 429


def _is_safe_next(target: str) -> bool:
    """Вернуть True, если ``target`` — безопасный локальный URL для редиректа.

    Защита от open redirect: разрешены только пути без схемы и домена.
    """
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith("/")


def _safe_referrer(fallback: str) -> str:
    """Вернуть путь из Referer-заголовка, если он безопасен, иначе ``fallback``.

    Извлекает только ``path?query`` из Referer, чтобы предотвратить
    open redirect через заголовок Referer.
    """
    ref = request.referrer or ""
    if not ref:
        return fallback
    parsed = urlparse(ref)
    path = parsed.path
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if _is_safe_next(path):
        return path
    return fallback


@app.after_request
def add_cache_headers(response):
    """Добавить Cache-Control: max-age=30d для статических ресурсов в /assets/.

    Шрифты, CSS, JS, изображения кэшируются на 30 дней браузером и CDN.
    """
    path = request.path
    if path.startswith("/assets/"):
        ext = path.rsplit(".", 1)[-1].lower()
        if ext in ("css", "js", "woff", "woff2", "ttf", "otf", "webp", "png", "jpg", "jpeg", "svg", "ico"):
            response.cache_control.max_age = 2592000
            response.cache_control.public = True
    return response


with app.app_context():
    init_db()

import routes_public  # noqa: E402, F401
import routes_admin   # noqa: E402, F401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
