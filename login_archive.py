"""
Локальное CSV-архивирование журнала входов.

Настройки хранятся в site_texts:
  login_archive_enabled  — "yes" / "no"
  login_archive_dir      — абсолютный или относительный путь к папке
  login_archive_notify   — "yes" / "no"  (email при каждом входе)
"""
from __future__ import annotations

import csv
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ARCHIVE_SUBDIR = "login_archive"
CSV_FILENAME   = "login_log.csv"
CSV_HEADER     = ["datetime_utc", "username", "result", "ip", "user_agent"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings() -> dict:
    try:
        from db import SessionLocal
        session = SessionLocal()
        try:
            from sqlalchemy import text
            rows = session.execute(
                text("SELECT key, value FROM site_texts WHERE key IN "
                     "('login_archive_enabled','login_archive_dir','login_archive_notify')")
            ).fetchall()
            return {r[0]: (r[1] or "").strip() for r in rows}
        finally:
            session.close()
    except Exception:
        return {}


def _bool(val: str) -> bool:
    return val.strip().lower() in ("yes", "y", "1", "true", "on", "да")


def resolve_archive_path(base_dir: str) -> Optional[Path]:
    """Вернуть Path к CSV-файлу или None при ошибке."""
    try:
        p = Path(base_dir).expanduser().resolve()
        p = p / ARCHIVE_SUBDIR
        p.mkdir(parents=True, exist_ok=True)
        return p / CSV_FILENAME
    except Exception as exc:
        logger.warning("login_archive: cannot resolve path %r: %s", base_dir, exc)
        return None


def _write_row(csv_path: Path, row: dict) -> None:
    new_file = not csv_path.exists()
    try:
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
            if new_file:
                writer.writeheader()
            writer.writerow(row)
    except Exception as exc:
        logger.warning("login_archive: write failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def archive_login(
    username: str,
    success: bool,
    ip: str,
    user_agent: str,
) -> None:
    """Записать строку в CSV-архив (синхронно, вызывать из фонового треда)."""
    settings = _get_settings()
    if not _bool(settings.get("login_archive_enabled", "no")):
        return

    base_dir = settings.get("login_archive_dir", "").strip()
    if not base_dir:
        logger.debug("login_archive: no directory configured, skipping")
        return

    csv_path = resolve_archive_path(base_dir)
    if csv_path is None:
        return

    row = {
        "datetime_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "username":     username,
        "result":       "успех" if success else "отказ",
        "ip":           ip or "",
        "user_agent":   user_agent or "",
    }
    _write_row(csv_path, row)
    logger.info("login_archive: wrote %s for %r at %s", row["result"], username, csv_path)


def archive_login_async(
    username: str,
    success: bool,
    ip: str,
    user_agent: str,
) -> None:
    """Запустить запись в фоновом треде, не блокируя запрос."""
    def _run():
        try:
            archive_login(username, success, ip, user_agent)
        except Exception:
            logger.exception("login_archive: async write crashed")

    threading.Thread(target=_run, daemon=True, name="login-archive").start()


def send_login_notify_async(
    username: str,
    success: bool,
    ip: str,
    user_agent: str,
    base_url: str = "",
) -> None:
    """Email-уведомление о входе через уже готовый SMTP (фоново)."""
    settings = _get_settings()
    if not _bool(settings.get("login_archive_notify", "no")):
        return

    def _run():
        try:
            from mailer import _send_smtp, _get_recipient_and_toggle
            recipient, enabled = _get_recipient_and_toggle()
            if not enabled or not recipient:
                return

            result_word = "УСПЕШНЫЙ ВХОД" if success else "НЕУДАЧНАЯ ПОПЫТКА ВХОДА"
            emoji      = "✅" if success else "⚠️"
            ts         = datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")
            subject    = f"{emoji} Аксай Гриль: {result_word} — {username}"

            plain = (
                f"Событие входа в панель администратора.\n\n"
                f"Логин: {username}\n"
                f"Результат: {'успех' if success else 'отказ'}\n"
                f"Время: {ts}\n"
                f"IP: {ip or '—'}\n"
                f"User-Agent: {user_agent or '—'}\n\n"
                f"Если это не вы — немедленно смените пароль."
            )

            brand   = "#9b3f1c"
            bg_bad  = "#fce8e8"
            bg_good = "#e8f5e9"
            bg      = bg_good if success else bg_bad
            color   = "#2e7d32" if success else "#c62828"

            html = f"""\
<!doctype html><html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f5f1e8;padding:24px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.06);">
  <div style="background:{brand};color:#fff;padding:18px 24px;">
    <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;opacity:0.85;">Аксай Гриль · безопасность</div>
    <div style="font-size:20px;font-weight:600;margin-top:4px;">{emoji} {result_word}</div>
  </div>
  <div style="padding:20px 24px;">
    <div style="background:{bg};color:{color};border-radius:8px;padding:12px 16px;font-size:14px;margin-bottom:16px;">
      {'Вход в панель администратора выполнен успешно.' if success else 'Зафиксирована неудачная попытка входа.'}
    </div>
    <table width="100%" cellpadding="6" cellspacing="0" style="font-size:14px;">
      <tr><td style="color:#56423a;width:40%;">Логин</td><td><strong>{username}</strong></td></tr>
      <tr><td style="color:#56423a;">Время (UTC)</td><td>{ts}</td></tr>
      <tr><td style="color:#56423a;">IP-адрес</td><td style="font-family:monospace;">{ip or '—'}</td></tr>
      <tr><td style="color:#56423a;">Браузер</td><td style="font-size:12px;">{user_agent[:120] if user_agent else '—'}</td></tr>
    </table>
    {"<p style='margin-top:18px;font-size:13px;color:#c62828;font-weight:600;'>Если это были не вы — немедленно смените пароль.</p>" if not success else ""}
  </div>
  <div style="background:#f5f1e8;padding:14px 24px;font-size:11px;color:#56423a;">
    Автоматическое уведомление. {'Если ваши данные скомпрометированы — обратитесь к разработчику.' if not success else 'На это письмо отвечать не нужно.'}
  </div>
</div></body></html>"""

            _send_smtp(subject, plain, html, recipient)
        except Exception:
            logger.exception("login_archive: email notify crashed")

    threading.Thread(target=_run, daemon=True, name="login-notify").start()


def is_setup_done() -> bool:
    """True если архив уже был настроен (ключ есть в БД)."""
    try:
        from db import SessionLocal
        from sqlalchemy import text
        session = SessionLocal()
        try:
            row = session.execute(
                text("SELECT value FROM site_texts WHERE key='login_archive_dir' LIMIT 1")
            ).fetchone()
            return bool(row)
        finally:
            session.close()
    except Exception:
        return False


def save_settings(enabled: bool, archive_dir: str, notify: bool) -> None:
    """Сохранить настройки архива в site_texts."""
    from db import SessionLocal
    from models import SiteText
    session = SessionLocal()
    try:
        pairs = [
            ("login_archive_enabled", "yes" if enabled else "no"),
            ("login_archive_dir",     archive_dir.strip()),
            ("login_archive_notify",  "yes" if notify else "no"),
        ]
        existing = {r.key: r for r in session.query(SiteText).filter(
            SiteText.key.in_([k for k, _ in pairs])
        ).all()}
        for key, value in pairs:
            if key in existing:
                existing[key].value = value
            else:
                session.add(SiteText(key=key, value=value))
        session.commit()
    finally:
        session.close()
