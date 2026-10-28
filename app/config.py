from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36"
API_URL = "https://api.okko.sport/screenapi/v5/noauth/sportcollection/web/1"
ELEMENT_ALIAS = "basketball-broadcasts"
ELEMENT_TYPE = "SPORT_COLLECTION"
MAX_RESULTS = 50
TZ = "Europe/Moscow"
DIGEST_TIME = "17:00"
POLLING_TIMEOUT = 30
BOT_HTTP_TIMEOUT = 75
EUROLEAGUE_ROUND_PREFIX = "euroleague-25-26-regular-season-"
HELP_TEXT = """
<b>Привет! 👋</b>

Здесь можно посмотреть результаты европейского баскетбола, турнирные таблицы и расписание трансляций Okko.

<b>Результаты и таблицы</b>
Нажми «🏀 Евролига» или «🏆 Еврокубок» под полем ввода. Я загружу актуальную таблицу и результаты последних 7 дней, включая сегодня. Результаты и таблица придут отдельными сообщениями.

Также работают команды /euroleague и /eurocup.

<b>Трансляции Okko</b>
/today — матчи на сегодня
/tomorrow — матчи на завтра

<b>В <a href="https://t.me/okko_basketball">канале</a></b>
По понедельникам в 09:00 МСК — результаты прошедшей недели и текущие таблицы, отдельно для Еврокубка и Евролиги.
Каждый день в 17:00 МСК — расписание трансляций Okko.

Если кнопки скрылись, отправь /menu или /start.

Мой код на <a href="https://github.com/ivanpanda08/basketball_okko_tv_bot">GitHub</a>
"""

@dataclass
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()
    chat_id: str = os.getenv("CHAT_ID", "").strip()
    digest_time: str = os.getenv("DIGEST_TIME", DIGEST_TIME)
    timezone: str = os.getenv("TZ", TZ)
    api_url: str = os.getenv("API_URL", API_URL)
    element_alias: str = os.getenv("ELEMENT_ALIAS", ELEMENT_ALIAS)
    element_type: str = os.getenv("ELEMENT_TYPE", ELEMENT_TYPE)
    max_results: int = int(os.getenv("MAX_RESULTS", MAX_RESULTS))
    user_agent: str = os.getenv("USER_AGENT", USER_AGENT)
    euroleague_round_prefix: str = os.getenv("EUROLEAGUE_ROUND_PREFIX", EUROLEAGUE_ROUND_PREFIX)
    polling_timeout: int = int(os.getenv("POLLING_TIMEOUT", POLLING_TIMEOUT))
    bot_http_timeout: int = int(os.getenv("BOT_HTTP_TIMEOUT", BOT_HTTP_TIMEOUT))

def get_settings() -> Settings:
    settings = Settings()
    if not settings.bot_token or not settings.chat_id:
        raise RuntimeError("BOT_TOKEN and CHAT_ID must be set in environment.")
    return settings
