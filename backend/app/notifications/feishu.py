import base64
import hashlib
import hmac
import logging
import re
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class FeishuNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.feishu_webhook_url)

    async def send_markdown(self, content: str) -> None:
        if not self.enabled:
            raise RuntimeError("FEISHU_WEBHOOK_URL is not configured")

        clean_content = self._strip_segment_titles(content)
        chunks = self._split(clean_content, self.settings.feishu_max_message_chars)
        client_kwargs = {"timeout": 30}
        if self.settings.proxy_url:
            client_kwargs["proxy"] = self.settings.proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            for index, chunk in enumerate(chunks, start=1):
                title = "每日破圈赚钱情报" if len(chunks) == 1 else f"每日破圈赚钱情报 ({index}/{len(chunks)})"
                payload = self._payload(title, chunk)
                response = await client.post(self.settings.feishu_webhook_url, json=payload)
                response.raise_for_status()
                data = response.json()
                if data.get("code", 0) != 0:
                    raise RuntimeError(f"Feishu push failed: {data}")
                logger.info("Feishu chunk sent: %s/%s", index, len(chunks))

    def _payload(self, title: str, content: str) -> dict:
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": [{"tag": "markdown", "content": content}],
            },
        }
        if self.settings.feishu_secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._sign(timestamp)
        return payload

    def _sign(self, timestamp: str) -> str:
        string_to_sign = f"{timestamp}\n{self.settings.feishu_secret}".encode("utf-8")
        digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _split(self, content: str, limit: int) -> list[str]:
        content = self._strip_segment_titles(content)
        if len(content) <= limit:
            return [content]
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for block in content.split("\n\n"):
            block_len = len(block) + 2
            if current and current_len + block_len > limit:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            if block_len > limit:
                for i in range(0, len(block), limit):
                    chunks.append(block[i : i + limit])
                continue
            current.append(block)
            current_len += block_len
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    def _strip_segment_titles(self, content: str) -> str:
        return re.sub(r"(?m)^#?\s*每日破圈赚钱情报\s+\(\d+/\d+\)\s*$\n?", "", content)
