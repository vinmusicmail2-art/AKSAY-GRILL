# Аксай Гриль — Сайт доставки

Flask-приложение для ресторана с системой заказов, админ-панелью и интеграцией email-уведомлений.

## Возможности

- 📋 Онлайн меню с категориями
- 🍱 Бизнес-ланчи
- 🎉 Бронирование зала для мероприятий
- 🚚 Доставка и кейтеринг
- 📧 Email уведомления о заказах
- 🔐 Админ-панель для управления
- 📊 Статистика и отчёты
- 📱 Адаптивный дизайн

## Технологии

- **Backend:** Python 3.11, Flask 3.1
- **Database:** SQLite (SQLAlchemy ORM)
- **Frontend:** Tailwind CSS, Alpine.js
- **Auth:** Flask-Login
- **Forms:** Flask-WTF, WTForms
- **Server:** Gunicorn

## Установка локально

```bash
# Клонировать репозиторий
git clone <repo-url>
cd aksay_gril_20260503_200418

# Создать виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Запустить сервер
python main.py
```

Сайт будет доступен по адресу: http://localhost:5000

## Деплой на хостинг

См. подробную инструкцию в [DEPLOY.md](DEPLOY.md)

**Быстрый старт:**
1. Render.com — автоматический деплой из GitHub
2. Railway.app — один клик деплой
3. VPS — полный контроль

## Переменные окружения

```bash
SESSION_SECRET=<случайная строка 64+ символов>
FLASK_ENV=production
```

## Структура проекта

```
.
├── app.py              # Инициализация Flask
├── main.py             # Точка входа
├── models.py           # Модели БД
├── routes_admin.py     # Админ маршруты
├── routes_public.py    # Публичные маршруты
├── forms.py            # WTForms формы
├── mailer.py           # Email уведомления
├── db.py               # Настройка БД
├── utils/              # Утилиты
│   ├── db_helpers.py
│   ├── admin_helpers.py
│   └── constants.py
├── templates/          # Jinja2 шаблоны
├── assets/             # Статика (CSS, JS, изображения)
└── requirements.txt    # Python зависимости
```

## Админ-панель

Доступ: `/admin/login`

Первый запуск — создать администратора через `/admin/setup`

**Возможности админки:**
- Управление меню и блюдами
- Просмотр заказов и заявок
- Статистика по администраторам
- Настройка текстов сайта
- Email уведомления
- Экспорт в CSV

## Безопасность

- ✅ CSRF защита (Flask-WTF)
- ✅ Rate limiting (Flask-Limiter)
- ✅ Bcrypt хеширование паролей
- ✅ Валидация форм
- ✅ Безопасные сессии
- ✅ XSS защита (Jinja2 автоэкранирование)

## Производительность

- ✅ Gzip сжатие (Flask-Compress)
- ✅ Кэширование site_texts (TTL 5 мин)
- ✅ Оптимизированные изображения (WebP)
- ✅ Минифицированный CSS

## Лицензия

Proprietary — все права защищены

## Контакты

Для вопросов и поддержки: [контактная информация]
