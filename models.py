"""
Модели БД для админки «Аксай Гриль».
"""
from __future__ import annotations

from datetime import datetime

import bcrypt
from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session, relationship

from db import Base

# ---------------------------------------------------------------------------
# Каталог редактируемых текстов сайта.
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
    {
        "key": "contact_email",
        "label": "Реквизиты: публичный e-mail для отображения на сайте",
        "kind": "text",
        "default": "aksaygryl@mail.ru",
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
    # ----- Уведомления администратора -----
    {
        "key": "notify_email_recipient",
        "label": "E-mail для уведомлений о новых заявках (бизнес-ланчи, кейтеринг, банкеты)",
        "kind": "text",
        "default": "",
        "section": "Уведомления",
    },
    {
        "key": "notify_email_enabled",
        "label": "Присылать уведомления (yes / no)",
        "kind": "text",
        "default": "yes",
        "section": "Уведомления",
    },
    # ----- Страница «О нас» -----
    {
        "key": "about_badge",
        "label": "О нас: бейдж над заголовком",
        "kind": "text",
        "default": "Работаем с 2022 года",
        "section": "Страница «О нас»",
    },
    {
        "key": "about_hero_subtitle",
        "label": "О нас: подзаголовок в hero-баннере",
        "kind": "textarea",
        "default": "Кафе-гриль в г. Аксай — шашлык, кейтеринг и доставка обедов на предприятия. Натуральные продукты, живой огонь, домашний вкус.",
        "section": "Страница «О нас»",
    },
    {
        "key": "about_history_title",
        "label": "О нас: заголовок раздела «Наша история»",
        "kind": "text",
        "default": "Кафе «Аксай Гриль» — гриль-ресторан в Аксайском районе с 2022 года",
        "section": "Страница «О нас»",
    },
    {
        "key": "about_history_p1",
        "label": "О нас: первый абзац истории",
        "kind": "textarea",
        "default": (
            "«Аксай Гриль» — кафе-гриль в г. Аксай, работаем с 2022 года. Готовим шашлык из свинины, "
            "говядины, баранины и курицы, люля-кебаб, куриные крылья и домашние первые блюда. "
            "Доставляем горячие обеды на предприятия и строительные площадки Аксайского района — вовремя и без переплат."
        ),
        "section": "Страница «О нас»",
    },
    {
        "key": "about_history_p2",
        "label": "О нас: второй абзац истории (расположение)",
        "kind": "textarea",
        "default": (
            "Находимся на рынке «Казачий», г. Аксай — удобный въезд, просторная парковка, "
            "перекрёсток трёх дорог. Рядом микрорайон Придонье (120\u202f000 жителей): до нас "
            "пешком или пара минут на машине. Звоните — ответим и рассчитаем стоимость: +7\u202f(908)\u202f513-78-80."
        ),
        "section": "Страница «О нас»",
    },
    {
        "key": "about_advantage_title",
        "label": "О нас: заголовок главного преимущества",
        "kind": "text",
        "default": "Только свежее мясо и натуральные продукты — без заморозки и полуфабрикатов",
        "section": "Страница «О нас»",
    },
    {
        "key": "about_advantage_text",
        "label": "О нас: описание главного преимущества",
        "kind": "textarea",
        "default": (
            "Мясо закупаем ежедневно, готовим только из натуральных продуктов. Никаких полуфабрикатов, "
            "никакой заморозки — каждое блюдо делается здесь и сейчас. Именно поэтому шашлык из «Аксай Гриля» — "
            "это всегда сочно, свежо и по-домашнему вкусно. Заказывайте доставку обедов или кейтеринг — "
            "звоните: +7\u202f(908)\u202f513-78-80."
        ),
        "section": "Страница «О нас»",
    },
    {
        "key": "working_hours",
        "label": "О нас / контакты: часы работы заведения",
        "kind": "text",
        "default": "10:00 – 22:00",
        "section": "Страница «О нас»",
    },
    # ----- Страница «Кейтеринг» -----
    {
        "key": "catering_hero_badge",
        "label": "Кейтеринг: бейдж над заголовком",
        "kind": "text",
        "default": "Под ключ",
        "section": "Страница «Кейтеринг»",
    },
    {
        "key": "catering_hero_subtitle",
        "label": "Кейтеринг: подзаголовок в hero-баннере",
        "kind": "textarea",
        "default": (
            "Полное обслуживание мероприятий: меню под ваш формат и бюджет, сервировка, "
            "посуда и персонал. Вы занимаетесь гостями — мы всем остальным."
        ),
        "section": "Страница «Кейтеринг»",
    },
    # ----- Страница «Мероприятия» -----
    {
        "key": "events_hero_badge",
        "label": "Мероприятия: бейдж над заголовком",
        "kind": "text",
        "default": "Праздники и банкеты",
        "section": "Страница «Мероприятия»",
    },
    {
        "key": "events_hero_subtitle",
        "label": "Мероприятия: подзаголовок в hero-баннере",
        "kind": "textarea",
        "default": (
            "Юбилеи, свадьбы, корпоративы и семейные торжества в зале нашего ресторана. "
            "Меню, оформление и сервис — под ваш формат и бюджет."
        ),
        "section": "Страница «Мероприятия»",
    },
    # ----- Страница «Бизнес-ланчи» -----
    {
        "key": "bl_hero_badge",
        "label": "Бизнес-ланчи: бейдж над заголовком",
        "kind": "text",
        "default": "Для офисов",
        "section": "Страница «Бизнес-ланчи»",
    },
    {
        "key": "bl_hero_subtitle",
        "label": "Бизнес-ланчи: подзаголовок в hero-баннере",
        "kind": "textarea",
        "default": (
            "Сытные и сбалансированные комплексные обеды для вашей команды. "
            "Доставка к назначенному времени, удобные форматы порций и фиксированная цена."
        ),
        "section": "Страница «Бизнес-ланчи»",
    },
    # ----- SEO -----
    {
        "key": "yandex_metrika_id",
        "label": "Яндекс.Метрика: номер счётчика (только цифры, напр. 12345678)",
        "kind": "text",
        "default": "",
        "section": "SEO",
    },
    {
        "key": "meta_description_main",
        "label": "SEO: meta description главной страницы (до 160 символов)",
        "kind": "textarea",
        "default": "Аксай Гриль — кафе-гриль в г. Аксай. Шашлык, кейтеринг, доставка обедов на предприятия. Натуральные продукты, живой огонь. Тел: +7 (908) 513-78-80.",
        "section": "SEO",
    },
    {
        "key": "meta_description_about",
        "label": "SEO: meta description страницы «О нас» (до 160 символов)",
        "kind": "textarea",
        "default": "Кафе-гриль Аксай Гриль в г. Аксай с 2022 года. Шашлык из свежего мяса, домашняя кухня, доставка обедов и кейтеринг. Рынок «Казачий», тел: +7 (908) 513-78-80.",
        "section": "SEO",
    },
    {
        "key": "meta_description_catering",
        "label": "SEO: meta description страницы «Кейтеринг» (до 160 символов)",
        "kind": "textarea",
        "default": "Кейтеринг в Аксае и Ростовской области — Аксай Гриль. Корпоративы, свадьбы, выездное обслуживание. Меню под бюджет. Тел: +7 (908) 513-78-80.",
        "section": "SEO",
    },
    {
        "key": "meta_description_events",
        "label": "SEO: meta description страницы «Мероприятия» (до 160 символов)",
        "kind": "textarea",
        "default": "Банкеты и мероприятия в зале ресторана Аксай Гриль, г. Аксай. Свадьбы, юбилеи, корпоративы. Меню, сервировка, оформление. Тел: +7 (908) 513-78-80.",
        "section": "SEO",
    },
    {
        "key": "meta_description_business_lunch",
        "label": "SEO: meta description страницы «Бизнес-ланчи» (до 160 символов)",
        "kind": "textarea",
        "default": "Бизнес-ланчи с доставкой в Аксае — Аксай Гриль. Горячие комплексные обеды для офисов и предприятий. Фиксированная цена, доставка к сроку. Тел: +7 (908) 513-78-80.",
        "section": "SEO",
    },
    {
        "key": "og_image",
        "label": "SEO: URL картинки для соцсетей (og:image), рекомендуется 1200×630px",
        "kind": "text",
        "default": "/assets/about-hero.webp",
        "section": "SEO",
    },
    # ----- Юридические страницы -----
    {
        "key": "legal_privacy_last_updated",
        "label": "Политика конфиденциальности: дата последнего обновления",
        "kind": "text",
        "default": "26 апреля 2026 г.",
        "section": "Юридические страницы",
    },
    {
        "key": "legal_offer_html",
        "label": "Публичная оферта: полный текст (HTML разрешён)",
        "kind": "html",
        "default": (
            "<h2>1. Общие положения</h2>"
            "<p>Настоящая публичная оферта является официальным предложением "
            "ИП Секретёв Алексей Сергеевич (далее — «Исполнитель») заключить договор "
            "на оказание услуг общественного питания и доставки готовых блюд.</p>"
            "<h2>2. Предмет оферты</h2>"
            "<p>Исполнитель обязуется приготовить и доставить блюда согласно заказу "
            "Пользователя, а Пользователь обязуется оплатить заказ.</p>"
            "<h2>3. Оформление заказа</h2>"
            "<p>Заказ оформляется через сайт или по телефону. "
            "Договор считается заключённым с момента подтверждения заказа Исполнителем.</p>"
            "<h2>4. Стоимость и оплата</h2>"
            "<p>Стоимость блюд указана на сайте. Оплата производится наличными или "
            "банковской картой при получении.</p>"
            "<h2>5. Доставка</h2>"
            "<p>Доставка осуществляется по г. Аксай и прилегающим территориям. "
            "Сроки доставки — до 45 минут с момента подтверждения заказа. "
            "При заказе от 1500 рублей доставка бесплатная.</p>"
            "<h2>6. Отказ от заказа</h2>"
            "<p>Пользователь вправе отказаться от заказа до его передачи курьеру. "
            "После передачи курьеру возврат денежных средств не производится.</p>"
            "<h2>7. Реквизиты Исполнителя</h2>"
            "<p>ИП Секретёв Алексей Сергеевич · ИНН 614200356558 · "
            "ОГРНИП 324619600091280 · Тел: +7 (908) 513-78-80</p>"
        ),
        "section": "Юридические страницы",
    },
    {
        "key": "legal_cookies_html",
        "label": "Политика cookies: полный текст (HTML разрешён)",
        "kind": "html",
        "default": (
            "<h2>Что такое cookies</h2>"
            "<p>Cookies — небольшие текстовые файлы, которые сохраняются на вашем устройстве "
            "при посещении сайта. Они помогают нам улучшать работу сайта и предоставлять "
            "персонализированный опыт.</p>"
            "<h2>Какие cookies мы используем</h2>"
            "<ul>"
            "<li><strong>Технические cookies</strong> — необходимы для корректной работы сайта "
            "(например, сохранение содержимого корзины).</li>"
            "<li><strong>Аналитические cookies</strong> — помогают нам понять, как посетители "
            "используют сайт (Яндекс.Метрика).</li>"
            "</ul>"
            "<h2>Управление cookies</h2>"
            "<p>Вы можете отключить cookies в настройках браузера. Однако некоторые функции "
            "сайта могут работать некорректно.</p>"
            "<h2>Согласие</h2>"
            "<p>Продолжая использовать сайт, вы соглашаетесь с использованием cookies "
            "в соответствии с настоящей политикой.</p>"
        ),
        "section": "Юридические страницы",
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


# ---------------------------------------------------------------------------
# Меню: категории и блюда.
# ---------------------------------------------------------------------------

class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    heading = Column(String(128), nullable=False)
    description = Column(Text, default="")
    nav_icon = Column(String(64), default="restaurant_menu")
    sort_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True, nullable=False)
    show_in_nav = Column(Boolean, default=True, nullable=False)

    dishes = relationship(
        "Dish",
        back_populates="category",
        order_by="Dish.sort_order",
        cascade="all, delete-orphan",
    )


class Dish(Base):
    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    price = Column(Integer, default=0)
    image_src = Column(String(512), default="")
    is_available = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0)

    category = relationship("MenuCategory", back_populates="dishes")


