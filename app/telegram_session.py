from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiohttp import ClientConnectorError, ClientTimeout, ConnectionTimeoutError
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods.base import TelegramMethod, TelegramType


logger = logging.getLogger(__name__)


class TelegramSession(AiohttpSession):
    """Retry failed connections before Telegram receives a request."""

    async def make_request(
        self, bot: Bot, method: TelegramMethod[TelegramType], timeout: Optional[int] = None
    ) -> TelegramType:
        request_timeout = ClientTimeout(
            total=self.timeout if timeout is None else timeout,
            sock_connect=5,
        )
        for attempt in range(3):
            try:
                # aiogram forwards this value directly to aiohttp's request timeout.
                return await super().make_request(
                    bot, method, timeout=request_timeout  # type: ignore[arg-type]
                )
            except TelegramNetworkError as exc:
                # A read timeout may follow a successful send; retrying it can
                # duplicate messages. Only retry connection establishment failures.
                if attempt == 2 or not isinstance(
                    exc.__context__, (ConnectionTimeoutError, ClientConnectorError)
                ):
                    raise
                logger.warning(
                    "Connection failed for %s; retry %s/2",
                    method.__api_method__, attempt + 1,
                )
                await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError("Unreachable request state")
