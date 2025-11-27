"""Platform ID mapping between frontend and backend adapters."""
from __future__ import annotations

# Map frontend platform IDs to adapter names
PLATFORM_TO_ADAPTER: dict[str, str] = {
    "chatgpt": "openai",
    "openai": "openai",
    "gemini": "gemini",
    "grok": "groq",  # Note: Grok (X/Twitter) not implemented - uses Groq adapter as proxy
    "claude": "openai",  # Will need anthropic adapter
    "perplexity": "openai",  # Will need perplexity adapter
    "deepseek": "openai",  # Will need deepseek adapter
    "mistral": "openai",  # Will need mistral adapter
    "copilot": "openai",  # Will need copilot adapter
    "cohere": "openai",  # Will need cohere adapter
    "youchat": "openai",  # Will need youchat adapter
    "groq": "groq",
    "huggingface": "huggingface",
}

# Map platform IDs to display names
PLATFORM_NAMES: dict[str, str] = {
    "chatgpt": "ChatGPT",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "grok": "Grok",
    "claude": "Claude",
    "perplexity": "Perplexity",
    "deepseek": "DeepSeek",
    "mistral": "Mistral AI",
    "copilot": "Microsoft Copilot",
    "cohere": "Cohere",
    "youchat": "YouChat",
    "groq": "Groq",
    "huggingface": "Hugging Face",
}


def get_adapter_name(platform_id: str) -> str:
    """Get adapter name from platform ID."""
    return PLATFORM_TO_ADAPTER.get(platform_id.lower(), platform_id.lower())


def get_platform_name(platform_id: str) -> str:
    """Get display name for platform ID."""
    return PLATFORM_NAMES.get(platform_id.lower(), platform_id.title())


def is_valid_platform(platform_id: str) -> bool:
    """Check if platform ID is valid."""
    return platform_id.lower() in PLATFORM_TO_ADAPTER

