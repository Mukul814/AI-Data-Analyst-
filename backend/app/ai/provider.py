import json
import re
from typing import Protocol


class AIProvider(Protocol):
    async def explain(self, question: str, computed_answer: str, result: dict) -> str: ...


class MockProvider:
    async def explain(self, question: str, computed_answer: str, result: dict) -> str:
        return computed_answer


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def explain(self, question: str, computed_answer: str, result: dict) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=(
                "Explain only the verified result. Do not invent numbers. "
                f"Question: {question}\nVerified answer: {computed_answer}\nResult: {result}"
            ),
        )
        text = response.text or computed_answer
        verified = computed_answer + " " + json.dumps(result, default=str)
        numbers = set(re.findall(r"\d+(?:\.\d+)?%?", verified.replace(",", "")))
        generated = set(re.findall(r"\d+(?:\.\d+)?%?", text.replace(",", "")))
        return text if generated.issubset(numbers) else computed_answer


def create_provider():
    from app.core.config import get_settings

    settings = get_settings()
    if settings.ai_provider.lower() == "mock":
        return MockProvider()
    if settings.ai_provider.lower() == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Gemini is enabled but GEMINI_API_KEY is not configured.")
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    raise RuntimeError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
