"""
Модели БД для админки «Аксай Гриль».

- Admin: учётная запись администратора (UserMixin для Flask-Login).
- LoginLog: журнал попыток входа (152-ФЗ — ведём аудит доступа).
"""
from __future__ import annotations

from datetime import datetime

import bcrypt
from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from db import Base

# ---------------------------------------------------------------------------
# Каталог редактируемых текстов сайта.
# Описывается на уровне Python: ключ → (метка, тип поля, значение по умолчанию).
# При первом запуске значения по умолчанию записываются в БД,
# дальше админ редактирует их через /admin/texts.
# ---------------------------------------------------------------------------

SITE_TEXT_CATALOG: list[dict] = [
    {
        "key": "site_title",
        "label": "Заголовок вкладки браузера (<title>)",
        "kind": "text",
        "default": "Аксай Гриль | Вкусно, как дома",
        "section": "Главная страница",
    },
    {
        "key": "tagline",
        "label": "Слоган под логотипом",
        "kind": "text",
        "default": "Вкусно, как дома",
        "section": "Главная страница",
    },
    {
        "key": "hero_badge",
        "label": "Бейдж над заголовком героя",
        "kind": "text",
        "default": "Накормим вкусно, как дома!",
        "section": "Главная страница",
    },
    {
        "key": "hero_title",
        "label": "Заголовок героя",
        "kind": "textarea",
        "default": "Мясные и овощные блюда приготовленные на мангале или гриле:",
        "section": "Главная страница",
    },
    {
        "key": "hero_meat_text",
        "label": "Список мясных блюд героя (HTML, можно <br/>)",
        "kind": "html",
        "default": (
            "Шашлык (свинина, баранина, говядина, курица) / Люля-кебаб / "
            "Куриные крылья, бедра и ножки<br/>/ Свиные ребрышки / Стейки / "
            "Купаты, колбаски"
        ),
        "section": "Главная страница",
    },
    {
        "key": "hero_veg_text",
        "label": "Список овощных блюд героя (HTML, можно <br/>)",
        "kind": "html",
        "default": (
            "Аджапсандал / Овощи-гриль на шпажках / Запечённые перцы и "
            "баклажаны с чесноком и зеленью<br/>/ Овощная икра с дымком / "
            "Запеченные грибы"
        ),
        "section": "Главная страница",
    },
    {
        "key": "hero_cta_primary",
        "label": "Текст основной кнопки героя",
        "kind": "text",
        "default": "Заказать доставку",
        "section": "Главная страница",
    },
    {
        "key": "hero_cta_secondary",
        "label": "Текст второй кнопки героя",
        "kind": "text",
        "default": "Посмотреть отзывы",
        "section": "Главная страница",
    },
    {
        "key": "footer_copyright",
        "label": "Текст копирайта в подвале (HTML, можно <br/>)",
        "kind": "html",
        "default": (
            "© 2024 Аксай Гриль. Все права защищены. <br/> "
            "Сделано с любовью к домашней кухне."
        ),
        "section": "Главная страница",
    },
    # ----- Реквизиты оператора (ИП) — для подвала и политики -----
    {
        "key": "operator_name",
        "label": "Реквизиты: наименование оператора",
        "kind": "text",
        "default": "ИП Секретёв Алексей Сергеевич",
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_inn",
        "label": "Реквизиты: ИНН",
        "kind": "text",
        "default": "614200356558",
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_ogrnip",
        "label": "Реквизиты: ОГРНИП",
        "kind": "text",
        "default": "324619600091280",
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_reg_date",
        "label": "Реквизиты: дата регистрации ИП",
        "kind": "text",
        "default": "17.04.2024",
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_address",
        "label": "Реквизиты: адрес для корреспонденции",
        "kind": "textarea",
        "default": "344000, г. Ростов-на-Дону, пер. Журавлева, д. 150, кв. 31",
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_tax_authority",
        "label": "Реквизиты: налоговый орган",
        "kind": "textarea",
        "default": (
            "Межрайонная инспекция Федеральной налоговой службы № 25 "
            "по Ростовской области"
        ),
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_email",
        "label": "Реквизиты: контактный e-mail (заполнить позже)",
        "kind": "text",
        "default": "",
        "section": "Реквизиты оператора (ИП)",
    },
    {
        "key": "operator_phone",
        "label": "Реквизиты: контактный телефон (заполнить позже)",
        "kind": "text",
        "default": "",
        "section": "Реквизиты оператора (ИП)",
    },
    # ----- Контактная строка в шапке сайта -----
    {
        "key": "contact_address",
        "label": "Шапка-контакты: адрес",
        "kind": "text",
        "default": "г. Аксай",
        "section": "Контакты в шапке",
    },
    {
        "key": "contact_phone",
        "label": "Шапка-контакты: телефон (отображается жирным)",
        "kind": "text",
        "default": "+7 (908) 513-78-80",
        "section": "Контакты в шапке",
    },
    {
        "key": "contact_hours",
        "label": "Шапка-контакты: часы работы",
        "kind": "text",
        "default": "10:00 – 22:00",
        "section": "Контакты в шапке",
    },
    # ----- Блок «Как нас найти» (Яндекс-карта) -----
    {
        "key": "map_address_text",
        "label": "Карта: адрес под картой (отображается над картой)",
        "kind": "text",
        "default": "улица Авиаторов, Аксай, Ростовская область",
        "section": "Карта и адрес",
    },
    {
        "key": "map_lat",
        "label": "Карта: широта (latitude). Пример: 47.288037",
        "kind": "text",
        "default": "47.288037",
        "section": "Карта и адрес",
    },
    {
        "key": "map_lng",
        "label": "Карта: долгота (longitude). Пример: 39.863328",
        "kind": "text",
        "default": "39.863328",
        "section": "Карта и адрес",
    },
    {
        "key": "map_zoom",
        "label": "Карта: масштаб (zoom 0–19, обычно 17)",
        "kind": "text",
        "default": "17",
        "section": "Карта и адрес",
    },
]


