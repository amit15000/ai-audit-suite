"""LLM-based prompt parser for extracting instructions, requirements, and constraints."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.utils import (
    JUDGE_SYSTEM_PROMPT,
    extract_json_float,
    extract_json_string,
)


@dataclass
class ParsedPrompt:
    """Structured representation of parsed prompt requirements."""
    
    instructions: list[str]  # List of actionable instructions
    tone_requirement: Optional[str]  # Required tone (e.g., "Professional", "Casual")
    length_constraint: Optional[dict]  # {"min_words": int, "max_words": int, "category": str}
    format_requirements: list[str]  # Format rules (e.g., "bullet_points", "markdown", "json")
    brand_voice_guidelines: Optional[str]  # Brand voice description
    explicit_requirements: list[str]  # Other explicit requirements found
    
    def __init__(
        self,
        instructions: Optional[list[str]] = None,
        tone_requirement: Optional[str] = None,
        length_constraint: Optional[dict] = None,
        format_requirements: Optional[list[str]] = None,
        brand_voice_guidelines: Optional[str] = None,
        explicit_requirements: Optional[list[str]] = None,
    ):
        """Initialize ParsedPrompt with default values."""
        self.instructions = instructions or []
        self.tone_requirement = tone_requirement
        self.length_constraint = length_constraint
        self.format_requirements = format_requirements or []
        self.brand_voice_guidelines = brand_voice_guidelines
        self.explicit_requirements = explicit_requirements or []


PROMPT_PARSING_SYSTEM_PROMPT = """You are an expert prompt analyzer specializing in extracting structured requirements from natural language prompts.

Your task is to analyze prompts and extract:
1. All actionable instructions
2. Tone of voice requirements
3. Length constraints (word count, character count, or category)
4. Format specifications (markdown, JSON, bullet points, etc.)
5. Brand voice guidelines
6. Any other explicit requirements

CRITICAL: You MUST return ONLY valid JSON. No other text before or after the JSON.

Return this exact JSON structure:
{
    "instructions": ["instruction1", "instruction2", ...],
    "tone_requirement": "Professional|Casual|Formal|Friendly|Polite|Neutral|Not specified",
    "length_constraint": {
        "min_words": <number or null>,
        "max_words": <number or null>,
        "min_chars": <number or null>,
        "max_chars": <number or null>,
        "category": "Short|Medium|Long|Very Long|Not specified",
        "explicit_requirement": "<exact text from prompt about length>"
    },
    "format_requirements": ["format1", "format2", ...],
    "brand_voice_guidelines": "<description or null>",
    "explicit_requirements": ["requirement1", "requirement2", ...]
}

INSTRUCTIONS EXTRACTION:
- Extract ALL actionable instructions (verbs, requirements, must-do items)
- Examples: "use bullet points", "include examples", "cite sources", "be concise"
- Include both explicit and implicit instructions
- Each instruction should be a clear, actionable item

TONE REQUIREMENT:
- Detect if prompt specifies tone: "professional", "casual", "formal", "friendly", "polite", etc.
- Return "Not specified" if no tone requirement found
- Look for phrases like "write in a [tone] tone", "be [tone]", "use [tone] language"

LENGTH CONSTRAINT:
- Extract explicit word/character counts: "200 words", "under 500 characters", "100-300 words"
- Extract length categories: "brief", "short", "concise", "detailed", "comprehensive", "long"
- Map categories: brief/short/concise = Short, medium = Medium, detailed/comprehensive/long = Long
- Return null for unspecified values

FORMAT REQUIREMENTS:
- Extract format specifications: "markdown", "JSON", "HTML", "bullet points", "numbered list", "table", "code block"
- Look for phrases like "format as", "use", "in [format]", "as [format]"
- Include structural requirements: "with headings", "include sections", "use paragraphs"

BRAND VOICE GUIDELINES:
- Extract any brand voice descriptions or personality traits mentioned
- Look for phrases about brand personality, style, or voice
- Return null if not specified

EXPLICIT REQUIREMENTS:
- Capture any other specific requirements not covered above
- Examples: "include call-to-action", "mention product features", "avoid technical jargon"
"""


class PromptParser:
    """LLM-based prompt parser for extracting structured requirements."""
    
    def __init__(self, ai_service: AIPlatformService):
        """Initialize prompt parser.
        
        Args:
            ai_service: Service for LLM interactions
        """
        self.ai_service = ai_service
    
    async def parse_prompt(
        self,
        prompt: str,
        judge_platform_id: str = "openai",
        use_llm: bool = True,
    ) -> ParsedPrompt:
        """Parse prompt to extract structured requirements.
        
        Args:
            prompt: The original prompt/instructions to parse
            judge_platform_id: Platform ID for LLM judge
            use_llm: Whether to use LLM for parsing (default: True)
            
        Returns:
            ParsedPrompt with extracted requirements
        """
        if not prompt or not prompt.strip():
            return ParsedPrompt()
        
        if not use_llm:
            # Fallback to basic rule-based parsing
            return self._parse_basic(prompt)
        
        try:
            # Use LLM to parse prompt
            user_prompt = f"""Analyze this prompt and extract all requirements:

PROMPT TO ANALYZE:
{prompt[:3000]}

Extract:
1. All actionable instructions
2. Tone of voice requirement (if specified)
3. Length constraints (word count, character count, or category)
4. Format specifications (markdown, JSON, bullet points, etc.)
5. Brand voice guidelines (if mentioned)
6. Any other explicit requirements

