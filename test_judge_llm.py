"""Test script for Judge LLM Evaluation feature."""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import adapters to ensure they're registered
from app.adapters import openai as _openai_adapter  # noqa: F401
from app.adapters import gemini as _gemini_adapter  # noqa: F401
from app.adapters import groq as _groq_adapter  # noqa: F401
from app.adapters import huggingface as _huggingface_adapter  # noqa: F401

from app.services.judgment.judge_llm_service import JudgeLLMService


async def test_judge_evaluation():
    """Test judge LLM evaluation with real responses."""
    print("=" * 80)
    print("Testing Judge LLM Evaluation")
    print("=" * 80)
    
    # Test responses
    test_responses = {
        "good_response": """Artificial Intelligence (AI) is a branch of computer science that aims to create intelligent machines capable of performing tasks that typically require human intelligence. These tasks include learning, reasoning, problem-solving, perception, and language understanding. AI systems can be categorized into narrow AI (designed for specific tasks) and general AI (hypothetical systems with human-like cognitive abilities). Machine learning, a subset of AI, enables systems to learn and improve from experience without being explicitly programmed.""",
        
        "incomplete_response": "AI is computers doing smart things.",
        
        "unsafe_response": "I cannot provide information about creating harmful content or illegal activities.",
        
        "hallucination_response": """Artificial Intelligence was invented in 1956 by John McCarthy at the Dartmouth Conference. The first AI system, called ELIZA, was created in 1965 and could hold conversations with humans. AI has since evolved to include neural networks, which are modeled after the human brain and contain approximately 10 billion neurons. Modern AI systems like GPT-4 can process information at speeds exceeding 1 petabyte per second.""",
    }
    
    # Test with different judge platforms
    judge_platforms = ["openai", "gemini", "groq"]
    
    judge_service = JudgeLLMService()
    
    for response_name, response_text in test_responses.items():
        print(f"\n{'=' * 80}")
        print(f"Testing: {response_name}")
        print(f"{'=' * 80}")
        print(f"Response: {response_text[:100]}...")
        
        for judge_platform in judge_platforms:
            try:
                print(f"\n--- Judge Platform: {judge_platform} ---")
                result = await judge_service.evaluate(
                    response_text=response_text,
                    judge_platform_id=judge_platform,
                    user_query="What is Artificial Intelligence?",
                )
                
                print(f"[OK] Evaluation successful")
                print(f"  Accuracy: {result.scores.accuracy}/10")
                print(f"  Completeness: {result.scores.completeness}/10")
                print(f"  Clarity: {result.scores.clarity}/10")
                print(f"  Reasoning: {result.scores.reasoning}/10")
                print(f"  Safety: {result.scores.safety}/10")
                print(f"  Hallucination Risk: {result.scores.hallucination_risk}/10")
                print(f"  Trust Score: {result.trust_score}/10")
                print(f"  Fallback Applied: {result.fallback_applied}")
                
                if result.fallback_applied:
                    print(f"  [WARNING] Fallback scores used!")
                
            except Exception as e:
                print(f"[ERROR] Error with {judge_platform}: {str(e)}")
                import traceback
                traceback.print_exc()
    
    # Test batch evaluation
    print(f"\n{'=' * 80}")
    print("Testing Batch Evaluation")
    print(f"{'=' * 80}")
    
    try:
        batch_results = await judge_service.evaluate_batch(
            responses=test_responses,
            judge_platform_id="openai",
            user_query="What is Artificial Intelligence?",
        )
        
        print(f"[OK] Batch evaluation successful ({len(batch_results)} responses)")
        for response_id, result in batch_results.items():
            print(f"  {response_id}: Trust Score = {result.trust_score}/10")
            
    except Exception as e:
        print(f"[ERROR] Batch evaluation error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_comparison_integration():
    """Test judge evaluation in comparison context."""
    print(f"\n{'=' * 80}")
    print("Testing Comparison Integration")
    print(f"{'=' * 80}")
    
    from app.services.comparison.comparison_service import process_comparison
    from app.core.database import get_session_factory
    from app.domain.models import Comparison, ComparisonStatus
    from datetime import datetime
    
    # Create a test comparison
    session_factory = get_session_factory()
    db = session_factory()
    
    try:
        import uuid
        # Create test comparison with unique IDs
        test_id = f"test_judge_{uuid.uuid4().hex[:8]}"
        test_msg_id = f"msg_test_{uuid.uuid4().hex[:8]}"
        
        test_comparison = Comparison(
            id=test_id,
            message_id=test_msg_id,
            user_id="test_user",
            prompt="What is machine learning?",
            judge_platform="openai",
            selected_platforms=["openai", "gemini"],
            status=ComparisonStatus.QUEUED.value,
            progress=0,
        )
        db.add(test_comparison)
        db.commit()
        
        print("[OK] Test comparison created")
        
        # Process comparison
        await process_comparison(db, test_comparison)
        
        db.refresh(test_comparison)
        
        if test_comparison.status == ComparisonStatus.COMPLETED.value:
            print("[OK] Comparison completed successfully")
            
            # Check results
            results = test_comparison.results
            if results and isinstance(results, dict):
                platforms = results.get("platforms", [])
                print(f"  Processed {len(platforms)} platforms")
                
                for platform in platforms:
                    platform_id = platform.get("id")
                    judge_eval = platform.get("judgeEvaluation")
                    
                    if judge_eval:
                        print(f"\n  Platform: {platform_id}")
                        print(f"    Trust Score: {judge_eval.get('trustScore')}/10")
                        print(f"    Accuracy: {judge_eval['scores'].get('accuracy')}/10")
                        print(f"    Fallback: {judge_eval.get('fallbackApplied')}")
                    else:
                        print(f"  Platform: {platform_id} - No judge evaluation")
            else:
                print("  [WARNING] No results found")
        else:
            print(f"[ERROR] Comparison failed: {test_comparison.status}")
            if test_comparison.error_message:
                print(f"  Error: {test_comparison.error_message}")
        
        # Cleanup
        db.delete(test_comparison)
        db.commit()
        
    except Exception as e:
        print(f"[ERROR] Integration test error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("\nStarting Judge LLM Evaluation Tests...\n")
    
    # Check API keys
    has_openai = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ADAPTER_OPENAI_API_KEY"))
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("ADAPTER_GEMINI_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY") or os.getenv("ADAPTER_GROQ_API_KEY"))
    
    print("API Keys Status:")
    print(f"  OpenAI: {'OK' if has_openai else 'MISSING'}")
    print(f"  Gemini: {'OK' if has_gemini else 'MISSING'}")
    print(f"  Groq: {'OK' if has_groq else 'MISSING'}")
    print()
    
    # Run tests
    asyncio.run(test_judge_evaluation())
    asyncio.run(test_comparison_integration())
    
    print(f"\n{'=' * 80}")
    print("Tests completed!")
    print(f"{'=' * 80}\n")

