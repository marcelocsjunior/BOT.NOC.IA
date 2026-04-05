from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from noc_bot.handlers import callbacks as cb


class _FakeCallbackQuery:
    def __init__(self, data: str, message_text: str = "") -> None:
        self.data = data
        self.message = SimpleNamespace(text=message_text)
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class _FakeUpdate:
    def __init__(self, data: str, message_text: str = "") -> None:
        self.callback_query = _FakeCallbackQuery(data, message_text)
        self.effective_chat = SimpleNamespace(type="private", id=123)


class _FakeContext(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(args=[], bot=SimpleNamespace(send_message=AsyncMock()))


class PanelUnitCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_sup_now_keeps_un2_context(self) -> None:
        update = _FakeUpdate("sup:now", "UN2 — Barreiro\n🌐🔒 VPN — Conectada ✅")
        context = _FakeContext()

        with (
            patch.object(cb, "cmd_dm_unit", new=AsyncMock()) as cmd_dm_unit,
            patch.object(cb, "cmd_supervisor_now", new=AsyncMock()) as cmd_supervisor_now,
        ):
            await cb.on_callback(update, context)

        cmd_dm_unit.assert_awaited_once_with(update, context, "UN2")
        cmd_supervisor_now.assert_not_awaited()

    async def test_sup_now_keeps_un3_context(self) -> None:
        update = _FakeUpdate("sup:now", "UN3 — Alípio de Mello\n🌐🔒 VPN — FORA 🔴")
        context = _FakeContext()

        with (
            patch.object(cb, "cmd_dm_unit", new=AsyncMock()) as cmd_dm_unit,
            patch.object(cb, "cmd_supervisor_now", new=AsyncMock()) as cmd_supervisor_now,
        ):
            await cb.on_callback(update, context)

        cmd_dm_unit.assert_awaited_once_with(update, context, "UN3")
        cmd_supervisor_now.assert_not_awaited()

    async def test_sup_now_defaults_to_un1_panel(self) -> None:
        update = _FakeUpdate("sup:now", "🟢 Torre de Controle — Agora (UN1)")
        context = _FakeContext()

        with (
            patch.object(cb, "cmd_dm_unit", new=AsyncMock()) as cmd_dm_unit,
            patch.object(cb, "cmd_supervisor_now", new=AsyncMock()) as cmd_supervisor_now,
        ):
            await cb.on_callback(update, context)

        cmd_dm_unit.assert_not_awaited()
        cmd_supervisor_now.assert_awaited_once_with(update, context, user_text="(callback)")
