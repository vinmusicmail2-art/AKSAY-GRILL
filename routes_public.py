"""Публичные маршруты Аксай Гриль."""
import logging

from flask import flash, redirect, render_template, request, send_from_directory, url_for

from app import app, csrf, _client_ip
from db import BASE_DIR, SessionLocal

logger = logging.getLogger(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/privacy.html")
def privacy():
    return render_template("privacy.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/business-lunch", methods=["GET", "POST"])
def business_lunch():
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

            order_snapshot = {
                "id": order.id,
                "contact_name": order.contact_name,
                "company": order.company,
                "phone": order.phone,
                "email": order.email,
                "persons": order.persons,
                "delivery_date": order.delivery_date,
                "delivery_time": order.delivery_time,
                "delivery_address": order.delivery_address,
                "selected_combos": order.selected_combos,
                "comment": order.comment,
            }

            from mailer import send_order_notification_async
            send_order_notification_async(order_snapshot, base_url=request.host_url.rstrip("/"))

            flash("Заявка принята. Мы свяжемся с вами для подтверждения.", "success")
            return redirect(url_for("business_lunch"))
        finally:
            session.close()

    return render_template("business-lunch.html", menu=BUSINESS_LUNCH_MENU, form=form)


@app.route("/catering", methods=["GET", "POST"])
def catering():
    from forms import CateringRequestForm
    from models import CATERING_FORMATS, CateringRequest

    form = CateringRequestForm()
    form.event_format.choices = [
        (item["key"], item["title"]) for item in CATERING_FORMATS
    ]

    if form.validate_on_submit():
        session = SessionLocal()
        try:
            req = CateringRequest(
                contact_name=form.contact_name.data.strip(),
                company=(form.company.data or "").strip() or None,
                phone=form.phone.data.strip(),
                email=(form.email.data or "").strip() or None,
                event_format=form.event_format.data,
                guests=form.guests.data,
                event_date=form.event_date.data.isoformat(),
                event_time=(form.event_time.data or "").strip() or None,
                venue=form.venue.data.strip(),
                budget_per_guest=form.budget_per_guest.data,
                comment=(form.comment.data or "").strip() or None,
                ip_address=_client_ip(),
            )
            session.add(req)
            session.commit()

            req_snapshot = {
                "id": req.id,
                "contact_name": req.contact_name,
                "company": req.company,
                "phone": req.phone,
                "email": req.email,
                "event_format": req.event_format,
                "guests": req.guests,
                "event_date": req.event_date,
                "event_time": req.event_time,
                "venue": req.venue,
                "budget_per_guest": req.budget_per_guest,
                "comment": req.comment,
            }

            from mailer import send_catering_notification_async
            send_catering_notification_async(req_snapshot, base_url=request.host_url.rstrip("/"))

            flash(
                "Заявка принята. Менеджер свяжется с вами для расчёта меню и согласования деталей.",
                "success",
            )
            return redirect(url_for("catering"))
        finally:
            session.close()

    return render_template("catering.html", formats=CATERING_FORMATS, form=form)


@app.route("/events", methods=["GET", "POST"])
def events():
    from forms import HallReservationForm
    from models import EVENT_TYPES, HallReservation

    form = HallReservationForm()
    form.event_type.choices = [
        (item["key"], item["title"]) for item in EVENT_TYPES
    ]

    if form.validate_on_submit():
        session = SessionLocal()
        try:
            req = HallReservation(
                contact_name=form.contact_name.data.strip(),
                company=(form.company.data or "").strip() or None,
                phone=form.phone.data.strip(),
                email=(form.email.data or "").strip() or None,
                event_type=form.event_type.data,
                guests=form.guests.data,
                event_date=form.event_date.data.isoformat(),
                event_time=(form.event_time.data or "").strip(),
                duration_hours=form.duration_hours.data,
                needs_decor=bool(form.needs_decor.data),
                needs_menu_help=bool(form.needs_menu_help.data),
                comment=(form.comment.data or "").strip() or None,
                ip_address=_client_ip(),
            )
            session.add(req)
            session.commit()

            req_snapshot = {
                "id": req.id,
                "contact_name": req.contact_name,
                "company": req.company,
                "phone": req.phone,
                "email": req.email,
                "event_type": req.event_type,
                "guests": req.guests,
                "event_date": req.event_date,
                "event_time": req.event_time,
                "duration_hours": req.duration_hours,
                "needs_decor": req.needs_decor,
                "needs_menu_help": req.needs_menu_help,
                "comment": req.comment,
            }

            from mailer import send_hall_notification_async
            send_hall_notification_async(req_snapshot, base_url=request.host_url.rstrip("/"))

            flash(
                "Заявка на бронирование принята. Менеджер свяжется с вами, чтобы "
                "подтвердить дату, обсудить меню и оформление.",
                "success",
            )
            return redirect(url_for("events"))
        finally:
            session.close()

    return render_template("events.html", event_types=EVENT_TYPES, form=form)


@app.route("/uploads/<path:filename>")
def uploads(filename: str):
    uploads_dir = BASE_DIR / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    return send_from_directory(uploads_dir, filename)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/order/delivery", methods=["POST"])
@csrf.exempt
def order_delivery():
    import json as _json
    from models import DeliveryOrder

    data = request.get_json(silent=True) or {}
    contact_name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip() or None
    delivery_address = (data.get("address") or "").strip()
    comment = (data.get("comment") or "").strip() or None
    items = data.get("items") or []
    total = data.get("total") or 0

    if not contact_name or not phone or not delivery_address or not items:
        return {"ok": False, "error": "Не заполнены обязательные поля."}, 400

    session = SessionLocal()
    try:
        order = DeliveryOrder(
            contact_name=contact_name,
            phone=phone,
            email=email,
            delivery_address=delivery_address,
            items_json=_json.dumps(items, ensure_ascii=False),
            total_amount=int(total),
            comment=comment,
            ip_address=_client_ip(),
        )
        session.add(order)
        session.commit()
        return {"ok": True, "id": order.id}
    finally:
        session.close()


@app.route("/quick-request", methods=["POST"])
def quick_request():
    from models import QuickRequest

    contact_name = (request.form.get("contact_name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    address = (request.form.get("address") or "").strip()
    comment = (request.form.get("comment") or "").strip() or None

    if not contact_name or not phone or not address:
        flash("Пожалуйста, заполните все обязательные поля.", "error")
        return redirect(url_for("home") + "#dostavka")

    session = SessionLocal()
    try:
        req = QuickRequest(
            contact_name=contact_name,
            phone=phone,
            address=address,
            comment=comment,
            ip_address=_client_ip(),
        )
        session.add(req)
        session.commit()
        flash("Заявка принята! Мы свяжемся с вами в ближайшее время.", "success")
        return redirect(url_for("home") + "#dostavka")
    finally:
        session.close()
