import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import ConnectionTimeoutError
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetMe

from app.telegram_session import TelegramSession


def network_error(cause):
    try:
        raise cause
    except Exception:
        try:
            raise TelegramNetworkError(method=GetMe(), message="Request timeout error")
        except TelegramNetworkError as error:
            return error


class TelegramSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_connection_failure_and_preserves_polling_timeout(self):
        request = AsyncMock(side_effect=[network_error(ConnectionTimeoutError()), "ok"])
        with patch.object(AiohttpSession, "make_request", request), patch(
            "app.telegram_session.asyncio.sleep", new_callable=AsyncMock
        ):
            result = await TelegramSession(timeout=75).make_request(object(), GetMe(), timeout=105)
        self.assertEqual(result, "ok")
        self.assertEqual(request.await_count, 2)
        timeout = request.call_args.kwargs["timeout"]
        self.assertEqual(timeout.total, 105)
        self.assertEqual(timeout.sock_connect, 5)

    async def test_does_not_retry_ambiguous_read_timeout(self):
        error = network_error(asyncio.TimeoutError())
        request = AsyncMock(side_effect=error)
        with patch.object(AiohttpSession, "make_request", request):
            with self.assertRaises(TelegramNetworkError):
                await TelegramSession(timeout=75).make_request(object(), GetMe())
        self.assertEqual(request.await_count, 1)

    async def test_stops_after_three_connection_failures(self):
        request = AsyncMock(side_effect=network_error(ConnectionTimeoutError()))
        with patch.object(AiohttpSession, "make_request", request), patch(
            "app.telegram_session.asyncio.sleep", new_callable=AsyncMock
        ):
            with self.assertRaises(TelegramNetworkError):
                await TelegramSession(timeout=75).make_request(object(), GetMe())
        self.assertEqual(request.await_count, 3)


if __name__ == "__main__":
    unittest.main()
