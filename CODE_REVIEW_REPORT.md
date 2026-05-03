# Отчёт о проверке кода — Аксай Гриль

**Дата проверки:** 03.05.2026  
**Проверено строк кода:** ~4,784 строк Python

---

## Исправленные проблемы

### ✅ 1. Кэширование site_texts (КРИТИЧНО)
**Проблема:** Запрос к таблице `site_texts` выполнялся на **каждом HTTP-запросе** через `@app.context_processor`.

**Влияние:** N+1 на уровне приложения — один запрос к БД на каждую загрузку страницы для данных, которые редко меняются.

**Исправление:** Добавлено кэширование с TTL 5 минут в `app.py`:
```python
_site_texts_cache = None
_site_texts_cache_time = None
_CACHE_TTL = 300

def get_cached_site_texts():
    # Кэширование с проверкой TTL
```

**Файл:** `app.py:117-145`

---

### ✅ 2. Дублирование toggle-функций
**Проблема:** 5 идентичных функций для переключения статуса обработки заявок (~150 строк дублирующегося кода).

**Исправление:** Создана универсальная функция `toggle_processed_status()` в `utils/admin_helpers.py`.

**Заменены функции:**
- `admin_business_lunch_toggle()` — routes_admin.py:522
- `admin_catering_toggle()` — routes_admin.py:610
- `admin_events_toggle()` — routes_admin.py:706
- `admin_quick_request_toggle()` — routes_admin.py:788
- `admin_delivery_order_toggle()` — routes_admin.py:963

**Экономия:** ~120 строк кода

---

### ✅ 3. Создана структура утилит
**Создано:**
- `utils/db_helpers.py` — context manager для сессий БД
- `utils/admin_helpers.py` — универсальные функции для админки
- `utils/constants.py` — константы для magic strings

---

## Найденные проблемы (требуют исправления)

### 🔴 Высокий приоритет

#### 1. Повторяющиеся запросы списка администраторов
**Локации:**
- routes_admin.py:464-470 (business_lunches)
- routes_admin.py:561-567 (catering)
- routes_admin.py:660-666 (events)
- routes_admin.py:873-879 (delivery_orders)

**Проблема:** Каждая страница списка выполняет отдельный `DISTINCT` запрос для получения списка админов для фильтра.

**Рекомендация:** Кэшировать список администраторов или объединить с основным запросом.

---

#### 2. Дублирование admin list views (~400 строк)
**Локации:**
- `admin_business_lunches()` (454-519)
- `admin_catering()` (551-618)
- `admin_events()` (650-714)
- `admin_delivery_orders()` (863-933)

**Проблема:** Четыре почти идентичные функции с одинаковой логикой фильтрации, сортировки и поиска.

**Рекомендация:** Создать универсальную функцию `build_admin_list_query()` в `utils/admin_views.py`.

---

#### 3. Множественные последовательные запросы в dashboard
**Локация:** routes_admin.py:176-259

**Проблема:** Dashboard выполняет **10 отдельных запросов** последовательно:
- 5 `COUNT()` запросов для pending items
- 5 `SELECT` запросов с `LIMIT 50` для recent items

**Рекомендация:** Использовать `UNION ALL` или выполнять запросы параллельно.

---

### 🟡 Средний приоритет

#### 4. Дублирование CSV export функций (~120 строк)
**Локации:**
- `admin_delivery_orders_export()` (1668-1696)
- `admin_business_lunches_export()` (1701-1731)
- `admin_catering_export()` (1736-1768)
- `admin_events_export()` (1773-1806)

**Рекомендация:** Создать универсальную функцию экспорта в `utils/csv_helpers.py`.

---

#### 5. Повторяющиеся вызовы load_site_texts() в mailer
**Локация:** mailer.py:74-86

**Проблема:** Каждое email-уведомление открывает новую сессию и запрашивает всю таблицу `site_texts` для чтения 2 значений.

**Рекомендация:** Передавать значения как параметры или использовать кэш.

---

#### 6. Статистика вычисляется в Python вместо SQL
**Локации:**
- routes_admin.py:262-335 (`admin_stats`)
- routes_admin.py:1809-1887 (`admin_journal`)
- routes_admin.py:1957-2028 (`admin_stats_export`)

**Проблема:** Загружаются все строки через `.all()`, затем агрегация выполняется в Python циклами.

**Рекомендация:** Использовать SQL агрегацию (`GROUP BY`, `COUNT()`, `AVG()`, `SUM()`).

---

#### 7. Дублирование email-форматирования (~200 строк)
**Локация:** mailer.py

