<!-- Badges -->
<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://www.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white"></a>
  <a href="https://t.me/okko_basketball_bot"><img alt="Telegram Bot" src="https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white"></a>
  <a href="https://t.me/okko_basketball"><img alt="Telegram Channel" src="https://img.shields.io/badge/Telegram-Channel-26A5E4?logo=telegram&logoColor=white"></a>
  <img alt="Timezone" src="https://img.shields.io/badge/TZ-Europe%2FMoscow-000000?logo=clockify&logoColor=white">
</p>

<h2 align="center">🏀 Баскетбол на Okko — Telegram Bot</h2>

Telegram-бот с расписанием трансляций Okko, результатами матчей и таблицами Евролиги и Еврокубка.

Быстрые ссылки:
- [🤖 Бот](https://t.me/okko_basketball_bot)
- [📢 Канал](https://t.me/okko_basketball)

---

- Источник матчей: [okko.sport — Баскетбол](https://okko.sport/sport_collection/basketball-broadcasts)
- Источник данных (noauth API): `https://api.okko.sport/screenapi/v5/noauth/sportcollection/web/1?elementAlias=basketball-broadcasts&elementType=SPORT_COLLECTION&maxResults=50&includeProductsForUpsale=false`

---

## 🗒️ Команды бота

- `/today` — присылает дайджест матчей на сегодня
- `/tomorrow` — присылает дайджест матчей на завтра
- `/euroleague` — актуальная таблица Евролиги и результаты последних 7 календарных дней, включая сегодня
- `/eurocup` — актуальные таблицы Еврокубка по группам и результаты последних 7 календарных дней
- `/menu` или `/start` — показывает отдельные кнопки «🏀 Евролига» и «🏆 Еврокубок»

## 🏀 Результаты и таблицы

Источник — `https://api-live.euroleague.net`: матчи из API v2, таблицы из API v3.
Ключ API не нужен. Сезон выбирается автоматически по списку сезонов источника.
Каждое нажатие кнопки загружает свежие данные. Результаты и таблица приходят
отдельными сообщениями; длинные сводки разделяются в пределах лимита Telegram.
В сообщениях используются русские названия клубов, жирным выделяются счёт
и победитель. Даты матчей и группы отмечены эмодзи. Внизу каждого сообщения
есть ссылка на официальный сайт турнира и время обновления по Москве.
Для новых клубов без перевода сохраняется название источника.

По понедельникам в **09:00 по Москве** в `CHAT_ID` отправляются сначала
Еврокубок, затем Евролига: результаты предыдущей календарной недели
(понедельник–воскресенье по Москве) и текущие таблицы. Расписание этой сводки
фиксировано по Москве и не зависит от `DIGEST_TIME` и `TZ`.
Существующий ежедневный дайджест трансляций Okko в 17:00 сохраняется.

Места команд берутся из таблицы источника для последнего сыгранного тура
регулярного сезона. Если таблица ещё не учитывает все завершённые матчи,
бот сообщает, что она обновляется, вместо показа устаревших мест.
В плей-офф остаётся итоговая таблица регулярного сезона, а результаты включают
матчи всех стадий.

Бот должен работать в момент рассылки: после перезапуска планируется следующий
понедельник, пропущенная рассылка автоматически не воспроизводится.
При сбое рассылки предусмотрены три попытки для каждого турнира с интервалом
в минуту; окончательная ошибка записывается в журнал.
Если Telegram не подтвердил отправку после ожидания ответа, повтор этой
отправки пропускается, чтобы не опубликовать сообщение дважды.

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

Команда `/start` показывает инструкцию и кнопки выбора Евролиги и Еврокубка.
Расписание трансляций запрашивается командами `/today` и `/tomorrow`.

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
  euroleague.py    # результаты и таблицы EuroLeague Basketball
  league_jobs.py   # сводка по понедельникам в 09:00 МСК
  telegram_session.py # соединение с Telegram и повторы при сбое подключения
```

## Проверка

```bash
python -m unittest discover -s tests -v
```
