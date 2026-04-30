"""
Отправка e-mail-уведомлений администратору.

Используется стандартная smtplib через переменные окружения:
- SMTP_HOST       — например, smtp.yandex.ru
- SMTP_PORT       — 465 (SSL) или 587 (STARTTLS)
- SMTP_USER       — логин (обычно совпадает с e-mail отправителя)
- SMTP_PASSWORD   — пароль приложения SMTP
- SMTP_FROM       — адрес «От кого» (если не задан — берётся SMTP_USER)

Если хотя бы одно из обязательных значений не задано или адрес получателя
не настроен в админке — функция возвращает (False, "причина") без падений,
чтобы не сломать оформление заказа.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from typing import Optional, Tuple

from db import SessionLocal

logger = logging.getLogger(__name__)


def _get_smtp_config() -> dict:
    import os

    return {
        "host": (os.environ.get("SMTP_HOST") or "").strip(),
        "port": (os.environ.get("SMTP_PORT") or "").strip(),
        "user": (os.environ.get("SMTP_USER") or "").strip(),
        "password": os.environ.get("SMTP_PASSWORD") or "",
        "from_addr": (
            os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or ""
        ).strip(),
    }


def smtp_status() -> dict:
    """Вернуть статус конфигурации SMTP (без раскрытия пароля)."""
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
    """Прочитать e-mail получателя и флаг включения уведомлений из site_texts."""
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
    """Низкоуровневая отправка письма. Возвращает (ok, message)."""
    cfg = _get_smtp_config()
    if smtp_status()["missing"]:
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
                    pass  # сервер без TLS
                s.login(cfg["user"], cfg["password"])
                s.send_message(msg)
        return True, f"Отправлено на {to_addr}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("SMTP send failed")
        return False, f"Ошибка SMTP: {exc.__class__.__name__}: {exc}"


def _format_order_email(order, base_url: str = "") -> Tuple[str, str, str]:
    """Сформировать subject + plain + html для письма по заявке."""
    from models import BUSINESS_LUNCH_MENU

    titles = {i["key"]: i["title"] for i in BUSINESS_LUNCH_MENU}
    prices = {i["key"]: i["price"] for i in BUSINESS_LUNCH_MENU}

    combo_keys = [k for k in (order.selected_combos or "").split(",") if k]
    combo_lines = [
        f"  • {titles.get(k, k)} — {prices.get(k, '?')}₽"
        for k in combo_keys
    ]

    subject = (
        f"Новая заявка на бизнес-ланч #{order.id}"
        f" — {order.persons} чел., {order.delivery_date}"
    )
    admin_link = f"{base_url}/admin/business-lunches" if base_url else "/admin/business-lunches"

    plain_lines = [
        f"Получена новая заявка на бизнес-ланч #{order.id}.",
        "",
        f"Контактное лицо: {order.contact_name}",
        f"Компания: {order.company or '—'}",
        f"Телефон: {order.phone}",
        f"E-mail: {order.email or '—'}",
        "",
        f"Дата доставки: {order.delivery_date}"
        + (f", время: {order.delivery_time}" if order.delivery_time else ""),
        f"Адрес: {order.delivery_address}",
        f"Количество персон: {order.persons}",
        "",
        "Выбранные комплексы:",
        *(combo_lines or ["  • не выбраны (уточнить у клиента)"]),
        "",
        f"Комментарий: {order.comment or '—'}",
        "",
        f"Открыть в админке: {admin_link}",
    ]
    plain = "\n".join(plain_lines)

    combos_html = "".join(
        f"<li>{titles.get(k, k)} — <strong>{prices.get(k, '?')}₽</strong></li>"
        for k in combo_keys
    ) or "<li><em>не выбраны (уточнить у клиента)</em></li>"

    html = f"""\