_MENU_SEED: list[dict] = [
    {
        "slug": "mangal", "name": "Блюда на мангале",
        "heading": "БЛЮДА НА МАНГАЛЕ ИЛИ ГРИЛЕ (1 кг)",
        "description": "Мясо, птица и овощи на углях с дымком — порции от 1 кг для большой компании.",
        "nav_icon": "outdoor_grill", "sort_order": 10, "show_in_nav": True,
        "dishes": [
            ("Шашлык на мангале", "Сочный шашлык на ваш выбор — свинина, баранина, говядина или курица.", 1200, "/assets/dishes/shashlyk-mix.webp"),
            ("Куриные крылья, бедра и ножки", "Ассорти куриных частей с золотистой румяной корочкой на углях.", 850, "/assets/dishes/kurinye-grill.webp"),
            ("Свиные ребрышки", "Сочные свиные ребрышки в карамельной глазури с дымком.", 1100, "/assets/dishes/rebryshki-grill.webp"),
            ("Стейки", "Толстые сочные стейки на гриле с румяными полосками от решётки.", 1800, "/assets/dishes/steiki-grill.webp"),
            ("Купаты, колбаски", "Домашние купаты и колбаски на углях с румяной хрустящей корочкой.", 900, "/assets/dishes/kupaty-grill.webp"),
            ("Аджапсандал", "Грузинское овощное рагу из баклажанов, перцев и томатов с зеленью.", 650, "/assets/dishes/adzhapsandal.webp"),
            ("Овощи-гриль на шпажках", "Перец, кабачок, баклажан, томаты и лук на шпажках с дымком.", 600, "/assets/dishes/ovoshi-shpazhki.webp"),
            ("Запечённые перцы и баклажаны", "Целиком запечённые овощи с чесноком, кинзой и петрушкой.", 650, "/assets/dishes/perci-baklazhany.webp"),
            ("Овощная икра с дымком", "Икра из запечённых баклажанов и перцев с лёгким ароматом дыма.", 550, "/assets/dishes/ovoshnaya-ikra.webp"),
            ("Запеченные грибы", "Целые шампиньоны на гриле с маслом, чесноком и зеленью.", 750, "/assets/dishes/griby-grill.webp"),
        ],
    },
    {
        "slug": "pervye", "name": "Первые блюда",
        "heading": "ПЕРВЫЕ БЛЮДА",
        "description": "Наваристые супы, приготовленные по старинным рецептам с использованием только свежих ингредиентов.",
        "nav_icon": "soup_kitchen", "sort_order": 20, "show_in_nav": True,
        "dishes": [
            ("Борщ", "Классический наваристый борщ со свеклой, нежной говядиной и свежей зеленью.", 220, "/assets/dishes/borshch_new.png"),
            ("Шурпа", "Традиционный восточный суп с крупными кусками баранины и овощами.", 250, "/assets/dishes/shurpa_new.png"),
            ("Солянка", "Наваристая солянка с копчёностями, оливками, лимоном и сметаной.", 250, "/assets/dishes/solyanka.webp"),
            ("Суп Лагман", "Узбекский суп с домашней тянутой лапшой, говядиной и овощами.", 350, "/assets/dishes/lagman.webp"),
            ("Суп гороховый", "Густой гороховый суп с копчёностями, сухариками и свежим укропом.", 220, "/assets/dishes/gorohovyi.webp"),
            ("Лапша куриная", "Прозрачный куриный бульон с домашней лапшой и свежей зеленью.", 200, "/assets/dishes/lapsha-kurinaya.webp"),
            ("Суп с фасолью", "Сытный суп с красной фасолью, томатами и копчёным мясом.", 220, "/assets/dishes/sup-fasol.webp"),
            ("Суп Харчо", "Острый грузинский суп с говядиной, рисом, грецкими орехами и кинзой.", 220, "/assets/dishes/harcho.webp"),
            ("Окрошка на кефире", "Освежающий холодный суп на кефире с овощами, яйцом и зеленью.", 250, "/assets/dishes/okroshka.webp"),
        ],
    },
    {
        "slug": "vtorye", "name": "Вторые блюда",
        "heading": "ВТОРЫЕ БЛЮДА",
        "description": "Сытные мясные и рыбные блюда домашней кухни — от фирменных котлет до классических вторых блюд.",
        "nav_icon": "restaurant_menu", "sort_order": 30, "show_in_nav": True,
        "dishes": [
            ("Куриная котлета", "Сочная домашняя куриная котлета на пару.", 150, "/assets/dishes/kuriniaja-kotleta.webp"),
            ("Гуляш из говядины", "Нежный гуляш из говядины с томатным соусом и зеленью.", 220, "/assets/dishes/gulyash-govyadina.webp"),
            ("Котлета «По-киевски»", "Сочная котлета с начинкой из масла и зелени.", 170, "/assets/dishes/kotleta-po-kievski.webp"),
            ("Медвежья лапа", "Фирменная котлета из рубленого мяса с грибной начинкой.", 250, "/assets/dishes/medvezhya-lapa.webp"),
            ("Макароны по-флотски", "Классические макароны по-флотски с мясным фаршем.", 200, "/assets/dishes/makarony-po-flotski.webp"),
            ("Пельмени домашние со сметаной", "Домашние пельмени с нежным тестом и сочной начинкой.", 350, "/assets/dishes/pelmeni-smetana.webp"),
            ("Курица тушеная в сливках", "Нежная курица, тушённая в сливочном соусе с травами.", 170, "/assets/dishes/kuritsa-v-slivkah.webp"),
            ("Рыба жареная Хек", "Хек, обжаренный до золотистой корочки.", 190, "/assets/dishes/ryba-hek.webp"),
            ("Отбивная куриная", "Куриное филе, отбитое и обжаренное в панировке.", 170, "/assets/dishes/otbivnaja-kurinaja.webp"),
            ("Вареники со сметаной", "Домашние вареники с картофелем и творогом.", 300, "/assets/dishes/vareniki-smetana.webp"),
            ("Люля-кебаб из курицы", "Фирменный люля-кебаб из рубленого куриного мяса.", 160, "/assets/dishes/lyulya-kuritsa.webp"),
            ("Куриное бедро жареное", "Румяное куриное бедро с золотистой корочкой.", 170, "/assets/dishes/kurinoe-bedro.webp"),
            ("Яичница глазунья натуральная", "Аппетитная глазунья из трёх яиц со свежей зеленью.", 150, "/assets/dishes/yaichnitsa-glazunja.webp"),
            ("Яичница 2 яйца", "Классическая яичница из двух яиц с зеленью.", 100, "/assets/dishes/yaichnitsa-2.webp"),
            ("Крылья жареные (1 кг)", "Хрустящие жареные куриные крылья. Цена за килограмм.", 650, "/assets/dishes/krylya-zharenye.webp"),
        ],
    },
    {
        "slug": "garniry", "name": "Гарниры",
        "heading": "ГАРНИРЫ",
        "description": "Идеальное дополнение к основным блюдам — классические гарниры из круп, картофеля и овощей.",
        "nav_icon": "rice_bowl", "sort_order": 40, "show_in_nav": True,
        "dishes": [
            ("Картофельное пюре со сливочным маслом", "Воздушное картофельное пюре.", 95, "/assets/dishes/pure-maslo.webp"),
            ("Гречка отварная", "Рассыпчатая гречневая каша.", 80, "/assets/dishes/grechka.webp"),
            ("Макароны отварные", "Классические отварные макароны со сливочным маслом.", 80, "/assets/dishes/makarony-otvar.webp"),
            ("Рис отварной с овощами", "Лёгкий рис с морковью, кукурузой и зелёным горошком.", 80, "/assets/dishes/ris-ovoshhi.webp"),
            ("Картофель по-деревенски", "Запечённые дольки картофеля с золотистой корочкой и травами.", 80, "/assets/dishes/kartofel-derevenski.webp"),
            ("Капуста тушеная", "Сочная тушёная капуста с морковью и томатом.", 80, "/assets/dishes/kapusta-tushenaya.webp"),
            ("Каша пшеничная рассыпчатая", "Ароматная пшеничная каша рассыпчатая со сливочным маслом.", 70, "/assets/dishes/kasha-pshenichnaya.webp"),
        ],
    },
    {
        "slug": "salaty", "name": "Салаты",
        "heading": "САЛАТЫ",
        "description": "Свежие овощные и классические салаты — лёгкое дополнение к основному меню.",
        "nav_icon": "flatware", "sort_order": 50, "show_in_nav": True,
        "dishes": [
            ("Свекла с чесноком", "Тёртая свёкла с чесноком и нежной заправкой.", 100, "/assets/dishes/svekla-chesnok.webp"),
            ("Салат «Оливье» с колбасой", "Классический оливье с колбасой, овощами и майонезной заправкой.", 100, "/assets/dishes/olivie-kolbasa.webp"),
            ("Капуста по-грузински", "Острая маринованная капуста по-грузински с морковью и свёклой.", 100, "/assets/dishes/kapusta-gruzinski.webp"),
            ("Салат из помидоров с огурцами", "Свежие помидоры и огурцы с луком, зеленью и лёгкой заправкой.", 100, "/assets/dishes/salat-pomidor-ogurec.webp"),
            ("Кабачки жареные", "Золотистые жареные кабачки с чесночным соусом.", 100, "/assets/dishes/kabachki-zharenye.webp"),
            ("Капуста с горошком", "Свежий капустный салат с зелёным горошком и морковью.", 100, "/assets/dishes/kapusta-goroshek.webp"),
            ("Морковь с чесноком", "Острая морковь по-корейски с чесноком и пряностями.", 100, "/assets/dishes/morkov-chesnok.webp"),
        ],
    },
    {
        "slug": "vypechka", "name": "Выпечка",
        "heading": "ВЫПЕЧКА",
        "description": "Домашняя выпечка из печи — пирожки, беляши, сырники, блинчики и фирменная самса.",
        "nav_icon": "bakery_dining", "sort_order": 60, "show_in_nav": True,
        "dishes": [
            ("Хлеб пшеничный", "Свежий пшеничный хлеб собственной выпечки.", 5, "/assets/dishes/hleb-pshenichnyj.webp"),
            ("Пирожок жареный", "Румяный жареный пирожок с начинкой на выбор.", 80, "/assets/dishes/pirozhok-zharenyj.webp"),
            ("Сосиска в тесте", "Аппетитная сосиска в нежном слоёном тесте.", 100, "/assets/dishes/sosiska-v-teste.webp"),
            ("Беляши", "Классические беляши с сочной мясной начинкой.", 150, "/assets/dishes/belyashi.webp"),
            ("Сырники из творога", "Нежные сырники из творога со сметаной и вареньем.", 170, "/assets/dishes/syrniki.webp"),
            ("Булочка чесночная", "Ароматная булочка с чесноком, маслом и зеленью.", 40, "/assets/dishes/bulochka-chesnochnaya.webp"),
            ("Блинчики с мясом", "Тонкие блинчики с сочной мясной начинкой.", 200, "/assets/dishes/blinchiki-myaso.webp"),
            ("Самса", "Узбекская самса с мясом в хрустящем слоёном тесте.", 160, "/assets/dishes/samsa.webp"),
            ("Оладьи 2 шт.", "Пышные домашние оладьи со сметаной и мёдом.", 150, "/assets/dishes/oladi.webp"),
        ],
    },
    {
        "slug": "napitki", "name": "Напитки",
        "heading": "НАПИТКИ",
        "description": "Горячие и прохладительные напитки — компоты, чай, кофе, газировка и вода.",
        "nav_icon": "local_bar", "sort_order": 70, "show_in_nav": True,
        "dishes": [
            ("Компот из сухофруктов", "Домашний ароматный компот из сушёных яблок и кураги.", 50, "/assets/dishes/kompot.webp"),
            ("Кока-кола 0,5 л", "Газированный напиток в стеклянной бутылке.", 120, "/assets/dishes/kola-05.webp"),
            ("Чай в пакетиках", "Свежезаваренный чёрный чай в чашке.", 50, "/assets/dishes/chay-paket.webp"),
            ("Кофе растворимый", "Классический растворимый кофе.", 50, "/assets/dishes/kofe-rastvor.webp"),
            ("Кофе 3 в 1", "Сливочный кофе со сливками и сахаром.", 50, "/assets/dishes/kofe-3v1.webp"),
            ("BURN 0,5 л", "Энергетический напиток.", 150, "/assets/dishes/burn.webp"),
            ("Флеш 0,5 л", "Энергетический напиток.", 110, "/assets/dishes/flesh.webp"),
            ("Адреналин Раш 0,5 л", "Энергетический напиток.", 190, "/assets/dishes/adrenalin.webp"),
            ("Вода 0,5 л Аквадон", "Питьевая негазированная вода.", 50, "/assets/dishes/voda-05.webp"),
            ("Кубай 1,5 л", "Газированная минеральная вода в большой бутылке.", 90, "/assets/dishes/kubay.webp"),
            ("Кока-кола 1 л", "Газированный напиток в большой бутылке.", 150, "/assets/dishes/kola-1l.webp"),
            ("Лимонад в стекле", "Домашний лимонад в стеклянной бутылке.", 110, "/assets/dishes/limonad-steklo.webp"),
            ("Вода 5 л питьевая", "Питьевая вода в большой бутылке для всей семьи.", 160, "/assets/dishes/voda-5l.webp"),
            ("Холодный чай LIPTON зелёный персик", "Прохладительный холодный чай со вкусом персика.", 150, "/assets/dishes/ice-tea.webp"),
            ("Чай чёрный в чайнике", "Свежезаваренный чёрный чай в чайнике на компанию.", 300, "/assets/dishes/chaynik-chay.webp"),
        ],
    },
    {
        "slug": "extras", "name": "Дополнительно",
        "heading": "ДОПОЛНИТЕЛЬНО",
        "description": "Контейнеры для еды на вынос и дополнительные порции соусов.",
        "nav_icon": "add_circle", "sort_order": 80, "show_in_nav": False,
        "dishes": [
            ("Контейнер", "Одноразовый контейнер для еды на вынос.", 10, "/assets/dishes/konteiner.webp"),
            ("Соус к блюду", "Дополнительная порция соуса (чесночный, томатный или сметанный).", 10, "/assets/dishes/sous.webp"),
        ],
    },
]


