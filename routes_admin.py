"""Административные маршруты Аксай Гриль."""
import json as _json
import logging
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import app, _client_ip, _is_safe_next, _safe_referrer
from db import SessionLocal

logger = logging.getLogger(__name__)


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
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


@app.route("/admin")
@app.route("/admin/")
@login_required
def admin_dashboard():
    from models import BusinessLunchOrder, CateringRequest, DeliveryOrder, HallReservation, LoginLog

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
        pending_catering = (
            session.query(CateringRequest)
            .filter(CateringRequest.is_processed.is_(False))
            .count()
        )
        pending_events = (
            session.query(HallReservation)
            .filter(HallReservation.is_processed.is_(False))
            .count()
        )
        pending_delivery = (
            session.query(DeliveryOrder)
            .filter(DeliveryOrder.is_processed.is_(False))
            .count()
        )
        return render_template(
            "admin/dashboard.html",
            recent_logs=recent_logs,
            pending_orders=pending_orders,
            pending_catering=pending_catering,
            pending_events=pending_events,
            pending_delivery=pending_delivery,
        )
    finally:
        session.close()


@app.route("/admin/texts", methods=["GET", "POST"])
@login_required
def admin_texts():
    from models import SITE_TEXT_CATALOG, SiteText, get_catalog_grouped

    session = SessionLocal()
    try:
        rows = {t.key: t for t in session.query(SiteText).all()}

        if request.method == "POST":
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

        values = {
            item["key"]: rows[item["key"]].value if item["key"] in rows else item["default"]
            for item in SITE_TEXT_CATALOG
        }
        return render_template(
            "admin/texts.html",
            catalog=SITE_TEXT_CATALOG,
            grouped_catalog=get_catalog_grouped(),
            values=values,
        )
    finally:
        session.close()


@app.route("/admin/email-settings", methods=["GET", "POST"])
@login_required
def admin_email_settings():
    from mailer import send_test_email, smtp_status
    from models import SiteText, load_site_texts

    session = SessionLocal()
    try:
        if request.method == "POST":
            action = request.form.get("action", "save")

            if action == "save":
                recipient = (request.form.get("notify_email_recipient") or "").strip()
                enabled_raw = (request.form.get("notify_email_enabled") or "").strip()
                enabled_value = "yes" if enabled_raw in ("on", "yes", "1", "true") else "no"
                new_password = (request.form.get("smtp_password") or "").strip()

                pairs = [
                    ("notify_email_recipient", recipient),
                    ("notify_email_enabled", enabled_value),
                ]
                if new_password:
                    pairs.append(("smtp_password", new_password))

                for key, value in pairs:
                    row = session.query(SiteText).filter(SiteText.key == key).first()
                    if row:
                        row.value = value
                    else:
                        session.add(SiteText(key=key, value=value))
                session.commit()
                flash("Настройки уведомлений сохранены.", "success")
                return redirect(url_for("admin_email_settings"))

            if action == "test":
                test_to = (request.form.get("test_to") or "").strip()
                if not test_to:
                    flash("Укажите адрес для тестового письма.", "error")
                else:
                    ok, msg = send_test_email(test_to)
                    flash(
                        ("Тестовое письмо отправлено: " if ok else "Не удалось отправить: ") + msg,
                        "success" if ok else "error",
                    )
                return redirect(url_for("admin_email_settings"))

        texts = load_site_texts(session)
        from sqlalchemy import text as sa_text
        pw_row = session.execute(
            sa_text("SELECT value FROM site_texts WHERE key = 'smtp_password' LIMIT 1")
        ).fetchone()
        smtp_password_set = bool(pw_row and (pw_row[0] or "").strip())
        return render_template(
            "admin/email_settings.html",
            recipient=texts.get("notify_email_recipient", ""),
            enabled=(texts.get("notify_email_enabled", "yes") or "").strip().lower()
                    in ("yes", "y", "1", "true", "on", "да"),
            smtp=smtp_status(),
            smtp_password_set=smtp_password_set,
        )
    finally:
        session.close()