def get_catalog_grouped() -> list[tuple[str, list[dict]]]:
    """Вернуть каталог, сгруппированный по разделам, с сохранением порядка."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for item in SITE_TEXT_CATALOG:
        section = item.get("section", "Прочее")
        if section not in groups:
            groups[section] = []
            order.append(section)
        groups[section].append(item)
    return [(name, groups[name]) for name in order]


class SiteText(Base):
    __tablename__ = "site_texts"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                        nullable=False)


def seed_site_texts(session: Session) -> None:
    """Создать недостающие тексты со значениями по умолчанию."""
    existing = {t.key for t in session.query(SiteText.key).all()}
    added = False
    for item in SITE_TEXT_CATALOG:
        if item["key"] not in existing:
            session.add(SiteText(key=item["key"], value=item["default"]))
            added = True
    if added:
        session.commit()


def load_site_texts(session: Session) -> dict[str, str]:
    """Вернуть {key: value} для всех текстов (с подстановкой defaults
    на случай, если запись ещё не сидирована)."""
    rows = {t.key: t.value for t in session.query(SiteText).all()}
    return {item["key"]: rows.get(item["key"], item["default"])
            for item in SITE_TEXT_CATALOG}

class Admin(Base, UserMixin):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def set_password(self, password: str) -> None:
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except ValueError:
            return False

    def get_id(self) -> str:
        return str(self.id)


class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True)
    username_attempted = Column(String(128), nullable=False, index=True)
    success = Column(Boolean, default=False, nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


def admins_count(session: Session) -> int:
    return session.query(Admin).count()


# ---------------------------------------------------------------------------
# Бизнес-ланчи: каталог комплексов и заявки от компаний.
# ---------------------------------------------------------------------------

BUSINESS_LUNCH_MENU: list[dict] = [
    {
        "key": "light",
        "title": "Лёгкий",
        "price": 280,
        "badge": "Курица",
        "items": [
            "Куриный суп с лапшой",
            "Куриная котлета на пару",
            "Рис с овощами",
            "Салат «Помидор-огурец»",
            "Хлеб пшеничный",
            "Компот",
        ],
    },
    {
        "key": "hearty",
        "title": "Сытный",
        "price": 350,
        "badge": "Свинина",
        "items": [
            "Солянка домашняя",
            "Гуляш из говядины",
            "Гречка с маслом",
            "Капуста по-грузински",
            "Хлеб пшеничный",
            "Компот",
        ],
    },
    {
        "key": "grill",
        "title": "Мясной с мангала",
        "price": 450,
        "badge": "Гриль",
        "items": [
            "Харчо",
            "Шашлык из свинины (140 г)",
            "Картофель по-деревенски",
            "Овощи-гриль на шпажках",
            "Булочка чесночная",
            "Морс",
        ],
    },
    {
        "key": "veg",
        "title": "Постный",
        "price": 250,
        "badge": "Без мяса",
        "items": [
            "Гороховый суп без мяса",
            "Аджапсандал",
            "Каша пшеничная",
            "Свекла с чесноком",
            "Хлеб пшеничный",
            "Чай",
        ],
    },
]


class BusinessLunchOrder(Base):
    """Заявка на корпоративные бизнес-ланчи."""

    __tablename__ = "business_lunch_orders"

    id = Column(Integer, primary_key=True)
    contact_name = Column(String(128), nullable=False)
    company = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    persons = Column(Integer, nullable=False, default=1)
    delivery_date = Column(String(32), nullable=False)  # ISO YYYY-MM-DD
    delivery_time = Column(String(16), nullable=True)
    delivery_address = Column(Text, nullable=False)
    selected_combos = Column(Text, nullable=True)  # comma-separated keys
    comment = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    is_processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(64), nullable=True)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