<!doctype html>
<html><body style="font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#1d1c16; background:#f5f1e8; padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,0.06);">
    <tr><td style="background:#9b3f1c; color:#fff; padding:18px 24px;">
      <div style="font-size:11px; letter-spacing:0.15em; text-transform:uppercase; opacity:0.85;">Аксай Гриль · уведомление</div>
      <div style="font-size:20px; font-weight:600; margin-top:4px;">Новая заявка #{order.id}</div>
    </td></tr>
    <tr><td style="padding:20px 24px;">
      <p style="margin:0 0 14px;">Получена новая заявка на бизнес-ланч от компании.</p>
      <table width="100%" cellpadding="6" cellspacing="0" style="font-size:14px;">
        <tr><td style="color:#56423a; width:40%;">Контактное лицо</td><td><strong>{order.contact_name}</strong></td></tr>
        <tr><td style="color:#56423a;">Компания</td><td>{order.company or '—'}</td></tr>
        <tr><td style="color:#56423a;">Телефон</td><td><a href="tel:{order.phone}" style="color:#9b3f1c;">{order.phone}</a></td></tr>
        <tr><td style="color:#56423a;">E-mail</td><td>{order.email or '—'}</td></tr>
        <tr><td style="color:#56423a;">Дата / время</td><td>{order.delivery_date}{', ' + order.delivery_time if order.delivery_time else ''}</td></tr>
        <tr><td style="color:#56423a;">Адрес</td><td>{order.delivery_address}</td></tr>
        <tr><td style="color:#56423a;">Персон</td><td><strong>{order.persons}</strong></td></tr>
      </table>
      <div style="margin-top:18px;">
        <div style="font-size:12px; color:#56423a; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:6px;">Выбранные комплексы</div>
        <ul style="margin:0; padding-left:18px;">{combos_html}</ul>
      </div>
      {f'<div style="margin-top:18px;"><div style="font-size:12px; color:#56423a; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:6px;">Комментарий</div><div style="white-space:pre-wrap;">{order.comment}</div></div>' if order.comment else ''}
      <div style="margin-top:24px;">
        <a href="{admin_link}" style="display:inline-block; background:#9b3f1c; color:#fff; padding:10px 18px; border-radius:8px; text-decoration:none; font-weight:600; font-size:14px;">Открыть в админке</a>
      </div>
    </td></tr>
    <tr><td style="background:#f5f1e8; padding:14px 24px; font-size:11px; color:#56423a;">
      Это автоматическое уведомление. На него отвечать не нужно.
    </td></tr>
  </table>
</body></html>"""

    return subject, plain, html


def send_order_notification(order, base_url: str = "") -> Tuple[bool, str]:
    """Послать уведомление о новой заявке. Возвращает (ok, message)."""
    recipient, enabled = _get_recipient_and_toggle()
    if not enabled:
        return False, "Уведомления выключены в настройках."
    if not recipient:
        return False, "Не задан e-mail получателя в настройках."

    subject, plain, html = _format_order_email(order, base_url=base_url)
    return _send_smtp(subject, plain, html, recipient)


def send_order_notification_async(order_data: dict, base_url: str = "") -> None:
    """Отправить уведомление в фоне, чтобы не задерживать ответ HTTP.

    Принимает dict с примитивами (не объект SQLA), чтобы не таскать сессию
    в другой поток.
    """
    class _OrderShim:
        pass

    o = _OrderShim()
    for k, v in order_data.items():
        setattr(o, k, v)

    def _run():
        try:
            ok, msg = send_order_notification(o, base_url=base_url)
            if ok:
                logger.info("Order notification sent: %s", msg)
            else:
                logger.warning("Order notification skipped: %s", msg)
        except Exception:  # noqa: BLE001
            logger.exception("Order notification crashed")

    threading.Thread(target=_run, daemon=True, name="order-notify").start()


def _format_catering_email(req, base_url: str = "") -> Tuple[str, str, str]:
    """Сформировать subject + plain + html для письма по заявке на кейтеринг."""
    from models import CATERING_FORMATS

    formats = {f["key"]: f["title"] for f in CATERING_FORMATS}
    fmt_title = formats.get(req.event_format, req.event_format)

    subject = (
        f"Новая заявка на кейтеринг #{req.id}"
        f" — {fmt_title}, {req.guests} гостей, {req.event_date}"
    )
    admin_link = f"{base_url}/admin/catering" if base_url else "/admin/catering"

    budget_line = (
        f"Бюджет на гостя: {req.budget_per_guest}₽"
        f" (≈ {req.budget_per_guest * req.guests}₽ на всех)"
        if req.budget_per_guest else "Бюджет на гостя: не указан"
    )

    plain_lines = [
        f"Получена новая заявка на кейтеринг #{req.id}.",
        "",
        f"Контактное лицо: {req.contact_name}",
        f"Компания / организатор: {req.company or '—'}",
        f"Телефон: {req.phone}",
        f"E-mail: {req.email or '—'}",
        "",
        f"Формат: {fmt_title}",
        f"Дата мероприятия: {req.event_date}"
        + (f", время: {req.event_time}" if req.event_time else ""),
        f"Площадка: {req.venue}",
        f"Количество гостей: {req.guests}",
        budget_line,
        "",
        f"Комментарий: {req.comment or '—'}",
        "",
        f"Открыть в админке: {admin_link}",
    ]
    plain = "\n".join(plain_lines)

    html = f"""\