Return ONLY valid JSON with the exact structure specified in the system prompt."""
            
            llm_response = await self.ai_service.get_response(
                judge_platform_id,
                user_prompt,
                system_prompt=PROMPT_PARSING_SYSTEM_PROMPT,
            )
            
            return self._parse_llm_response(llm_response, prompt)
        except Exception as e:
            # Fallback to basic parsing on error
            return self._parse_basic(prompt)
    
    def _parse_llm_response(self, llm_response: str, original_prompt: str) -> ParsedPrompt:
        """Parse LLM JSON response into ParsedPrompt.
        
        Args:
            llm_response: LLM response text
            original_prompt: Original prompt for fallback
            
        Returns:
            ParsedPrompt object
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                # Try parsing entire response
                data = json.loads(llm_response.strip())
            
            # Extract instructions
            instructions = data.get("instructions", [])
            if isinstance(instructions, str):
                instructions = [instructions] if instructions else []
            
            # Extract tone requirement
            tone_requirement = data.get("tone_requirement", "Not specified")
            if tone_requirement == "Not specified":
                tone_requirement = None
            
            # Extract length constraint
            length_data = data.get("length_constraint", {})
            length_constraint = None
            if length_data and isinstance(length_data, dict):
                length_constraint = {
                    "min_words": length_data.get("min_words"),
                    "max_words": length_data.get("max_words"),
                    "min_chars": length_data.get("min_chars"),
                    "max_chars": length_data.get("max_chars"),
                    "category": length_data.get("category", "Not specified"),
                    "explicit_requirement": length_data.get("explicit_requirement", ""),
                }
            
            # Extract format requirements
            format_reqs = data.get("format_requirements", [])
            if isinstance(format_reqs, str):
                format_reqs = [format_reqs] if format_reqs else []
            
            # Extract brand voice guidelines
            brand_voice = data.get("brand_voice_guidelines")
            if brand_voice and brand_voice.lower() in ["null", "none", "not specified", ""]:
                brand_voice = None
            
            # Extract explicit requirements
            explicit_reqs = data.get("explicit_requirements", [])
            if isinstance(explicit_reqs, str):
                explicit_reqs = [explicit_reqs] if explicit_reqs else []
            
            return ParsedPrompt(
                instructions=instructions,
                tone_requirement=tone_requirement,
                length_constraint=length_constraint,
                format_requirements=format_reqs,
                brand_voice_guidelines=brand_voice,
                explicit_requirements=explicit_reqs,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback to basic parsing
            return self._parse_basic(original_prompt)
    
    def _parse_basic(self, prompt: str) -> ParsedPrompt:
        """Basic rule-based parsing as fallback.
        
        Args:
            prompt: Prompt to parse
            
        Returns:
            ParsedPrompt with basic extraction
        """
        prompt_lower = prompt.lower()
        instructions = []
        tone_requirement = None
        length_constraint = None
        format_requirements = []
        
        # Extract tone
        tone_keywords = {
            "professional": ["professional", "business", "corporate"],
            "casual": ["casual", "informal", "relaxed"],
            "formal": ["formal", "formal tone", "formally"],
            "friendly": ["friendly", "warm", "welcoming"],
            "polite": ["polite", "courteous", "respectful"],
        }
        for tone, keywords in tone_keywords.items():
            if any(keyword in prompt_lower for keyword in keywords):
                tone_requirement = tone.capitalize()
                break
        
        # Extract length constraints
        word_count_match = re.search(r'(\d+)\s*(?:to|-)?\s*(\d+)?\s*words?', prompt_lower)
        if word_count_match:
            min_words = int(word_count_match.group(1))
            max_words = int(word_count_match.group(2)) if word_count_match.group(2) else None
            length_constraint = {
                "min_words": min_words,
                "max_words": max_words,
                "category": "Not specified",
                "explicit_requirement": word_count_match.group(0),
            }
        else:
            # Check for length categories
            if any(word in prompt_lower for word in ["brief", "short", "concise"]):
                length_constraint = {"category": "Short", "explicit_requirement": "brief/short/concise"}
            elif any(word in prompt_lower for word in ["detailed", "comprehensive", "long", "extensive"]):
                length_constraint = {"category": "Long", "explicit_requirement": "detailed/comprehensive/long"}
        
        # Extract format requirements
        if "bullet" in prompt_lower or "bullet points" in prompt_lower:
            format_requirements.append("bullet_points")
        if "numbered" in prompt_lower or "numbered list" in prompt_lower:
            format_requirements.append("numbered_list")
        if "markdown" in prompt_lower:
            format_requirements.append("markdown")
        if "json" in prompt_lower:
            format_requirements.append("json")
        if "table" in prompt_lower:
            format_requirements.append("table")
        
        # Extract basic instructions
        instruction_verbs = ["use", "include", "mention", "avoid", "write", "format", "create"]
        sentences = re.split(r'[.!?]+', prompt)
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            if any(verb in sentence_lower for verb in instruction_verbs):
                if len(sentence.strip()) > 5:  # Filter out very short fragments
                    instructions.append(sentence.strip())
        
        return ParsedPrompt(
            instructions=instructions[:10],  # Limit to 10 instructions
            tone_requirement=tone_requirement,
            length_constraint=length_constraint,
            format_requirements=format_requirements,
            brand_voice_guidelines=None,
            explicit_requirements=[],
        )

