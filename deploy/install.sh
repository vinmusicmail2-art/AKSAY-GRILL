#!/bin/bash
# =============================================================================
# Скрипт установки Аксай Гриль на Ubuntu 22.04 VPS
# Запускать от root: bash install.sh
# =============================================================================

set -e

APP_USER="aksaygril"
APP_DIR="/var/www/aksaygril"
LOG_DIR="/var/log/aksaygril"
DOMAIN="aksaygril.ru"

echo "=== [1/8] Обновление системы ==="
apt update && apt upgrade -y

echo "=== [2/8] Установка зависимостей ==="
apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx git curl

echo "=== [3/8] Создание пользователя приложения ==="
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false "$APP_USER"
    echo "Пользователь $APP_USER создан"
fi

echo "=== [4/8] Создание директорий ==="
mkdir -p "$APP_DIR"
mkdir -p "$LOG_DIR"

echo "=== [5/8] Копирование файлов приложения ==="
# Копируем все файлы из текущей директории (кроме .git, __pycache__ и т.д.)
rsync -av --exclude='.git' \
          --exclude='__pycache__' \
          --exclude='*.pyc' \
          --exclude='.env' \
          --exclude='deploy/' \
          --exclude='attached_assets/' \
          --exclude='screen.png' \
          ./ "$APP_DIR/"

echo "=== [6/8] Создание виртуального окружения и установка пакетов ==="
python3.11 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install \
    flask \
    flask-login \
    flask-sqlalchemy \
    flask-wtf \
    gunicorn \
    sqlalchemy \
    werkzeug \
    wtforms \
    bcrypt \
    email-validator \
    Pillow

echo "=== [7/8] Настройка прав доступа ==="
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$LOG_DIR"
chmod 750 "$APP_DIR"
chmod 640 "$APP_DIR/data.db" 2>/dev/null || true

echo "=== [8/8] Настройка nginx ==="
cp deploy/nginx.conf /etc/nginx/sites-available/aksaygril
ln -sf /etc/nginx/sites-available/aksaygril /etc/nginx/sites-enabled/aksaygril
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== Установка systemd сервиса ==="
cp deploy/aksaygril.service /etc/systemd/system/aksaygril.service
systemctl daemon-reload
systemctl enable aksaygril

echo ""
echo "============================================================"
echo " УСТАНОВКА ЗАВЕРШЕНА"
echo "============================================================"
echo ""
echo " СЛЕДУЮЩИЕ ШАГИ:"
echo ""
echo " 1. Отредактируйте /etc/systemd/system/aksaygril.service"
echo "    — заполните SESSION_SECRET, SMTP_* переменные"
echo ""
echo " 2. Запустите сервис:"
echo "    systemctl start aksaygril"
echo "    systemctl status aksaygril"
echo ""
echo " 3. Выпустите SSL-сертификат:"
echo "    certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo " 4. Раскомментируйте HTTPS-блок в /etc/nginx/sites-available/aksaygril"
echo "    и перезагрузите: systemctl reload nginx"
echo ""
echo " 5. Проверьте логи при необходимости:"
echo "    journalctl -u aksaygril -f"
echo "    tail -f $LOG_DIR/error.log"
echo ""
