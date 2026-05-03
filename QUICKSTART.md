# 🚀 Быстрый старт — Деплой за 10 минут

## Самый простой способ — Render.com

### Шаг 1: Подготовка (2 минуты)

1. Создайте аккаунт на GitHub (если нет)
2. Создайте новый репозиторий `aksay-grill`
3. Загрузите все файлы проекта в репозиторий

**Команды для Git:**
```bash
cd "E:\АксайГриль\ГОТОВЫЙ САЙТ\REPLIT\aksay_gril_20260503_200418"
git init
git add .
git commit -m "Initial commit - Aksay Grill website"
git branch -M main
git remote add origin https://github.com/ваш-username/aksay-grill.git
git push -u origin main
```

### Шаг 2: Деплой на Render (5 минут)

1. **Зайдите на https://render.com**
2. **Sign Up** → войдите через GitHub
3. **New** → **Web Service**
4. **Connect Repository** → выберите `aksay-grill`
5. **Настройте:**
   - **Name:** `aksay-grill`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn main:app --bind 0.0.0.0:$PORT --workers 2`
   - **Instance Type:** `Free`

6. **Environment Variables** → Add:
   ```
   SESSION_SECRET = <сгенерируйте случайную строку>
   ```
   
   Для генерации:
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```

7. **Create Web Service** — ждите 3-5 минут

### Шаг 3: Первый запуск (3 минуты)

1. Откройте ваш сайт: `https://aksay-grill.onrender.com`
2. Перейдите в админку: `https://aksay-grill.onrender.com/admin/setup`
3. Создайте первого администратора
4. Настройте email для уведомлений в админке
5. Готово! 🎉

---

## Альтернатива — Railway.app (ещё проще)

1. https://railway.app → Sign Up через GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Выберите репозиторий `aksay-grill`
4. Добавьте переменную `SESSION_SECRET`
5. Готово! Railway всё настроит автоматически

---

## Что дальше?

### Обязательно:
- ✅ Настроить email в админке
- ✅ Загрузить фото блюд
- ✅ Проверить все формы заказа
- ✅ Протестировать на телефоне

### Опционально:
- 🌐 Подключить свой домен
- 🔒 Настроить SSL (автоматически на Render/Railway)
- 📊 Добавить Яндекс.Метрику
- 📧 Настроить SMTP для email

---

## Нужна помощь?

Смотрите подробные инструкции:
- [DEPLOY.md](DEPLOY.md) — полная инструкция по деплою
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) — чеклист
- [README.md](README.md) — документация проекта

---

## Важно для России 🇷🇺

Render.com и Railway.app могут быть недоступны из России. Альтернативы:

1. **Timeweb** — https://timeweb.com (от 200₽/мес)
2. **Beget** — https://beget.com (от 150₽/мес)
3. **Reg.ru** — https://reg.ru (от 200₽/мес)

Для этих хостингов используйте инструкцию VPS из [DEPLOY.md](DEPLOY.md)
