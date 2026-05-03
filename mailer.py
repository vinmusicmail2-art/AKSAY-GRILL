"""
Отправка e-mail-уведомлений администратору.

Переменные окружения:
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import threading
import types
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from typing import Optional, Tuple

from db import SessionLocal

logger = logging.getLogger(__name__)

_BRAND = "#9b3f1c"
_BODY_BG = "#f5f1e8"
_LABEL_COLOR = "#56423a"


def _get_smtp_password_from_db() -> str:
    """Читает пароль SMTP из таблицы site_texts, если он там сохранён."""
    try:
        from sqlalchemy import text
        session = SessionLocal()
        try:
            row = session.execute(
                text("SELECT value FROM site_texts WHERE key = 'smtp_password' LIMIT 1")
            ).fetchone()
            return (row[0] or "").strip() if row else ""
        finally:
            session.close()
    except Exception:
        return ""


def _get_smtp_config() -> dict:
    import os
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    if not password:
        password = _get_smtp_password_from_db()
    return {
        "host": (os.environ.get("SMTP_HOST") or "").strip(),
        "port": (os.environ.get("SMTP_PORT") or "").strip(),
        "user": (os.environ.get("SMTP_USER") or "").strip(),
        "password": password,
        "from_addr": (
            os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or ""
        ).strip(),
    }


def smtp_status() -> dict:
    cfg = _get_smtp_config()
    required = ["host", "port", "user", "password", "from_addr"]
    missing = [k for k in required if not cfg.get(k)]
    return {
        "host": cfg["host"] or None,
        "port": cfg["port"] or None,
        "user": cfg["user"] or None,
        "from_addr": cfg["from_addr"] or None,
        "password_set": bool(cfg["password"]),
        "missing": missing,
        "configured": not missing,
    }


def _get_recipient_and_toggle() -> Tuple[Optional[str], bool]:
    from models import load_site_texts

    session = SessionLocal()
    try:
        texts = load_site_texts(session)
    finally:
        session.close()
    recipient = (texts.get("notify_email_recipient") or "").strip() or None
    enabled = (texts.get("notify_email_enabled") or "").strip().lower() in (
        "1", "yes", "y", "true", "on", "да",
    )
    return recipient, enabled


def _send_smtp(subject: str, body_text: str, body_html: Optional[str],
               to_addr: str) -> Tuple[bool, str]:
    """Отправить письмо через SMTP. Возвращает (ok, сообщение)."""
    cfg = _get_smtp_config()
    missing = [k for k in ("host", "port", "user", "password", "from_addr") if not cfg.get(k)]
    if missing:
        return False, "SMTP не настроен (нет одного из SMTP_* секретов)."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Аксай Гриль", cfg["from_addr"]))
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        port = int(cfg["port"])
    except ValueError:
        return False, f"SMTP_PORT должен быть числом, получено: {cfg['port']!r}"

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], port, context=ctx, timeout=20) as s:
                s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], port, timeout=20) as s:
                s.ehlo()
                try:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                except smtplib.SMTPException:
                    pass
                s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
        return True, f"Отправлено на {to_addr}"
    except Exception as exc:
        logger.exception("SMTP send failed")
        return False, f"Ошибка SMTP: {exc.__class__.__name__}: {exc}"


def _render_email_html(
    order_id: int,
    subtitle: str,
    intro: str,
    rows_html: str,
    extras_html: str,
    admin_link: str,
) -> str:
    """Собрать полное HTML-письмо из секций."""
    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1d1c16;background:{_BODY_BG};padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.06);">
    <tr><td style="background:{_BRAND};color:#fff;padding:18px 24px;">
      <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;opacity:0.85;">Аксай Гриль · {subtitle}</div>
      <div style="font-size:20px;font-weight:600;margin-top:4px;">Новая заявка #{order_id}</div>
    </td></tr>
    <tr><td style="padding:20px 24px;">
      <p style="margin:0 0 14px;">{intro}</p>
      <table width="100%" cellpadding="6" cellspacing="0" style="font-size:14px;">{rows_html}</table>
      {extras_html}
      <div style="margin-top:24px;">
        <a href="{admin_link}" style="display:inline-block;background:{_BRAND};color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">Открыть в админке</a>
      </div>
    </td></tr>
    <tr><td style="background:{_BODY_BG};padding:14px 24px;font-size:11px;color:{_LABEL_COLOR};">
      Это автоматическое уведомление. На него отвечать не нужно.
    </td></tr>
  </table>
</body></html>"""


