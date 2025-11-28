"""Service for getting responses from AI platforms."""
from __future__ import annotations

from app.adapters.base import AdapterRegistry
from app.domain.schemas import AdapterInvocation, AdapterResponse
from app.utils.platform_mapping import get_adapter_name


class AIPlatformService:
    """Service for interacting with various AI platforms."""

    async def get_response(self, platform_id: str, prompt: str, system_prompt: str | None = None) -> str:
        """Get response from specified AI platform.
        
        Args:
            platform_id: Frontend platform ID (e.g., "openai", "gemini")
            prompt: The prompt to send
            system_prompt: Optional system prompt
            
        Returns:
            Response text from the platform
            
        Raises:
            ValueError: If platform is not supported or adapter not found
        """
        adapter_name = get_adapter_name(platform_id)
        adapter = AdapterRegistry.get(adapter_name)
        
        if not adapter:
            raise ValueError(f"Adapter '{adapter_name}' not found for platform '{platform_id}'")
        
        invocation = AdapterInvocation(
            adapter_id=adapter_name,
            instructions=prompt,
            system_prompt=system_prompt,
        )
        
        response: AdapterResponse = await adapter.run_async(invocation)
        
        if response.error:
            raise ValueError(f"Platform '{platform_id}' error: {response.error}")
        
        return response.text

