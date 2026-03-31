"""Quick test script for Context-Adherence Score - single test case."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import adapters to register them
from app.adapters import openai as _openai_adapter  # noqa: F401
from app.adapters import gemini as _gemini_adapter  # noqa: F401
from app.adapters import groq as _groq_adapter  # noqa: F401
from app.adapters import huggingface as _huggingface_adapter  # noqa: F401

from app.services.comparison.context_adherence_scorer import ContextAdherenceScorer
from app.services.comparison.context_adherence.prompt_parser import PromptParser
from app.services.llm.ai_platform_service import AIPlatformService


async def main():
    """Run a quick test of context adherence scoring."""
    print("="*80)
    print("CONTEXT-ADHERENCE SCORE - QUICK TEST")
    print("="*80)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  ERROR: OPENAI_API_KEY not set in environment variables")
        print("   Please set your OpenAI API key to run this test.")
        return
    
    scorer = ContextAdherenceScorer()
    parser = PromptParser(scorer.ai_service)
    
    # Test prompt and response
    prompt = """Write a professional marketing email for our new product launch. 
    Requirements:
    - Use a friendly and professional tone
    - Keep it under 200 words
    - Use bullet points to highlight key features
    - Include a call-to-action
    - Maintain our brand voice: innovative, customer-focused, and trustworthy"""
    
    response = """Subject: Introducing Our Revolutionary New Product!

Dear Valued Customers,

We're thrilled to announce the launch of our latest innovation! Our new product is designed with you in mind, combining cutting-edge technology with user-friendly design.

Key Features:
• Advanced AI-powered functionality
• Seamless integration with existing systems
• 24/7 customer support
• Industry-leading security

We've built this product based on your feedback, ensuring it meets your needs while maintaining the highest standards of quality and reliability.

Ready to experience the future? Click here to learn more and get started today!

Best regards,
The Team"""
    
    print("\n📋 PROMPT:")
    print("-" * 80)
    print(prompt)
    print("-" * 80)
    
    print("\n📝 RESPONSE:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    
    # Parse prompt
    print("\n🔍 Parsing prompt requirements...")
    try:
        parsed_prompt = await parser.parse_prompt(
            prompt=prompt,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n✅ Prompt parsed successfully!")
        print(f"   Instructions found: {len(parsed_prompt.instructions)}")
        print(f"   Tone requirement: {parsed_prompt.tone_requirement or 'Not specified'}")
        print(f"   Format requirements: {len(parsed_prompt.format_requirements)}")
    except Exception as e:
        print(f"\n❌ Error parsing prompt: {str(e)}")
        return
    
    # Calculate scores
    print("\n🔄 Analyzing response adherence...")
    print("   (This may take 15-30 seconds)")
    
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response,
            prompt=prompt,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "="*80)
        print("RESULTS:")
        print("="*80)
        
        print(f"\n  ✅ All Instructions Adherence: {sub_scores.allInstructions:.2f}%")
        print(f"  🎭 Tone of Voice: {sub_scores.toneOfVoice}")
        print(f"  📏 Length Constraints: {sub_scores.lengthConstraints}")
        print(f"  📄 Format Rules Adherence: {sub_scores.formatRules:.2f}%")
        print(f"  🎨 Brand Voice Adherence: {sub_scores.brandVoice:.2f}%")
        
        # Calculate overall
        numeric_scores = [
            sub_scores.allInstructions,
            sub_scores.formatRules,
            sub_scores.brandVoice,
        ]
        overall = sum(numeric_scores) / len(numeric_scores)
        
        print("\n" + "-"*80)
        print(f"OVERALL ADHERENCE: {overall:.2f}%")
        print("-"*80)
        
        if overall >= 90:
            print("  ✅ EXCELLENT - Response perfectly adheres to requirements")
        elif overall >= 70:
            print("  🟢 GOOD - Response mostly adheres to requirements")
        elif overall >= 50:
            print("  🟡 MODERATE - Response partially adheres to requirements")
        else:
            print("  🔴 POOR - Response does not adhere well to requirements")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