def _td_label(text: str) -> str:
    return f'<td style="color:{_LABEL_COLOR};width:40%;">{text}</td>'


def _comment_block(comment: str) -> str:
    if not comment:
        return ""
    return (
        f'<div style="margin-top:18px;">'
        f'<div style="font-size:12px;color:{_LABEL_COLOR};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Комментарий</div>'
        f'<div style="white-space:pre-wrap;">{comment}</div></div>'
    )


def _guarded_send(
    format_fn,
    req,
    base_url: str = "",
) -> Tuple[bool, str]:
    """Проверить флаг уведомлений и адрес получателя, затем отправить письмо.

    Используется всеми ``send_*_notification`` функциями вместо копипасты
    одинаковых четырёх строк guard-логики.
    """
    recipient, enabled = _get_recipient_and_toggle()
    if not enabled:
        return False, "Уведомления выключены в настройках."
    if not recipient:
        return False, "Не задан e-mail получателя в настройках."
    subject, plain, html = format_fn(req, base_url=base_url)
    return _send_smtp(subject, plain, html, recipient)


def _send_notification_async(send_fn, data: dict, base_url: str, thread_name: str) -> None:
    """Запустить ``send_fn`` в фоновом треде.

    ``data`` — словарь полей заявки; преобразуется в объект через
    ``SimpleNamespace`` чтобы форматировщики письма могли обращаться к
    атрибутам через точку (``req.phone`` и т.д.).
    """
    o = types.SimpleNamespace(**data)

    def _run():
        try:
            ok, msg = send_fn(o, base_url=base_url)
            if ok:
                logger.info("%s notification sent: %s", thread_name, msg)
            else:
                logger.warning("%s notification skipped: %s", thread_name, msg)
        except Exception:
            logger.exception("%s notification crashed", thread_name)

    threading.Thread(target=_run, daemon=True, name=thread_name).start()


# ──────────────────────────── Бизнес-ланч ────────────────────────────

def _format_order_email(order, base_url: str = "") -> Tuple[str, str, str]:
    from models import BUSINESS_LUNCH_MENU

    titles = {i["key"]: i["title"] for i in BUSINESS_LUNCH_MENU}
    prices = {i["key"]: i["price"] for i in BUSINESS_LUNCH_MENU}
    combo_keys = [k for k in (order.selected_combos or "").split(",") if k]

    subject = f"Новая заявка на бизнес-ланч #{order.id} — {order.persons} чел., {order.delivery_date}"
    admin_link = f"{base_url}/admin/business-lunches" if base_url else "/admin/business-lunches"

    plain = "\n".join([
        f"Получена новая заявка на бизнес-ланч #{order.id}.",
        "",
        f"Контактное лицо: {order.contact_name}",
        f"Компания: {order.company or '—'}",
        f"Телефон: {order.phone}",
        f"E-mail: {order.email or '—'}",
        "",
        f"Дата доставки: {order.delivery_date}" + (f", время: {order.delivery_time}" if order.delivery_time else ""),
        f"Адрес: {order.delivery_address}",
        f"Количество персон: {order.persons}",
        "",
        "Выбранные комплексы:",
        *([f"  • {titles.get(k, k)} — {prices.get(k, '?')}₽" for k in combo_keys]
          or ["  • не выбраны (уточнить у клиента)"]),
        "",
        f"Комментарий: {order.comment or '—'}",
        "",
        f"Открыть в админке: {admin_link}",
    ])

    combos_html = "".join(
        f"<li>{titles.get(k, k)} — <strong>{prices.get(k, '?')}₽</strong></li>"
        for k in combo_keys
    ) or "<li><em>не выбраны (уточнить у клиента)</em></li>"

    rows_html = (
        f"<tr>{_td_label('Контактное лицо')}<td><strong>{order.contact_name}</strong></td></tr>"
        f"<tr>{_td_label('Компания')}<td>{order.company or '—'}</td></tr>"
        f"<tr>{_td_label('Телефон')}<td><a href='tel:{order.phone}' style='color:{_BRAND};'>{order.phone}</a></td></tr>"
        f"<tr>{_td_label('E-mail')}<td>{order.email or '—'}</td></tr>"
        f"<tr>{_td_label('Дата / время')}<td>{order.delivery_date}{', ' + order.delivery_time if order.delivery_time else ''}</td></tr>"
        f"<tr>{_td_label('Адрес')}<td>{order.delivery_address}</td></tr>"
        f"<tr>{_td_label('Персон')}<td><strong>{order.persons}</strong></td></tr>"
    )
    extras_html = (
        f'<div style="margin-top:18px;">'
        f'<div style="font-size:12px;color:{_LABEL_COLOR};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Выбранные комплексы</div>'
        f'<ul style="margin:0;padding-left:18px;">{combos_html}</ul></div>'
        + _comment_block(order.comment or "")
    )

    html = _render_email_html(
        order.id, "уведомление",
        "Получена новая заявка на бизнес-ланч от компании.",
        rows_html, extras_html, admin_link,
    )
    return subject, plain, html