def seed_menu(session: Session) -> None:
    """Создать категории и блюда меню при первом запуске."""
    existing_count = session.query(MenuCategory).count()
    if existing_count > 0:
        return
    for i, cat_data in enumerate(_MENU_SEED):
        cat = MenuCategory(
            slug=cat_data["slug"],
            name=cat_data["name"],
            heading=cat_data["heading"],
            description=cat_data["description"],
            nav_icon=cat_data["nav_icon"],
            sort_order=cat_data["sort_order"],
            show_in_nav=cat_data["show_in_nav"],
            is_visible=True,
        )
        session.add(cat)
        session.flush()
        for j, (name, desc, price, img) in enumerate(cat_data["dishes"]):
            session.add(Dish(
                category_id=cat.id,
                name=name,
                description=desc,
                price=price,
                image_src=img,
                is_available=True,
                sort_order=j * 10,
            ))
    session.commit()


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
            "Хлеб пшеничный",
            "Компот",
        ],
    },
]

CATERING_FORMATS: list[dict] = [
    {"key": "corporate", "title": "Корпоративное мероприятие"},
    {"key": "wedding", "title": "Свадьба"},
    {"key": "birthday", "title": "День рождения / юбилей"},
    {"key": "outdoor", "title": "Выездное мероприятие на природе"},
    {"key": "other", "title": "Другое"},
]

