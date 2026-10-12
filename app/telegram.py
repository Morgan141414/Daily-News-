import logging
from pathlib import Path
log = logging.getLogger(__name__)

class TelegramDelivery:
    def __init__(self, settings): self.settings = settings; self.client = None
    @property
    def auth_configured(self): return bool(self.settings.telegram_api_id and self.settings.telegram_api_hash)
    @property
    def configured(self): return self.auth_configured and bool(self.settings.telegram_target)
    async def connect(self, interactive=False):
        if not self.auth_configured: return False
        from telethon import TelegramClient
        self.client = TelegramClient(str(self.settings.telegram_session), self.settings.telegram_api_id, self.settings.telegram_api_hash)
        if interactive:
            await self.client.start()
            return True
        if not Path(str(self.settings.telegram_session) + ".session").exists() and not Path(self.settings.telegram_session).exists():
            return False
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.disconnect()
            return False
        return True
    async def authorize(self):
        if not self.auth_configured: raise RuntimeError("Заполните Telegram API параметры в .env")
        await self.connect(interactive=True); await self.client.disconnect(); print("Telegram-сессия авторизована.")
    async def list_dialogs(self):
        if not await self.connect(): raise RuntimeError("Telegram-сессия не авторизована; сначала выполните python -m app --authorize")
        dialogs = []
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            if getattr(entity, "megagroup", False) or getattr(entity, "broadcast", False) or getattr(entity, "title", None):
                dialogs.append((dialog.id, dialog.name, getattr(entity, "username", None)))
        await self.client.disconnect()
        return dialogs

    async def resolve_target(self):
        """Resolve a channel by username or numeric ID without assuming group semantics."""
        target = str(self.settings.telegram_target).strip()
        candidates = [target]
        if target.lstrip("-").isdigit():
            number = int(target)
            candidates.insert(0, number)
            if number > 0 and target.startswith("100"):
                candidates.append(-number)
            elif number > 0:
                candidates.append(-100 * number)
        for candidate in candidates:
            try:
                return await self.client.get_entity(candidate)
            except Exception:
                continue
        raise RuntimeError("TELEGRAM_TARGET не найден среди доступных каналов/чатов")
    async def schedule(self, body, when):
        if not self.settings.telegram_target:
            log.warning("TELEGRAM_TARGET не настроен; выпуск сохранён локально")
            return []
        if not await self.connect():
            log.warning("Telegram-сессия не авторизована; выпуск сохранён локально")
            return []
        entity = await self.resolve_target()
        ids = []
        for part in [body[i:i+3900] for i in range(0, len(body), 3900)]:
            message = await self.client.send_message(entity, part, schedule=when)
            ids.append(message.id)
        await self.client.disconnect(); return ids

    async def send_now(self, body):
        """Send an explicitly requested test release immediately."""
        if not self.settings.telegram_target:
            raise RuntimeError("TELEGRAM_TARGET не настроен")
        if not await self.connect():
            raise RuntimeError("Telegram-сессия не авторизована")
        try:
            entity = await self.resolve_target()
            ids = []
            for part in [body[i:i+3900] for i in range(0, len(body), 3900)]:
                message = await self.client.send_message(entity, part)
                ids.append(message.id)
            return ids
        finally:
            await self.client.disconnect()