def send_order_notification(order, base_url: str = "") -> Tuple[bool, str]:
    """Отправить e-mail о новой заявке на бизнес-ланч."""
    return _guarded_send(_format_order_email, order, base_url)


def send_order_notification_async(order_data: dict, base_url: str = "") -> None:
    _send_notification_async(send_order_notification, order_data, base_url, "order-notify")


# ──────────────────────────── Кейтеринг ────────────────────────────

def _format_catering_email(req, base_url: str = "") -> Tuple[str, str, str]:
    from models import CATERING_FORMATS

    formats = {f["key"]: f["title"] for f in CATERING_FORMATS}
    fmt_title = formats.get(req.event_format, req.event_format)
    admin_link = f"{base_url}/admin/catering" if base_url else "/admin/catering"

    budget_line = (
        f"Бюджет на гостя: {req.budget_per_guest}₽ (≈ {req.budget_per_guest * req.guests}₽ на всех)"
        if req.budget_per_guest else "Бюджет на гостя: не указан"
    )

    subject = f"Новая заявка на кейтеринг #{req.id} — {fmt_title}, {req.guests} гостей, {req.event_date}"

    plain = "\n".join([
        f"Получена новая заявка на кейтеринг #{req.id}.",
        "",
        f"Контактное лицо: {req.contact_name}",
        f"Компания / организатор: {req.company or '—'}",
        f"Телефон: {req.phone}",
        f"E-mail: {req.email or '—'}",
        "",
        f"Формат: {fmt_title}",
        f"Дата мероприятия: {req.event_date}" + (f", время: {req.event_time}" if req.event_time else ""),
        f"Площадка: {req.venue}",
        f"Количество гостей: {req.guests}",
        budget_line,
        "",
        f"Комментарий: {req.comment or '—'}",
        "",
        f"Открыть в админке: {admin_link}",
    ])

    budget_html = (
        f"{req.budget_per_guest}₽ (≈ {req.budget_per_guest * req.guests}₽ на всех)"
        if req.budget_per_guest else "<em>не указан</em>"
    )
    rows_html = (
        f"<tr>{_td_label('Контактное лицо')}<td><strong>{req.contact_name}</strong></td></tr>"
        f"<tr>{_td_label('Компания')}<td>{req.company or '—'}</td></tr>"
        f"<tr>{_td_label('Телефон')}<td><a href='tel:{req.phone}' style='color:{_BRAND};'>{req.phone}</a></td></tr>"
        f"<tr>{_td_label('E-mail')}<td>{req.email or '—'}</td></tr>"
        f"<tr>{_td_label('Формат')}<td><strong>{fmt_title}</strong></td></tr>"
        f"<tr>{_td_label('Дата / время')}<td>{req.event_date}{', ' + req.event_time if req.event_time else ''}</td></tr>"
        f"<tr>{_td_label('Площадка')}<td>{req.venue}</td></tr>"
        f"<tr>{_td_label('Гостей')}<td><strong>{req.guests}</strong></td></tr>"
        f"<tr>{_td_label('Бюджет на гостя')}<td>{budget_html}</td></tr>"
    )

    html = _render_email_html(
        req.id, "кейтеринг",
        "Получена новая заявка на обслуживание мероприятия.",
        rows_html, _comment_block(req.comment or ""), admin_link,
    )
    return subject, plain, html