<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1d1c16;background:#f5f1e8;padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.06);">
    <tr><td style="background:#9b3f1c;color:#fff;padding:18px 24px;">
      <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;opacity:0.85;">Аксай Гриль · кейтеринг</div>
      <div style="font-size:20px;font-weight:600;margin-top:4px;">Новая заявка #{req.id}</div>
    </td></tr>
    <tr><td style="padding:20px 24px;">
      <p style="margin:0 0 14px;">Получена новая заявка на обслуживание мероприятия.</p>
      <table width="100%" cellpadding="6" cellspacing="0" style="font-size:14px;">
        <tr><td style="color:#56423a;width:40%;">Контактное лицо</td><td><strong>{req.contact_name}</strong></td></tr>
        <tr><td style="color:#56423a;">Компания</td><td>{req.company or '—'}</td></tr>
        <tr><td style="color:#56423a;">Телефон</td><td><a href="tel:{req.phone}" style="color:#9b3f1c;">{req.phone}</a></td></tr>
        <tr><td style="color:#56423a;">E-mail</td><td>{req.email or '—'}</td></tr>
        <tr><td style="color:#56423a;">Формат</td><td><strong>{fmt_title}</strong></td></tr>
        <tr><td style="color:#56423a;">Дата / время</td><td>{req.event_date}{', ' + req.event_time if req.event_time else ''}</td></tr>
        <tr><td style="color:#56423a;">Площадка</td><td>{req.venue}</td></tr>
        <tr><td style="color:#56423a;">Гостей</td><td><strong>{req.guests}</strong></td></tr>
        <tr><td style="color:#56423a;">Бюджет на гостя</td><td>{(str(req.budget_per_guest) + '₽ (≈ ' + str(req.budget_per_guest * req.guests) + '₽ на всех)') if req.budget_per_guest else '<em>не указан</em>'}</td></tr>
      </table>
      {f'<div style="margin-top:18px;"><div style="font-size:12px;color:#56423a;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Комментарий</div><div style="white-space:pre-wrap;">{req.comment}</div></div>' if req.comment else ''}
      <div style="margin-top:24px;">
        <a href="{admin_link}" style="display:inline-block;background:#9b3f1c;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">Открыть в админке</a>
      </div>
    </td></tr>
    <tr><td style="background:#f5f1e8;padding:14px 24px;font-size:11px;color:#56423a;">
      Это автоматическое уведомление. На него отвечать не нужно.
    </td></tr>
  </table>
</body></html>"""

    return subject, plain, html


def send_catering_notification(req, base_url: str = "") -> Tuple[bool, str]:
    """Отправить уведомление о новой заявке на кейтеринг."""
    recipient, enabled = _get_recipient_and_toggle()
    if not enabled:
        return False, "Уведомления выключены в настройках."
    if not recipient:
        return False, "Не задан e-mail получателя в настройках."
    subject, plain, html = _format_catering_email(req, base_url=base_url)
    return _send_smtp(subject, plain, html, recipient)


def send_catering_notification_async(data: dict, base_url: str = "") -> None:
    """Фоновая отправка уведомления о заявке на кейтеринг."""
    class _Shim:
        pass

    o = _Shim()
    for k, v in data.items():
        setattr(o, k, v)

    def _run():
        try:
            ok, msg = send_catering_notification(o, base_url=base_url)
            if ok:
                logger.info("Catering notification sent: %s", msg)
            else:
                logger.warning("Catering notification skipped: %s", msg)
        except Exception:  # noqa: BLE001
            logger.exception("Catering notification crashed")

    threading.Thread(target=_run, daemon=True, name="catering-notify").start()


def send_test_email(to_addr: str) -> Tuple[bool, str]:
    """Отправить тестовое письмо для проверки настроек SMTP."""
    subject = "Тест уведомлений · Аксай Гриль"
    plain = (
        "Это тестовое письмо от Аксай Гриль.\n\n"
        "Если вы видите это сообщение, значит настройки SMTP работают, "
        "и админка сможет присылать уведомления о новых заявках на бизнес-ланчи."
    )
    html = """\
<!doctype html><html><body style="font-family:Arial,sans-serif;background:#f5f1e8;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;padding:24px;border-radius:12px;">
  <div style="font-size:11px;color:#56423a;text-transform:uppercase;letter-spacing:0.15em;">Аксай Гриль</div>
  <h2 style="color:#9b3f1c;margin:6px 0 12px;font-weight:300;">Тест уведомлений</h2>
  <p>Это тестовое письмо. Если вы его видите — настройки SMTP работают,
  и уведомления о новых заявках на бизнес-ланчи будут приходить на этот адрес.</p>
