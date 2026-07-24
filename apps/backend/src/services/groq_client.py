from typing import Protocol, cast

from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam

from src.config import settings

# NOTE: unverified against a live Groq account — see embedding_service.py's note
# on credential provenance.


class ChatCompleter(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, str]],
        response_format_json: bool,
    ) -> str: ...


class GroqChatCompleter:
    def __init__(self) -> None:
        self._client = AsyncGroq(
            api_key=settings.GROQ_API_KEY, timeout=settings.GROQ_TIMEOUT_SECONDS
        )

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, str]],
        response_format_json: bool,
    ) -> str:
        chat_messages = cast(
            list[ChatCompletionMessageParam],
            [{"role": "system", "content": system_prompt}, *messages],
        )
        response = await self._client.chat.completions.create(
            model=model,
            messages=chat_messages,
            response_format={"type": "json_object"} if response_format_json else None,
        )
        return response.choices[0].message.content or ""
