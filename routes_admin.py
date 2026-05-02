"""Административные маршруты Аксай Гриль."""
import json as _json
import logging
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
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
            .order_by(DeliveryOrder.created_at.desc())
            .limit(50)
            .all()
        )
        all_lunch = (
            session.query(BusinessLunchOrder)
            .order_by(BusinessLunchOrder.created_at.desc())
            .limit(50)
            .all()
        )
        all_catering = (
            session.query(CateringRequest)
            .order_by(CateringRequest.created_at.desc())
            .limit(50)
            .all()
        )
        all_events = (
            session.query(HallReservation)
            .order_by(HallReservation.created_at.desc())
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
            dish = Dish(
                category_id=category_id,
                name=name,
                description=(request.form.get("description") or "").strip(),
                price=int(request.form.get("price") or 0),
                image_src=(request.form.get("image_src") or "").strip(),
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
            dish.name = name
            dish.category_id = category_id
            dish.description = (request.form.get("description") or "").strip()
            dish.price = int(request.form.get("price") or 0)
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