def send_catering_notification(req, base_url: str = "") -> Tuple[bool, str]:
    """Отправить e-mail о новой заявке на кейтеринг."""
    return _guarded_send(_format_catering_email, req, base_url)


def send_catering_notification_async(data: dict, base_url: str = "") -> None:
    _send_notification_async(send_catering_notification, data, base_url, "catering-notify")


# ──────────────────────────── Банкет / зал ────────────────────────────

def _format_hall_email(req, base_url: str = "") -> Tuple[str, str, str]:
    from models import EVENT_TYPES

    types = {t["key"]: t["title"] for t in EVENT_TYPES}
    type_title = types.get(req.event_type, req.event_type)
    admin_link = f"{base_url}/admin/events" if base_url else "/admin/events"

    extras = [x for x, flag in (("оформление зала", req.needs_decor), ("помощь с меню", req.needs_menu_help)) if flag]
    extras_line = ", ".join(extras) if extras else "—"
    duration_line = f"{req.duration_hours} ч" if req.duration_hours else "не указана"

    subject = f"Новая заявка на банкет #{req.id} — {type_title}, {req.guests} гостей, {req.event_date}"

    plain = "\n".join([
        f"Получена новая заявка на бронирование зала #{req.id}.",
        "",
        f"Контактное лицо: {req.contact_name}",
        f"Компания: {req.company or '—'}",
        f"Телефон: {req.phone}",
        f"E-mail: {req.email or '—'}",
        "",
        f"Тип мероприятия: {type_title}",
        f"Дата: {req.event_date}, начало: {req.event_time}",
        f"Длительность: {duration_line}",
        f"Гостей: {req.guests}",
        f"Доп. услуги: {extras_line}",
        "",
        f"Комментарий: {req.comment or '—'}",
        "",
        f"Открыть в админке: {admin_link}",
    ])

    rows_html = (
        f"<tr>{_td_label('Контактное лицо')}<td><strong>{req.contact_name}</strong></td></tr>"
        f"<tr>{_td_label('Компания')}<td>{req.company or '—'}</td></tr>"
        f"<tr>{_td_label('Телефон')}<td><a href='tel:{req.phone}' style='color:{_BRAND};'>{req.phone}</a></td></tr>"
        f"<tr>{_td_label('E-mail')}<td>{req.email or '—'}</td></tr>"
        f"<tr>{_td_label('Тип')}<td><strong>{type_title}</strong></td></tr>"
        f"<tr>{_td_label('Дата / начало')}<td>{req.event_date} в {req.event_time}</td></tr>"
        f"<tr>{_td_label('Длительность')}<td>{duration_line}</td></tr>"
        f"<tr>{_td_label('Гостей')}<td><strong>{req.guests}</strong></td></tr>"
        f"<tr>{_td_label('Доп. услуги')}<td>{extras_line}</td></tr>"
    )

    html = _render_email_html(
        req.id, "банкеты",
        "Получена новая заявка на бронирование зала.",
        rows_html, _comment_block(req.comment or ""), admin_link,
    )
    return subject, plain, html


def send_hall_notification(req, base_url: str = "") -> Tuple[bool, str]:
    """Отправить e-mail о новой заявке на бронирование зала."""
    return _guarded_send(_format_hall_email, req, base_url)


