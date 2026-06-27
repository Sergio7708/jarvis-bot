# 🚀 Deploy Telegram Mini App 3D-магазина

## 📋 Требования
- GitHub аккаунт (бесплатный, для GitHub Pages)
- Домен (опционально, можно без него)
- @BotFather доступ

## 🔧 Шаг 1: Настройка GitHub Pages (бесплатный HTTPS)

1. Создайте репозиторий `3d-shop` на GitHub
2. Загрузите туда папку `webapp/`:
   ```
   git clone https://github.com/ВАШ_ЛОГИН/3d-shop.git
   cd 3d-shop
   cp -r C:\Users\Сергей\Documents\Hermes\projects\jarvis-bot\webapp\ .
   git add .
   git commit -m "3D Print Store Mini App"
   git push
   ```
3. В Settings → Pages → выберите `main` ветку, `/` корень → **Save**
4. Через минуту сайт будет доступен по адресу:
   `https://ВАШ_ЛОГИН.github.io/3d-shop/mini_app.html`

> **⚠️ Важно:** GitHub Pages отдаёт статический HTML. API `/api/products` ДОЛЖЕН
> запускаться отдельно (на вашем сервере) или данные можно вшить прямо в HTML
> (см. демо-данные в `getDemoProducts()`).

## 🔧 Шаг 2: Обновить WEBAPP_URL в боте

Файл: `C:\Users\Сергей\Documents\Hermes\projects\jarvis-bot\handlers\webapp.py`

```python
WEBAPP_URL = "https://ВАШ_ЛОГИН.github.io/3d-shop"
```

## 🔧 Шаг 3: Настройка в @BotFather

1. Откройте @BotFather
2. Отправьте `/mybots` → выберите @Jarvisvetogorbot
3. **Bot Settings** → **Menu Button** → укажите URL:
   `https://ВАШ_ЛОГИН.github.io/3d-shop/mini_app.html`
4. Теперь кнопка "Магазин" будет открывать Mini App прямо из меню бота

## 🔧 Шаг 4: Альтернатива — Cloudflare Tunnel

Если нужен свой сервер с API:

```bash
# Установите cloudflared
winget install cloudflare.cloudflared

# Заトunnель к локальному серверу
cloudflared tunnel --url http://localhost:8765
```

Вы получите HTTPS URL вида `https://random-name.trycloudflare.com`

Обновите `WEBAPP_URL` в `handlers/webapp.py`.

## 🔧 Шаг 5: Перезапустить бота

1. Убейте старый процесс бота (Task Manager)
2. Запустите `start_bot_and_shop.bat`

## 📝 Структура проекта

```
jarvis-bot/
├── main.py                  # Точка входа бота
├── handlers/webapp.py       # Mini App Aiogram роутер
├── serve_webapp.py          # HTTP сервер (для локального теста)
├── start_bot_and_shop.bat   # Быстрый запуск
├── config.py                # Конфигурация с токенами
├── db.py                    # База данных SQLite
├── webapp/
│   └── mini_app.html        # Telegram Mini App (магазин)
└── bot_data.db              # БД с товарами и заказами
```

## ✅ Проверка после деплоя

1. Напишите боту: `/shop`
2. Нажмите "Открыть магазин 3D-печати"
3. Проверьте: категории, поиск, корзина, оформление заказа
4. Заказ должен прийти в Telegram админу
