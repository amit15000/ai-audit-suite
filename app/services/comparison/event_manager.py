"""Event manager for streaming comparison events."""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, Optional
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


class ComparisonEventManager:
    """Manages event streaming for comparison processing."""
    
    def __init__(self, comparison_id: str):
        """Initialize event manager for a comparison."""
        self.comparison_id = comparison_id
        self._event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._closed = False
    
    async def emit_event(
        self,
        event_type: str,
        platform_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit an event to the stream."""
        if self._closed:
            return
        
        event = {
            "type": event_type,
            "platform_id": platform_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {},
        }
        
        try:
            await self._event_queue.put(event)
        except Exception as e:
            logger.warning(
                "event_manager.emit_failed",
                comparison_id=self.comparison_id,
                event_type=event_type,
                error=str(e),
            )
    
    async def stream_events(self) -> AsyncIterator[str]:
        """Stream events as SSE format."""
        import json
        
        try:
            while not self._closed:
                try:
                    # Wait for event with timeout to allow checking closed status
                    event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Check if closed while waiting
                    if self._closed:
                        break
                    continue
                except Exception as e:
                    logger.error(
                        "event_manager.stream_error",
                        comparison_id=self.comparison_id,
                        error=str(e),
                    )
                    # Emit error event
                    error_event = {
                        "type": "error",
                        "platform_id": None,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {"error": str(e)},
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            self._closed = True
    
    def close(self) -> None:
        """Close the event stream."""
        self._closed = True
        # Put a sentinel to wake up any waiting readers
        try:
            asyncio.create_task(self._event_queue.put({"type": "closed"}))
        except Exception:
            pass


# Global registry to store event managers by comparison_id
_event_managers: Dict[str, ComparisonEventManager] = {}


def get_event_manager(comparison_id: str) -> ComparisonEventManager:
    """Get or create event manager for a comparison."""
    if comparison_id not in _event_managers:
        _event_managers[comparison_id] = ComparisonEventManager(comparison_id)
    return _event_managers[comparison_id]


def remove_event_manager(comparison_id: str) -> None:
    """Remove event manager for a comparison."""
    if comparison_id in _event_managers:
        manager = _event_managers.pop(comparison_id)
        manager.close()

