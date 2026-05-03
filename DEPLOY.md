# Инструкция по деплою Аксай Гриль

## Вариант 1: Render.com (Рекомендуется)

### Шаги:

1. **Создать аккаунт на Render.com**
   - Перейти на https://render.com
   - Зарегистрироваться через GitHub или email

2. **Подключить GitHub репозиторий**
   - Создать репозиторий на GitHub
   - Загрузить код проекта в репозиторий
   - В Render: New → Web Service → Connect Repository

3. **Настроить сервис**
   ```
   Name: aksay-grill
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn main:app --bind 0.0.0.0:$PORT --workers 2
   ```

4. **Добавить переменные окружения**
   ```
   SESSION_SECRET=<сгенерировать случайную строку>
   FLASK_ENV=production
   ```

5. **Deploy** — нажать кнопку Deploy

---

## Вариант 2: Railway.app

### Шаги:

1. **Создать аккаунт на Railway.app**
   - https://railway.app
   - Войти через GitHub

2. **Создать новый проект**
   - New Project → Deploy from GitHub repo
   - Выбрать репозиторий

3. **Railway автоматически определит Python**
   - Настройки применятся автоматически

4. **Добавить переменные окружения**
   ```
   SESSION_SECRET=<случайная строка>
   ```

5. **Deploy** — автоматически

---

## Вариант 3: VPS (Timeweb/Beget для России)

### Требования:
- Ubuntu 22.04 или новее
- Python 3.11+
- Nginx
- Supervisor

### Шаги:

1. **Подключиться к серверу по SSH**
   ```bash
   ssh root@your-server-ip
   ```

2. **Установить зависимости**
   ```bash
   apt update
   apt install python3.11 python3.11-venv nginx supervisor git -y
   ```

3. **Клонировать проект**
   ```bash
   cd /var/www
   git clone <your-repo-url> aksay-grill
   cd aksay-grill
   ```

4. **Создать виртуальное окружение**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Настроить переменные окружения**
   ```bash
   nano .env
   ```
   Добавить:
   ```
   SESSION_SECRET=<случайная строка>
   FLASK_ENV=production
   ```

6. **Настроить Supervisor**
   ```bash
   nano /etc/supervisor/conf.d/aksay-grill.conf
   ```
   Содержимое:
   ```ini
   [program:aksay-grill]
   directory=/var/www/aksay-grill
   command=/var/www/aksay-grill/venv/bin/gunicorn main:app --bind 127.0.0.1:8000 --workers 2
   user=www-data
   autostart=true
   autorestart=true
   stderr_logfile=/var/log/aksay-grill.err.log
   stdout_logfile=/var/log/aksay-grill.out.log
   environment=SESSION_SECRET="<ваш секрет>"
   ```

7. **Настроить Nginx**
   ```bash
   nano /etc/nginx/sites-available/aksay-grill
   ```
   Содержимое:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /assets {
           alias /var/www/aksay-grill/assets;
           expires 30d;
       }
   }
   ```

8. **Активировать конфигурацию**
   ```bash
   ln -s /etc/nginx/sites-available/aksay-grill /etc/nginx/sites-enabled/
   nginx -t
   systemctl restart nginx
   supervisorctl reread
   supervisorctl update
   supervisorctl start aksay-grill
   ```

9. **Установить SSL (Let's Encrypt)**
   ```bash
   apt install certbot python3-certbot-nginx -y
   certbot --nginx -d your-domain.com
   ```

---

## Важные настройки перед деплоем

### 1. Изменить SECRET_KEY в app.py

Сгенерировать случайный ключ:
```python
import secrets
print(secrets.token_hex(32))
```

Установить как переменную окружения `SESSION_SECRET`

### 2. Отключить DEBUG режим

В `main.py` изменить:
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
```

### 3. Настроить базу данных

SQLite подходит для небольшого трафика. Для высокой нагрузки рекомендуется PostgreSQL.

### 4. Настроить email для уведомлений

В админке сайта настроить SMTP для отправки уведомлений о заказах.

---

## Проверка после деплоя

1. ✅ Сайт открывается по URL
2. ✅ Главная страница загружается
3. ✅ Меню отображается
4. ✅ Формы заказа работают
5. ✅ Админка доступна по /admin/login
6. ✅ Email уведомления приходят
7. ✅ Изображения загружаются
8. ✅ SSL сертификат установлен (https://)

---

## Мониторинг

- Логи ошибок: проверять регулярно
- Резервные копии БД: делать ежедневно
- Обновления безопасности: устанавливать своевременно

---

## Поддержка

При возникновении проблем проверить:
1. Логи приложения
2. Логи веб-сервера (Nginx)
3. Статус процесса (supervisor/systemctl)
4. Доступность портов
5. Права доступа к файлам
