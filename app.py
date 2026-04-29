"""
Аксай Гриль — Flask backend.

Этап 2: добавлена админка с авторизацией и журналом входов.
- /admin/setup — одноразовое создание первого администратора
- /admin/login — вход
- /admin/logout — выход
- /admin — кабинет администратора (заглушка с журналом входов)
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from db import BASE_DIR, Base, SessionLocal, engine

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
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 МБ для загрузок
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Сначала войдите в админку."
login_manager.login_message_category = "warning"


def init_db() -> None:
    """Создать таблицы при первом запуске и засеять дефолтные тексты."""
    import models  # noqa: F401  — регистрируем модели в Base.metadata

    Base.metadata.create_all(bind=engine)

    # Лёгкая миграция SQLite: добавим недостающие колонки в business_lunch_orders.
    # SQLite не поддерживает «add if not exists», поэтому сверяемся с PRAGMA.
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        try:
            cols = {row[1] for row in conn.exec_driver_sql(
                "PRAGMA table_info(business_lunch_orders)").fetchall()}
            if "is_processed" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE business_lunch_orders "
                    "ADD COLUMN is_processed BOOLEAN NOT NULL DEFAULT 0")
            if "processed_at" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE business_lunch_orders "
                    "ADD COLUMN processed_at DATETIME")
            if "processed_by" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE business_lunch_orders "
                    "ADD COLUMN processed_by VARCHAR(64)")
        except Exception as exc:  # pragma: no cover
            logging.getLogger(__name__).warning(
                "business_lunch_orders migration skipped: %s", exc)

    session = SessionLocal()
    try:
        models.seed_site_texts(session)
    finally:
        session.close()


@app.context_processor
def inject_site_texts():
    """Кладём словарь текстов сайта во все шаблоны как `texts`."""
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
    """Разрешаем только относительные внутренние пути."""
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith("/")


# ----------------------------- публичные роуты -----------------------------


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/privacy.html")
def privacy():
    return render_template("privacy.html")


@app.route("/business-lunch", methods=["GET", "POST"])
def business_lunch():
    """Страница комплексных бизнес-ланчей с формой корпоративного заказа."""
    from forms import BusinessLunchOrderForm
    from models import BUSINESS_LUNCH_MENU, BusinessLunchOrder

    form = BusinessLunchOrderForm()
    form.selected_combos.choices = [
        (item["key"], item["title"]) for item in BUSINESS_LUNCH_MENU
    ]

    if form.validate_on_submit():
        session = SessionLocal()
        try:
            order = BusinessLunchOrder(
                contact_name=form.contact_name.data.strip(),
                company=(form.company.data or "").strip() or None,
                phone=form.phone.data.strip(),
                email=(form.email.data or "").strip() or None,
                persons=form.persons.data,
                delivery_date=form.delivery_date.data.isoformat(),
                delivery_time=(form.delivery_time.data or "").strip() or None,
                delivery_address=form.delivery_address.data.strip(),
                selected_combos=",".join(form.selected_combos.data or []) or None,
                comment=(form.comment.data or "").strip() or None,
                ip_address=_client_ip(),
            )
            session.add(order)
            session.commit()
            flash(
                "Заявка принята. Мы свяжемся с вами для подтверждения.",
                "success",
            )
            return redirect(url_for("business_lunch"))
        finally:
            session.close()

    return render_template(
        "business-lunch.html",
        menu=BUSINESS_LUNCH_MENU,
        form=form,
    )


@app.route("/uploads/<path:filename>")
def uploads(filename: str):
    uploads_dir = BASE_DIR / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    return send_from_directory(uploads_dir, filename)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


# ------------------------------- админка ----------------------------------


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    """Одноразовое создание первого администратора.

    Доступно только пока в БД нет ни одного администратора.
    """
    from forms import SetupForm
    from models import Admin, admins_count

    session = SessionLocal()
    try:
        if admins_count(session) > 0:
            abort(404)

        form = SetupForm()
        if form.validate_on_submit():
            admin = Admin(username=form.username.data.strip())
            admin.set_password(form.password.data)
            session.add(admin)
            session.commit()
            flash("Администратор создан. Войдите в систему.", "success")
            return redirect(url_for("admin_login"))

        return render_template("admin/setup.html", form=form)
    finally:
        session.close()


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    from forms import LoginForm
    from models import Admin, LoginLog, admins_count

    session = SessionLocal()
    try:
        if admins_count(session) == 0:
            return redirect(url_for("admin_setup"))

        if current_user.is_authenticated:
            return redirect(url_for("admin_dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            username = form.username.data.strip()
            password = form.password.data
            admin = (
                session.query(Admin)
                .filter(Admin.username == username, Admin.is_active.is_(True))
                .first()
            )
            success = bool(admin and admin.check_password(password))

            log = LoginLog(
                username_attempted=username,
                success=success,
                ip_address=_client_ip(),
                user_agent=(request.user_agent.string or "")[:1024],
            )
            session.add(log)

            if success:
                admin.last_login_at = datetime.utcnow()
                session.commit()
                login_user(admin)
                next_url = request.args.get("next")
                if _is_safe_next(next_url):
                    return redirect(next_url)
                return redirect(url_for("admin_dashboard"))

            session.commit()
            flash("Неверный логин или пароль.", "error")

        return render_template("admin/login.html", form=form)
    finally:
        session.close()


@app.route("/admin/logout", methods=["POST"])
@login_required
def admin_logout():
    logout_user()
    flash("Вы вышли из админки.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin/texts", methods=["GET", "POST"])
@login_required
def admin_texts():
    """Редактирование текстов главной страницы."""
    from models import SITE_TEXT_CATALOG, SiteText, get_catalog_grouped

    session = SessionLocal()
    try:
        # Подтянем существующие записи
        rows = {t.key: t for t in session.query(SiteText).all()}

        if request.method == "POST":
            # CSRF проверится автоматически (CSRFProtect+скрытое поле в форме)
            for item in SITE_TEXT_CATALOG:
                key = item["key"]
                value = request.form.get(key, "")
                if key in rows:
                    rows[key].value = value
                else:
                    session.add(SiteText(key=key, value=value))
            session.commit()
            flash("Тексты сохранены.", "success")
            return redirect(url_for("admin_texts"))

        # GET — соберём текущие значения с подстановкой defaults
        values = {item["key"]: rows[item["key"]].value if item["key"] in rows
                  else item["default"]
                  for item in SITE_TEXT_CATALOG}
        return render_template(
            "admin/texts.html",
            catalog=SITE_TEXT_CATALOG,
            grouped_catalog=get_catalog_grouped(),
            values=values,
        )
    finally:
        session.close()


@app.route("/admin")
@app.route("/admin/")
@login_required
def admin_dashboard():
    from models import BusinessLunchOrder, LoginLog

    session = SessionLocal()
    try:
        recent_logs = (
            session.query(LoginLog)
            .order_by(LoginLog.created_at.desc())
            .limit(50)
            .all()
        )
        pending_orders = (
            session.query(BusinessLunchOrder)
            .filter(BusinessLunchOrder.is_processed.is_(False))
            .count()
        )
        return render_template(
            "admin/dashboard.html",
            recent_logs=recent_logs,
            pending_orders=pending_orders,
        )
    finally:
        session.close()


@app.route("/admin/business-lunches")
@login_required
def admin_business_lunches():
    """Список заявок на бизнес-ланчи."""
    from models import BUSINESS_LUNCH_MENU, BusinessLunchOrder

    show = request.args.get("show", "pending")  # pending|all|processed

    session = SessionLocal()
    try:
        q = session.query(BusinessLunchOrder)
        if show == "pending":
            q = q.filter(BusinessLunchOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(BusinessLunchOrder.is_processed.is_(True))
        orders = q.order_by(BusinessLunchOrder.created_at.desc()).limit(200).all()

        combo_titles = {item["key"]: item["title"] for item in BUSINESS_LUNCH_MENU}
        combo_prices = {item["key"]: item["price"] for item in BUSINESS_LUNCH_MENU}

        return render_template(
            "admin/business_lunches.html",
            orders=orders,
            show=show,
            combo_titles=combo_titles,
            combo_prices=combo_prices,
        )
    finally:
        session.close()


@app.route("/admin/business-lunches/<int:order_id>/toggle", methods=["POST"])
@login_required
def admin_business_lunch_toggle(order_id: int):
    """Отметить заявку обработанной / снять отметку."""
    from models import BusinessLunchOrder

    session = SessionLocal()
    try:
        order = session.get(BusinessLunchOrder, order_id)
        if order is None:
            abort(404)
        if order.is_processed:
            order.is_processed = False
            order.processed_at = None
            order.processed_by = None
            flash(f"Заявка #{order.id} возвращена в работу.", "success")
        else:
            order.is_processed = True
            order.processed_at = datetime.utcnow()
            order.processed_by = current_user.username
            flash(f"Заявка #{order.id} отмечена как обработанная.", "success")
        session.commit()
    finally:
        session.close()

    return redirect(
        request.referrer or url_for("admin_business_lunches")
    )


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
