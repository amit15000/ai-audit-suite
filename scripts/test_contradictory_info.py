"""Test script for contradictory information detection."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.comparison.hallucination.contradictory_info import ContradictoryInfoScorer


async def test_contradictory_info_detection():
    """Test contradictory information detection with various scenarios."""
    
    # Initialize scorer
    scorer = ContradictoryInfoScorer()
    
    # Judge platform ID (not used, kept for compatibility)
    judge_platform_id = "openai"
    
    print("=" * 80)
    print("TESTING CONTRADICTORY INFORMATION DETECTION")
    print("=" * 80)
    print(f"Judge Platform: {judge_platform_id}")
    print(f"LLM Required: Yes")
    print()
    
    # Test 1: Clear direct contradiction
    print("TEST 1: Direct Contradiction")
    print("-" * 80)
    response1 = """
    The company reported record profits this quarter. The financial results show 
    that revenue increased by 25% compared to last year. However, the company also 
    reported that it made no profit this quarter and actually lost money. The CEO 
    stated that the company is doing very well financially.
    """
    print("Response:")
    print(response1.strip())
    print()
    
    try:
        detailed1 = await scorer.get_detailed_contradictions(response1, judge_platform_id, use_llm=True)
        score1 = detailed1["score"]
        print(f"Score: {score1}/10")
        print(f"Contradictions Found: {detailed1['contradictions_found']}")
        print()
        
        if detailed1["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed1["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed1.get("explanation"):
            print(f"\nOverall Explanation: {detailed1['explanation']}")
        
        print(f"\nExpected: Low score (2-4) due to clear contradiction")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 2: Factual contradiction (same subject, different values)
    print("TEST 2: Factual Contradiction (Same Subject, Different Values)")
    print("-" * 80)
    response2 = """
    New York City is the most populous city in the United States. According to 
    the latest census data, the city has a population of approximately 8.8 million 
    residents. However, recent studies indicate that New York City actually has 
    a population of 12 million people. The city spans 302.6 square miles across 
    five boroughs.
    """
    print("Response:")
    print(response2.strip())
    print()
    
    try:
        detailed2 = await scorer.get_detailed_contradictions(response2, judge_platform_id, use_llm=True)
        score2 = detailed2["score"]
        print(f"Score: {score2}/10")
        print(f"Contradictions Found: {detailed2['contradictions_found']}")
        print()
        
        if detailed2["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed2["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed2.get("explanation"):
            print(f"\nOverall Explanation: {detailed2['explanation']}")
        
        print(f"\nExpected: Low score (3-5) due to population contradiction")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 3: Temporal contradiction
    print("TEST 3: Temporal Contradiction")
    print("-" * 80)
    response3 = """
    The Industrial Revolution began in 1760 and marked a significant shift in 
    manufacturing processes. This period of rapid industrialization started in 
    England and spread throughout Europe. However, historical records show that 
    the Industrial Revolution actually began in 1800, not 1760. The revolution 
    transformed society and the economy.
    """
    print("Response:")
    print(response3.strip())
    print()
    
    try:
        detailed3 = await scorer.get_detailed_contradictions(response3, judge_platform_id, use_llm=True)
        score3 = detailed3["score"]
        print(f"Score: {score3}/10")
        print(f"Contradictions Found: {detailed3['contradictions_found']}")
        print()
        
        if detailed3["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed3["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed3.get("explanation"):
            print(f"\nOverall Explanation: {detailed3['explanation']}")
        
        print(f"\nExpected: Low score (3-5) due to temporal contradiction")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 4: Logical contradiction
    print("TEST 4: Logical Contradiction")
    print("-" * 80)
    response4 = """
    If it rains, then the ground will be wet. When precipitation occurs, the 
    soil becomes moist. However, if it rains, the ground will remain dry. The 
    weather patterns determine the condition of the terrain.
    """
    print("Response:")
    print(response4.strip())
    print()
    
    try:
        detailed4 = await scorer.get_detailed_contradictions(response4, judge_platform_id, use_llm=True)
        score4 = detailed4["score"]
        print(f"Score: {score4}/10")
        print(f"Contradictions Found: {detailed4['contradictions_found']}")
        print()
        
        if detailed4["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed4["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed4.get("explanation"):
            print(f"\nOverall Explanation: {detailed4['explanation']}")
        
        print(f"\nExpected: Low score (2-4) due to logical contradiction")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 5: Causal contradiction
    print("TEST 5: Causal Contradiction")
    print("-" * 80)
    response5 = """
    Regular exercise causes weight loss by increasing metabolism and burning 
    calories. Physical activity is essential for maintaining a healthy body weight. 
    However, regular exercise actually prevents weight loss and leads to weight 
    gain. The relationship between exercise and weight is complex.
    """
    print("Response:")
    print(response5.strip())
    print()
    
    try:
        detailed5 = await scorer.get_detailed_contradictions(response5, judge_platform_id, use_llm=True)
        score5 = detailed5["score"]
        print(f"Score: {score5}/10")
        print(f"Contradictions Found: {detailed5['contradictions_found']}")
        print()
        
        if detailed5["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed5["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed5.get("explanation"):
            print(f"\nOverall Explanation: {detailed5['explanation']}")
        
        print(f"\nExpected: Low score (2-4) due to causal contradiction")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 6: No contradiction (should score high)
    print("TEST 6: No Contradiction (Consistent Information)")
    print("-" * 80)
    response6 = """
    Machine learning is a subset of artificial intelligence that enables systems 
    to learn from data. Deep learning, which uses neural networks with multiple 
    layers, is a type of machine learning. These technologies have revolutionized 
    many industries including healthcare, finance, and transportation. The field 
    continues to evolve rapidly with new breakthroughs and applications.
    """
    print("Response:")
    print(response6.strip())
    print()
    
    try:
        detailed6 = await scorer.get_detailed_contradictions(response6, judge_platform_id, use_llm=True)
        score6 = detailed6["score"]
        print(f"Score: {score6}/10")
        print(f"Contradictions Found: {detailed6['contradictions_found']}")
        print()
        
        if detailed6["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed6["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed6.get("explanation"):
            print(f"\nOverall Explanation: {detailed6['explanation']}")
        
        print(f"\nExpected: High score (8-10) - no contradictions")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 7: Semantic equivalence (should NOT be flagged as contradiction)
    print("TEST 7: Semantic Equivalence (Different Words, Same Meaning)")
    print("-" * 80)
    response7 = """
    The city has a population of 8 million people. The urban area is home to 
    8 million residents. The metropolitan region contains 8 million inhabitants. 
    These numbers reflect the latest census data.
    """
    print("Response:")
    print(response7.strip())
    print()
    
    try:
        detailed7 = await scorer.get_detailed_contradictions(response7, judge_platform_id, use_llm=True)
        score7 = detailed7["score"]
        print(f"Score: {score7}/10")
        print(f"Contradictions Found: {detailed7['contradictions_found']}")
        print()
        
        if detailed7["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed7["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed7.get("explanation"):
            print(f"\nOverall Explanation: {detailed7['explanation']}")
        
        print(f"\nExpected: High score (9-10) - same meaning, different words")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 8: Multiple contradictions
    print("TEST 8: Multiple Contradictions")
    print("-" * 80)
    response8 = """
    The company was founded in 1990 and has been operating for over 30 years. 
    However, the company was actually established in 2000, making it 24 years old. 
    The company has 500 employees working across multiple departments. Recent reports 
    indicate the company has 200 employees. The company is profitable and making 
    good financial progress. However, the company is losing money and facing 
    financial difficulties.
    """
    print("Response:")
    print(response8.strip())
    print()
    
    try:
        detailed8 = await scorer.get_detailed_contradictions(response8, judge_platform_id, use_llm=True)
        score8 = detailed8["score"]
        print(f"Score: {score8}/10")
        print(f"Contradictions Found: {detailed8['contradictions_found']}")
        print()
        
        if detailed8["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed8["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed8.get("explanation"):
            print(f"\nOverall Explanation: {detailed8['explanation']}")
        
        print(f"\nExpected: Very low score (0-3) - multiple contradictions")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 9: Different contexts (should NOT be contradiction)
    print("TEST 9: Different Contexts (Not Contradictory)")
    print("-" * 80)
    response9 = """
    The temperature in New York is high during summer, often reaching 90 degrees 
    Fahrenheit. During winter, the temperature in New York is low, frequently 
    dropping below freezing. The city experiences significant seasonal variation 
    in weather patterns.
    """
    print("Response:")
    print(response9.strip())
    print()
    
    try:
        detailed9 = await scorer.get_detailed_contradictions(response9, judge_platform_id, use_llm=True)
        score9 = detailed9["score"]
        print(f"Score: {score9}/10")
        print(f"Contradictions Found: {detailed9['contradictions_found']}")
        print()
        
        if detailed9["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed9["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed9.get("explanation"):
            print(f"\nOverall Explanation: {detailed9['explanation']}")
        
        print(f"\nExpected: High score (9-10) - different contexts, not contradictory")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 10: Complex semantic contradiction
    print("TEST 10: Complex Semantic Contradiction")
    print("-" * 80)
    response10 = """
    Artificial intelligence systems are becoming increasingly capable and can 
    perform complex tasks that were previously thought to require human intelligence. 
    These systems demonstrate remarkable abilities in pattern recognition, natural 
    language processing, and decision-making. However, AI systems lack the ability 
    to perform complex tasks and cannot match human intelligence in any meaningful 
    way. Current AI technology is fundamentally limited and cannot demonstrate 
    true understanding or reasoning capabilities.
    """
    print("Response:")
    print(response10.strip())
    print()
    
    try:
        detailed10 = await scorer.get_detailed_contradictions(response10, judge_platform_id, use_llm=True)
        score10 = detailed10["score"]
        print(f"Score: {score10}/10")
        print(f"Contradictions Found: {detailed10['contradictions_found']}")
        print()
        
        if detailed10["contradiction_pairs"]:
            print("Contradiction Statements:")
            for idx, pair in enumerate(detailed10["contradiction_pairs"], 1):
                print(f"\n  Contradiction {idx}:")
                print(f"    Statement 1: {pair.get('statement_1', 'N/A')}")
                print(f"    Statement 2: {pair.get('statement_2', 'N/A')}")
                print(f"    Type: {pair.get('type', 'N/A')}")
                print(f"    Severity: {pair.get('severity', 'N/A')}")
                print(f"    Explanation: {pair.get('semantic_reasoning', 'N/A')}")
        else:
            print("No contradictions detected.")
        
        if detailed10.get("explanation"):
            print(f"\nOverall Explanation: {detailed10['explanation']}")
        
        print(f"\nExpected: Low score (2-4) - semantic contradiction about AI capabilities")
        print()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("All tests completed. Review scores above to verify contradiction detection.")
    print()
    print("Expected behavior:")
    print("- Tests 1-5, 8, 10: Should have LOW scores (0-5) due to contradictions")
    print("- Tests 6, 7, 9: Should have HIGH scores (8-10) - no contradictions")
    print()


async def test_error_handling():
    """Test error handling when LLM is not enabled."""
    print("=" * 80)
    print("TESTING ERROR HANDLING")
    print("=" * 80)
    
    scorer = ContradictoryInfoScorer()
    judge_platform_id = os.getenv("JUDGE_PLATFORM_ID", "openai")
    
    response = "This is a test response with some content."
    
    print("Test: use_llm=False (should raise ValueError)")
    print("-" * 80)
    try:
        score = await scorer.calculate_score(response, judge_platform_id, use_llm=False)
        print(f"ERROR: Should have raised ValueError, but got score: {score}")
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"ERROR: Raised unexpected exception: {e}")
    
    print()


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CONTRADICTORY INFORMATION DETECTION TEST SUITE")
    print("=" * 80)
    print()
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("JUDGE_PLATFORM_ID"):
        print("[WARNING] OPENAI_API_KEY or JUDGE_PLATFORM_ID not set!")
        print("   This test requires LLM access. Set one of these in your .env file.")
        print()
    
    # Run main tests
    try:
        await test_contradictory_info_detection()
    except Exception as e:
        print(f"\n[ERROR] Main test suite failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test error handling
    try:
        await test_error_handling()
    except Exception as e:
        print(f"\n[ERROR] Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)
    print()


if __name__ == "__main__":
    asyncio.run(main())