</div></body></html>"""
    return _send_smtp(subject, plain, html, to_addr)


def _format_hall_email(req, base_url: str = "") -> Tuple[str, str, str]:
    """Сформировать subject + plain + html для бронирования зала."""
    from models import EVENT_TYPES

    types = {t["key"]: t["title"] for t in EVENT_TYPES}
    type_title = types.get(req.event_type, req.event_type)

    subject = (
        f"Новая заявка на банкет #{req.id}"
        f" — {type_title}, {req.guests} гостей, {req.event_date}"
    )
    admin_link = f"{base_url}/admin/events" if base_url else "/admin/events"

    extras = []
    if req.needs_decor:
        extras.append("оформление зала")
    if req.needs_menu_help:
        extras.append("помощь с меню")
    extras_line = ", ".join(extras) if extras else "—"

    duration_line = (
        f"{req.duration_hours} ч" if req.duration_hours else "не указана"
    )

    plain_lines = [
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
    ]
    plain = "\n".join(plain_lines)

    html = f"""\
<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1d1c16;background:#f5f1e8;padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.06);">
    <tr><td style="background:#9b3f1c;color:#fff;padding:18px 24px;">
      <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;opacity:0.85;">Аксай Гриль · банкеты</div>
      <div style="font-size:20px;font-weight:600;margin-top:4px;">Новая заявка #{req.id}</div>
    </td></tr>
    <tr><td style="padding:20px 24px;">
      <p style="margin:0 0 14px;">Получена новая заявка на бронирование зала.</p>
      <table width="100%" cellpadding="6" cellspacing="0" style="font-size:14px;">
        <tr><td style="color:#56423a;width:40%;">Контактное лицо</td><td><strong>{req.contact_name}</strong></td></tr>
        <tr><td style="color:#56423a;">Компания</td><td>{req.company or '—'}</td></tr>
        <tr><td style="color:#56423a;">Телефон</td><td><a href="tel:{req.phone}" style="color:#9b3f1c;">{req.phone}</a></td></tr>
        <tr><td style="color:#56423a;">E-mail</td><td>{req.email or '—'}</td></tr>
        <tr><td style="color:#56423a;">Тип</td><td><strong>{type_title}</strong></td></tr>
        <tr><td style="color:#56423a;">Дата / начало</td><td>{req.event_date} в {req.event_time}</td></tr>
        <tr><td style="color:#56423a;">Длительность</td><td>{duration_line}</td></tr>
        <tr><td style="color:#56423a;">Гостей</td><td><strong>{req.guests}</strong></td></tr>
        <tr><td style="color:#56423a;">Доп. услуги</td><td>{extras_line}</td></tr>
      </table>
      {f'<div style="margin-top:18px;"><div style="font-size:12px;color:#56423a;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Комментарий</div><div style="white-space:pre-wrap;">{req.comment}</div></div>' if req.comment else ''}
      <div style="margin-top:24px;">
        <a href="{admin_link}" style="display:inline-block;background:#9b3f1c;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">Открыть в админке</a>
      </div>
    </td></tr>
    <tr><td style="background:#f5f1e8;padding:14px 24px;font-size:11px;color:#56423a;">
      Это автоматическое уведомление. На него отвечать не нужно.
    </td></tr>
  </table>
</body></html>"""

    return subject, plain, html


def send_hall_notification(req, base_url: str = "") -> Tuple[bool, str]:
    """Отправить уведомление о новой заявке на бронирование зала."""
    recipient, enabled = _get_recipient_and_toggle()
    if not enabled:
        return False, "Уведомления выключены в настройках."
    if not recipient:
        return False, "Не задан e-mail получателя в настройках."
    subject, plain, html = _format_hall_email(req, base_url=base_url)
    return _send_smtp(subject, plain, html, recipient)


def send_hall_notification_async(data: dict, base_url: str = "") -> None:
    """Фоновая отправка уведомления о бронировании зала."""
    class _Shim:
        pass

    o = _Shim()
    for k, v in data.items():
        setattr(o, k, v)

    def _run():
        try:
            ok, msg = send_hall_notification(o, base_url=base_url)
            if ok:
                logger.info("Hall reservation notification sent: %s", msg)
            else:
                logger.warning("Hall reservation notification not sent: %s", msg)
        except Exception:
            logger.exception("Hall reservation notification failed")

    threading.Thread(target=_run, daemon=True).start()
