"""Simple test script for External Fact Check feature."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.services.comparison.hallucination.external_fact_check import (
    ClaimExtractor,
    ExternalFactCheckScorer,
)


async def test_claim_extraction():
    """Test claim extraction (both LLM and rule-based)."""
    print("=" * 60)
    print("TEST 1: Claim Extraction")
    print("=" * 60)
    
    settings = get_settings().external_fact_check
    
    # Test with LLM (default)
    print("\n1. Testing LLM-based extraction (default):")
    extractor_llm = ClaimExtractor(use_llm=True)
    
    response = """
    New York City has a population of 8.5 million people according to the 2020 census.
    The city covers an area of 468 square miles.
    According to recent research, 50% of residents prefer public transportation.
    In 1624, the city was founded by Dutch settlers.
    """
    
    try:
        claims = await extractor_llm.extract_claims(response, max_claims=10)
        print(f"   [OK] Extracted {len(claims)} claims using LLM")
        for i, claim in enumerate(claims[:3], 1):
            print(f"   {i}. {claim.claim[:70]}...")
    except Exception as e:
        print(f"   [ERROR] LLM extraction failed: {e}")
        print("   → Falling back to rule-based...")
    
    # Test with rule-based fallback
    print("\n2. Testing rule-based extraction (fallback):")
    extractor_rule = ClaimExtractor(use_llm=False)
    claims = await extractor_rule.extract_claims(response, max_claims=10)
    print(f"   [OK] Extracted {len(claims)} claims using rule-based method")
    for i, claim in enumerate(claims[:3], 1):
        print(f"   {i}. {claim.claim[:70]}...")


async def test_full_scoring():
    """Test full external fact check scoring."""
    print("\n" + "=" * 60)
    print("TEST 2: Full External Fact Check Scoring (LLM + Web Search)")
    print("=" * 60)
    
    settings = get_settings().external_fact_check
    
    if not settings.enabled:
        print("\n⚠ External Fact Check is disabled in config.")
        print("   Set EXTERNAL_FACT_CHECK_ENABLED=true in .env")
        return
    
    # Check for OpenAI API key
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[WARNING] OPENAI_API_KEY is not set in environment variables!")
        print("   This is required for LLM-based fact checking.")
        print("   Set OPENAI_API_KEY in your .env file or environment.")
        return
    
    print("\n[OK] Using LLM-based fact checking with OpenAI")
    print("   Watch the logs below for detailed claim extraction, evidence retrieval, and verification...\n")
    
    scorer = ExternalFactCheckScorer()
    
    # Single test response with multiple claims
    test_response = """
    New York City has a population of 8.5 million people according to the 2020 census.
    The city covers an area of 468 square miles.
    New York City was founded in 1624 by Dutch settlers.
    The Statue of Liberty was dedicated in 1886.
    According to a 2023 study, 75% of New Yorkers prefer public transportation.
    """
    
    print(f"\nTesting Response:")
    print(f"   {test_response[:100]}...")
    
    try:
        result = await scorer.calculate_sub_score(test_response)
        
        print(f"\n{'='*60}")
        print(f"   RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"   • Score: {result.score}/100")
        print(f"   • Coverage: {result.coverage:.1%}")
        print(f"   • Claims Verified: {len(result.claims)}")
        print(f"   • Total Sources Used: {len(result.sources_used)}")
        
        if result.claims:
            print(f"\n{'='*60}")
            print(f"   CLAIMS LIST ({len(result.claims)}):")
            print(f"{'='*60}")
            
            for i, claim in enumerate(result.claims, 1):
                print(f"\n   {i}. {claim.claim}")
                
                # Verification result
                is_true = claim.verdict == "SUPPORTED"
                status_icon = "[TRUE]" if is_true else "[FALSE]"
                status_text = "TRUE" if is_true else "FALSE"
                print(f"      {status_icon} Result: {status_text}")
                
                # Sources (domains from OpenAI)
                if claim.top_evidence:
                    print(f"      Sources ({len(claim.top_evidence)}):")
                    for j, evidence in enumerate(claim.top_evidence, 1):
                        print(f"         • {evidence.domain}")
                else:
                    print(f"      Sources: None provided")
                
                # Explanation (from evidence snippet which contains explanation)
                if claim.top_evidence and claim.top_evidence[0].snippet:
                    explanation = claim.top_evidence[0].snippet
                    if len(explanation) > 150:
                        explanation = explanation[:150] + "..."
                    print(f"      Explanation: {explanation}")
        
        if result.notes:
            print(f"\n   Notes: {', '.join(result.notes)}")
            
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


async def test_configuration():
    """Test configuration settings."""
    print("\n" + "=" * 60)
    print("TEST 3: Configuration Check")
    print("=" * 60)
    
    settings = get_settings().external_fact_check
    
    import os
    
    print(f"\nConfiguration:")
    print(f"  • Enabled: {settings.enabled}")
    print(f"  • OpenAI API Key: {'[SET]' if os.getenv('OPENAI_API_KEY') else '[NOT SET - REQUIRED]'}")
    print(f"  • Use LLM for extraction: {settings.claim_extraction_use_llm}")
    print(f"  • Max Claims: {settings.max_claims_per_response}")
    print(f"  • Verification Timeout: {settings.verification_timeout}s")
    
    if not settings.enabled:
        print("\n[WARNING] External Fact Check is disabled!")
    print(f"  • Search Provider: {settings.search_provider}")
    print(f"  • Top K Results: {settings.top_k_results}")
    print(f"  • Search Timeout: {settings.search_timeout}s")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("EXTERNAL FACT CHECK TEST SUITE")
    print("=" * 60)
    
    # Check configuration first
    await test_configuration()
    
    # Test claim extraction
    try:
        await test_claim_extraction()
    except Exception as e:
        print(f"\n[ERROR] Claim extraction test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test full scoring (may take longer due to API calls)
    print("\n" + "=" * 60)
    print("Running full scoring test (this may take 30-60 seconds)...")
    print("=" * 60)
    
    try:
        await test_full_scoring()
    except Exception as e:
        print(f"\n[ERROR] Full scoring test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print("\nFor more detailed testing, see:")
    print("  • Unit tests: pytest tests/test_external_fact_check.py -v")
    print("  • Documentation: docs/EXTERNAL_FACT_CHECK_TESTING.md")


if __name__ == "__main__":
    asyncio.run(main())