@app.route("/admin/business-lunches")
@login_required
def admin_business_lunches():
    from models import BUSINESS_LUNCH_MENU, BusinessLunchOrder

    show = request.args.get("show", "pending")
    session = SessionLocal()
    try:
        q = session.query(BusinessLunchOrder)
        if show == "pending":
            q = q.filter(BusinessLunchOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(BusinessLunchOrder.is_processed.is_(True))
        orders = q.order_by(BusinessLunchOrder.created_at.desc()).limit(200).all()

        return render_template(
            "admin/business_lunches.html",
            orders=orders,
            show=show,
            combo_titles={item["key"]: item["title"] for item in BUSINESS_LUNCH_MENU},
            combo_prices={item["key"]: item["price"] for item in BUSINESS_LUNCH_MENU},
        )
    finally:
        session.close()


@app.route("/admin/business-lunches/<int:order_id>/toggle", methods=["POST"])
@login_required
def admin_business_lunch_toggle(order_id: int):
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

    return redirect(_safe_referrer(url_for("admin_business_lunches")))


@app.route("/admin/catering")
@login_required
def admin_catering():
    from models import CATERING_FORMATS, CateringRequest

    show = request.args.get("show", "pending")
    session = SessionLocal()
    try:
        q = session.query(CateringRequest)
        if show == "pending":
            q = q.filter(CateringRequest.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(CateringRequest.is_processed.is_(True))
        requests_list = q.order_by(CateringRequest.created_at.desc()).limit(200).all()

        return render_template(
            "admin/catering.html",
            requests=requests_list,
            show=show,
            format_titles={item["key"]: item["title"] for item in CATERING_FORMATS},
        )
    finally:
        session.close()


@app.route("/admin/catering/<int:request_id>/toggle", methods=["POST"])
@login_required
def admin_catering_toggle(request_id: int):
    from models import CateringRequest

    session = SessionLocal()
    try:
        req = session.get(CateringRequest, request_id)
        if req is None:
            abort(404)
        if req.is_processed:
            req.is_processed = False
            req.processed_at = None
            req.processed_by = None
            flash(f"Заявка #{req.id} возвращена в работу.", "success")
        else:
            req.is_processed = True
            req.processed_at = datetime.utcnow()
            req.processed_by = current_user.username
            flash(f"Заявка #{req.id} отмечена как обработанная.", "success")
        session.commit()
    finally:
        session.close()

    return redirect(_safe_referrer(url_for("admin_catering")))


@app.route("/admin/events")
@login_required
def admin_events():
    from models import EVENT_TYPES, HallReservation

    show = request.args.get("show", "pending")
    session = SessionLocal()
    try:
        q = session.query(HallReservation)
        if show == "pending":
            q = q.filter(HallReservation.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(HallReservation.is_processed.is_(True))
        requests_list = q.order_by(HallReservation.created_at.desc()).limit(200).all()

        return render_template(
            "admin/events.html",
            requests=requests_list,
            show=show,
            type_titles={item["key"]: item["title"] for item in EVENT_TYPES},
        )
    finally:
        session.close()


@app.route("/admin/events/<int:request_id>/toggle", methods=["POST"])
@login_required
def admin_events_toggle(request_id: int):
    from models import HallReservation

    session = SessionLocal()
    try:
        req = session.get(HallReservation, request_id)
        if req is None:
            abort(404)
        if req.is_processed:
            req.is_processed = False
            req.processed_at = None
            req.processed_by = None
            flash(f"Заявка #{req.id} возвращена в работу.", "success")
        else:
            req.is_processed = True
            req.processed_at = datetime.utcnow()
            req.processed_by = current_user.username
            flash(f"Заявка #{req.id} отмечена как обработанная.", "success")
        session.commit()
    finally:
        session.close()

    return redirect(_safe_referrer(url_for("admin_events")))


@app.route("/admin/delivery-orders")
@login_required
def admin_delivery_orders():
    from models import DeliveryOrder

    show = request.args.get("show", "pending")
    session = SessionLocal()
    try:
        q = session.query(DeliveryOrder)
        if show == "pending":
            q = q.filter(DeliveryOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(DeliveryOrder.is_processed.is_(True))
        orders = q.order_by(DeliveryOrder.created_at.desc()).limit(200).all()

        def parse_items(o):
            try:
                return _json.loads(o.items_json)
            except Exception:
                return []

        return render_template(
            "admin/delivery_orders.html",
            orders=orders,
            show=show,
            parse_items=parse_items,
        )
    finally:
        session.close()


@app.route("/admin/delivery-orders/<int:order_id>/toggle", methods=["POST"])
@login_required
def admin_delivery_order_toggle(order_id: int):
    from models import DeliveryOrder

    session = SessionLocal()
    try:
        order = session.get(DeliveryOrder, order_id)
        if order is None:
            abort(404)
        if order.is_processed:
            order.is_processed = False
            order.processed_at = None
            order.processed_by = None
            flash(f"Заказ #{order.id} возвращён в работу.", "success")
        else:
            order.is_processed = True
            order.processed_at = datetime.utcnow()
            order.processed_by = current_user.username
            flash(f"Заказ #{order.id} отмечен как выполненный.", "success")
        session.commit()
    finally:
        session.close()

    return redirect(_safe_referrer(url_for("admin_delivery_orders")))
