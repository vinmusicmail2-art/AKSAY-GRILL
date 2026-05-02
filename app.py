"""
Аксай Гриль — Flask backend.
Маршруты вынесены в routes_public.py и routes_admin.py.
"""
import logging
import os
from urllib.parse import urlparse

from flask import Flask, request
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
app.secret_key = os.environ.get("SESSION_SECRET") or os.environ.get(
    "SECRET_KEY", "dev-secret-change-me"
)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Сначала войдите в админку."
login_manager.login_message_category = "warning"


def init_db() -> None:
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

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

    session = SessionLocal()
    try:
        models.seed_site_texts(session)
        models.seed_menu(session)
    finally:
        session.close()


@app.context_processor
def inject_site_texts():
    from models import load_site_texts

    session = SessionLocal()
    try:
        return {"texts": load_site_texts(session)}
    finally:
        session.close()


@login_manager.user_loader
def load_user(user_id: str):
    from models import Admin

    session = SessionLocal()
    try:
        return session.get(Admin, int(user_id))
    finally:
        session.close()


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _is_safe_next(target: str) -> bool:
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith("/")


def _safe_referrer(fallback: str) -> str:
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


with app.app_context():
    init_db()

import routes_public  # noqa: E402, F401
import routes_admin   # noqa: E402, F401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
