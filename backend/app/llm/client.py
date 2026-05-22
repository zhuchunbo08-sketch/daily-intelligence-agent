import json
import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.ai_api_key)

    async def analyze_json(self, system_prompt: str, user_prompt: str) -> dict:
        content = await self.chat_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
        )
        return self._loads_json(content)

    async def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict | None = None,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("AI API key is not configured")

        url = f"{self.settings.ai_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if response_format:
            payload["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        client_kwargs = {"timeout": self.settings.ai_timeout_seconds}
        if self.settings.proxy_url:
            client_kwargs["proxy"] = self.settings.proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code in {400, 422} and response_format:
                logger.warning(
                    "AI provider rejected response_format; retrying without it: %s",
                    response.text[:500],
                )
                payload.pop("response_format", None)
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    def _loads_json(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.S)
            if not match:
                raise
            return json.loads(match.group(0))
