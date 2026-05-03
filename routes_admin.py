"""Административные маршруты Аксай Гриль."""
import csv
import io
import json as _json
import logging
import os
import re
import time
from datetime import datetime, timedelta

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import app, _client_ip, _is_safe_next, _safe_referrer
from db import SessionLocal
from login_archive import (
    archive_login_async,
    send_login_notify_async,
    is_setup_done,
    save_settings,
    resolve_archive_path,
)

logger = logging.getLogger(__name__)

_DISHES_DIR = os.path.join(os.path.dirname(__file__), "assets", "dishes")
_ALLOWED_IMG_EXT = {"jpg", "jpeg", "png", "webp", "gif"}


def _save_dish_image(file_storage, dish_name: str = "") -> str | None:
    """Сохранить загруженное изображение блюда, вернуть относительный путь /assets/dishes/..."""
    if not file_storage or not file_storage.filename:
        return None
    orig = file_storage.filename
    ext = orig.rsplit(".", 1)[-1].lower() if "." in orig else "jpg"
    if ext not in _ALLOWED_IMG_EXT:
        return None
    slug = re.sub(r"[^a-z0-9]", "-", dish_name.lower()) if dish_name else ""
    slug = re.sub(r"-+", "-", slug).strip("-")[:40]
    ts = int(time.time())
    filename = f"{slug}-{ts}.{ext}" if slug else f"dish-{ts}.{ext}"
    os.makedirs(_DISHES_DIR, exist_ok=True)
    file_storage.save(os.path.join(_DISHES_DIR, filename))
    return f"/assets/dishes/{filename}"


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
            ip        = _client_ip()
            ua        = (request.user_agent.string or "")[:1024]

            log = LoginLog(
                username_attempted=username,
                success=success,
                ip_address=ip,
                user_agent=ua,
            )
            session.add(log)

            if success:
                admin.last_login_at = datetime.utcnow()
                session.commit()
                login_user(admin)

                archive_login_async(username, True, ip, ua)
                send_login_notify_async(username, True, ip, ua,
                                        base_url=request.host_url.rstrip("/"))

                if not is_setup_done():
                    return redirect(url_for("admin_archive_setup"))

                next_url = request.args.get("next")
                if _is_safe_next(next_url):
                    return redirect(next_url)
                return redirect(url_for("admin_dashboard"))

            session.commit()
            archive_login_async(username, False, ip, ua)
            send_login_notify_async(username, False, ip, ua,
                                    base_url=request.host_url.rstrip("/"))
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


@app.route("/admin/profile", methods=["GET", "POST"])
@login_required
def admin_profile():
    """Профиль текущего администратора: смена пароля."""
    from forms import ChangePasswordForm
    from models import Admin

    form = ChangePasswordForm()
    if form.validate_on_submit():
        session = SessionLocal()
        try:
            admin = session.get(Admin, current_user.id)
            if not admin:
                flash("Пользователь не найден.", "error")
                return redirect(url_for("admin_profile"))

            if not admin.check_password(form.current_password.data):
                flash("Текущий пароль указан неверно.", "error")
                return redirect(url_for("admin_profile"))

            admin.set_password(form.new_password.data)
            session.commit()
            flash("Пароль успешно изменён.", "success")
            logger.info("Admin '%s' changed password from IP %s",
                        current_user.username, _client_ip())
            return redirect(url_for("admin_profile"))
        finally:
            session.close()

    return render_template("admin/profile.html", form=form)


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
        all_delivery = (
            session.query(DeliveryOrder)
            .order_by(DeliveryOrder.is_processed.asc(), DeliveryOrder.created_at.desc())
            .limit(50)
            .all()
        )
        all_lunch = (
            session.query(BusinessLunchOrder)
            .order_by(BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.created_at.desc())
            .limit(50)
            .all()
        )
        all_catering = (
            session.query(CateringRequest)
            .order_by(CateringRequest.is_processed.asc(), CateringRequest.created_at.desc())
            .limit(50)
            .all()
        )
        all_events = (
            session.query(HallReservation)
            .order_by(HallReservation.is_processed.asc(), HallReservation.created_at.desc())
            .limit(50)
            .all()
        )
        total_new = pending_delivery + pending_orders + pending_catering + pending_events
        return render_template(
            "admin/dashboard.html",
            recent_logs=recent_logs,
            pending_orders=pending_orders,
            pending_catering=pending_catering,
            pending_events=pending_events,
            pending_delivery=pending_delivery,
            all_delivery=all_delivery,
            all_lunch=all_lunch,
            all_catering=all_catering,
            all_events=all_events,
            total_new=total_new,
        )
    finally:
        session.close()


@app.route("/admin/stats")
@login_required
def admin_stats():
    from models import BusinessLunchOrder, CateringRequest, DeliveryOrder, HallReservation

    period = request.args.get("period", "all")
    now = datetime.utcnow()
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    tables = [
        (DeliveryOrder,       "delivery",  "Доставка"),
        (BusinessLunchOrder,  "lunch",     "Ланчи"),
        (CateringRequest,     "catering",  "Кейтеринг"),
        (HallReservation,     "events",    "Банкеты"),
    ]

    session = SessionLocal()
    try:
        stats = {}

        for model, key, _label in tables:
            q = session.query(model).filter(
                model.is_processed.is_(True),
                model.processed_by.isnot(None),
            )
            if since:
                q = q.filter(model.processed_at >= since)
            for row in q.all():
                by = row.processed_by
                if by not in stats:
                    stats[by] = {
                        "delivery": 0, "lunch": 0,
                        "catering": 0, "events": 0,
                        "total": 0,
                        "total_minutes": 0.0, "timed_count": 0,
                        "last_at": None,
                    }
                stats[by][key] += 1
                stats[by]["total"] += 1
                if row.processed_at and row.created_at:
                    diff = (row.processed_at - row.created_at).total_seconds() / 60.0
                    if diff >= 0:
                        stats[by]["total_minutes"] += diff
                        stats[by]["timed_count"] += 1
                if row.processed_at:
                    if stats[by]["last_at"] is None or row.processed_at > stats[by]["last_at"]:
                        stats[by]["last_at"] = row.processed_at

        for by in stats:
            tc = stats[by]["timed_count"]
            stats[by]["avg_minutes"] = round(stats[by]["total_minutes"] / tc) if tc else None

        stats_list = sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True)

        totals = {"delivery": 0, "lunch": 0, "catering": 0, "events": 0, "total": 0}
        for _by, s in stats_list:
            for k in totals:
                totals[k] += s[k]

        return render_template(
            "admin/stats.html",
            stats_list=stats_list,
            totals=totals,
            period=period,
        )
    finally:
        session.close()