EVENT_TYPES: list[dict] = [
    {"key": "birthday", "title": "День рождения / юбилей"},
    {"key": "wedding", "title": "Свадьба"},
    {"key": "corporate", "title": "Корпоратив"},
    {"key": "funeral", "title": "Поминальный обед"},
    {"key": "other", "title": "Другое"},
]


class BusinessLunchOrder(Base):
    __tablename__ = "business_lunch_orders"

    id = Column(Integer, primary_key=True)
    contact_name = Column(String(128), nullable=False)
    company = Column(String(256), nullable=True)
    phone = Column(String(30), nullable=False)
    email = Column(String(120), nullable=True)
    persons = Column(Integer, nullable=False)
    delivery_date = Column(String(20), nullable=False)
    delivery_time = Column(String(20), nullable=True)
    delivery_address = Column(Text, nullable=False)
    selected_combos = Column(String(256), nullable=True)
    comment = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(64), nullable=True)


class CateringRequest(Base):
    __tablename__ = "catering_requests"

    id = Column(Integer, primary_key=True)
    contact_name = Column(String(128), nullable=False)
    company = Column(String(256), nullable=True)
    phone = Column(String(30), nullable=False)
    email = Column(String(120), nullable=True)
    event_format = Column(String(64), nullable=False)
    guests = Column(Integer, nullable=False)
    event_date = Column(String(20), nullable=False)
    event_time = Column(String(20), nullable=True)
    venue = Column(Text, nullable=False)
    budget_per_guest = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(64), nullable=True)


