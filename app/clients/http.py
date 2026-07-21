import aiohttp


class HttpClient:
    """Общий HTTP-клиент для всех бирж."""

    def __init__(self):
        self.session = None

    async def connect(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def get_json(self, url, params=None):
        async with self.session.get(url, params=params, timeout=20) as response:
            response.raise_for_status()
            return await response.json()
