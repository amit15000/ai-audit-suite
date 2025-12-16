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
        on_chunk: Optional[Callable[[str, str], Any]] = None,
    ) -> AsyncIterator[str]:
        """Get response from specified AI platform with streaming.
        
        Args:
            platform_id: Frontend platform ID (e.g., "openai", "gemini")
            prompt: The prompt to send
            system_prompt: Optional system prompt
            on_chunk: Optional async callback function(chunk, accumulated_text) called for each chunk
            
        Yields:
            Response text chunks as they arrive (word-by-word when possible)
            
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
            # Adapters like OpenAI/Gemini/Groq already stream fine-grained chunks
            # (token-by-token or word-by-word), so we pass them through directly
            async for chunk in adapter.invoke_streaming(invocation):
                accumulated_text += chunk
                # Call on_chunk callback for each chunk (awaits if it's async)
                if on_chunk:
                    import inspect
                    if inspect.iscoroutinefunction(on_chunk):
                        await on_chunk(chunk, accumulated_text)
                    else:
                        on_chunk(chunk, accumulated_text)
                yield chunk
        else:
            # Fallback: get full response and simulate word-by-word streaming
            response: AdapterResponse = await adapter.run_async(invocation)
            
            if response.error:
                raise ValueError(f"Platform '{platform_id}' error: {response.error}")
            
            # Simulate word-by-word streaming for better UX
            import asyncio
            import re
            
            # Split text into words while preserving spaces
            words = re.findall(r'\S+\s*', response.text)
            accumulated_text = ""
            
            # Yield word-by-word with small delay for realistic streaming effect
            for word in words:
                chunk = word
                accumulated_text += chunk
                
                # Call on_chunk callback (awaits if it's async)
                if on_chunk:
                    import inspect
                    if inspect.iscoroutinefunction(on_chunk):
                        await on_chunk(chunk, accumulated_text)
                    else:
                        on_chunk(chunk, accumulated_text)
                
                yield chunk
                
                # Small delay between words to simulate streaming (20ms = smooth but fast)
                await asyncio.sleep(0.02)

