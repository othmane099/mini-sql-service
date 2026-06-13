from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import AzureChatOpenAI

from config import settings


def create_llm() -> BaseChatModel:
    return AzureChatOpenAI(
        azure_endpoint=settings.LLM_ENDPOINT,
        api_key=settings.LLM_API_KEY,
        api_version=settings.LLM_API_VERSION,
        azure_deployment=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
    )
