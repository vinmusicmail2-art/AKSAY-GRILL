from datetime import datetime
from typing import Type
from flask import flash, redirect, abort, url_for
from flask_login import current_user
from sqlalchemy.orm import Session


def toggle_processed_status(
    session: Session,
    model: Type,
    item_id: int,
    item_label: str,
    fallback_url: str
):
    """Generic handler for toggling processed status.

    Args:
        session: Database session
        model: SQLAlchemy model class
        item_id: ID of the item to toggle
        item_label: Label for flash messages (e.g., "Заявка")
        fallback_url: URL to redirect to after toggle

    Returns:
        Flask redirect response
    """
    item = session.get(model, item_id)
    if item is None:
        abort(404)

    if item.is_processed:
        item.is_processed = False
        item.processed_at = None
        item.processed_by = None
        flash(f"{item_label} #{item.id} возвращена в работу.", "success")
    else:
        item.is_processed = True
        item.processed_at = datetime.utcnow()
        item.processed_by = current_user.username
        flash(f"{item_label} #{item.id} отмечена как обработанная.", "success")

    session.commit()

    from app import _safe_referrer
    return redirect(_safe_referrer(fallback_url))