**Проблема:** 5 похожих функций форматирования email с повторяющейся структурой:
- `_format_order_email()` (222-279)
- `_format_catering_email()` (293-347)
- `_format_hall_email()` (361-410)
- `_format_delivery_email()` (424-482)
- `_format_quick_request_email()` (496-524)

**Рекомендация:** Создать универсальный email builder на основе шаблонов.

---

### 🟢 Низкий приоритет

#### 8. Отсутствие eager loading для relationships
**Локация:** routes_admin.py:1017-1018

**Проблема:** Ручной eager loading через `_ = cat.dishes` вместо использования SQLAlchemy `selectinload()`.

**Рекомендация:** Использовать `selectinload()` или `joinedload()` явно.

---

#### 9. Повторяющийся паттерн try-finally для сессий (56 раз)
**Проблема:** Паттерн создания сессии повторяется 56 раз во всех файлах.

**Рекомендация:** Использовать созданный `utils/db_helpers.py` context manager:
```python
from utils.db_helpers import get_session

with get_session() as session:
    # работа с БД
```

**Экономия:** ~200 строк кода

---

#### 10. Sanitization форм (94 повторения)
**Проблема:** Паттерн `(form.field.data or "").strip() or None` повторяется 94 раза.

**Рекомендация:** Создать функции `sanitize_optional()` и `sanitize_required()` в `utils/form_helpers.py`.

---

#### 11. Magic strings вместо констант (~20+ мест)
**Проблема:** Используются строковые литералы для sort keys, show filters:
- "date_desc", "date_asc", "guests_desc"
- "pending", "processed", "all"

**Рекомендация:** Использовать созданные константы из `utils/constants.py`.

---

#### 12. Hardcoded данные в models.py
**Локации:**
- BUSINESS_LUNCH_MENU (769-812)
- CATERING_FORMATS (814-820)
- EVENT_TYPES (822-828)

**Проблема:** Данные меню захардкожены в Python коде вместо БД.

**Рекомендация:** Перенести в таблицы БД для упрощения редактирования.

---

## Качество кода

### Найдено проблем:
- **Copy-paste нарушения:** ~15 крупных случаев
- **Глубокая вложенность:** 2 случая
- **Parameter sprawl:** 1 функция
- **Избыточное состояние:** 4 hardcoded структуры
- **Magic strings:** ~20+ локаций
- **Leaky abstractions:** 5 локаций
- **Ненужные комментарии:** 3-5 случаев

---

## Рекомендуемая структура utils/

```
utils/
├── __init__.py
├── db_helpers.py       ✅ Создан — Session management
├── admin_helpers.py    ✅ Создан — Toggle abstractions
├── constants.py        ✅ Создан — Shared constants
├── admin_views.py      ⏳ TODO — Admin list/filter abstractions
├── csv_helpers.py      ⏳ TODO — CSV export utilities
├── form_helpers.py     ⏳ TODO — Form sanitization
├── email_builder.py    ⏳ TODO — Email template builder
├── stats_helpers.py    ⏳ TODO — Statistics calculations
└── async_helpers.py    ⏳ TODO — Async execution
```

---

## Потенциальная экономия

При полном рефакторинге:
- **~1,150+ строк кода** можно устранить через абстракции
- **Улучшенная поддерживаемость** через DRY принципы
- **Меньше багов** за счёт централизации общей логики
- **Лучшая тестируемость** с изолированными утилитами

---

## Безопасность

### ✅ Хорошие практики:
- CSRF защита включена
- Rate limiting настроен
- Параметризованные SQL запросы (SQLAlchemy ORM)
- Валидация загружаемых изображений

### ⚠️ Рекомендации:
- Добавить валидацию размера загружаемых файлов
- Рассмотреть использование prepared statements для raw SQL в миграциях
- Добавить логирование неудачных попыток входа

---

## Следующие шаги

### Немедленно:
1. ✅ Кэширование site_texts — **ВЫПОЛНЕНО**
2. ✅ Унификация toggle handlers — **ВЫПОЛНЕНО**
3. ⏳ Рефакторинг admin list views
4. ⏳ Оптимизация dashboard запросов

### В следующем спринте:
5. Унификация CSV export
6. Рефакторинг email notifications
7. SQL агрегация для статистики
8. Замена try-finally на context managers

### Технический долг:
9. Sanitization утилиты для форм
10. Eager loading для relationships
11. Миграция на Alembic
12. Перенос hardcoded данных в БД

---

**Общая оценка:** Код функционален и безопасен, но имеет значительные возможности для улучшения через устранение дублирования и оптимизацию запросов к БД.