_TEXTS_EXCLUDED_SECTIONS = {
    "Реквизиты оператора (ИП)",
    "Юридические страницы",
}


@app.route("/admin/texts", methods=["GET", "POST"])
@login_required
def admin_texts():
    from models import SITE_TEXT_CATALOG, SiteText, get_catalog_grouped

    editable = [i for i in SITE_TEXT_CATALOG
                if i.get("section") not in _TEXTS_EXCLUDED_SECTIONS]

    session = SessionLocal()
    try:
        rows = {t.key: t for t in session.query(SiteText).all()}

        if request.method == "POST":
            for item in editable:
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
            for item in editable
        }

        grouped: list[tuple] = [
            (sec, items) for sec, items in get_catalog_grouped()
            if sec not in _TEXTS_EXCLUDED_SECTIONS
        ]

        return render_template(
            "admin/texts.html",
            catalog=editable,
            grouped_catalog=grouped,
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

    show         = request.args.get("show", "pending")
    sort         = request.args.get("sort", "date_desc")
    admin_filter = (request.args.get("admin") or "").strip()
    period       = (request.args.get("period") or "").strip()
    search_q     = (request.args.get("q") or "").strip()
    session = SessionLocal()
    try:
        all_admins = sorted({
            row[0] for row in
            session.query(BusinessLunchOrder.processed_by)
            .filter(BusinessLunchOrder.is_processed.is_(True),
                    BusinessLunchOrder.processed_by.isnot(None))
            .distinct().all()
        })
        q = session.query(BusinessLunchOrder)
        if show == "pending":
            q = q.filter(BusinessLunchOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(BusinessLunchOrder.is_processed.is_(True))
        if admin_filter:
            q = q.filter(BusinessLunchOrder.processed_by == admin_filter)
        now = datetime.utcnow()
        if period == "today":
            q = q.filter(BusinessLunchOrder.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        elif period == "week":
            q = q.filter(BusinessLunchOrder.created_at >= now - timedelta(days=7))
        elif period == "month":
            q = q.filter(BusinessLunchOrder.created_at >= now - timedelta(days=30))
        if search_q:
            like = f"%{search_q}%"
            from sqlalchemy import or_
            q = q.filter(or_(
                BusinessLunchOrder.contact_name.like(like),
                BusinessLunchOrder.phone.like(like),
                BusinessLunchOrder.company.like(like),
                BusinessLunchOrder.comment.like(like),
            ))
        _LUNCH_SORT = {
            "date_desc": [BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.created_at.desc()],
            "date_asc":  [BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.created_at.asc()],
            "persons_desc": [BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.persons.desc()],
            "persons_asc":  [BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.persons.asc()],
            "status_new":  [BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.created_at.desc()],
            "status_done": [BusinessLunchOrder.is_processed.desc(), BusinessLunchOrder.created_at.desc()],
        }
        for col in _LUNCH_SORT.get(sort, _LUNCH_SORT["date_desc"]):
            q = q.order_by(col)
        orders = q.limit(200).all()

        return render_template(
            "admin/business_lunches.html",
            orders=orders,
            show=show,
            sort=sort,
            admin_filter=admin_filter,
            all_admins=all_admins,
            period=period,
            search_q=search_q,
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

    show         = request.args.get("show", "pending")
    sort         = request.args.get("sort", "date_desc")
    admin_filter = (request.args.get("admin") or "").strip()
    period       = (request.args.get("period") or "").strip()
    search_q     = (request.args.get("q") or "").strip()
    session = SessionLocal()
    try:
        all_admins = sorted({
            row[0] for row in
            session.query(CateringRequest.processed_by)
            .filter(CateringRequest.is_processed.is_(True),
                    CateringRequest.processed_by.isnot(None))
            .distinct().all()
        })
        q = session.query(CateringRequest)
        if show == "pending":
            q = q.filter(CateringRequest.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(CateringRequest.is_processed.is_(True))
        if admin_filter:
            q = q.filter(CateringRequest.processed_by == admin_filter)
        now = datetime.utcnow()
        if period == "today":
            q = q.filter(CateringRequest.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        elif period == "week":
            q = q.filter(CateringRequest.created_at >= now - timedelta(days=7))
        elif period == "month":
            q = q.filter(CateringRequest.created_at >= now - timedelta(days=30))
        if search_q:
            like = f"%{search_q}%"
            from sqlalchemy import or_
            q = q.filter(or_(
                CateringRequest.contact_name.like(like),
                CateringRequest.phone.like(like),
                CateringRequest.company.like(like),
                CateringRequest.comment.like(like),
                CateringRequest.venue.like(like),
            ))
        _CAT_SORT = {
            "date_desc":   [CateringRequest.is_processed.asc(), CateringRequest.created_at.desc()],
            "date_asc":    [CateringRequest.is_processed.asc(), CateringRequest.created_at.asc()],
            "guests_desc": [CateringRequest.is_processed.asc(), CateringRequest.guests.desc()],
            "guests_asc":  [CateringRequest.is_processed.asc(), CateringRequest.guests.asc()],
            "price_desc":  [CateringRequest.is_processed.asc(), CateringRequest.budget_per_guest.desc()],
            "price_asc":   [CateringRequest.is_processed.asc(), CateringRequest.budget_per_guest.asc()],
            "status_new":  [CateringRequest.is_processed.asc(), CateringRequest.created_at.desc()],
            "status_done": [CateringRequest.is_processed.desc(), CateringRequest.created_at.desc()],
        }
        for col in _CAT_SORT.get(sort, _CAT_SORT["date_desc"]):
            q = q.order_by(col)
        requests_list = q.limit(200).all()

        return render_template(
            "admin/catering.html",
            requests=requests_list,
            show=show,
            sort=sort,
            admin_filter=admin_filter,
            all_admins=all_admins,
            period=period,
            search_q=search_q,
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

    show         = request.args.get("show", "pending")
    sort         = request.args.get("sort", "date_desc")
    admin_filter = (request.args.get("admin") or "").strip()
    period       = (request.args.get("period") or "").strip()
    search_q     = (request.args.get("q") or "").strip()
    session = SessionLocal()
    try:
        all_admins = sorted({
            row[0] for row in
            session.query(HallReservation.processed_by)
            .filter(HallReservation.is_processed.is_(True),
                    HallReservation.processed_by.isnot(None))
            .distinct().all()
        })
        q = session.query(HallReservation)
        if show == "pending":
            q = q.filter(HallReservation.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(HallReservation.is_processed.is_(True))
        if admin_filter:
            q = q.filter(HallReservation.processed_by == admin_filter)
        now = datetime.utcnow()
        if period == "today":
            q = q.filter(HallReservation.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        elif period == "week":
            q = q.filter(HallReservation.created_at >= now - timedelta(days=7))
        elif period == "month":
            q = q.filter(HallReservation.created_at >= now - timedelta(days=30))
        if search_q:
            like = f"%{search_q}%"
            from sqlalchemy import or_
            q = q.filter(or_(
                HallReservation.contact_name.like(like),
                HallReservation.phone.like(like),
                HallReservation.company.like(like),
                HallReservation.comment.like(like),
            ))
        _EV_SORT = {
            "date_desc":   [HallReservation.is_processed.asc(), HallReservation.created_at.desc()],
            "date_asc":    [HallReservation.is_processed.asc(), HallReservation.created_at.asc()],
            "guests_desc": [HallReservation.is_processed.asc(), HallReservation.guests.desc()],
            "guests_asc":  [HallReservation.is_processed.asc(), HallReservation.guests.asc()],
            "status_new":  [HallReservation.is_processed.asc(), HallReservation.created_at.desc()],
            "status_done": [HallReservation.is_processed.desc(), HallReservation.created_at.desc()],
        }
        for col in _EV_SORT.get(sort, _EV_SORT["date_desc"]):
            q = q.order_by(col)
        requests_list = q.limit(200).all()

        return render_template(
            "admin/events.html",
            requests=requests_list,
            show=show,
            sort=sort,
            admin_filter=admin_filter,
            all_admins=all_admins,
            period=period,
            search_q=search_q,
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

    show         = request.args.get("show", "pending")
    sort         = request.args.get("sort", "date_desc")
    admin_filter = (request.args.get("admin") or "").strip()
    period       = (request.args.get("period") or "").strip()
    search_q     = (request.args.get("q") or "").strip()
    session = SessionLocal()
    try:
        all_admins = sorted({
            row[0] for row in
            session.query(DeliveryOrder.processed_by)
            .filter(DeliveryOrder.is_processed.is_(True),
                    DeliveryOrder.processed_by.isnot(None))
            .distinct().all()
        })
        q = session.query(DeliveryOrder)
        if show == "pending":
            q = q.filter(DeliveryOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(DeliveryOrder.is_processed.is_(True))
        if admin_filter:
            q = q.filter(DeliveryOrder.processed_by == admin_filter)
        now = datetime.utcnow()
        if period == "today":
            q = q.filter(DeliveryOrder.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        elif period == "week":
            q = q.filter(DeliveryOrder.created_at >= now - timedelta(days=7))
        elif period == "month":
            q = q.filter(DeliveryOrder.created_at >= now - timedelta(days=30))
        if search_q:
            like = f"%{search_q}%"
            from sqlalchemy import or_
            q = q.filter(or_(
                DeliveryOrder.contact_name.like(like),
                DeliveryOrder.phone.like(like),
                DeliveryOrder.delivery_address.like(like),
                DeliveryOrder.comment.like(like),
            ))
        _DEL_SORT = {
            "date_desc":  [DeliveryOrder.is_processed.asc(), DeliveryOrder.created_at.desc()],
            "date_asc":   [DeliveryOrder.is_processed.asc(), DeliveryOrder.created_at.asc()],
            "price_desc": [DeliveryOrder.is_processed.asc(), DeliveryOrder.total_amount.desc()],
            "price_asc":  [DeliveryOrder.is_processed.asc(), DeliveryOrder.total_amount.asc()],
            "status_new":  [DeliveryOrder.is_processed.asc(), DeliveryOrder.created_at.desc()],
            "status_done": [DeliveryOrder.is_processed.desc(), DeliveryOrder.created_at.desc()],
        }
        for col in _DEL_SORT.get(sort, _DEL_SORT["date_desc"]):
            q = q.order_by(col)
        orders = q.limit(200).all()

        def parse_items(o):
            try:
                return _json.loads(o.items_json)
            except Exception:
                return []

        return render_template(
            "admin/delivery_orders.html",
            orders=orders,
            show=show,
            sort=sort,
            admin_filter=admin_filter,
            all_admins=all_admins,
            period=period,
            search_q=search_q,
            parse_items=parse_items,
        )
    finally:
        session.close()


@app.route("/admin/seo", methods=["GET", "POST"])
@login_required
def admin_seo():
    from models import load_site_texts, SiteText, SITE_TEXT_CATALOG

    SEO_KEYS = [
        "yandex_metrika_id",
        "meta_description_main",
        "meta_description_about",
        "meta_description_catering",
        "meta_description_events",
        "meta_description_business_lunch",
        "og_image",
    ]
    catalog = {item["key"]: item for item in SITE_TEXT_CATALOG}

    session = SessionLocal()
    try:
        if request.method == "POST":
            for key in SEO_KEYS:
                value = (request.form.get(key) or "").strip()
                row = session.query(SiteText).filter_by(key=key).first()
                if row:
                    row.value = value
                else:
                    session.add(SiteText(key=key, value=value))
            session.commit()
            flash("SEO-настройки сохранены.", "success")
            return redirect(url_for("admin_seo"))

        texts = load_site_texts(session)
        fields = [catalog[k] for k in SEO_KEYS if k in catalog]
        values = {k: texts.get(k, "") for k in SEO_KEYS}
        return render_template("admin/seo.html", fields=fields, values=values)
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


# ---------------------------------------------------------------------------
# Меню: категории и блюда.
# ---------------------------------------------------------------------------

@app.route("/admin/menu")
@login_required
def admin_menu():
    from models import Dish, MenuCategory

    session = SessionLocal()
    try:
        categories = (
            session.query(MenuCategory)
            .order_by(MenuCategory.sort_order)
            .all()
        )
        for cat in categories:
            _ = cat.dishes  # eager-load
        total_dishes = session.query(Dish).count()
        return render_template("admin/menu.html", categories=categories, total_dishes=total_dishes)
    finally:
        session.close()


@app.route("/admin/menu/stats")
@login_required
def admin_menu_stats():
    from models import Dish, MenuCategory

    session = SessionLocal()
    try:
        categories = (
            session.query(MenuCategory)
            .order_by(MenuCategory.sort_order)
            .all()
        )

        all_dishes = session.query(Dish).all()
        total = len(all_dishes)
        available = sum(1 for d in all_dishes if d.is_available)
        hidden = total - available
        no_photo = sum(1 for d in all_dishes if not d.image_src)
        prices = [d.price for d in all_dishes if d.price > 0]
        global_min = min(prices) if prices else 0
        global_max = max(prices) if prices else 0
        global_avg = round(sum(prices) / len(prices)) if prices else 0

        cat_stats = []
        for cat in categories:
            dishes = cat.dishes
            cnt = len(dishes)
            avail = sum(1 for d in dishes if d.is_available)
            hid = cnt - avail
            no_ph = sum(1 for d in dishes if not d.image_src)
            cat_prices = [d.price for d in dishes if d.price > 0]
            cat_stats.append({
                "cat": cat,
                "total": cnt,
                "available": avail,
                "hidden": hid,
                "no_photo": no_ph,
                "min_price": min(cat_prices) if cat_prices else 0,
                "max_price": max(cat_prices) if cat_prices else 0,
                "avg_price": round(sum(cat_prices) / len(cat_prices)) if cat_prices else 0,
                "all_hidden": cnt > 0 and avail == 0,
            })

        cheapest = min(all_dishes, key=lambda d: d.price, default=None)
        priciest = max(all_dishes, key=lambda d: d.price, default=None)

        return render_template(
            "admin/menu_stats.html",
            cat_stats=cat_stats,
            total=total,
            available=available,
            hidden=hidden,
            no_photo=no_photo,
            global_min=global_min,
            global_max=global_max,
            global_avg=global_avg,
            cheapest=cheapest,
            priciest=priciest,
        )
    finally:
        session.close()


@app.route("/admin/menu/category/add", methods=["POST"])
@login_required
def admin_menu_category_add():
    from models import MenuCategory

    session = SessionLocal()
    try:
        slug = (request.form.get("slug") or "").strip().lower()
        name = (request.form.get("name") or "").strip()
        heading = (request.form.get("heading") or "").strip()
        if not slug or not name or not heading:
            flash("Заполните обязательные поля: название, slug и заголовок.", "error")
            return redirect(url_for("admin_menu"))
        existing = session.query(MenuCategory).filter_by(slug=slug).first()
        if existing:
            flash(f"Категория со slug «{slug}» уже существует.", "error")
            return redirect(url_for("admin_menu"))
        cat = MenuCategory(
            slug=slug,
            name=name,
            heading=heading,
            description=(request.form.get("description") or "").strip(),
            nav_icon=(request.form.get("nav_icon") or "restaurant_menu").strip(),
            sort_order=int(request.form.get("sort_order") or 100),
            show_in_nav=bool(request.form.get("show_in_nav")),
            is_visible=True,
        )
        session.add(cat)
        session.commit()
        flash(f"Категория «{name}» добавлена.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error adding menu category: %s", exc)
        flash("Ошибка при добавлении категории.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/category/<int:cat_id>/edit", methods=["POST"])
@login_required
def admin_menu_category_edit(cat_id: int):
    from models import MenuCategory

    session = SessionLocal()
    try:
        cat = session.get(MenuCategory, cat_id)
        if cat is None:
            abort(404)
        slug = (request.form.get("slug") or "").strip().lower()
        name = (request.form.get("name") or "").strip()
        heading = (request.form.get("heading") or "").strip()
        if not slug or not name or not heading:
            flash("Заполните обязательные поля.", "error")
            return redirect(url_for("admin_menu"))
        conflict = (
            session.query(MenuCategory)
            .filter(MenuCategory.slug == slug, MenuCategory.id != cat_id)
            .first()
        )
        if conflict:
            flash(f"Slug «{slug}» уже занят другой категорией.", "error")
            return redirect(url_for("admin_menu"))
        cat.slug = slug
        cat.name = name
        cat.heading = heading
        cat.description = (request.form.get("description") or "").strip()
        cat.nav_icon = (request.form.get("nav_icon") or "restaurant_menu").strip()
        cat.sort_order = int(request.form.get("sort_order") or cat.sort_order)
        cat.show_in_nav = bool(request.form.get("show_in_nav"))
        session.commit()
        flash(f"Категория «{name}» обновлена.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error editing menu category %d: %s", cat_id, exc)
        flash("Ошибка при сохранении категории.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/category/<int:cat_id>/delete", methods=["POST"])
@login_required
def admin_menu_category_delete(cat_id: int):
    from models import MenuCategory

    session = SessionLocal()
    try:
        cat = session.get(MenuCategory, cat_id)
        if cat is None:
            abort(404)
        if cat.dishes:
            flash("Нельзя удалить категорию с блюдами. Сначала удалите все блюда.", "error")
            return redirect(url_for("admin_menu"))
        name = cat.name
        session.delete(cat)
        session.commit()
        flash(f"Категория «{name}» удалена.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error deleting menu category %d: %s", cat_id, exc)
        flash("Ошибка при удалении категории.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/category/<int:cat_id>/toggle-visibility", methods=["POST"])
@login_required
def admin_menu_category_toggle_visibility(cat_id: int):
    from models import MenuCategory

    session = SessionLocal()
    try:
        cat = session.get(MenuCategory, cat_id)
        if cat is None:
            abort(404)
        cat.is_visible = not cat.is_visible
        session.commit()
        state = "показана" if cat.is_visible else "скрыта"
        flash(f"Категория «{cat.name}» {state}.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error toggling category visibility %d: %s", cat_id, exc)
        flash("Ошибка.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/dish/add", methods=["GET", "POST"])
@login_required
def admin_menu_dish_add():
    from models import Dish, MenuCategory

    session = SessionLocal()
    try:
        categories = session.query(MenuCategory).order_by(MenuCategory.sort_order).all()
        preselect_cat_id = int(request.args.get("cat_id") or 0)

        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            category_id = int(request.form.get("category_id") or 0)
            if not name or not category_id:
                flash("Укажите название и категорию блюда.", "error")
                return render_template(
                    "admin/menu_dish_form.html",
                    dish=None,
                    categories=categories,
                    preselect_cat_id=preselect_cat_id,
                )
            uploaded = _save_dish_image(request.files.get("image_file"), name)
            image_src = uploaded or (request.form.get("image_src") or "").strip()
            dish = Dish(
                category_id=category_id,
                name=name,
                description=(request.form.get("description") or "").strip(),
                price=int(request.form.get("price") or 0),
                image_src=image_src,
                is_available=bool(request.form.get("is_available")),
                sort_order=int(request.form.get("sort_order") or 0),
            )
            session.add(dish)
            session.commit()
            flash(f"Блюдо «{name}» добавлено.", "success")
            return redirect(url_for("admin_menu"))

        return render_template(
            "admin/menu_dish_form.html",
            dish=None,
            categories=categories,
            preselect_cat_id=preselect_cat_id,
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Error adding dish: %s", exc)
        flash("Ошибка при добавлении блюда.", "error")
        return redirect(url_for("admin_menu"))
    finally:
        session.close()


@app.route("/admin/menu/dish/<int:dish_id>/edit", methods=["GET", "POST"])
@login_required
def admin_menu_dish_edit(dish_id: int):
    from models import Dish, MenuCategory

    session = SessionLocal()
    try:
        dish = session.get(Dish, dish_id)
        if dish is None:
            abort(404)
        categories = session.query(MenuCategory).order_by(MenuCategory.sort_order).all()

        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            category_id = int(request.form.get("category_id") or dish.category_id)
            if not name:
                flash("Название блюда не может быть пустым.", "error")
                return render_template(
                    "admin/menu_dish_form.html",
                    dish=dish,
                    categories=categories,
                    preselect_cat_id=dish.category_id,
                )
            uploaded = _save_dish_image(request.files.get("image_file"), name)
            remove_image = request.form.get("remove_image") == "1"
            dish.name = name
            dish.category_id = category_id
            dish.description = (request.form.get("description") or "").strip()
            dish.price = int(request.form.get("price") or 0)
            if uploaded:
                dish.image_src = uploaded
            elif remove_image:
                dish.image_src = ""
            else:
                dish.image_src = (request.form.get("image_src") or "").strip()
            dish.is_available = bool(request.form.get("is_available"))
            dish.sort_order = int(request.form.get("sort_order") or 0)
            session.commit()
            flash(f"Блюдо «{name}» обновлено.", "success")
            return redirect(url_for("admin_menu"))

        return render_template(
            "admin/menu_dish_form.html",
            dish=dish,
            categories=categories,
            preselect_cat_id=dish.category_id,
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Error editing dish %d: %s", dish_id, exc)
        flash("Ошибка при редактировании блюда.", "error")
        return redirect(url_for("admin_menu"))
    finally:
        session.close()


@app.route("/admin/menu/dish/<int:dish_id>/delete", methods=["POST"])
@login_required
def admin_menu_dish_delete(dish_id: int):
    from models import Dish

    session = SessionLocal()
    try:
        dish = session.get(Dish, dish_id)
        if dish is None:
            abort(404)
        name = dish.name
        session.delete(dish)
        session.commit()
        flash(f"Блюдо «{name}» удалено.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error deleting dish %d: %s", dish_id, exc)
        flash("Ошибка при удалении блюда.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/category/<int:cat_id>/reorder-dishes", methods=["POST"])
@login_required
def admin_menu_category_reorder_dishes(cat_id: int):
    from models import Dish, MenuCategory

    session = SessionLocal()
    try:
        cat = session.get(MenuCategory, cat_id)
        if cat is None:
            abort(404)
        raw = (request.form.get("order") or "").strip()
        if not raw:
            flash("Порядок не передан.", "error")
            return redirect(url_for("admin_menu"))
        ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
        for rank, dish_id in enumerate(ids):
            dish = session.get(Dish, dish_id)
            if dish and dish.category_id == cat_id:
                dish.sort_order = rank
        session.commit()
        flash(f"Порядок блюд в «{cat.name}» сохранён.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error reordering dishes in cat %d: %s", cat_id, exc)
        flash("Ошибка при сохранении порядка.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/dish/<int:dish_id>/update-price", methods=["POST"])
@login_required
def admin_menu_dish_update_price(dish_id: int):
    from models import Dish

    session = SessionLocal()
    try:
        dish = session.get(Dish, dish_id)
        if dish is None:
            abort(404)
        new_price = request.form.get("price", "").strip()
        if not new_price.isdigit():
            flash("Цена должна быть числом.", "error")
        else:
            dish.price = int(new_price)
            session.commit()
            flash(f"Цена «{dish.name}» обновлена: {dish.price} ₽", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error updating price for dish %d: %s", dish_id, exc)
        flash("Ошибка при обновлении цены.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/dish/<int:dish_id>/upload-image", methods=["POST"])
@login_required
def admin_menu_dish_upload_image(dish_id: int):
    from models import Dish

    session = SessionLocal()
    try:
        dish = session.get(Dish, dish_id)
        if dish is None:
            abort(404)
        uploaded = _save_dish_image(request.files.get("image_file"), dish.name)
        if uploaded:
            dish.image_src = uploaded
            session.commit()
            flash(f"Фото блюда «{dish.name}» обновлено.", "success")
        else:
            flash("Не удалось загрузить файл. Проверьте формат (JPG, PNG, WebP) и размер (до 5 МБ).", "error")
    except Exception as exc:
        session.rollback()
        logger.exception("Error uploading image for dish %d: %s", dish_id, exc)
        flash("Ошибка при загрузке фото.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/dish/<int:dish_id>/toggle", methods=["POST"])
@login_required
def admin_menu_dish_toggle(dish_id: int):
    from models import Dish

    session = SessionLocal()
    try:
        dish = session.get(Dish, dish_id)
        if dish is None:
            abort(404)
        dish.is_available = not dish.is_available
        session.commit()
        state = "доступно" if dish.is_available else "скрыто"
        flash(f"«{dish.name}» теперь {state}.", "success")
    except Exception as exc:
        session.rollback()
        logger.exception("Error toggling dish %d: %s", dish_id, exc)
        flash("Ошибка.", "error")
    finally:
        session.close()
    return redirect(url_for("admin_menu"))


# ---------------------------------------------------------------------------
# Реквизиты.
# ---------------------------------------------------------------------------

REQUISITES_KEYS = [
    "operator_name",
    "operator_inn",
    "operator_ogrnip",
    "operator_reg_date",
    "operator_phone",
    "operator_email",
    "contact_email",
    "operator_tax_authority",
    "operator_address",
]


@app.route("/admin/requisites", methods=["GET", "POST"])
@login_required
def admin_requisites():
    from models import SiteText, load_site_texts

    session = SessionLocal()
    try:
        if request.method == "POST":
            for key in REQUISITES_KEYS:
                value = (request.form.get(key) or "").strip()
                row = session.query(SiteText).filter_by(key=key).first()
                if row:
                    row.value = value
                else:
                    session.add(SiteText(key=key, value=value))
            session.commit()
            flash("Реквизиты сохранены.", "success")
            return redirect(url_for("admin_requisites"))

        return render_template("admin/requisites.html")
    except Exception as exc:
        session.rollback()
        logger.exception("Error saving requisites: %s", exc)
        flash("Ошибка при сохранении.", "error")
        return redirect(url_for("admin_requisites"))
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Архив журнала входов.
# ---------------------------------------------------------------------------

@app.route("/admin/archive-setup", methods=["GET", "POST"])
@login_required
def admin_archive_setup():
    """Мастер первоначальной настройки архива (показывается один раз после входа)."""
    if request.method == "POST":
        archive_dir = (request.form.get("archive_dir") or "").strip()
        enabled     = bool(request.form.get("enabled"))
        notify      = bool(request.form.get("notify"))
        if not archive_dir:
            flash("Укажите папку для архива.", "error")
            return redirect(url_for("admin_archive_setup"))
        csv_path = resolve_archive_path(archive_dir)
        if csv_path is None:
            flash("Не удалось создать папку по указанному пути. Проверьте правильность пути и права доступа.", "error")
            return redirect(url_for("admin_archive_setup"))
        save_settings(enabled, archive_dir, notify)
        flash(f"Архив настроен. Файл будет сохраняться в: {csv_path}", "success")
        return redirect(url_for("admin_dashboard"))

    import os
    suggested = os.path.expanduser("~")
    return render_template("admin/archive_setup.html", suggested=suggested)


@app.route("/admin/archive", methods=["GET", "POST"])
@login_required
def admin_archive():
    """Настройки архива журнала входов (доступно всегда из меню)."""
    from login_archive import _get_settings, resolve_archive_path
    import os

    settings = _get_settings()
    archive_dir  = settings.get("login_archive_dir", "")
    enabled      = settings.get("login_archive_enabled", "no").lower() in ("yes","y","1","true","on","да")
    notify       = settings.get("login_archive_notify", "no").lower()  in ("yes","y","1","true","on","да")

    csv_path  = resolve_archive_path(archive_dir) if archive_dir else None
    csv_exists = bool(csv_path and csv_path.exists())
    csv_size   = f"{csv_path.stat().st_size:,} байт" if csv_exists else None

    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            new_dir    = (request.form.get("archive_dir") or "").strip()
            new_enabled = bool(request.form.get("enabled"))
            new_notify  = bool(request.form.get("notify"))
            if new_enabled and not new_dir:
                flash("Укажите папку для архива.", "error")
                return redirect(url_for("admin_archive"))
            if new_dir:
                test_path = resolve_archive_path(new_dir)
                if test_path is None:
                    flash("Не удалось создать папку по указанному пути.", "error")
                    return redirect(url_for("admin_archive"))
            save_settings(new_enabled, new_dir, new_notify)
            flash("Настройки архива сохранены.", "success")
            return redirect(url_for("admin_archive"))

    return render_template(
        "admin/archive.html",
        archive_dir=archive_dir,
        enabled=enabled,
        notify=notify,
        csv_path=str(csv_path) if csv_path else None,
        csv_exists=csv_exists,
        csv_size=csv_size,
    )


# ---------------------------------------------------------------------------
# Юридические страницы.
# ---------------------------------------------------------------------------

LEGAL_KEYS = [
    "legal_privacy_last_updated",
    "legal_offer_html",
    "legal_cookies_html",
]


@app.route("/admin/legal", methods=["GET", "POST"])
@login_required
def admin_legal():
    from models import SiteText

    session = SessionLocal()
    try:
        if request.method == "POST":
            for key in LEGAL_KEYS:
                value = (request.form.get(key) or "").strip()
                row = session.query(SiteText).filter_by(key=key).first()
                if row:
                    row.value = value
                else:
                    session.add(SiteText(key=key, value=value))
            session.commit()
            flash("Юридические страницы сохранены.", "success")
            return redirect(url_for("admin_legal"))

        return render_template("admin/legal.html")
    except Exception as exc:
        session.rollback()
        logger.exception("Error saving legal pages: %s", exc)
        flash("Ошибка при сохранении.", "error")
        return redirect(url_for("admin_legal"))
    finally:
        session.close()


@app.route("/admin/browse-dirs")
@login_required
def admin_browse_dirs():
    """Возвращает список подпапок заданного пути для браузера директорий."""
    from flask import jsonify
    import os

    requested = request.args.get("path", "").strip()
    if not requested:
        requested = os.path.expanduser("~")

    try:
        target = os.path.realpath(requested)
    except Exception:
        target = os.path.expanduser("~")

    dirs = []
    try:
        for entry in sorted(os.scandir(target), key=lambda e: e.name.lower()):
            if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                dirs.append(entry.name)
    except PermissionError:
        pass
    except Exception:
        pass

    parent = str(os.path.dirname(target)) if target != os.path.dirname(target) else None

    return jsonify({
        "current": target,
        "parent": parent,
        "dirs": dirs,
    })


# ---------------------------------------------------------------------------
# CSV-экспорт заявок
# ---------------------------------------------------------------------------

def _csv_response(filename: str, rows: list[list]) -> Response:
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM для Excel
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    for row in rows:
        writer.writerow(row)
    output = buf.getvalue()
    return Response(
        output,
        mimetype="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/admin/delivery-orders/export")
@login_required
def admin_delivery_orders_export():
    from models import DeliveryOrder
    show = request.args.get("show", "all")
    session = SessionLocal()
    try:
        q = session.query(DeliveryOrder)
        if show == "pending":
            q = q.filter(DeliveryOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(DeliveryOrder.is_processed.is_(True))
        orders = q.order_by(DeliveryOrder.is_processed.asc(), DeliveryOrder.created_at.desc()).all()

        rows = [["#", "Имя", "Телефон", "E-mail", "Адрес доставки",
                 "Сумма (₽)", "Комментарий", "Дата заявки", "Статус",
                 "Дата обработки", "Обработал"]]
        for o in orders:
            rows.append([
                o.id, o.contact_name, o.phone, o.email or "",
                o.delivery_address, o.total_amount or "",
                o.comment or "",
                o.created_at.strftime("%d.%m.%Y %H:%M"),
                "Выполнен" if o.is_processed else "Новый",
                o.processed_at.strftime("%d.%m.%Y %H:%M") if o.processed_at else "",
                o.processed_by or "",
            ])
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        return _csv_response(f"dostavka_{ts}.csv", rows)
    finally:
        session.close()


@app.route("/admin/business-lunches/export")
@login_required
def admin_business_lunches_export():
    from models import BusinessLunchOrder
    show = request.args.get("show", "all")
    session = SessionLocal()
    try:
        q = session.query(BusinessLunchOrder)
        if show == "pending":
            q = q.filter(BusinessLunchOrder.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(BusinessLunchOrder.is_processed.is_(True))
        orders = q.order_by(BusinessLunchOrder.is_processed.asc(), BusinessLunchOrder.created_at.desc()).all()

        rows = [["#", "Имя", "Компания", "Телефон", "E-mail",
                 "Количество чел.", "Дата доставки", "Время доставки",
                 "Адрес доставки", "Комплексы", "Комментарий",
                 "Дата заявки", "Статус", "Дата обработки", "Обработал"]]
        for o in orders:
            rows.append([
                o.id, o.contact_name, o.company or "", o.phone, o.email or "",
                o.persons, o.delivery_date, o.delivery_time or "",
                o.delivery_address, o.selected_combos or "",
                o.comment or "",
                o.created_at.strftime("%d.%m.%Y %H:%M"),
                "Обработана" if o.is_processed else "Новая",
                o.processed_at.strftime("%d.%m.%Y %H:%M") if o.processed_at else "",
                o.processed_by or "",
            ])
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        return _csv_response(f"biznes_lanchi_{ts}.csv", rows)
    finally:
        session.close()


@app.route("/admin/catering/export")
@login_required
def admin_catering_export():
    from models import CateringRequest
    show = request.args.get("show", "all")
    session = SessionLocal()
    try:
        q = session.query(CateringRequest)
        if show == "pending":
            q = q.filter(CateringRequest.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(CateringRequest.is_processed.is_(True))
        reqs = q.order_by(CateringRequest.is_processed.asc(), CateringRequest.created_at.desc()).all()

        rows = [["#", "Имя", "Компания", "Телефон", "E-mail",
                 "Формат", "Гостей", "Дата мероприятия", "Время",
                 "Место проведения", "Бюджет на гостя (₽)", "Итого (₽)",
                 "Комментарий", "Дата заявки", "Статус",
                 "Дата обработки", "Обработал"]]
        for r in reqs:
            total = (r.budget_per_guest * r.guests) if r.budget_per_guest else ""
            rows.append([
                r.id, r.contact_name, r.company or "", r.phone, r.email or "",
                r.event_format, r.guests, r.event_date, r.event_time or "",
                r.venue, r.budget_per_guest or "", total,
                r.comment or "",
                r.created_at.strftime("%d.%m.%Y %H:%M"),
                "Обработана" if r.is_processed else "Новая",
                r.processed_at.strftime("%d.%m.%Y %H:%M") if r.processed_at else "",
                r.processed_by or "",
            ])
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        return _csv_response(f"kejtering_{ts}.csv", rows)
    finally:
        session.close()


@app.route("/admin/events/export")
@login_required
def admin_events_export():
    from models import HallReservation
    show = request.args.get("show", "all")
    session = SessionLocal()
    try:
        q = session.query(HallReservation)
        if show == "pending":
            q = q.filter(HallReservation.is_processed.is_(False))
        elif show == "processed":
            q = q.filter(HallReservation.is_processed.is_(True))
        reqs = q.order_by(HallReservation.is_processed.asc(), HallReservation.created_at.desc()).all()

        rows = [["#", "Имя", "Компания", "Телефон", "E-mail",
                 "Тип мероприятия", "Гостей", "Дата", "Время",
                 "Длительность (ч)", "Оформление зала", "Помощь с меню",
                 "Комментарий", "Дата заявки", "Статус",
                 "Дата обработки", "Обработал"]]
        for r in reqs:
            rows.append([
                r.id, r.contact_name, r.company or "", r.phone, r.email or "",
                r.event_type, r.guests, r.event_date, r.event_time,
                r.duration_hours or "",
                "Да" if r.needs_decor else "Нет",
                "Да" if r.needs_menu_help else "Нет",
                r.comment or "",
                r.created_at.strftime("%d.%m.%Y %H:%M"),
                "Обработана" if r.is_processed else "Новая",
                r.processed_at.strftime("%d.%m.%Y %H:%M") if r.processed_at else "",
                r.processed_by or "",
            ])
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        return _csv_response(f"bankety_{ts}.csv", rows)
    finally:
        session.close()


@app.route("/admin/journal")
@login_required
def admin_journal():
    from datetime import datetime as _dt, timedelta

    from models import BusinessLunchOrder, CateringRequest, DeliveryOrder, HallReservation

    admin_filter = (request.args.get("admin") or "").strip()
    type_filter  = request.args.get("type", "all")
    period       = request.args.get("period", "all")

    now = _dt.utcnow()
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    tables = [
        (DeliveryOrder,      "delivery",  "Доставка",   "delivery_dining"),
        (BusinessLunchOrder, "lunch",     "Ланчи",      "restaurant"),
        (CateringRequest,    "catering",  "Кейтеринг",  "local_shipping"),
        (HallReservation,    "events",    "Банкеты",    "celebration"),
    ]

    entries = []
    all_admins = set()

    session = SessionLocal()
    try:
        for model, key, label, icon in tables:
            if type_filter != "all" and type_filter != key:
                continue
            q = session.query(model).filter(
                model.is_processed.is_(True),
                model.processed_by.isnot(None),
            )
            if since:
                q = q.filter(model.processed_at >= since)
            if admin_filter:
                q = q.filter(model.processed_by == admin_filter)
            for row in q.all():
                all_admins.add(row.processed_by)
                entries.append({
                    "processed_at": row.processed_at or row.created_at,
                    "admin":        row.processed_by,
                    "type_key":     key,
                    "type_label":   label,
                    "type_icon":    icon,
                    "order_id":     row.id,
                    "customer":     row.contact_name,
                    "phone":        row.phone,
                    "created_at":   row.created_at,
                })

        # Collect all distinct admin names for the filter dropdown
        if not admin_filter:
            for model, *_ in tables:
                for row in session.query(model.processed_by).filter(
                    model.is_processed.is_(True),
                    model.processed_by.isnot(None),
                ).distinct():
                    all_admins.add(row[0])

        entries.sort(key=lambda e: e["processed_at"] or _dt.min, reverse=True)

        return render_template(
            "admin/journal.html",
            entries=entries,
            all_admins=sorted(all_admins),
            admin_filter=admin_filter,
            type_filter=type_filter,
            period=period,
        )
    finally:
        session.close()


@app.route("/admin/journal/export")
@login_required
def admin_journal_export():
    from datetime import datetime as _dt, timedelta

    from models import BusinessLunchOrder, CateringRequest, DeliveryOrder, HallReservation

    admin_filter = (request.args.get("admin") or "").strip()
    type_filter  = request.args.get("type", "all")
    period       = request.args.get("period", "all")

    now = _dt.utcnow()
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    tables = [
        (DeliveryOrder,      "delivery",  "Доставка"),
        (BusinessLunchOrder, "lunch",     "Ланчи"),
        (CateringRequest,    "catering",  "Кейтеринг"),
        (HallReservation,    "events",    "Банкеты"),
    ]

    session = SessionLocal()
    try:
        rows = [["Дата обработки", "Администратор", "Тип заявки", "ID заявки",
                 "Клиент", "Телефон", "Дата поступления"]]
        entries = []
        for model, key, label in tables:
            if type_filter != "all" and type_filter != key:
                continue
            q = session.query(model).filter(
                model.is_processed.is_(True),
                model.processed_by.isnot(None),
            )
            if since:
                q = q.filter(model.processed_at >= since)
            if admin_filter:
                q = q.filter(model.processed_by == admin_filter)
            for row in q.all():
                entries.append((
                    row.processed_at or row.created_at,
                    row.processed_by,
                    label,
                    row.id,
                    row.contact_name,
                    row.phone,
                    row.created_at,
                ))
        entries.sort(key=lambda e: e[0] or _dt.min, reverse=True)
        for e in entries:
            rows.append([
                e[0].strftime("%d.%m.%Y %H:%M") if e[0] else "",
                e[1], e[2], e[3], e[4], e[5],
                e[6].strftime("%d.%m.%Y %H:%M") if e[6] else "",
            ])
        ts = _dt.utcnow().strftime("%Y%m%d_%H%M")
        return _csv_response(f"zhurnal_admin_{ts}.csv", rows)
    finally:
        session.close()


@app.route("/admin/stats/export")
@login_required
def admin_stats_export():
    from datetime import datetime as _dt, timedelta

    from models import BusinessLunchOrder, CateringRequest, DeliveryOrder, HallReservation

    period = request.args.get("period", "all")
    now = _dt.utcnow()
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    tables = [
        (DeliveryOrder,      "delivery",  "Доставка"),
        (BusinessLunchOrder, "lunch",     "Ланчи"),
        (CateringRequest,    "catering",  "Кейтеринг"),
        (HallReservation,    "events",    "Банкеты"),
    ]

    session = SessionLocal()
    try:
        stats = {}
        for model, key, _label in tables:
            q = session.query(model).filter(
                model.is_processed.is_(True),
                model.processed_by.isnot(None),
            )
            if since:
                q = q.filter(model.processed_at >= since)
            for row in q.all():
                by = row.processed_by
                if by not in stats:
                    stats[by] = {
                        "delivery": 0, "lunch": 0, "catering": 0, "events": 0,
                        "total": 0, "total_minutes": 0.0, "timed_count": 0, "last_at": None,
                    }
                stats[by][key] += 1
                stats[by]["total"] += 1
                if row.processed_at and row.created_at:
                    diff = (row.processed_at - row.created_at).total_seconds() / 60.0
                    if diff >= 0:
                        stats[by]["total_minutes"] += diff
                        stats[by]["timed_count"] += 1
                if row.processed_at:
                    if stats[by]["last_at"] is None or row.processed_at > stats[by]["last_at"]:
                        stats[by]["last_at"] = row.processed_at

        period_labels = {"today": "Сегодня", "week": "7 дней", "month": "30 дней", "all": "Всё время"}
        rows = [["Администратор", "Доставка", "Ланчи", "Кейтеринг", "Банкеты",
                 "Всего", "Ср. время обработки (мин)", "Последняя обработка",
                 "Период"]]
        for by, s in sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True):
            tc = s["timed_count"]
            avg = round(s["total_minutes"] / tc) if tc else ""
            last = s["last_at"].strftime("%d.%m.%Y %H:%M") if s["last_at"] else ""
            rows.append([
                by,
                s["delivery"], s["lunch"], s["catering"], s["events"],
                s["total"], avg, last,
                period_labels.get(period, period),
            ])

        ts = _dt.utcnow().strftime("%Y%m%d_%H%M")
        return _csv_response(f"statistika_adminov_{ts}.csv", rows)
    finally:
        session.close()
