<!-- Badges -->
<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://www.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white"></a>
  <a href="https://t.me/okko_basketball_bot"><img alt="Telegram Bot" src="https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white"></a>
  <a href="https://t.me/okko_basketball"><img alt="Telegram Channel" src="https://img.shields.io/badge/Telegram-Channel-26A5E4?logo=telegram&logoColor=white"></a>
  <img alt="Timezone" src="https://img.shields.io/badge/TZ-Europe%2FMoscow-000000?logo=clockify&logoColor=white">
</p>

<h2 align="center">🏀 Баскетбол на Okko — Telegram Bot</h2>

Ежедневный дайджест предстоящих баскетбольных матчей из noauth API Okko в Telegram.

Быстрые ссылки:
- [🤖 Бот](https://t.me/okko_basketball_bot)
- [📢 Канал](https://t.me/okko_basketball)

---

- Источник матчей: [okko.sport — Баскетбол](https://okko.sport/sport_collection/basketball-broadcasts)
- Источник данных (noauth API): `https://ctx.playfamily.ru/screenapi/v5/noauth/sportcollection/web/1?elementAlias=basketball-broadcasts&elementType=SPORT_COLLECTION&maxResults=50&includeProductsForUpsale=false`

---

## 🗒️ Команды бота

- `/today` — присылает дайджест матчей на сегодня
- `/tomorrow` — присылает дайджест матчей на завтра

## ✨ Что делает бот

- Парсит `element.collectionItems.items[*].element` из noauth API
- Фильтрует по `gameStatus == NOT_STARTED` и дате старта в пределах локального дня `TZ`
- Группирует по лиге и сортирует встречи по времени начала
- В 17:00 по `GMT+3` публикует дайджест в канал

## 🧰 Требования

- Python 3.11+ (локально) или Docker/Compose

## 🚀 Установка (локально)

```bash
# 1) Клонирование репозитория
git clone https://github.com/ivanpanda08/basketball_okko_tv_bot
cd okko_tv_bot

# 2) Виртуальное окружение и зависимости
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Конфигурация

Используй шаблон окружения и при необходимости поменяй значения:
```bash
cp .env.template .env
```

Примечания:

- Обязательно указать - `BOT_TOKEN`
- `CHAT_ID` может быть ID пользователя или чата/канала (для канала нужен бот как админ)
- `TZ` влияет на определение «сегодня» и формат времени

## ▶️ Запуск бота (polling)

Бот отвечает на `/start` и сразу присылает дайджест «на сегодня».

```bash
. .venv/bin/activate
python -m app.poller
```

## 🐳 Запуск через Docker Compose

```bash
docker compose up -d --build
```

---

## 🧭 Навигация по проекту

```
app/
  config.py        # конфигурация/переменные окружения
  formatting.py    # форматирование сообщений
  http.py          # HTTP-клиент
  models.py        # доменные модели
  parser.py        # парсинг ответа Okko
  poller.py        # telegram polling
```