def send_hall_notification_async(data: dict, base_url: str = "") -> None:
    _send_notification_async(send_hall_notification, data, base_url, "hall-notify")


# ──────────────────────────── Доставка ────────────────────────────

def _format_delivery_email(order, base_url: str = "") -> Tuple[str, str, str]:
    admin_link = f"{base_url}/admin/delivery-orders" if base_url else "/admin/delivery-orders"

    subject = f"Новый заказ на доставку #{order.id} — {order.contact_name}, {order.total_amount or 0}₽"

    # Пытаемся распарсить состав заказа
    try:
        import json as _json
        items = _json.loads(order.items_json) if order.items_json else []
    except Exception:
        items = []

    items_lines = "\n".join(
        f"  • {i.get('name', '?')} × {i.get('qty', 1)} — {i.get('price', 0) * i.get('qty', 1)}₽"
        for i in items
    ) or "  (состав не распознан)"

    plain = "\n".join([
        f"Получен новый заказ на доставку #{order.id}.",
        "",
        f"Клиент:  {order.contact_name}",
        f"Телефон: {order.phone}",
        f"E-mail:  {order.email or '—'}",
        f"Адрес:   {order.delivery_address}",
        "",
        "Состав заказа:",
        items_lines,
        "",
        f"Итого: {order.total_amount or 0}₽",
        f"Комментарий: {order.comment or '—'}",
        "",
        f"Открыть в админке: {admin_link}",
    ])

    items_html = "".join(
        f"<li>{i.get('name','?')} × {i.get('qty',1)} — <strong>{i.get('price',0)*i.get('qty',1)}₽</strong></li>"
        for i in items
    ) or "<li><em>состав не распознан</em></li>"

    rows_html = (
        f"<tr>{_td_label('Клиент')}<td><strong>{order.contact_name}</strong></td></tr>"
        f"<tr>{_td_label('Телефон')}<td><a href='tel:{order.phone}' style='color:{_BRAND};'>{order.phone}</a></td></tr>"
        f"<tr>{_td_label('E-mail')}<td>{order.email or '—'}</td></tr>"
        f"<tr>{_td_label('Адрес доставки')}<td>{order.delivery_address}</td></tr>"
        f"<tr>{_td_label('Сумма')}<td><strong style='color:{_BRAND};font-size:16px;'>{order.total_amount or 0}₽</strong></td></tr>"
    )
    extras_html = (
        f'<div style="margin-top:18px;">'
        f'<div style="font-size:12px;color:{_LABEL_COLOR};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Состав заказа</div>'
        f'<ul style="margin:0;padding-left:18px;">{items_html}</ul></div>'
        + _comment_block(order.comment or "")
    )

    html = _render_email_html(
        order.id, "доставка",
        "Получен новый заказ из корзины на сайте.",
        rows_html, extras_html, admin_link,
    )
    return subject, plain, html


def send_delivery_notification(order, base_url: str = "") -> Tuple[bool, str]:
    """Отправить e-mail о новом заказе доставки."""
    return _guarded_send(_format_delivery_email, order, base_url)


def send_delivery_notification_async(order_data: dict, base_url: str = "") -> None:
    _send_notification_async(send_delivery_notification, order_data, base_url, "delivery-notify")


# ──────────────────────────── Быстрый заказ (главная страница) ────────────────────────────

