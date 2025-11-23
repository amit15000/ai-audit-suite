from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models import AdapterInvocation, AdapterResponse


class AdapterError(Exception):
    """Raised when adapter execution fails."""


@dataclass
class AdapterContext:
    invocation: AdapterInvocation
    metadata: Dict[str, Any]


class BaseAdapter(ABC):
    name: str

    def __init__(self) -> None:
        settings = get_settings()
        self._max_retries = settings.adapter.max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    def run(self, invocation: AdapterInvocation) -> AdapterResponse:
        try:
            return self.invoke(invocation)
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(str(exc)) from exc

    @abstractmethod
    def invoke(self, invocation: AdapterInvocation) -> AdapterResponse:
        ...


class AdapterRegistry:
    _registry: Dict[str, BaseAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter: BaseAdapter) -> None:
        cls._registry[name] = adapter

    @classmethod
    def get(cls, name: str) -> Optional[BaseAdapter]:
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> Dict[str, BaseAdapter]:
        return cls._registry