class HallReservation(Base):
    __tablename__ = "hall_reservations"

    id = Column(Integer, primary_key=True)
    contact_name = Column(String(128), nullable=False)
    company = Column(String(256), nullable=True)
    phone = Column(String(30), nullable=False)
    email = Column(String(120), nullable=True)
    event_type = Column(String(64), nullable=False)
    guests = Column(Integer, nullable=False)
    event_date = Column(String(20), nullable=False)
    event_time = Column(String(20), nullable=False)
    duration_hours = Column(Integer, nullable=True)
    needs_decor = Column(Boolean, default=False)
    needs_menu_help = Column(Boolean, default=False)
    comment = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(64), nullable=True)


class DeliveryOrder(Base):
    __tablename__ = "delivery_orders"

    id = Column(Integer, primary_key=True)
    contact_name = Column(String(128), nullable=False)
    phone = Column(String(30), nullable=False)
    email = Column(String(120), nullable=True)
    delivery_address = Column(Text, nullable=False)
    items_json = Column(Text, nullable=False)
    total_amount = Column(Integer, default=0)
    comment = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(64), nullable=True)


class QuickRequest(Base):
    __tablename__ = "quick_requests"

    id = Column(Integer, primary_key=True)
    contact_name = Column(String(128), nullable=False)
    phone = Column(String(30), nullable=False)
    address = Column(Text, nullable=False)
    comment = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(64), nullable=True)
