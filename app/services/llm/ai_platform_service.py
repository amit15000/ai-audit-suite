"""Service for getting responses from AI platforms."""
from __future__ import annotations

from typing import AsyncIterator, Callable, Optional

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
    
    async def get_response_streaming(
        self,
        platform_id: str,
        prompt: str,
        system_prompt: str | None = None,
        on_chunk: Optional[Callable[[str, str], None]] = None,
    ) -> AsyncIterator[str]:
        """Get response from specified AI platform with streaming.
        
        Args:
            platform_id: Frontend platform ID (e.g., "openai", "gemini")
            prompt: The prompt to send
            system_prompt: Optional system prompt
            on_chunk: Optional callback function(chunk, accumulated_text) called for each chunk
            
        Yields:
            Response text chunks as they arrive
            
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
        
        # Check if adapter supports streaming
        if hasattr(adapter, 'invoke_streaming'):
            accumulated_text = ""
            async for chunk in adapter.invoke_streaming(invocation):
                accumulated_text += chunk
                if on_chunk:
                    on_chunk(chunk, accumulated_text)
                yield chunk
        else:
            # Fallback: get full response and simulate chunking
            response: AdapterResponse = await adapter.run_async(invocation)
            
            if response.error:
                raise ValueError(f"Platform '{platform_id}' error: {response.error}")
            
            # Simulate chunking by splitting into words and yielding progressively
            words = response.text.split()
            accumulated_text = ""
            
            # Yield in chunks of ~10 words at a time for better UX
            chunk_size = 10
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk = " ".join(chunk_words) + (" " if i + chunk_size < len(words) else "")
                accumulated_text += chunk
                
                if on_chunk:
                    on_chunk(chunk, accumulated_text)
                yield chunk
                
                # Small delay to simulate streaming
                import asyncio
                await asyncio.sleep(0.05)  # 50ms delay between chunks

