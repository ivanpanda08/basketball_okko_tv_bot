# Okko Basketball Digest Bot

Ежедневный дайджест предстоящих баскетбольных матчей из noauth API Okko в Telegram.
Бот в телеграм доступен по ссылке https://t.me/okko_basketball_bot
Канал с ежедневным дайджестом в 17.00 по МСК - https://t.me/okko_basketball

- Источник матчей: [okko.sport — Баскетбол](https://okko.sport/sport_collection/basketball-broadcasts)
- Источник данных (noauth API): `https://ctx.playfamily.ru/screenapi/v5/noauth/sportcollection/web/1?elementAlias=basketball-broadcasts&elementType=SPORT_COLLECTION&maxResults=50&includeProductsForUpsale=false`

## Требования
- Python 3.11+ (для локального запуска) или Docker/Compose

## Установка
```bash
cd /okko_tv_bot
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Конфигурация
Создай файл `.env` в корне со следующим содержимым:
```bash
# Telegram bot
BOT_TOKEN=xxxxxxxx:yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
CHAT_ID=123456789

# Scheduling / locale
TZ=Europe/Moscow
DIGEST_TIME=17:00

# API source
API_URL=https://ctx.playfamily.ru/screenapi/v5/noauth/sportcollection/web/1
ELEMENT_ALIAS=basketball-broadcasts
ELEMENT_TYPE=SPORT_COLLECTION
MAX_RESULTS=50
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36

```

Примечания:
- `CHAT_ID` может быть ID пользователя или чата/канала (для канала нужен бот как админ).
- `TZ` влияет на определение «сегодня» и формат времени.

## Запуск бота (polling)
Бот отвечает на `/start` и сразу присылает дайджест «на сегодня».
```bash
. .venv/bin/activate
python -m app.poller
```

## Запуск через Docker Compose

```bash
docker compose up -d --build
```

## Как формируется дайджест
- Парсинг `element.collectionItems.items[*].element` из noauth API.
- Фильтр по `gameStatus == NOT_STARTED` и `kickOffDate` в пределах локального дня `TZ`.
- Группировка по лиге: матчи выводятся блоками по названию лиги, внутри блока — отсортированы по времени начала