def _format_quick_request_email(req, base_url: str = "") -> Tuple[str, str, str]:
    admin_link = f"{base_url}/admin/delivery-orders" if base_url else "/admin/delivery-orders"

    subject = f"Быстрый заказ с сайта — {req.contact_name}, {req.phone}"

    plain = "\n".join([
        "Получен быстрый заказ с главной страницы сайта.",
        "",
        f"Клиент:  {req.contact_name}",
        f"Телефон: {req.phone}",
        f"Адрес:   {req.address}",
        f"Комментарий: {req.comment or '—'}",
        "",
        f"Открыть заказы доставки в админке: {admin_link}",
    ])

    rows_html = (
        f"<tr>{_td_label('Клиент')}<td><strong>{req.contact_name}</strong></td></tr>"
        f"<tr>{_td_label('Телефон')}<td><a href='tel:{req.phone}' style='color:{_BRAND};'>{req.phone}</a></td></tr>"
        f"<tr>{_td_label('Адрес доставки')}<td>{req.address}</td></tr>"
    )

    html = _render_email_html(
        0, "быстрый заказ",
        "Клиент оставил заявку через кнопку «Заказать» на главной странице.",
        rows_html, _comment_block(req.comment or ""), admin_link,
    ).replace("Новая заявка #0", "Быстрый заказ с сайта")

    return subject, plain, html


def send_quick_request_notification(req, base_url: str = "") -> Tuple[bool, str]:
    """Отправить e-mail о быстром заказе с главной страницы."""
    return _guarded_send(_format_quick_request_email, req, base_url)


def send_quick_request_notification_async(data: dict, base_url: str = "") -> None:
    _send_notification_async(send_quick_request_notification, data, base_url, "quick-request-notify")


# ──────────────────────────── Контакт (вопрос с сайта) ────────────────────────────

def send_contact_question(name: str, phone: str, message: str) -> Tuple[bool, str]:
    """Отправить вопрос посетителя на адрес из настроек (notify_email_recipient)."""
    recipient, enabled = _get_recipient_and_toggle()
    if not enabled:
        return False, "Уведомления выключены в настройках."
    if not recipient:
        return False, "Не задан e-mail получателя в настройках."
    subject = f"Вопрос с сайта от {name}"
    plain = (
        f"Имя: {name}\n"
        f"Телефон: {phone}\n\n"
        f"Вопрос:\n{message}"
    )
    html = f"""\
<!doctype html><html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:{_BODY_BG};padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.06);">
  <div style="background:{_BRAND};color:#fff;padding:18px 24px;">
    <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;opacity:0.85;">Аксай Гриль · сайт</div>
    <div style="font-size:20px;font-weight:300;margin-top:4px;">Вопрос с сайта</div>
  </div>
  <div style="padding:20px 24px;">
    <table width="100%" cellpadding="6" cellspacing="0" style="font-size:14px;">
      <tr>{_td_label('Имя')}<td><strong>{name}</strong></td></tr>
      <tr>{_td_label('Телефон')}<td><a href="tel:{phone}" style="color:{_BRAND};">{phone}</a></td></tr>
    </table>
    <div style="margin-top:16px;">
      <div style="font-size:12px;color:{_LABEL_COLOR};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Вопрос</div>
      <div style="white-space:pre-wrap;font-size:14px;">{message}</div>
    </div>
  </div>
  <div style="background:{_BODY_BG};padding:14px 24px;font-size:11px;color:{_LABEL_COLOR};">
    Это автоматическое уведомление с сайта aksay-gril.ru
  </div>
</div></body></html>"""
    return _send_smtp(subject, plain, html, recipient)


# ──────────────────────────── Тест ────────────────────────────

def send_test_email(to_addr: str) -> Tuple[bool, str]:
    subject = "Тест уведомлений · Аксай Гриль"
    plain = (
        "Это тестовое письмо от Аксай Гриль.\n\n"
        "Если вы видите это сообщение, значит настройки SMTP работают."
    )
    html = f"""\
<!doctype html><html><body style="font-family:Arial,sans-serif;background:{_BODY_BG};padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;padding:24px;border-radius:12px;">
  <div style="font-size:11px;color:{_LABEL_COLOR};text-transform:uppercase;letter-spacing:0.15em;">Аксай Гриль</div>
  <h2 style="color:{_BRAND};margin:6px 0 12px;font-weight:300;">Тест уведомлений</h2>
  <p>Это тестовое письмо. Если вы его видите — настройки SMTP работают,
  и уведомления о новых заявках будут приходить на этот адрес.</p>
</div></body></html>"""
    return _send_smtp(subject, plain, html, to_addr)
